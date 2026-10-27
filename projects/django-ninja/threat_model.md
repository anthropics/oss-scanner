# Threat model: Django Ninja

## What this project does and where untrusted input enters
Django Ninja is a library for building HTTP APIs on top of Django, using Python type hints and pydantic
schemas. A developer declares operations (`@api.get(...)`, `Router`) with typed parameters; Django Ninja
parses and validates the incoming request, runs authentication, calls the view, and serializes the response.
It also generates an OpenAPI schema and serves interactive docs.

Assume every part of the HTTP request is attacker-controlled: path, query string, headers, cookies, body
(JSON, form-encoded, multipart and file uploads). The developer's own code and settings are trusted.

## Components that matter most
1. **Request parsing and validation**: `ninja/params/`, `ninja/parser.py`, `ninja/signature/`,
   `ninja/schema.py`, `ninja/files.py`, and the Query/Path/Header/Cookie/Body/Form/File handling. Of
   interest: input that passes validation it should fail, type confusion between parameter sources, mass
   assignment or extra fields slipping through, and parser crashes reachable from a request.
2. **Authentication and security**: `ninja/security/` (APIKeyQuery/Header/Cookie, HttpBearer, HttpBasic,
   SessionAuth, Django auth), `ninja/main.py`, `ninja/router.py`, `ninja/operation.py`. Of interest: auth
   bypasses, such as auth not inherited or wrongly overridden across routers and sub-routers, async/sync auth
   mismatches, a falsy auth result treated as success, and CSRF protection skipped when it should apply.
3. **Throttling and pagination**: `ninja/throttling.py`, `ninja/pagination.py`, `ninja/filter_schema.py`
   (FilterSchema). Of interest: throttle bypass (key spoofing, header confusion), unbounded page sizes, and
   filter or ordering input that reaches ORM lookups the developer did not declare.

Also in scope, but less important: `ninja/openapi/` and the docs views (Swagger/Redoc), error handlers
(`ninja/errors.py`) and response rendering.

## How to exercise it
- `tests/` is a pytest suite. Run it with `uv run pytest tests` (or plain `pytest tests`) from `/src`.
- `ninja.testing.TestClient` / `TestAsyncClient` (`ninja/testing/`) run requests against a `NinjaAPI` or `Router` without a
  server; most tests in `tests/` show the pattern. Use it to write PoCs as small pytest files.
- The tests use SQLite via `tests/demo_project`; no database server is needed.

## How we rate severity
We rate conservatively:
- **Critical**: only with a working proof of concept against an API that uses default settings and
  documented patterns, giving unauthenticated access to a protected operation or code execution.
- **High**: an auth bypass or CSRF bypass that needs an unusual but documented configuration; injection
  that reaches the ORM or a template through Django Ninja's own code.
- **Medium**: validation bypass with a clear security impact, or information disclosure (e.g. exception
  details or internal fields in responses) under default settings.
- **Low**: all denial of service (throttle bypass, expensive pagination, oversized or deeply nested input),
  and anything reachable only with DEBUG=True.

## Anything to leave alone
- Vulnerabilities in Django, pydantic or other dependencies themselves. Report them only if Django Ninja
  calls them in an unsafe way.
- Issues that need the developer to misconfigure or misuse the framework, such as disabling CSRF,
  declaring an operation without auth, putting secret fields in their own response schema, or passing raw
  user input to `.extra()`/`.raw()` in their own view.
- `docs/` (the documentation site and its example snippets).
