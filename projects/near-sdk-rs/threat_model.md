# NEAR Rust SDK

This repository provides Rust libraries and macros for NEAR smart contracts,
including near-sdk, near-sdk-macros, near-contract-standards, host interfaces,
and shared SDK value types. The execution model and standards are documented at
https://docs.near.org and https://nomicon.io.

## Trust boundaries and priorities

- Contract arguments, cross-contract messages and callback results may be
  adversarial. A receiver contract may behave maliciously or fail.
- Distinguish the predecessor account (immediate caller) from the signer of the
  originating transaction. NEAR cross-contract calls and callbacks execute
  asynchronously in separate receipts; do not assume EVM-style synchronous
  reentrancy. Explore relevant receipt orders and failed promises explicitly.
- Prioritize generated method wrappers and access restrictions, initialization
  and migration checks, promise and callback handling, storage collections,
  serialization, attached-deposit handling, and fungible/non-fungible token
  accounting in near-contract-standards.
- Include unsafe code, host-buffer handling, collection aliasing and persistence,
  drop/flush behavior, and differences between native mocks and deployed Wasm.
  Identify the precise optional features and target needed for each issue.
- SDK consumer code and contract administrators are trusted to follow documented
  preconditions. Provide a minimal contract showing that the SDK or standard
  implementation fails under supported usage. An arbitrary insecure example
  contract is not evidence that every SDK consumer is vulnerable.
- NEAR's host runtime and protocol enforcement are external dependencies. Do not
  report a mock-only behavior as a production host vulnerability. Defects in the
  SDK's own mock can still be reported as testing-fidelity bugs with that scope.

## Reproduction and severity

State the affected source/API, feature set, native or Wasm target, toolchain,
attacker control, required state, and expected versus actual behavior. For claims
about deployed contracts, callback failures, gas, or receipt ordering, prefer a
minimal local sandbox reproduction in addition to unit tests. Use local sandbox
accounts only; no mainnet/testnet RPC access or real funds are needed.

Critical or high severity requires a demonstrated consequence such as theft,
unauthorized state changes, irrecoverable accounting corruption, or a substantial
availability failure across a real trust boundary. Name any administrator access,
fees, deposits, gas, or repeated transactions required. A caller exhausting its
own paid gas or deliberately failing its own call is not automatically a
vulnerability. Assess whether an attack harms other users, traps assets, corrupts
shared state, or leaves persistent unpaid work.

Do not classify documented API limitations, unsafe consumer code, theoretical
host behavior, or a changed performance threshold as an exploit without proving
the missing steps. Keep distinct root causes separate and include a regression
test with any proposed patch. Do not remove checks or rewrite expected snapshots
to hide the failure.

## Build and tests

The checkout is at /src. The image includes Rust 1.95, the wasm32-unknown-unknown
target, cargo-near 0.21.0, and a local near-sandbox 2.14.0-rc.2 binary selected by
NEAR_SANDBOX_BIN_PATH. Native and Wasm build caches and dependency sources remain
available for offline reproduction. CARGO_BUILD_JOBS and RUST_TEST_THREADS are
limited to two to fit the scanning environment.

Run the principal workspace suite, including integration tests and doctests:

```sh
cargo test --workspace --features unstable,legacy,__abi-generate,deterministic-account-ids
```

For faster iteration, start with `cargo test --workspace --lib` with the same
features, or a focused package/test filter. Tests under near-sdk/tests include
sandbox-backed checks that build contracts from near-sdk/tests/test-contracts.
Examples are separate workspaces; their dependency sources are prefetched, and
their source is useful for building minimal consumer contracts. Performance and
Wasm-size expectations can depend on the exact compiler and runtime; report a
security consequence rather than only a changed measurement.
