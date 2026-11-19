# Threat model: Starlette

## What this project does and where untrusted input enters
Starlette is an ASGI framework and toolkit. Applications use it directly, and through frameworks built on it
(FastAPI and others), to route requests, parse bodies, serve files, manage sessions and handle WebSockets.

Assume every part of the ASGI scope and every message from `receive` is attacker-controlled: path, query
string, headers, cookies, body (JSON, form-encoded, multipart and file uploads) and WebSocket frames. The
ASGI server, the developer's code and their configuration are trusted.

## Components that matter most
1. **Request parsing**: `starlette/requests.py`, `starlette/formparsers.py`, `starlette/datastructures.py`.
   Of interest: limits (`max_files`, `max_fields`, `max_part_size`) that can be bypassed, temporary files
   that leak or are not cleaned up, header/cookie parsing confusion.
2. **Static files and routing**: `starlette/staticfiles.py`, `starlette/routing.py`, `starlette/convertors.py`.
   Of interest: path traversal or reading files outside the configured directories, symlink handling,
   `Mount`/`Host` matching that routes a request somewhere the developer did not intend.
3. **Security middleware**: `starlette/middleware/` - `sessions.py` (signed cookies), `cors.py`,
   `trustedhost.py`, `httpsredirect.py`, `body_limit.py`, `authentication.py`. Of interest: CORS or host
   checks that can be bypassed, session forgery or fixation, body limits that can be evaded.
4. **Responses**: `starlette/responses.py` (`FileResponse` range requests, redirects, header injection).

Also in scope, but less important: `starlette/websockets.py`, `starlette/middleware/gzip.py`,
`starlette/middleware/errors.py` (the debug traceback page) and `starlette/templating.py`.

## How to exercise it
- `tests/` is a pytest suite. Run `pytest tests` from `/src`.
- `starlette.testclient.TestClient` runs requests against an app in-process; most tests show the pattern.
  Write PoCs as small pytest files that build an app with documented APIs and send a request.

## How we rate severity
- **Critical**: unauthenticated code execution, or arbitrary file read, under default settings.
- **High**: path traversal, auth/session/CORS/host-check bypass, or a single small request that exhausts
  CPU or memory (or blocks the event loop) under default settings.
- **Medium**: the same issues when they need an unusual but documented configuration; information disclosure.
- **Low**: anything reachable only with `debug=True`, and DoS that needs volume rather than a crafted input.

## Anything to leave alone
- Vulnerabilities in dependencies (`python-multipart`, `itsdangerous`, `jinja2`, the ASGI server) themselves,
  unless Starlette calls them in an unsafe way.
- Developer misuse: disabling limits, `allow_origins=["*"]` with credentials, passing user input to
  `FileResponse` or templates without validation, a weak `secret_key`.
- `starlette/testclient.py`, `docs/`, `benchmarks/` and deprecated modules (`starlette/middleware/wsgi.py`).
