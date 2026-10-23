# Threat model: libssz

## What this project does and where untrusted input enters

libssz is a `no_std + alloc` Rust implementation of Ethereum Simple Serialize (SSZ), including bounded types, progressive types, derive macros, and hash-tree-root calculation. Consensus clients and zkVM guest programs use it for data whose encoding and root must agree exactly across implementations.

The library does not open sockets itself. Its callers supply bytes received from P2P gossip, request/response sync, Beacon APIs, checkpoint sync, files, or other untrusted sources. Treat every call that decodes such bytes as a security boundary. Values influenced by an attacker also reach encoding and hash-tree-root code.

Important input classes include:

- Truncated or trailing bytes, invalid fixed and variable lengths, out-of-order or overflowing offsets, and inconsistent fixed/variable container layouts.
- Lists, vectors, bitlists, bitvectors, progressive lists/bitlists, and containers whose declared or decoded length exceeds a type bound.
- Invalid union selectors, incompatible or nested unions, inactive progressive-container fields, malformed bitlist termination, and non-canonical padding.
- Deep nesting and inputs that request disproportionate allocation, hashing, recursion, or CPU before a bound is checked.

Security goals are canonical acceptance and rejection, exact re-encoding and hash-tree roots, enforcement of SSZ type bounds, deterministic behavior across targets, and graceful handling of malformed bytes without panics or excessive resource use.

## Components that matter most

- `crates/ssz`: primitive and container encoding/decoding, offset handling, union behavior, and decode errors. Look for acceptance of non-canonical data, rejection of valid data, integer overflow, out-of-bounds access, and unchecked allocation.
- `crates/ssz-types`: `SszVector`, `SszList`, bit collections, progressive collections, construction APIs, and length/bound invariants. A bound bypass can turn a small network message into excessive work or violate downstream consensus assumptions.
- `crates/ssz-merkle`: chunking, padding, merkleization, progressive merkleization, and hash-tree roots. Differential roots are consensus-critical even when decoding itself succeeds.
- `crates/ssz-derive`: generated encode/decode/hash implementations for containers, unions, transparent types, and progressive containers. Check generated bounds, field order, active-field handling, and parity with hand-written implementations.
- `spec-tests` and `fuzz`: useful oracles and reproducer infrastructure, not production attack surface themselves.

The library's safe public APIs must preserve their invariants. Issues that require a caller to use `unsafe` or deliberately violate a documented unsafe contract are lower priority. A dependency flaw is relevant only with a demonstrated path through libssz; name the crate where the patch belongs.

## Severity guidance

Assess impact in a consuming consensus client, but state the required call path rather than assuming every application exposes every type. A correctness difference without a security consequence is not automatically a vulnerability.

- **Critical:** memory corruption or remote code execution; or a demonstrated decoding/hash-root divergence that enables invalid consensus state, finalized theft, or an equivalently severe downstream failure.
- **High:** acceptance of invalid SSZ or rejection of valid SSZ with a credible consensus-split path; hash-tree-root divergence for attacker-influenced values; a type-bound bypass; or a remotely reachable panic, stack overflow, abort, or small-input/unbounded-resource attack that terminates or stalls a client.
- **Medium:** bounded denial of service, panics that a caller demonstrably contains, correctness defects requiring unusual non-default types or configurations, and resource amplification with limited practical impact. Escalate when a common consensus container or many clients are affected.
- **Low:** defense-in-depth gaps without a demonstrated attack, caller misuse outside the safe API contract, and non-security documentation or performance issues.

For resource-exhaustion reports, measure encoded input size against allocation, CPU, recursion depth, and wall time. A type with a large legitimate protocol bound is not automatically a vulnerability; show why the implementation's cost is avoidable, exceeds its own bound, or violates a caller-visible limit.

## How to exercise it offline

The checkout is `/src`. Root and fuzz dependencies, both `no_std` target toolchains, nightly Rust, cargo-fuzz, all test binaries, and all 19 fuzz targets are prebuilt. `CARGO_NET_OFFLINE=true` is set. The root workspace does not commit a `Cargo.lock`; dependency resolution and fetching have already occurred during the image build.

Run the standard suites directly with Cargo:

```sh
cargo test --workspace --exclude spec-tests
cargo test --workspace --exclude spec-tests --no-default-features --features alloc
cargo test -p spec-tests
```

The official consensus vectors are already extracted under `target/spec-tests/v1.7.0-alpha.13`; `cargo test -p spec-tests` does not need to download them. They cover valid and invalid generic SSZ plus mainnet and minimal consensus containers across the supported forks.

Verify embedded/no-std targets with:

```sh
cargo check -p libssz -p libssz-types -p libssz-merkle \
  --target thumbv7m-none-eabi --no-default-features --features alloc
cargo check -p libssz -p libssz-types -p libssz-merkle \
  --target riscv64imac-unknown-none-elf --no-default-features --features alloc
```

List and run fuzzers from the `fuzz` directory:

```sh
cd fuzz
cargo +nightly fuzz list
cargo +nightly fuzz run decode_arbitrary -- -max_total_time=60
cargo +nightly fuzz run offset_adversarial -- -max_total_time=60
cargo +nightly fuzz run diff_hash_tree_root -- -max_total_time=60
```

`make fuzz-quick` runs every target for 10 seconds. The differential targets compare against Lighthouse's `ethereum_ssz`/`tree_hash` and `ssz_rs`; use those comparisons to distinguish a libssz defect from a test-oracle error. Any crash artifacts should be minimized and included in the report.

## Reporting and exclusions

Provide the affected revision, crate and type, exact input bytes or generator, expected versus actual result, and a minimal deterministic reproducer. For canonicality or root bugs, cite the SSZ rule and include the expected encoding/root or a reference implementation comparison. For panics and resource bugs, include the complete backtrace or measured cost. Propose a minimal patch and regression test where practical, and group reports with the same root cause.

Do not report ordinary performance differences, documented `unsafe` caller obligations, or a dependency problem with no reachable libssz path. Do not publish unpatched vulnerability details or open a public issue.

Report findings privately to `security@lambdaclass.com` and follow `.github/SECURITY.md`.
