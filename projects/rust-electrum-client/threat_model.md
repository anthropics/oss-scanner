# Threat model

## Project and trust boundaries
`electrum-client` is a Bitcoin Electrum JSON-RPC client supporting plaintext, TLS, onion, and SOCKS proxy connections. It parses untrusted server responses and maintains subscriptions and request/response correlation.

## Untrusted inputs
- Electrum server responses: JSON-RPC objects, hex payloads, lengths, IDs, notifications, and batch responses.
- TLS peer certificates and handshake data.
- SOCKS4/SOCKS5 proxy responses and credentials.
- User-supplied server URLs, ports, timeouts, and authentication providers.
- Network data returned by the server (headers, transactions, merkle proofs, histories, fee estimates).

## In scope
- JSON-RPC framing, parsing, request/response correlation, batching, and subscriptions.
- TLS certificate/hostname verification and rustls/openssl configuration.
- SOCKS proxy handshake and authentication handling.
- Unbounded allocation, integer parsing, panics, and CPU exhaustion on hostile responses.
- Secret handling for proxy/auth credentials and logging.

## Out of scope
- Live Electrum servers and the tests that require `TEST_ELECTRUM_SERVER`.
- Example `jwt_dynamic_auth` code and example-only dependencies.
- Electrum server software and `rust-bitcoin` behavior.
- Consensus/chain semantics that belong to a higher-level wallet.

## How to exercise the code offline
The image compiles all targets and tests. Live-server tests are excluded from the smoke test. Run:
- `cargo test --all-features --lib config::`
- `cargo test --all-features --lib types::`
- `cargo test --all-features --no-run` to compile the rest

No Internet access is available; do not add tests that connect to a real server.

## Severity rubric
- Critical: TLS verification bypass or MITM enabling forged chain data; RCE/memory corruption from parsing; proxy credential leak; SSRF to local services.
- High: unbounded allocation/CPU DoS from a malicious server; reliable panic that kills the client; incorrect response correlation causing wrong chain data; auth header/credential leak.
- Medium: protocol-version, reconnection, or subscription race that causes incorrect behavior under unusual conditions.
- Low: robustness or best-practice issues with no demonstrated security impact.

## Report and patch preferences
- Minimal reproducer using a mock stream or raw response bytes; do not require a live server.
- State required features (`rustls`, `openssl`, `proxy`, etc.).
- Prefer a minimal patch; call out behavior changes.
- Deduplicate by root cause and affected function.

## Known non-issues / do not report
- Tests that depend on a live Electrum server.
- Example JWT code.
- Behavior of the remote Electrum server.
