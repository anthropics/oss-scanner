# clvm_rs threat model

clvm_rs (crate `clvmr`) is the CLVM interpreter Chia consensus runs every puzzle, solution and block generator on.
chia_rs links it for block and mempool validation, so every Chia full node runs attacker-supplied CLVM through this
code. The puzzle author is untrusted: any program and any argument, up to the cost limit, must be safe to run.

## What we protect

1. Determinism: a program gives the same result (value or error, and the same cost) on every platform, CPU
   architecture, build profile and feature set. The fast paths (for example native-integer arithmetic) must agree with
   the generic bignum paths that `--features no-fastpath` forces; a difference is a consensus split.
2. Cost model: the cost charged (`src/cost.rs`, the operator costs in `src/more_ops.rs`, `src/core_ops.rs`,
   `src/bls_ops.rs`, `src/secp_ops.rs`, `src/keccak256_ops.rs`, `src/sha_tree_op.rs`) tracks the real CPU and memory
   an operator uses, so the block cost limit (11,000,000,000) bounds validation time and memory.
3. Resource limits: the allocator's atom, pair and heap limits and the stack depth limit (`src/allocator.rs`,
   `src/run_program.rs`) hold for every program, including through `softfork` guards and back-referenced input.
4. Serialization: deserializers (`src/serde/`, `src/serde_2026/`) reject or canonically parse every byte string, and
   tree hashing and serialized-length computations agree with what was parsed.

## Untrusted input

Programs and their arguments, in any serialization (plain, with back-references, and the 2026 format), and the
operator arguments they produce at run time. Trusted: the flags and the cost limit the caller passes.

## Components that matter most / least

- Most: `run_program.rs`, `chia_dialect.rs` (operator table, flags, mempool-mode restrictions), the operator
  implementations and their costs, `allocator.rs`, `number.rs`, `serde/` and `serde_2026/`, `treehash.rs`.
- Lower: `runtime_dialect.rs`, `test_ops.rs`, `tools/` (benchmarking and test generators), the Python bindings in
  `wheel/` where only test code uses them.
- Out of scope: `benches/`, `benchmark/`, `op-tests/` (test vectors).

## What counts as a vulnerability

- Cost mispricing: an operator or operator pattern whose real time or memory per unit of cost is far above the
  cost-proportional baseline (plain `sha256` at the same cost). Give the wall-clock time and peak memory for a program
  at the full block cost. Operators that grow intermediate values inside one call (multi-argument arithmetic, concat)
  are known places to look.
- Any result or cost difference between platforms, profiles or feature sets (`no-fastpath`, `pre-eval`, `counters`,
  `openssl`) for the same program and flags.
- A panic, abort, overflow, or memory growth past the allocator limits from any program within the cost limit.
- A `softfork` guard whose body's charged cost differs from its declared cost without failing, or an unknown
  extension that executes code.
- Mempool mode is deliberately stricter than consensus mode; a program accepted in mempool mode but rejected in
  consensus mode is a finding, the reverse is expected.

## Severity

- Critical: a consensus divergence between platforms or builds; a panic reachable from a relayed transaction or block
  on every node; a cost mispricing large enough that a maximum-cost block takes minutes or exhausts memory.
- High: a cost mispricing that makes a maximum-cost block take several seconds or more on ordinary hardware, or that
  exceeds the allocator limits; a deserializer accepting non-canonical input that other implementations reject.
- Medium: smaller mispricings, resource issues needing unusual flags.
- Low: everything else with a security angle.

Every report needs the program (hex), the flags, the result and cost, and timing or memory measurements marked as
measured or extrapolated.

## How to exercise it

- `cargo test` (and `--release`, and `--features <variant>`) runs offline.
- `cargo run --release -p clvm-rs-test-tools --bin run-clvm` runs a program; `benchmark-clvm-cost` measures per-operator time
  against cost. Check `tools/src/bin/` for the exact binary names and flags.
- Fuzz targets are in `fuzz/fuzz_targets/`: `cargo +nightly-2026-01-12 fuzz run <target>` from `/src`.
- The `clvm_rs` Python extension, built from this checkout, is installed in `/opt/venv`.
