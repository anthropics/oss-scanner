# Threat model

## Project and trust boundaries
`esplora-client` provides async and blocking HTTP clients and types for Esplora servers. It builds URLs, sends requests, parses untrusted JSON/hex responses, and exposes transaction, address, block, fee, and merkle data.

## Untrusted inputs
- Esplora HTTP responses: status codes, headers, JSON, hex, pagination fields, and large bodies.
- Server URLs, paths, query parameters, and user-supplied headers.
- TLS peer certificates and redirects.
- Data returned by the server (transactions, blocks, headers, merkle proofs, fee estimates, histories).

## In scope
- URL construction and escaping, header handling, redirect behavior, and request routing.
- TLS verification and native-tls/rustls configuration.
- JSON/hex parsing, pagination, and response typing.
- Unbounded allocation, integer parsing, panics, and CPU exhaustion on hostile responses.
- Secret/header leakage in errors or logs.

## Out of scope
- `tests/wasm`, `electrsd` testenv, and tests that require a live public Esplora server.
- `bitreq` upstream bugs, unless this crate misuses it.
- Esplora server software.
- Consensus/chain semantics that belong to a higher-level wallet.

## How to exercise the code offline
The image pre-builds tests and pre-downloads the local `bitcoind`/`electrsd` binaries. Run:
- `cargo test --all-features -- --test-threads=1`

No Internet access is available; tests use local regtest.

## Severity rubric
- Critical: TLS verification bypass or MITM; URL/header injection leading to credential leak or SSRF; RCE/memory corruption in parsing.
- High: unbounded memory/CPU DoS from a malicious server; reliable panic on malformed response; incorrect tx/merkle/fee parsing that leads to wrong wallet state.
- Medium: pagination/retry/backoff edge cases causing incorrect behavior under unusual conditions.
- Low: robustness or best-practice issues with no demonstrated security impact.

## Report and patch preferences
- Minimal reproducer with exact request/response bytes or a mock server/test.
- State required features (`blocking`, `async-https`, `tokio`, etc.).
- Prefer a minimal patch; call out behavior changes.
- Deduplicate by root cause and affected function.

## Known non-issues / do not report
- WASM test harness and `electrsd` testenv code.
- Public Esplora server behavior.
- `bitreq` upstream issues.
