# Threat model: HTTPX2

## What this project does and where untrusted input enters
HTTPX2 is an HTTP client for Python with sync and async APIs, HTTP/1.1, HTTP/2, proxies, WebSockets and
Server-Sent Events. This repository holds two packages: `httpx2` (`src/httpx2/`, the high-level client) and
`httpcore2` (`src/httpcore2/`, the connection pool and HTTP transport underneath it).

Assume every byte from a server or proxy is attacker-controlled: status line, headers, cookies, body,
compressed content, redirects, HTTP/2 frames and WebSocket frames. URLs are often attacker-influenced too,
since applications fetch user-supplied URLs. The calling code and its configuration are trusted.

## Components that matter most
1. **Response handling in httpcore2**: `src/httpcore2/httpcore2/_async/` and `_sync/` - `http11.py`,
   `http2.py`, `connection_pool.py`, `http_proxy.py`, `socks_proxy.py`. Of interest: response splitting or
   desync that lets one response poison another on a reused connection, unbounded buffering, proxy
   tunnelling errors, TLS verification that is skipped.
2. **URL parsing**: `src/httpx2/httpx2/_urlparse.py`, `_urls.py`. Of interest: parser differentials that
   send a request to a host other than the one the application validated (SSRF), and CRLF injection into
   the request line or headers.
3. **Redirects, auth and cookies**: `_client.py`, `_auth.py`, `_cookies.py`, `_config.py`. Of interest:
   `Authorization`, `Proxy-Authorization` or cookies sent to a different origin after a redirect, scheme
   downgrades, cookie scoping errors, `.netrc` credentials leaking to the wrong host.
4. **Decoders**: `_decoders.py` (gzip, deflate, brotli, zstd). Of interest: decompression bombs that
   bypass streaming, and decoders that buffer the whole body.

Also in scope, but less important: `_multipart.py` (header injection through field or file names),
`_sse.py`, `websockets/`, `_transports/asgi.py`, `_transports/wsgi.py`, and the `httpx2` CLI (`_main.py`).

## How to exercise it
- `tests/` is a pytest suite with tests for both packages. Run `pytest tests` from `/src`; tests marked
  `network` need the Internet and will fail offline.
- The tests start local servers (Uvicorn, `pytest-httpbin`) and use `httpx2.MockTransport`. A malicious
  server is easiest to model with a raw socket server on localhost, or with httpcore2's mock backends.

## How we rate severity
- **Critical**: code execution, or TLS verification bypassed under default settings.
- **High**: credential or cookie leaks to another origin, SSRF through URL parser differentials, response
  desync on pooled connections, or a single response that exhausts memory while the caller streams it.
- **Medium**: the same issues when they need a non-default but documented option; header injection that
  needs attacker-controlled input passed to an API documented as trusted.
- **Low**: crashes with a clean Python exception, and DoS from a server sending a large body to a caller
  that reads it fully (`response.read()` is unbounded by design).

## Anything to leave alone
- Vulnerabilities in `h11`, `h2`, `certifi`, `brotli`, `zstandard`, `socksio` or `websockets` themselves,
  unless HTTPX2 uses them in an unsafe way.
- Callers that disable verification (`verify=False`), opt into `trust_env` with a hostile environment, or
  pass untrusted values to APIs that take raw headers.
- `docs/`, `benchmark/` and `redirects/`.
