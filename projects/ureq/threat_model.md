# ureq threat model

ureq is a synchronous HTTP/1.1 client library for Rust. Applications use it to
fetch data from remote services, so a remote server's responses must be treated
as untrusted. It supports TLS, redirects, connection pooling, HTTP and SOCKS
proxies, cookies, decompression, character decoding, JSON, and multipart bodies.

## Trust boundaries and scope

The target is https://github.com/algesten/ureq on its main branch. Prioritize:

- Malicious HTTP responses: status lines, headers, framing, chunked bodies,
  truncated or oversized responses, and compressed or incorrectly encoded data.
- Redirect handling, including origin changes, HTTPS downgrades, credentials,
  authorization headers, cookies, and proxy authentication.
- TLS configuration and verification in both rustls and native-tls connectors,
  including certificate and hostname verification and proxy tunnels.
- Connection reuse and pooling: response boundaries, stale connections, and
  isolation of credentials and destinations between requests.
- Resource limits and timeouts, including slow or interrupted reads and writes,
  handshake timeouts, decompression, and bounded body consumption.
- URL, request, header, proxy, and multipart handling where attacker-influenced
  input can cross a protocol or origin boundary.

The caller controls client configuration, request destinations and bodies, TLS
trust settings, and any custom transport or resolver. Disabling certificate
verification is an explicit caller choice. ureq is a general-purpose HTTP client
and does not promise to prevent SSRF when an application accepts arbitrary URLs;
an SSRF report should demonstrate a bypass of a protection ureq actually offers.

Body streaming and explicitly unbounded reads can consume resources proportional
to the input. For resource-exhaustion findings, distinguish those choices from
bypasses of configured limits or disproportionate work caused by small inputs.

Dependencies such as ureq-proto, rustls, native-tls, and decompression libraries
are separate projects. Focus reports on defects in ureq or its use of those
dependencies, and identify the responsible component precisely.

## Build and tests

The source checkout and built artifacts are in /src. The image fetches the
Cargo.lock dependencies before setting CARGO_NET_OFFLINE=true. These commands
work without Internet access:

```sh
cd /src
cargo test --locked --all-features
cargo test --locked --no-default-features --features native-tls --test native_tls
cargo test --locked --no-default-features --features native-tls-no-default --test native_tls
cargo test --locked --no-default-features --test tcp_eintr
```

The internal `_test` feature is enabled by `--all-features`. It substitutes a
mock transport in src/unversioned/transport/test.rs, including responses for
URLs that appear to address public services. This is useful for the offline
unit and documentation tests, but it bypasses real TCP and TLS behavior. The
integration tests above omit `_test` and use local peers.

For new TCP, TLS, proxy, or timeout reproducers, omit `_test`, use a loopback
server, and run a specific integration-test target. The image also builds real
transports and examples with this production feature set:

```sh
cargo build --locked --all-targets \
  --features native-tls,platform-verifier,socks-proxy,cookies,brotli,charset,json,multipart
```

The existing src/io_timeout_tests.rs and tests/ contain examples of deterministic
transport and loopback tests. Running the entire suite without `_test` attempts
to contact public services, which are unavailable during an offline scan.

## Reports and severity

Include the affected revision and feature flags, attacker-controlled input,
required caller configuration, expected and observed behavior, and a minimal
deterministic reproducer. Prefer a regression test using a local server or
in-memory transport, with a small patch addressing the root cause. Group
variants of the same root cause together.

Assess severity from demonstrated impact and realistic caller configurations.
Remote code execution, TLS authentication bypass, or credential disclosure to
an unintended origin can be high or critical depending on prerequisites and
reach. Remotely triggered panics, hangs, or resource exhaustion should describe
their effect on the calling application and any configured limits they bypass.
