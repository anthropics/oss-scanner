# Threat model

## Project and trust boundaries
`bdk_wallet` is BDK's high-level descriptor-based Bitcoin wallet: address derivation, PSBT creation and signing, policy checks, balance/UTXO tracking, and persistence. It sits above `bdk_chain` and `bdk_tx` and is the component applications use to move funds.

## Untrusted inputs
- PSBTs and descriptors received from counterparties or external wallets.
- Chain data from Electrum/Esplora/bitcoind sources.
- External signer implementations and signatures returned to the wallet.
- Serialized wallet data loaded from SQLite or other persistent stores.
- Caller-supplied fee rates, UTXOs, change policies, recipients, and network parameters.

## In scope
- Descriptor/key handling, address derivation, and network/script consistency checks.
- PSBT construction, update, signing, and finalization paths.
- Policy and miniscript checks that gate spending.
- Fee, change, dust, and coin-selection integration.
- Persistence load/store and migration paths.
- Panics, integer arithmetic, secret handling, and error propagation on hostile PSBT/descriptor/chain input.

## Out of scope
- Bugs in `bdk_chain`, `bdk_tx`, `rust-bitcoin`, `rust-miniscript`, `rusqlite`, or `bdk_file_store`, unless `bdk_wallet` misuses them.
- Test utilities, examples, and benchmarks.
- Remote server behavior; malformed server responses should be reported against the chain-source crate unless the wallet mishandles them.

## How to exercise the code offline
The image builds all targets and tests. Run:
- `RUSTFLAGS="--cfg bdk_wallet_unstable" RUSTDOCFLAGS="--cfg bdk_wallet_unstable" cargo test --all-features`
- `cargo test --all-features` for the stable API surface

The image sets both `RUSTFLAGS` and `RUSTDOCFLAGS` to `--cfg bdk_wallet_unstable`.

No external services are required.

## Severity rubric
- Critical: signing a PSBT over the wrong sighash/input/amount; policy or timelock bypass; private key/seed extraction; undetected loss of funds.
- High: fee/change/dust/coin-selection bug that loses funds; address or network mismatch; persistence corruption; panic on a malicious PSBT/descriptor.
- Medium: DoS with unusual input, privacy leak, or incorrect behavior requiring user confirmation.
- Low: robustness or best-practice issues with no demonstrated fund/security impact.

## Report and patch preferences
- Minimal reproducer as a Rust test with the exact PSBT/descriptor bytes.
- State whether `--cfg bdk_wallet_unstable` or a specific feature is required.
- Prefer a minimal patch; call out any behavior change.
- Deduplicate by root cause and affected function.
- Do not report upstream dependency bugs unless `bdk_wallet` misuses the dependency.

## Known non-issues / do not report
- Test-only code and examples.
- Behavior that requires the caller to supply an already-validated descriptor or PSBT.
