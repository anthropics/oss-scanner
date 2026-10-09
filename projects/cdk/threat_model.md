# Cashu Development Kit (CDK)

CDK is a Rust workspace implementing Cashu e-cash wallets and mints. It handles
bearer tokens, blind signatures, wallet secrets, mint accounting, and Bitcoin
Lightning payments. See SECURITY.md in the scanned checkout for reporting policy.

## Trust boundaries and priorities

Treat mint HTTP and WebSocket requests, tokens received by wallets, remote mint
responses, invoices, payment callbacks, and Nostr messages as untrusted input.
Prioritize cashu protocol validation and cryptography; cdk mint and wallet logic;
cdk-axum endpoints and authentication; database transactions and recovery; signing
services; and payment backend integration. Include optional features when relevant.

Check value conservation, single-use proofs, spending conditions, signature and
keyset validation, payment settlement, authorization, and protection of private
keys and wallet secrets. Consider concurrency, retries, cancellation, process
restarts, and inconsistent or malicious remote responses at these boundaries.
Distinguish a hostile remote party from a trusted mint operator or administrator.
Administrative access alone is not evidence of an authorization bypass.

## Build and tests

The checkout is /src. The image retains Cargo's dependency cache and debug
artifacts in /src/target. cdk-mintd and cdk-cli are in target/debug.
The native Rust toolchain is selected by RUSTUP_TOOLCHAIN.

Run the precompiled library tests without Internet access:

    cargo test --locked --offline --lib -p cashu -p cdk-common -p cdk -p cdk-sqlite -p cdk-axum

Other workspace crates and optional features can be built with cargo --offline;
they are not all precompiled. Tests requiring PostgreSQL, Bitcoin, Lightning,
external mints, or relays need their respective local services. The image does
not start these services. Consult REGTEST_GUIDE.md and crates/cdk-integration-tests
for service-backed tests; prefer deterministic local mocks for focused reproductions.

## Assessing and reporting findings

Explain realistic attacker capabilities and deployment assumptions. Prioritize
unauthorized creation or theft of value, double spending, key disclosure, and
remote code execution. Assess denial of service by reachability, resource cost,
persistence, and recovery. Do not infer severity solely from a panic or a failing
test; establish a reachable production path and concrete impact.

Send detailed findings privately to the primary security contact. Follow
SECURITY.md: keep exploit details, reproductions, and root-cause specifics out of
public issues, PRs, commit messages, and code comments until release and coordinated
disclosure. This guidance does not assert that any specific vulnerability exists.
