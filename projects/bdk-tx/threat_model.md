# Threat model

## Project and trust boundaries
`bdk-tx` builds, updates, and finalizes Bitcoin transactions and PSBTs from descriptors and miniscript policies. It is the transaction-construction layer used by wallets and FFI bindings.

## Untrusted inputs
- PSBTs and descriptors from counterparties.
- UTXO metadata (values, scripts, weights, outpoints).
- Fee rates, target outputs, change policies, RBF/sequence parameters, and max-weight constraints.
- External signer results and caller-supplied signatures.
- Chain data used to select or verify inputs.

## In scope
- Transaction/PSBT construction, input/output ordering, fee and change arithmetic.
- Sighash computation and signature application/finalization.
- Timelock, sequence, RBF, and anti-fee-sniping logic.
- Miniscript/descriptor policy enforcement at the transaction layer.
- Overflow/underflow, panics, and invalid-transaction acceptance on adversarial inputs.

## Out of scope
- Bugs in `rust-miniscript`, `rust-bitcoin`, `bdk_coin_select`, or consensus rules, unless `bdk-tx` misuses them.
- `bdk_testenv`, examples, and tests.
- Policy decisions made by the calling wallet above this crate.

## How to exercise the code offline
The image builds all targets, including examples that use `bdk_testenv`, and pre-downloads the regtest binaries. Run:
- `cargo test --all-features`
- `cargo build --all-targets --all-features`

No Internet access is available.

## Severity rubric
- Critical: constructs or signs a transaction that pays the wrong recipient/amount; signs the wrong sighash; bypasses timelock/multisig policy; leaks key material.
- High: fee/change/RBF bug that loses funds; accepts an invalid transaction; panic on an adversarial PSBT.
- Medium: DoS with unusual input or incorrect behavior requiring user confirmation.
- Low: robustness or best-practice issues with no demonstrated fund/security impact.

## Report and patch preferences
- Minimal reproducer as a Rust test with exact PSBT/descriptor/UTXO inputs.
- State required features and whether the example testenv is involved.
- Prefer a minimal patch; call out behavior changes.
- Deduplicate by root cause and affected function.

## Known non-issues / do not report
- Examples and test-only code.
- Upstream miniscript/bitcoin behavior.
- Caller-supplied data that the caller is expected to validate.
