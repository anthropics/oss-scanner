# Threat model: sv2-apps

## What this project does and where untrusted input enters

This repository holds the applications of the Stratum V2 Reference Implementation (SRI). They are long-running network daemons that pool operators and miners run on the Internet. The protocol libraries they are built on (framing, Noise encryption, message codecs, channel and share accounting) live in https://github.com/stratum-mining/stratum, enrolled separately, and reach this repository through the `stratum-core` dependency of `stratum-apps` and `bitcoin-core-sv2`.

One Cargo workspace:

- `pool-apps/pool` (`pool_sv2`): a Stratum V2 pool. It accepts Sv2 mining connections from any miner, proxy or Job Declarator Client on the Internet, and connects to a Template Provider for block templates.
- `pool-apps/jd-server` (`jd_server_sv2`): the Job Declarator Server, a library that runs inside the pool process when the pool config has a `[jds]` section (which needs the Bitcoin Core IPC template provider). It accepts Job Declaration connections from miners' Job Declarator Clients, receives the block templates and transaction lists they declare, and validates the declared transactions against a mirror of the operator's Bitcoin Core mempool (over IPC).
- `miner-apps/jd-client` (`jd_client_sv2`): the Job Declarator Client a miner runs. It accepts Sv2 connections from downstream mining devices or proxies, builds its own block templates from a Template Provider, declares them to a pool's Job Declarator Server, and falls back to the next configured upstream or to solo mining when the pool misbehaves (it never mines jobs the pool sends).
- `miner-apps/translator` (`translator_sv2`): the Translator Proxy. It accepts Stratum V1 connections (plain-text JSON-RPC over TCP) from mining hardware and speaks Sv2 upstream to a pool or Job Declarator Client.
- `stratum-apps`: shared application code: configuration parsing (TOML), the network helpers for Noise-encrypted Sv2 connections and plaintext SV1 connections, coinbase output and payout-address construction, key handling, the fallback coordinator, and the `monitoring` module: an HTTP server (axum) that serves a JSON API under `/api/v1`, Swagger UI, the OpenAPI document and Prometheus `/metrics`.
- `bitcoin-core-sv2`: translates Bitcoin Core's IPC interface (Cap'n Proto over a Unix socket) into the Sv2 Template Distribution and Job Declaration protocols.
- `integration-tests`: a test framework that starts real instances of every role plus Bitcoin Core and sv2-tp, with a sniffer that sits between two roles and asserts on the messages they exchange.

Trust boundaries, from least to most trusted:

1. **Downstream peers** are anonymous and hostile. For the pool and the Job Declarator Server that is anyone on the Internet; for the Translator Proxy and the Job Declarator Client it is the mining hardware on the operator's network, which is often firmware the operator cannot inspect. Treat everything a downstream sends as attacker-controlled: the Noise handshake, every Sv2 message and its fields (channel ids, request ids, nonces, versions, extranonces, hashrate estimates, job and template ids, transaction lists), the Stratum V1 JSON that the Translator Proxy parses, and the timing of all of it (connections that stall mid-handshake, flood shares, open channels without using them, or disconnect at any point).
2. **Upstream peers**. A miner's Translator Proxy or Job Declarator Client treats the pool and the Job Declarator Server as a counterparty that may lie or misbehave: a wrong job, a bad target, a rejected valid share, a declaration never answered, or a connection that hangs. The Job Declarator Client's fallback logic exists for this and is in scope.
3. **The Template Provider and Bitcoin Core** are run by the same operator as the application that connects to them, or, in the `hosted-*` examples, the Template Provider is the community-hosted one pinned by its `public_key`. The Sv2 connection to a Template Provider is encrypted but only authenticated when the config sets its public key (`tp_type.rs`); the shipped `pool-config-local-sv2-tp-example.toml` files set none, while the `hosted-sv2-tp` ones set the hosted provider's key. A finding that needs a hostile Template Provider or a hostile IPC peer is real but lower severity than the same effect from a downstream.
4. **The monitoring HTTP server** has no authentication of its own. Operators are expected to keep it off the public Internet; report what an unauthenticated client of it can do, rated as below.
5. **Configuration files and the command line** are trusted; a malformed config file that crashes an app is not a finding.

## Components that matter most / least

Most important, in this order:

1. The connection setup and message handling of the pool and the Job Declarator Server, since they face the Internet: Noise handshake, `SetupConnection`, channel opening, share submission, job declaration and the transaction data that comes with it.
2. The share and coinbase handling of every role: share validation and accounting, the construction of coinbase outputs from the configured payout, and the custom jobs the Job Declarator Client builds and declares. A mistake here pays a miner for work it did not do, lets a miner have a block built with the wrong payout, or lets a pool refuse valid work.
3. The Translator Proxy's Stratum V1 side and the translation of V1 submits into Sv2 shares.
4. The Job Declarator Client's fallback and upstream-failure handling: a hostile pool must not be able to make a miner stop mining or mine for the wrong payout.
5. `stratum-apps`: the network helpers, the fallback coordinator and the monitoring server.
6. `bitcoin-core-sv2`: the IPC bindings and mempool mirror, reachable only from the operator's own node.

Out of scope: `integration-tests/` (test tooling, though it is the best way to drive the roles), `scripts/`, `docker/`, CI configuration, benchmarks, profiling (`PROFILING.md`, the `hotpath` features) and the configuration examples. The protocol libraries in `stratum-core` belong to the `stratum` enrolment: when a finding's root cause is in a `stratum` crate, report it against `stratum` and mention the sv2-apps path that reaches it. Bitcoin Core, sv2-tp and the mining firmware are separate projects.

## How to exercise it

The image is offline. Every dependency is in the cargo cache, `CARGO_NET_OFFLINE` is set, the workspace and its tests are built in `/src`, and the external binaries that the integration tests would otherwise download are already in place: Bitcoin Core 30.2 and 31.0 under `integration-tests/template-provider/bitcoin-<version>/`, sv2-tp under `integration-tests/template-provider/sv2-tp-1.1.0/`, and minerd (the Stratum V1 CPU miner) at `integration-tests/minerd/minerd`. All of them use only loopback.

- **Unit tests**: one crate at a time, as CI does: `cargo test -p stratum-apps --all-features`, `cargo test -p pool_sv2`, `cargo test -p jd_server_sv2`, `cargo test -p jd_client_sv2`, `cargo test -p translator_sv2`, `cargo test -p bitcoin_core_sv2`.
- **Integration tests**: `cargo test -p integration_tests_sv2 --test <file>` for any file under `integration-tests/tests/` (`pool_integration`, `jd_integration`, `translator_integration`, `jdc_fallback_to_solo`, `monitoring_integration`, `sv1`, and others). Each test starts the roles it needs on ephemeral ports against a regtest or signet Bitcoin Core, so they are the quickest way to stand up a full stack to attack. `integration-tests/README.md` and `integration-tests/lib/mod.rs` show the `start_<role>` helpers and the sniffer, and `integration-tests/lib/mock_roles.rs` has mock peers to build a hostile counterpart from. Set `RUST_LOG=debug` to see the roles' logs.
- **The binaries**: `cargo build --workspace` leaves `pool_sv2`, `jd_client_sv2` and `translator_sv2` in `target/debug/`; the Job Declarator Server has no binary of its own and runs inside `pool_sv2` with a `pool-jds-config-*.toml`. Each takes a TOML config; `pool-apps/pool/config-examples/`, `miner-apps/jd-client/config-examples/` and `miner-apps/translator/config-examples/` have examples per network (mainnet, signet, testnet4), and the integration tests build their own.
- **A mining device**: `cargo run -p integration_tests_sv2 --bin mining_device -- --address-pool 127.0.0.1:<port> --id-device test` is an Sv2 CPU miner; `integration-tests/minerd/minerd` is a Stratum V1 one for the Translator Proxy.
- **The monitoring API**: `/api/v1/health`, `/api/v1/global`, `/api/v1/clients`, `/api/v1/sv1/clients`, `/metrics` and `/swagger-ui` on the port each app's config sets; `stratum-apps/src/monitoring/README.md` lists them.
- **The protocol specification** is at https://github.com/stratum-mining/sv2-spec; it is not in the image, so quote the section you rely on when a finding is about spec conformance.

## How you rate severity

A finding counts when a network peer of a role can make it misbehave. Say which role, which peer (downstream, upstream, Template Provider, monitoring client) and what configuration the reproducer needs; a finding against the shipped config examples weighs more than one that needs a setting changed.

- **Critical**: memory corruption reachable from a downstream or upstream peer. A downstream share accepted that does not meet its channel's target, or a share or block credited to the wrong channel or payout. A block built or declared with a coinbase that pays someone other than the configured payout. A Noise connection accepted without the handshake completing, or a client that completes a handshake with a server that does not hold the expected authority key.
- **High**: an unauthenticated downstream that crashes or hangs a pool or Job Declarator Server, or makes its memory grow without bound (unbounded channels, jobs, pending declarations, buffered shares or transaction lists). A single misbehaving downstream that degrades service for the others. An upstream that can make a Job Declarator Client or Translator Proxy stop serving its miners for good, instead of falling back or reconnecting. A valid share or block rejected or lost because of an application error.
- **Medium**: a panic or stall confined to one connection, cleaned up without affecting the others. A per-connection resource that outlives its connection. Anything an unauthenticated monitoring client can do beyond reading the metrics and metadata the API documents, and any secret (keys, pool credentials) the API exposes. A desynchronisation between a role's view of a channel or job and its peer's that a peer can cause and that does not fit a higher rating.
- **Low**: a defect that needs a hostile Template Provider or Bitcoin Core, or a non-default feature. Information in log output.

A deviation from the Sv2 specification with no security consequence is a bug and not a vulnerability; do not report it. Shares that are valid under the protocol but unprofitable for the pool (for example, low-difficulty shares accepted at the configured minimum) are policy, not a finding.

## How to report

- Give a reproducer that runs in this image: an integration test or a script that starts the role and the hostile peer, the exact messages or bytes sent, and what was observed. For resource exhaustion, give the measured memory or time.
- Name the role, the crate, the cargo features, the Bitcoin Core version and the config setting that differs from the shipped examples.
- Propose a minimal patch against `main` with a regression test, and keep unrelated refactoring out of it.
- Report one root cause once. The same defect in two roles (the pool and the Job Declarator Client both accept downstream Sv2 connections and share code through `stratum-apps`) is one finding that lists each.

## Anything to leave alone

- The monitoring HTTP server has no authentication, TLS or rate limiting by design, and the shipped JDC and Translator Proxy examples bind it on `0.0.0.0`; operators are expected to firewall it. Report what it leaks or allows, not that it is unauthenticated or reachable.
- The `authority_secret_key`/`authority_public_key` pair in the pool and JDC examples, and the `authority_pubkey` starting `9auqWEzQ` that the JDC examples and all but the mainnet hosted-pool Translator Proxy example point upstream at, are published placeholders that operators replace with their own keys; a handshake that trusts that key is the example, not a finding.
- Stratum V1 is a plain-text protocol with no authentication beyond a username; the Translator Proxy implements it as miners speak it. Do not report the protocol's own weaknesses.
- The applications are alpha software (see `README.md`) and shut down on some unrecoverable conditions on purpose; a crash is a finding when a peer can trigger it (a Template Provider or Bitcoin Core counts as a peer, at Low), not when the operator's own config does.
- The `hotpath` and `hotpath-alloc` features are profiling instrumentation and are never enabled in a release.
