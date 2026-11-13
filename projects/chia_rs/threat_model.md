# chia_rs threat model

chia_rs is the Rust half of Chia consensus. chia-blockchain (the Python node) calls it through the `chia_rs` Python
extension (`wheel/`) to validate spend bundles and blocks, run block generators, parse and price CLVM conditions,
(de)serialize the streamable wire types, and verify BLS signatures. The CLVM interpreter itself is the `clvmr` crate
(clvm_rs), enrolled separately.

## What we protect

1. Consensus: the same block or spend bundle gets the same result (accept/reject, conditions, cost, error code) on
   every platform, every time, and the same as the Python node's own checks where both exist. A divergence is a chain
   split.
2. Cost accounting: the cost charged for a spend or block generator matches the real CPU and memory it needs, so
   `MAX_BLOCK_COST_CLVM` bounds validation time.
3. Availability: untrusted input cannot make validation panic, abort, hang or allocate without bound.
4. Signatures: aggregate BLS verification accepts exactly the signatures it should, including the infinity-point and
   duplicate-message edge cases handled by past soft forks.

## Untrusted input

Everything that arrives from a peer and reaches these crates is untrusted:

- spend bundles and block generators (`crates/chia-consensus/src/spendbundle_validation.rs`,
  `run_block_generator.rs`, `conditions.rs`, `get_puzzle_and_solution.rs`);
- streamable-encoded messages and blocks (`crates/chia-protocol`, `crates/chia-traits`, `chia_streamable_macro`);
- BLS public keys and signatures (`crates/chia-bls`);
- CLVM puzzles and solutions, including back-referenced (compressed) serialization.

Trusted: the consensus constants and flags the caller passes, the local filesystem, and the caller of the Rust API.
A panic only reachable by passing invalid arguments that chia-blockchain never passes is a bug, not a vulnerability.

## Components that matter most / least

- Most: `chia-consensus` (conditions, cost, flags and fork-height gating in `flags.rs`, fast-forward and dedup
  logic, mempool-mode vs consensus-mode differences), `chia-protocol` / `chia-traits` (parsing), `chia-bls`,
  `clvm-utils` (tree hashing, currying), and the Python bindings in `wheel/` (type conversion at the boundary).
- Lower: `chia-datalayer` (off by default in the node), `chia-client`, `chia-ssl`, `chia-tools`, `wasm/`.
- Out of scope: `ff-tests/`, `generator-tests/`, `test-bundles/` (test data), benchmarks, the npm packaging.

## What counts as a vulnerability

- Mempool mode is deliberately stricter than consensus mode. A spend accepted in mempool mode but rejected in
  consensus mode is a finding; the reverse is expected.
- Behaviour that a soft or hard fork changed is only a finding for the heights where the current flags apply.
- Cost mispricing: compare real time against a cost-proportional baseline (for example plain SHA-256 at the same
  cost) and give the wall-clock time for a generator at the maximum block cost.
- A panic, `unwrap`, integer overflow (in release builds) or unbounded allocation reachable from untrusted input.
- Resource use proportional to input size within the protocol's size and cost limits is expected.

## Severity

- Critical: a consensus divergence (between platforms, between runs, or between chia_rs and the Python node) that
  splits the chain; accepting an invalid signature or an invalid spend; a panic any block or relayed transaction can
  trigger on every node.
- High: a crash or long stall of a single node from one peer, in the default configuration; a large cost
  mispricing that makes a maximum-cost block take far longer than intended.
- Medium: smaller cost mispricings, bounded resource exhaustion, issues in non-default crates.
- Low: everything else with a security angle.

Every report needs a file and line, the path from untrusted input to the defect, and a reproducer that runs in this
image; for consensus divergences, both outputs.

## How to exercise it

- `cargo test --workspace --all-features` runs offline. Fuzz targets are under `crates/*/fuzz/fuzz_targets/`; run
  them with `cargo +nightly-2026-01-12 fuzz run <target>` from the crate directory.
- The `chia_rs` Python extension, built from this checkout, is installed in `/opt/venv`; `pytest tests/` runs the
  Python tests against it.
