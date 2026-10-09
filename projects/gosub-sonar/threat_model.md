# Threat model

## What this project does and where untrusted input enters
gosub-sonar is a browser-agnostic HTTP/HTTPS fetching library: a priority scheduler with request coalescing, caching, and web-platform policies. It is the networking stack of the Gosub browser engine and can also be used on its own.

Treat as untrusted:
- Everything from a remote server: status lines, headers (including `Set-Cookie`, `Location`, `WWW-Authenticate`, `Strict-Transport-Security`, cache and CORS headers), compressed and streamed bodies, and TLS peers
- Request parameters that come from web content, through the embedding engine: URLs, methods, request headers, request bodies, and referrer/CORS mode

The embedding application is trusted. So are its `FetcherConfig`, credential store, DNS resolver, proxy settings and observer hooks.

## Components that matter most / least
Most important are the policies a browser relies on for security. All of them are applied on every redirect hop:
- `net::cors`: preflights and response tainting. An opaque or cross-origin response readable when it should not be is a security bug.
- `net::referrer`, `net::fetch_metadata` (`Origin`, `Sec-Fetch-*`) and `net::mixed_content`
- `net::hsts`, and `net::tls` (certificate errors and user overrides)
- `net::auth`: credentials, and `Authorization`/`Cookie` stripped on cross-origin redirects
- `net::cache` (RFC 9111): cache poisoning, `Vary` handling, and responses leaking between requests or contexts that should be isolated
- `net::fetcher`: coalescing and fan-out. Two requests with different credentials, origins or cookie contexts must never be merged.
- `net::dns`: the pluggable resolver hook used for SSRF policies. Bypasses of the embedder's resolver (for example, a redirect that skips it) matter.
- Body handling: decompression, `max_bytes`, and idle and total timeouts (decompression bombs, unbounded memory)
- `file://` handling: path traversal or reading files the caller did not ask for

Lower priority: `net::proxy`, the `socks` feature, events/observers, and timing.

Out of scope: `examples/`, `net::test_support` (the mock server, behind the `test-support` feature), and the `wasm32` backend (the browser's own `fetch()` enforces policy there). Bugs in reqwest, hyper or rustls are out of scope unless sonar uses them wrongly.

## How to exercise it
- `cargo test --all-features` runs unit tests and `tests/e2e.rs`. These use the in-process mock HTTP/HTTPS server in `src/net/test_support.rs`, which listens on 127.0.0.1 and works without Internet access.
- `examples/` has small drivers (`simple_fetch`, `fetcher`, `streaming`, `caching`, `auth`, `tls_override`, `fetcher_harness`) that are easy to point at a local server.

## How you rate severity
The crate forbids `unsafe` code, so memory-corruption bugs are not expected. Rate by policy impact:
- Critical: a bypass that lets a malicious server or page read cross-origin data or credentials in the default configuration (for example, a CORS bypass, a cache returning another context's authenticated response, or credentials sent to another origin after a redirect).
- High: a TLS validation bypass; HSTS or mixed-content bypass; a redirect or DNS path that skips the embedder's SSRF resolver; cache poisoning; reading local files from a remote response through `file://`.
- Medium: weaknesses in the referrer or `Sec-Fetch-*` policy; DoS from a remote server (decompression bomb, `max_bytes` or timeout bypass, unbounded memory, scheduler starvation); a panic triggered by a malicious response.
- Low: problems that need a malicious embedder configuration; minor information leaks in events or timings.

## Anything to leave alone
- Do not report `unwrap`/`expect` in tests, `test_support`, or examples.
- Do not report differences from browsers that are documented design choices in the module docs, unless they lead to one of the impacts above.
