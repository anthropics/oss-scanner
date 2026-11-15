# Threat model: Uvicorn

## What this project does and where untrusted input enters
Uvicorn is an ASGI web server. It accepts TCP or Unix socket connections, parses HTTP/1.1 (and HTTP/2 with
`zttp`) and WebSocket traffic, and turns it into ASGI messages for the application.

Assume every byte a client sends is attacker-controlled. The application, the command-line options, the
environment and the files Uvicorn is told to load (app import string, SSL certificates, `--env-file`,
`--log-config`) are trusted.

## Components that matter most
1. **HTTP protocols**: `uvicorn/protocols/http/` - `h11_impl.py`, `httptools_impl.py`, `zttp_impl.py`,
   `zttp_h2_impl.py`, `flow_control.py`. Of interest: request smuggling (Content-Length/Transfer-Encoding
   confusion, pipelining, keep-alive state), header injection in responses, scope fields built wrongly
   from the request line, and unbounded buffering.
2. **WebSocket protocols**: `uvicorn/protocols/websockets/` (`websockets`, `websockets-sansio`, `wsproto`).
   Of interest: `ws_max_size` bypass, handshake confusion, and state machine errors.
3. **Proxy headers**: `uvicorn/middleware/proxy_headers.py`. Of interest: a client outside
   `forwarded_allow_ips` that can spoof its address or scheme through `X-Forwarded-*` headers.
4. **Server lifecycle**: `uvicorn/server.py` and `uvicorn/config.py`. Of interest: limits
   (`limit_concurrency`, `timeout_keep_alive`, `h11_max_incomplete_event_size`) that can be evaded.

Also in scope, but less important: `uvicorn/middleware/wsgi.py`, `uvicorn/middleware/asgi2.py`,
`uvicorn/supervisors/` and `uvicorn/workers.py`.

## How to exercise it
- `tests/` is a pytest suite. Run `pytest tests` from `/src`; it uses `pytest-xdist` (`-n 8` is set in `pyproject.toml`).
- Start a real server on localhost with `uvicorn.Config` + `uvicorn.Server`, as the tests do, and send raw
  bytes over a socket. Check every HTTP implementation (`--http h11|httptools|zttp`), since they differ.

## How we rate severity
- **Critical**: remote code execution, or memory corruption, from network input.
- **High**: request smuggling or response splitting with a working PoC, proxy-header spoofing from an
  untrusted client, or a single connection that exhausts CPU or memory (or blocks the event loop) under
  default settings.
- **Medium**: the same issues when they need a non-default but documented option; information disclosure.
- **Low**: DoS that needs volume rather than a crafted input (slowloris-style attacks are expected to be
  handled by a reverse proxy).

## Anything to leave alone
- Vulnerabilities in `h11`, `httptools`, `zttp`, `websockets`, `wsproto` or `uvloop` themselves, unless
  Uvicorn uses them in an unsafe way.
- Developer or operator misconfiguration: `--forwarded-allow-ips='*'` on an exposed port, a malicious app or
  config file, `--reload` in production.
- `docs/`. The WSGI interface is deprecated and lower priority.
