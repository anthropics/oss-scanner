# Threat model

## Project and trust boundaries
`bdk-ffi` is the UniFFI boundary that exposes `bdk_wallet`, Esplora, Electrum, and Kyoto/CBF to Kotlin (Android) and Swift. The Rust wrapper in `bdk-ffi/` is the security-relevant surface; generated Kotlin/Swift bindings are not reviewed as first-party code.

## Untrusted inputs
- Foreign-implemented callbacks and traits from Kotlin/Swift: signers, persistence/storage, sync progress, and any host object returning data into Rust.
- Descriptors, mnemonics, keys, PSBTs, transactions, addresses, outpoints, fee rates, and network URLs passed from the host language.
- Chain data from Electrum, Esplora, and Kyoto P2P.
- Persisted wallet/chain data supplied by the host storage implementation.
- Concurrent calls and object lifetimes from the host runtime.

## In scope
- Rust FFI wrapper types and functions in `bdk-ffi/src/` (wallet, tx builder, signer, store, esplora, electrum, kyoto, keys, types, error).
- Validation of data crossing the FFI boundary, especially signatures, PSBTs, descriptors, and persistence data.
- Object lifetime, reference counting, thread-safety, and panic behavior across UniFFI.
- Error mapping and secret handling (mnemonics, descriptors, keys) in errors/logs.
- Conversion between host-language types and Rust types, including integer truncation and invalid enum values.

## Out of scope
- Bugs in upstream `bdk_wallet`, `bdk_chain`, `bdk_tx`, `bdk_esplora`, `bdk_electrum`, `bdk_kyoto`, `rust-bitcoin`, `miniscript`, or UniFFI itself, unless the wrapper misuses them.
- Generated Kotlin/Swift binding code.
- Android Gradle, Swift Package, Xcode, signing, and publishing scripts.
- Tests that require live MutinyNet Esplora access.
- Build tooling for Android/Swift; the container builds only the Rust crate.

## How to exercise the code offline
The container builds and pre-compiles tests in `bdk-ffi/`. Run:
- `cd bdk-ffi && cargo test --locked`

Live-network tests are already `#[ignore]`. Do not enable `uniffi/bindgen-tests`; the JNA jar is not in the repository. No Internet access is available.

## Severity rubric
- Critical: private key/seed/mnemonic disclosure across the FFI boundary; signing the wrong sighash/input/amount; use-after-free/double-free or object-lifetime confusion; panic unwinding across FFI or abort on hostile host input; thread-safety violation mutating wallet state concurrently.
- High: fund loss via tx-builder/wallet behavior; error swallowing that hides a failed signature/broadcast; persistence corruption from a host callback; unbounded allocation/CPU in FFI conversions or CBF sync.
- Medium: DoS with unusual host input or incorrect behavior requiring user confirmation.
- Low: robustness or best-practice issues with no demonstrated security impact.

## Report and patch preferences
- Minimal reproducer as a Rust test where possible; for host-only issues, include the Kotlin/Swift call sequence and the Rust function involved.
- State whether the issue is in the wrapper, the generated binding, or an upstream crate.
- Prefer a minimal patch; call out behavior changes.
- Deduplicate by root cause and affected function.

## Known non-issues / do not report
- Generated bindings, Gradle/Xcode build failures, and publication scripts.
- Upstream BDK crate bugs, unless the FFI wrapper misuses them.
- Live MutinyNet tests and test-only code.
