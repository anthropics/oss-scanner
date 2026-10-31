# Actix Web threat model

## Project and scope

Actix Web is an asynchronous HTTP server framework for Rust. This enrollment covers
the following crates in the `actix/actix-web` workspace on `main`:

- `actix-web`: request extraction, routing, middleware, responses, and server setup.
- `actix-http`: HTTP/1, HTTP/2, WebSocket framing, payloads, and content encoding.
- `awc`: HTTP and WebSocket clients.
- `actix-files`: static file responses and directory listings.
- `actix-multipart` and `actix-multipart-derive`: streaming and typed multipart forms.
- `actix-router` and `actix-web-codegen`: route matching and routing macros.

`actix-test` and `actix-http-test` are outside the scan scope. They remain available
as test infrastructure.

The build enables all workspace features. This includes OpenSSL and the supported
Rustls versions, compression codecs, cookies, HTTP/2, and WebSockets.

Related repositories, such as `actix-net` and `actix-extras`, require their own
enrollment. If a finding involves dependency code, identify the repository that
owns the faulty code.

## Trust boundaries

Treat remote peers as untrusted. On the server side, an attacker can open and close
connections and send arbitrary request bytes, headers, paths, query strings,
cookies, body chunks, multipart fields, compressed streams, and WebSocket frames.
Include truncated input and input split across any transport boundary.

On the client side, a malicious server can control response bytes, headers, body
framing, compressed data, redirects, and WebSocket traffic. Applications can also
pass untrusted URLs to `awc`; distinguish library guarantees from application URL
validation and network access policy.

Application handlers, middleware, route definitions, and server configuration are
trusted Rust code. Local files and TLS keys are normally controlled by the
operator. Explain any additional attacker access a reproduction requires.

## Security goals and priority areas

- Preserve memory safety, including in unsafe code, buffer reuse, and asynchronous
  state transitions.
- Parse HTTP message boundaries consistently. Check conflicting length headers,
  transfer encodings, pipelined requests, connection reuse, protocol upgrades, and
  response splitting for request smuggling or cross-request data exposure.
- Enforce documented body, extraction, multipart, and parser limits. Check decoded
  output as well as compressed input, partial reads, cancellation, and error paths.
- Handle malformed input without attacker-triggered process termination, endless
  loops, or persistent loss of service. State whether a panic stops one request,
  one worker, or the whole service.
- Preserve route matching and path decoding rules across percent encoding,
  Unicode, separators, and normalization. Show a concrete routing or access-control
  consequence for a mismatch.
- Preserve documented static file path checks and response header handling. Check
  traversal, encoded paths, range requests, directory output, and file names.
  Account for configured roots, symlink behavior, and application permissions.
- Parse multipart boundaries and field metadata safely across arbitrary chunks.
  Check form limits, temporary file handling, and malformed or incomplete uploads.
- Preserve client connection isolation, TLS verification, and response framing.
  Check whether malformed responses, redirects, or connection reuse can expose data
  or cross an intended security boundary.
- Preserve documented cookie signing and encryption behavior when enabled. Show
  whether a failure is in the library or in an application's key handling.

## Assessing findings

Prioritize exploitable memory safety flaws, cross-request data exposure, request
smuggling, unauthorized file access, and remotely triggered denial of service.
Support severity with the actual impact and required deployment conditions.

For resource exhaustion, identify the affected limit or state machine and measure
attacker input, CPU use, memory use, or retained connections. Distinguish a bypass
of an enabled protection from an application that deliberately collects an
unbounded stream or omits its own timeout.

The framework does not supply application authentication, authorization, CSRF
policy, or an outbound URL allowlist. A report about application policy must show
how library behavior violates a documented guarantee or bypasses the policy.

## Reproductions and reports

Provide the affected crate, source location, feature flags, attacker prerequisites,
and a minimal reproduction. Prefer a regression test that uses a public API or raw
protocol bytes over a loopback connection. Do not depend on external services.

For parser bugs, include the exact bytes and chunk boundaries. For limits, give the
configured value and observed result. For a panic or hang, include the scope of the
failure and a bounded test. Keep proposed fixes small and preserve public APIs.

To repeat all workspace tests, run `cargo test --locked --workspace --all-features`
from `/src`. The image contains the dependencies needed without Internet access.

Send findings privately to the configured primary contact. Do not open public
issues or pull requests that disclose a vulnerability.
