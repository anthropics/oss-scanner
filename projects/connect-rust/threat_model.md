# Threat model: connect-rust

## What this project does and where untrusted input enters

connect-rust is the Rust implementation of ConnectRPC. The `connectrpc` crate is a Tower-based runtime that serves and calls RPCs over the Connect, gRPC and gRPC-Web protocols, on HTTP/1.1 and HTTP/2 (hyper), with binary or JSON protobuf messages (buffa), gzip and zstd compression, and TLS through rustls. The workspace also holds a code generator (`connectrpc-codegen`, with the `protoc-gen-connect-rust` plugin, and `connectrpc-build`) and two ready-made services, `connectrpc-health` and `connectrpc-reflection`.

A server built on this crate faces the network, and most of what it parses arrives before the application has authenticated the caller. Treat all of the following as attacker-controlled:

- **The request head**: method, path, `content-type`, the protocol version headers, the timeout headers (`connect-timeout-ms`, `grpc-timeout`), the compression headers, and metadata headers, including the base64 `-bin` forms.
- **Connect unary GET requests**, where the message, its encoding and its compression arrive in the query string.
- **Request bodies**: unary bodies, and the enveloped frames of streaming calls and of gRPC and gRPC-Web (a flag byte, a 4-byte length, a payload), including the end-of-stream frame and trailers.
- **Compressed payloads**, which the server inflates before decoding.
- **The timing and ordering of the peer's actions**: a client that sends nothing, sends part of a head or a frame and stalls, resets streams, opens many streams, or stops reading its response.
- **TLS connections**, including the client certificates that mutual TLS exposes to handlers as `PeerCerts`.
- **Requests to the health and reflection services**, which deployments often leave unauthenticated.

A client built on this crate treats the server as untrusted in the same way: response headers and trailers, error bodies and error details, enveloped frames, compressed payloads, and streams that never end.

The server's defences are documented under "Production hardening", "Interceptors" and "Hosting" in `docs/guide.md`. `Limits` bounds the request body as read (4 MB), each message after decompression (4 MB), and the element memory of a decode (32 MiB), and it is enforced while reading and inflating. `DeadlinePolicy` clamps the timeouts that clients ask for. The connection driver applies a header-read timeout and bounds how long it drains an abandoned request body. `Interceptor::intercept_head` and Tower layers run before any body byte is read, and a rejection there must end the request.

## Components that matter most / least

Most important, in this order:

1. `connectrpc/src`: request routing and protocol detection, envelope framing, compression, timeout parsing, error and trailer encoding, the interceptor chain, the server connection driver (`server.rs`, `axum.rs`), and the client transports.
2. `connectrpc-reflection` and `connectrpc-health`, because they answer unauthenticated peers.
3. The code that `connectrpc-codegen` emits: the checked-in instances are under `*/src/generated`.
4. `connectrpc-codegen` and `connectrpc-build`, when the input is a hostile schema.

The crate denies `unsafe` code, so memory-safety findings are most likely to sit in a dependency. Report one when connect-rust's use of the dependency makes it reachable from the network, and show the path. hyper, h2, rustls and tokio have their own security processes, and buffa is enrolled with this scanner separately; a flaw that lies wholly inside one of them belongs there.

Out of scope: `examples/`, `benches/`, `tests/`, `docs/`, `signatures/`, and CI configuration. The conformance server and client under `conformance/` are test fixtures that misbehave on request, so their own behaviour is out of scope; they remain the most convenient way to drive the library. What an application does inside its handlers, and how it chooses to authenticate, is the application's concern.

## How to exercise it

The image has no network and needs none beyond loopback: every dependency is in the cargo cache, `CARGO_NET_OFFLINE` is set, and the builds below are already done in `/src`.

- **Tests**: `cargo test --workspace --all-features`. `tests/streaming` holds the end-to-end streaming tests.
- **A server to attack**: `./target/debug/eliza-server`, `multiservice-server`, `middleware-server` (bearer-token authentication in a Tower layer) and `streaming-tour-server` are built; `examples/mtls-identity` shows mutual TLS. Each example's `README.md` and `src/` give its address and routes. `curl` is installed and speaks the Connect protocol directly: `curl -H 'content-type: application/json' -d '{}' http://127.0.0.1:8080/<package>.<Service>/<Method>`.
- **Conformance**: `./conformance/bin/connectconformance --mode server --conf conformance/config/connect-only.yaml -- ./target/release/conformance-server` runs the upstream ConnectRPC suite against the server. The other files in `conformance/config/` select gRPC, gRPC-Web, TLS and the client suites (`--mode client` with `./target/release/conformance-client`). Use the suite to check that a proposed patch does not change protocol behaviour.
- **Feature combinations**: CI also builds `-p connectrpc --no-default-features`, alone and with `--features server` and `--features axum,server`, and checks the client for `wasm32-unknown-unknown`, which is installed.
- **Code generation**: `protoc` 33.5 is installed, and `connectrpc-build` drives it from a `build.rs`, as `tests/streaming/build.rs` does.

## How you rate severity

A finding counts when a server or client that uses the documented API can be made to misbehave by its network peer. State the configuration the reproducer needs; a finding against the defaults weighs more than one that needs a limit raised.

- **Critical**: memory corruption reachable from the network. A request that reaches a handler without passing an interceptor's head check or a Tower layer that should have rejected it. A response, a request extension or a peer identity (`PeerAddr`, `PeerCerts`) that is delivered to, or attributed to, the wrong request or connection.
- **High**: denial of service that an unauthenticated peer achieves cheaply and that the documented defences should have stopped. Examples are memory growth beyond what `Limits` allows (including through compression), a task, stream or connection held past the configured timeouts, and a panic or abort that takes down the process or the accept loop rather than one request.
- **Medium**: a panic confined to one request. A parsing differential that makes an interceptor or layer see a different procedure, header, deadline or message from the one the handler acts on. A client that a hostile server can exhaust or hang despite its configured limits and timeouts. Detail about the server's internals returned to an unauthenticated peer.
- **Low**: a panic, hang or excessive memory use in the code generator on a malformed schema. A defect that needs a non-default option meant for trusted peers.

A deviation from the Connect, gRPC or gRPC-Web specification with no security consequence is a bug and not a vulnerability; do not report it.

## How to report

- Give a reproducer that runs in this image against one of the built servers or as a Rust test: the exact bytes or `curl` command sent, the server command line, and what was observed. For resource exhaustion, give the measured memory or time against the configured limit.
- Name the protocol (Connect, gRPC, gRPC-Web), the HTTP version, the cargo features, and any `Limits`, `DeadlinePolicy` or `ConnectionConfig` setting that differs from the default.
- Propose a minimal patch against `main` with a regression test. Keep unrelated refactoring out of it.
- Report one root cause once. The same flaw reachable through all three protocols is one finding that lists each path.

## Anything to leave alone

- With no `DeadlinePolicy`, the server trusts the client's timeout header, and a request with no timeout runs unbounded. The guide documents this and tells operators to set a policy.
- Reading up to `max_request_body_size` and inflating up to `max_message_size` per in-flight request before `intercept_unary` or `intercept_streaming` can reject is the documented cost of checking credentials there instead of in `intercept_head`.
- A bidirectional call whose handler stops reading while the client keeps sending small frames can draw a connection-wide `GOAWAY` from h2. The 0.9.1 changelog records this as a known residual.
- Do not report resource use that stays within the documented defaults multiplied by the HTTP/2 concurrent-stream limit, or the absence of authentication, rate limiting or TLS in the examples.
