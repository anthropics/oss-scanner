# Threat model — Arize Phoenix

## What this project does and where untrusted input enters
Phoenix is an open-source AI observability and evaluation platform. It is a Python web server (Starlette/FastAPI +
Strawberry GraphQL, SQLite or PostgreSQL via SQLAlchemy) with a React UI, usually self-hosted and often exposed to a
team or the Internet. Untrusted input enters through:
- **HTTP APIs**: the GraphQL API (`/graphql`, including subscriptions), the REST API (`/v1/...`), and the auth endpoints
  (login, logout, password reset, OAuth2/OIDC callbacks, LDAP login, API-key and JWT bearer auth).
- **Trace ingestion**: OTLP over HTTP (`/v1/traces`) and gRPC (`grpc_server.py`). Span attributes, events and
  payloads are attacker-controlled and are later rendered in the UI, so treat them as untrusted end to end.
- **User content**: datasets (CSV/JSONL/Parquet uploads), prompts and templates, annotations, experiments, evaluator
  definitions, project/user names.
- **Playground / agents / evaluators**: requests that make Phoenix call LLM providers using credentials stored on the
  server, and code evaluators executed in a sandbox (`server/sandbox/`: WASM, Deno, Docker and remote providers).
- **MCP server** (`server/mcp*`) and the OAuth2 authorization server used by MCP clients.

## Trust boundaries and roles
- With auth enabled (`PHOENIX_ENABLE_AUTH=true`), users are `ADMIN`, `MEMBER` or `VIEWER`. Viewers must not be able to
  write; members must not be able to perform admin actions (user management, system API keys, secrets, settings).
  Anything that lets a lower role cross into a higher one, or reach another user's resources it should not, is in scope.
- Without auth, Phoenix is intended for local/trusted use; findings that only require the server to be reachable with
  auth disabled are low unless they also lead to code execution on the host or reach beyond Phoenix.
- Stored secrets (LLM provider keys, encrypted with `PHOENIX_SECRET`) must never be returned to clients.
- Sandboxed code (evaluators) must not escape to the Phoenix host process, filesystem, environment or network.

## Components that matter most / least
- Most: authentication and session/JWT/API-key handling, OAuth2/LDAP, authorization checks in GraphQL resolvers and REST
  routers, SQL construction (span filters/query DSL in `trace_filters.py`, `session_filters.py`, `trace/dsl/`), the
  sandbox, server-side requests to user-supplied URLs (SSRF via provider base URLs, webhooks), stored XSS from span
  data/prompts/markdown rendering in `js/app`, file-upload parsing, and secret handling.
- Less: the Python client/evals/otel packages under `packages/` (libraries run by the user against their own data),
  `js/packages/*` client libraries, docs, examples, tutorials and notebooks.
- Out of scope: `src/phoenix/vendor/`, `packages/phoenix-sqlean` (vendored C extension), `helm/`, `kustomize/`.

## How to exercise it
- `phoenix serve` (or `python -m phoenix.server.main serve`) starts the server on port 6006; set
  `PHOENIX_ENABLE_AUTH=true PHOENIX_SECRET=<32+ chars>` to test with auth (default admin: `admin@localhost` / `admin`).
  `PHOENIX_SQL_DATABASE_URL=sqlite:///:memory:` gives a throwaway database.
- Unit tests: `cd tests && pytest unit/`. Integration tests in `tests/integration/` start real servers and exercise auth
  end to end; they are the best model for writing reproducers.

## How we rate severity
- Critical: unauthenticated RCE, sandbox escape to the host, auth bypass to admin, unauthenticated access to stored
  provider secrets or to all trace data.
- High: authenticated (member/viewer) privilege escalation, SQL injection, SSRF reaching internal networks or cloud
  metadata, stored XSS reachable from ingested spans or shared content that can act as another user, cross-user data
  access.
- Medium: reflected XSS, CSRF on state-changing endpoints, information disclosure of non-secret metadata, DoS that one
  unauthenticated request can trigger.
- Low: issues requiring admin privileges, auth-disabled deployments, or a local attacker; DoS needing sustained load.

## Anything to leave alone
- Admins are trusted: anything an admin can already do by design (configure providers, run code evaluators, manage users)
  is not a vulnerability.
- Missing rate limiting, verbose errors in development mode, and dependency CVEs without a reachable path in Phoenix.
