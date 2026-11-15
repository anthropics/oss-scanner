# Threat model: freenet-core

## What this project does and where untrusted input enters

Freenet is a peer-to-peer platform for decentralized applications. Each user runs a node (the `freenet` binary, built from `crates/core`). Nodes form a small-world ring over UDP and cooperate to store, retrieve and propagate the state of contracts. A contract is a WebAssembly module plus parameters. Its key is a hash of the code and the parameters, and its code decides which states and updates are valid. Delegates are WebAssembly modules that run only on the user's own node and hold that user's private data and keys. Web applications are themselves stored as contract state and are served to the user's browser by the node's local HTTP gateway.

Treat all of the following as attacker-controlled:

- **Every UDP datagram** reaching the node's network port, from anyone, before any handshake. The transport (`crates/core/src/transport/`) uses an X25519 key exchange with a ChaCha20-Poly1305 intro packet, then AES-128-GCM for every data packet. Messages larger than one packet are split into streams and reassembled. The initiator must know the responder's public key. Everything a remote peer sends after the handshake is untrusted too, including any identity, address or location it claims for itself or for other peers.
- **Inter-peer operation messages**: CONNECT (joining and topology), GET, PUT, UPDATE and SUBSCRIBE, plus the broadcast, interest and summary messages that keep subscribed copies in sync (`crates/core/src/message.rs`, `crates/core/src/operations/`, `crates/core/src/node/network_bridge/`).
- **Contract code, parameters, state and deltas received from the network.** Any peer can PUT a contract, and a node that routes or hosts it will compile and run that WASM.
- **Delegate code** registered by a web application, and every message a web application sends to a delegate.
- **Content served by the HTTP gateway.** A web app is a tar.xz archive inside contract state, written by whoever published the contract. The node unpacks it and serves it to the browser.
- **The browser**: other websites the user visits, and web apps served by this node, all of which may try to reach the client API.

Trusted: the operator, the node's config files and environment, local processes that can open a socket to the client API, and the release infrastructure.

### Trust boundaries the project intends to enforce

- A remote peer must not be able to execute code on a node, corrupt its memory, or crash, hang or permanently degrade it with a small number of messages.
- Contract and delegate WASM runs in a wasmtime sandbox (`crates/core/src/wasm_runtime/engine/wasmtime_engine.rs`). It may only use the host functions the node links in. Each instance is limited to 256 MiB of linear memory (`DEFAULT_MAX_MEMORY_PAGES` in `engine.rs`) and an 8 MiB WASM stack. Execution is preempted by epoch interruption after `max_execution_seconds` (5 s by default, `wasm_runtime/runtime.rs`); fuel metering exists but is off by default. Guest code must stay inside these bounds and must not read or write host memory or another instance's memory.
- A node must not store or serve contract code under a key that the code and parameters do not hash to (`verify_contract_identity` in `wasm_runtime/contract_store.rs`). It must not accept, store or forward contract state that the contract's own `validate_state` rejects.
- Delegate secrets are encrypted at rest with XChaCha20-Poly1305, under a per-delegate key derived by HKDF-SHA256 from a node key-encryption key (`docs/secrets-at-rest.md`, `wasm_runtime/secrets_store/`, `config/kek.rs`). One delegate must not read another delegate's secrets.
- The node tells a delegate which web app sent a message (`MessageOrigin`, resolved in `contract/executor/runtime/delegates.rs`). That attestation must be accurate: a page served for one contract must not be able to act as another app, and must not reach another app's delegate secrets.
- The client API (HTTP and WebSocket, default port 7509) is a fully privileged control surface. By default it binds to loopback only (`resolve_ws_api_address` in `config.rs`, `docs/client-api-exposure.md`). WebSocket upgrades are checked against `Origin` and `Host` (`client_events/websocket.rs`) so that an arbitrary website the user visits cannot drive the node.
- Web app content runs in a sandboxed iframe with an opaque origin, under a `sandbox` Content-Security-Policy that the node sends on every response carrying contract-authored bytes (`server/client_api.rs`). Contract content must never execute at the node's own origin, where it would gain the shell's credentials, the dashboard and the client API. Unpacking a web archive must never write outside its destination directory (`server/app_packaging.rs`).
- Node-authored permission prompts (`server/client_api/permission_prompts.rs`) and capability grants (`contract/delegate_capabilities.rs`) must only be answerable by the user, never by a web app or delegate.
- In hosted mode (`--hosted-mode`, off by default), a connection presenting a user token gets its own delegate-secret namespace. One user's token must never give access to another user's namespace.

## Components that matter most / least

Most important, roughly in order:

1. **Transport**: `transport/connection_handler.rs` (handshake, per-source rate limiting), `crypto.rs`, `packet_data.rs`, `symmetric_message.rs`, `peer_connection.rs` and `peer_connection/` (stream reassembly, `inbound_budget.rs`, the per-connection stream caps in `streaming.rs`).
2. **WASM runtime**: `wasm_runtime/engine/wasmtime_engine.rs` (engine configuration, resource limiter, linker), `native_api.rs` (host functions that copy data in and out of guest memory), `contract.rs`, `delegate.rs`, `contract_store.rs`, `state_store.rs`, `module_cache.rs`.
3. **Peer message handling**: `message.rs`, `node/network_bridge/`, `operations/` (connect, get, put, update, subscribe), `ring/`, `contract/executor/`.
4. **Delegates and secrets**: `wasm_runtime/secrets_store/`, `wasm_runtime/delegate_store.rs`, `contract/executor/runtime/delegates.rs`, `contract/delegate_capabilities.rs`, `config/kek.rs`, `config/secret.rs`.
5. **Client API and HTTP gateway**: `client_events/websocket.rs`, `client_events.rs`, `server/client_api.rs`, `server/path_handlers.rs` and its JS assets (`shell.html`, `shell_bridge.js`, `websocket_shim.js`, `navigation_interceptor.js`), `server/app_packaging.rs`, `server/client_api/permission_prompts.rs`, the hosted-mode endpoints in `server/client_api/hosted_*.rs`, and the dashboard in `server/home_page/`, which renders data learned from peers and contracts at the node's own origin.
6. **Storage**: `contract/storages/redb.rs` (the default backend) and `sqlite.rs` (the optional `sqlite` feature).
7. **`crates/website-contract`**: a contract that hosts signed static websites published with `fdev website`. It runs on every node that hosts such a site, and its signature check in `validate_state` is what stops a third party from replacing the site.

`freenet-stdlib` (contract and delegate interfaces, key derivation, the client API types) is maintained by the same team in a separate repository. A flaw in it that is reachable through the node is in scope; name the crate the fix belongs in. wasmtime, rustls, tokio, axum, tungstenite, redb and the RustCrypto crates have their own security processes; report a flaw here only when the node's use of the crate makes it reachable.

Lower priority: `crates/fdev` (developer CLI, reads local files), `crates/freenet-macros`, and the CLI-only commands in `crates/core/src/bin/commands/` (service install, tray, setup wizard).

Out of scope: `crates/netcheck`, `crates/release-agent`, `crates/replay-harness`, `crates/topology-sim` (project infrastructure and research tools, not part of the node); `apps/freenet-ping` and `tests/*` (test fixtures); code gated on `cfg(test)` or the `testing`, `simulation_tests`, `bench` and `nightly_tests` features; `docker/`, `nix/`, `scripts/`, `.github/` and `docs/`.

## How to exercise it

The toolchain is pinned in `rust-toolchain.toml` (1.94.0, with the `wasm32-unknown-unknown` target). Integration tests compile the test contracts and delegates under `tests/` to WASM at run time (`crates/core/src/test_utils.rs`), so the image needs that target and their dependencies cached offline.

- **Unit and integration tests**, as CI runs them (`.github/workflows/ci.yml`):
  `cargo nextest run --workspace --exclude freenet-ping-types --exclude freenet-ping-app --no-default-features --features trace,websocket,redb,wasmtime-backend,testing --profile ci -E 'not test(blocked_peers)'`
  The `ci` profile in `.config/nextest.toml` bounds slow tests. A few tests need the Internet (for example `tls_native_roots`, and anything that fetches the gateway list from freenet.org) and will fail offline.
- **Deterministic network simulation** (many peers in one process on a simulated clock, good for reproducing peer-message bugs):
  `cargo nextest run -p freenet --lib --test simulation_integration --test simulation_smoke --test streaming_e2e --test state_verification -E 'kind(test) | (kind(lib) & test(sim_e2e_tests))' --features simulation_tests,testing --profile ci`
- **Multi-node tests on real local sockets** use the `#[freenet_test]` macro (see `crates/core/tests/test_macro_example.rs`). `crates/core/tests/operations.rs` drives PUT, GET, UPDATE and SUBSCRIBE end to end.
- **WASM runtime tests**: the test module in `wasm_runtime/engine/wasmtime_engine.rs` runs hand-written WAT modules against the real engine, linker and limits, and `wasm_runtime/tests/` runs the compiled test contracts. Either is a good template for a sandbox or limit-bypass reproducer.
- **A running node**: `target/debug/freenet local` starts a node with no peers and the client API on loopback port 7509. `fdev publish` puts a contract into it. A web app contract is served at `http://127.0.0.1:7509/v1/contract/web/<key>/`, and the WebSocket API is at `/v1/contract/command`. `cargo run -p fdev -- test --gateways 1 --nodes 3 single-process` runs a small network in one process.

There are no fuzz targets in the repository. A finding against a parser is easiest to demonstrate as a unit test next to the parser that feeds it the bytes.

## How you rate severity

Say which position the attacker holds: a remote peer, the author of a contract or web app, a website the user visits, or a hosted-mode user. Findings against the default configuration weigh more than those that need a non-default flag.

- **Critical**
  - Code execution or memory corruption in the node, from any of the inputs above.
  - WASM sandbox escape: guest code reading or writing memory outside its own instance, or calling host functionality it was not linked.
  - Reading or using another delegate's secrets, or another hosted-mode user's secrets.
  - A web app obtaining another app's attested origin, or contract content executing at the node's own origin.
  - A host other than the local machine, or a website the user visits, driving the client API under the default configuration.
  - Writing files outside the node's data directories.
- **High**
  - A remote peer crashing, panicking (in a way that ends the node or its event loop), deadlocking or hanging a node with one or a few messages.
  - Cheap input that grows a node's memory, disk or CPU use without bound.
  - Contract code exceeding its CPU, memory or stack bounds, or crashing the host.
  - A node accepting, storing or forwarding state that fails `validate_state`, or code under a key it does not hash to.
  - A web app or delegate answering a permission prompt or obtaining a capability grant without the user.
  - Making a node send substantially more traffic to a third-party address than the attacker sent.
- **Medium**
  - Resource exhaustion that needs sustained traffic, or that stays bounded to one connection or operation.
  - A panic confined to one connection, operation or task.
  - Secrets or tokens written to logs at info level or above.
- **Low**
  - Issues that need a non-default flag meant for trusted setups, a malicious local config file or environment variable, or invalid CLI arguments.
  - Issues confined to developer tooling such as `fdev`.

A bug with no security consequence (a wrong metric, a stale doc, a flaky test) is not a vulnerability.

## Anything to leave alone

- Traffic analysis and forward secrecy are outside the transport's design goals (`docs/architecture/transport/security.md`).
- Contract state and code are public. Peers learn which contract keys a node routes or hosts.
- A contract that accepts bad data because its own `validate_state` or `update_state` is wrong has a bug in that contract, not in the node.
- The client API is fully privileged for whoever can reach it, by design (`docs/client-api-exposure.md`). A report that a non-default flag which exposes the API does in fact expose it is not a finding. Getting past the default loopback bind, the `Origin` and `Host` checks, or the per-app origin attestation is.
- Attacks that need the attacker to run a large share of the network's peers.
- Auto-update and gateway-list fetches need the Internet and cannot be exercised in this image.
