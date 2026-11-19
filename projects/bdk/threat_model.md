# Threat model

## Project and trust boundaries
`bdk` is the Rust workspace containing BDK's chain-data and chain-source crates: `bdk_chain`, `bdk_core`, `bdk_esplora`, `bdk_electrum`, `bdk_bitcoind_rpc`, `bdk_file_store`, and `bdk_testenv`. It builds and maintains wallet chain state from untrusted full nodes, Electrum servers, and Esplora servers, and persists that state locally.

## Untrusted inputs
- Electrum, Esplora, and Bitcoin Core RPC responses: JSON, hex, blocks, headers, transactions, merkle proofs, fee estimates, histories, and paginated results.
- Block and transaction data received from the Bitcoin network.
- Descriptors, scripts, outpoints, txids, and keychain identifiers supplied by callers.
- Serialized chain/wallet data read from `bdk_file_store` or the `rusqlite` backend.
- Environment/config values that select servers; the servers themselves are untrusted.

## In scope
- Parsing, validation, and state transitions in `bdk_chain` and `bdk_core`.
- `bdk_esplora` and `bdk_electrum` sync logic, batching, reorg handling, and response correlation.
- `bdk_bitcoind_rpc` block/transaction ingestion.
- Persistence load/store paths in `rusqlite`.
- Memory safety, integer arithmetic, unbounded allocation, panics, and CPU exhaustion on hostile server data.

## Out of scope
- Bugs in `rust-bitcoin`, `rust-miniscript`, `serde`, `electrsd`, `bitcoind`, or other dependencies, unless BDK misuses the dependency.
- `bdk_file_store`, `crates/testenv`, tests, benchmarks, and examples.
- Historical release branches and non-default feature combinations that the Dockerfile does not build.
- Behavior of the remote server software itself.

## How to exercise the code offline
The image pre-builds all workspace targets with `--all-features` and pre-downloads the regtest `bitcoind`/`electrs` binaries used by `bdk_testenv`. Run:
- `cargo test -p bdk_chain --all-features`
- `cargo test -p bdk_esplora --all-features`
- `cargo test -p bdk_electrum --all-features`
- `cargo test -p bdk_bitcoind_rpc --all-features`

No Internet access is available.

## Severity rubric
- Critical: forged or replayed chain data causes a wallet to treat a spend/confirmation incorrectly and lose funds without user action; memory corruption or RCE from parsing untrusted chain data.
- High: a malicious server can reliably desynchronize or crash a wallet, leak private address/script correlations, corrupt persisted state, or cause an incorrect broadcast decision.
- Medium: DoS requiring unusual input, panic on malformed server data, or privacy/behavior issues that require user action.
- Low: robustness or best-practice issues with no demonstrated security impact.

## Report and patch preferences
- Minimal reproducer as a Rust test or exact `cargo test` command.
- Include the feature set and raw input bytes/JSON.
- Prefer a minimal patch; call out any behavior change.
- Deduplicate by root cause and affected function, not by symptom.
- Do not report upstream dependency bugs unless BDK misuses the dependency.

## Known non-issues / do not report
- `bdk_testenv` requiring a local bitcoind/electrs, or tests that need those binaries.
- `bdk_file_store` is for testing only, not production users.
- Panics in test-only code.
- Missing validation that the caller is expected to perform (for example, trusting a descriptor the caller constructed).
