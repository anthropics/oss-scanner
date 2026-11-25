<!--
The trust model below is condensed from the MCP security policy, which applies to every official SDK:
https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/SECURITY.md
The rules that matter for a scan are copied here. Follow this file.
-->
# Threat model: MCP Rust SDK (rmcp)

## What this project does and where untrusted input enters

`rmcp`: client and server library for the Model Context Protocol (JSON-RPC 2.0 over stdio and Streamable HTTP; the client also over Unix sockets), with an OAuth client. It has no OAuth server: an application checks bearer tokens itself. Untrusted input enters through HTTP requests to a server (body, headers, session ids, `Last-Event-ID`, `requestState`), through HTTP responses and event streams that a client reads, and through OAuth metadata, redirects and token responses. The crate has very little `unsafe` code, so logic errors, panics on peer input and unbounded growth are more likely than memory corruption.

## Components that matter most / least

- Most, in `crates/rmcp/src`: `transport/auth.rs` and `transport/auth/` (OAuth discovery, registration, tokens, the address filter for metadata requests), `transport/streamable_http_server/` (`tower.rs`, `session/`), `transport/streamable_http_client.rs`, `transport/common/` (`reqwest/`, `auth/`, `client_side_sse.rs`, `mcp_headers.rs`, `http_header.rs`, `server_side_http.rs`, `unix_socket.rs`), `transport/async_rw.rs`, `transport/worker.rs`, `service.rs` and `service/` (with `client/cache.rs`), `model.rs` and `model/` (`request_state.rs`, `serde_impl.rs`, `skill.rs`, `elicitation_schema.rs`), `handler/` (with `server/skill_catalog.rs`), `task_manager.rs`.
- Least: `crates/rmcp-macros` (runs at build time on the developer's own code), `transport/child_process.rs` and `transport/io.rs` (stdio).
- Out of scope: `examples/`, `conformance/`, `docs/`, `scripts/`, tests. A flaw in an example counts only if it shows a flaw in the crate.

## Trust model

- Clients trust the servers that a user or administrator configured them to use. A malicious server that only does what a server may do (return hostile tool descriptions, results or prompts) is not a vulnerability in the SDK.
- A local (stdio) server is trusted like any other installed program. The client starts it with the configured command, with the client's privileges. The stdio channel is not a sandbox.
- A server trusts the environment it runs in, and the application code that uses the SDK is trusted.
- Remote peers over HTTP are NOT trusted before authentication, and an authenticated peer is trusted only for its own identity, session and scopes. Anything on a network path, any web page in a user's browser, and any other client of the same server are untrusted.

## In scope

A flaw in this repository's code that a remote peer, a web page or another tenant can reach through the documented API, where the application uses the SDK as documented and has no documented way to prevent it. In particular:

- Authentication or authorization bypass in the OAuth client: scopes, audience/resource and issuer checks, metadata and discovery, client registration, redirect handling, PKCE and state, client authentication, enterprise-managed token exchange.
- Token or credential theft or leakage: sending a token to the wrong server or origin, mixing up authorization servers, credentials in logs or error messages that reach a peer.
- Session hijacking, and cross-session or cross-client leaks: one client receiving another's responses, notifications, event-store replay, cached results or request state (a `requestState` sealed with `RequestStateCodec` that can be forged, or opened with the wrong associated data or after its TTL, too).
- Host and Origin validation bypass where that protection is enabled or on by default (DNS rebinding).
- Injection into HTTP headers, server-sent events or JSON-RPC framing, and messages that the two ends parse differently with a security effect.
- Server-side request forgery in the client's OAuth discovery that gets past the address policy documented in `transport/auth/metadata_resolver.rs`: metadata may name public hosts, but loopback or private addresses only when the base URL itself is one, and link-local and other reserved addresses never.
- Remote denial of service before authentication, or by one client against others: a panic or abort that ends the process or the service for others, unbounded memory (session tables and caches included) or CPU out of proportion to the request, regular expressions with super-linear time on peer input, limits that can be bypassed.
- Path traversal in the skill catalog (`skills-fs`), memory unsafety in this crate, or code execution from peer-controlled data.

## Not a vulnerability: please do not report

- A panic that only ends the task of the peer that caused it, without effect on other peers.
- Command execution through the stdio transport's configured command, arguments or environment. Starting that process is its purpose.
- One stdio peer crashing, hanging or exhausting the other. If the same code is reachable over a remote transport, report it for that transport.
- A tool, resource or prompt that does what the application's author wrote, an LLM that calls an unexpected tool, prompt injection, and tool descriptions that mislead a model.
- A problem that needs the application to do something the documentation says not to, for example to pass unvalidated peer data to a sink the application chose, or to turn a protection off.
- Volumetric denial of service: enough traffic to overload any server.
- A protection that the documentation describes as opt-in being off when the application did not enable it. `Origin` validation is opt-in here (`allowed_origins` is empty by default); `Host` validation is on by default and accepts loopback names only. Requests without an `Origin` header are meant to pass.
- A protection being off because the application passed its own implementation, as documented: a custom `reqwest::Client` (its redirects and DNS), a custom `OAuthHttpClient`, or `new_allowing_private_addresses`.
- The server accepting a body of up to `max_request_body_bytes` (4 MiB by default), or a client or stdio peer accepting a message of up to its documented limit (16 MiB by default). Getting past a limit is in scope.
- A sealed `requestState` being readable by the client, or usable more than once within its TTL: it is signed, not encrypted, and single use is left to the application.
- Correctness or spec-conformance bugs that cross no security boundary.
- Vulnerabilities in dependencies that cannot be reached through this repository's code.

## How we rate severity

- Critical: remote code execution, or a full authentication bypass, reachable by an unauthenticated remote peer in a default or documented configuration.
- High: theft of tokens or sessions, cross-tenant access, authorization bypass with real impact, bypass of Host or Origin validation that lets a web page drive a local server.
- Medium: an unauthenticated remote peer can crash the process or exhaust it with a small number of requests; a leak of limited information between clients; a high-impact issue that needs an uncommon but documented configuration.
- Low: hardening gaps with no direct impact. Please report these only with a concrete attack, and prefer one report per root cause.

Many MCP SDKs share the same design. If the cause is the MCP specification rather than this code, please say so.

## How to exercise it

- The tests are built, and both commands work offline: `cargo test --all-features`, and `cargo test -p rmcp --features "$(cat /opt/rmcp-features)"` (every feature but `local`, as CI does; many tests of the HTTP transports run only here). `Cargo.lock` is not committed; the one in `/src` was made when the image was built.
- `examples/servers`, `examples/clients` and `conformance` are built and make good drivers; `crates/rmcp/tests` has in-memory and HTTP harnesses, and peers in JavaScript and Python.
