# Kitaru threat model

## What Kitaru is and how it is deployed

Kitaru is an open-source runtime for recording, replaying and improving AI agents in production. Its parts:

- **Server**: a FastAPI application (`src/kitaru/server/`, app factory `kitaru.server.api.main:app`) backed by PostgreSQL. It stores recorded and imported agent "sessions", blobs, agents and agent versions, evaluations, users, API keys and encrypted secrets. Teams self-host it with Docker or Helm, often reachable from a company network or the Internet.
- **Workers** (`src/kitaru/worker/`, `src/kitaru/task/`): they claim tasks from the server and run them as subprocesses. Tasks include replaying a recorded session through the user's agent code, running importers and evaluators.
- **SDK, CLI and MCP server**: the Python client (`src/kitaru/client/`), the `kitaru` CLI (`src/kitaru/cli/`), and a stdio MCP server (`src/kitaru/mcp/`) that defaults to read-only mode.
- **Plugins** (`plugins/packages/*`):
  - framework adapters that record agent runs (LangGraph, Pydantic AI, OpenAI Agents, Claude Agent SDK)
  - importers that parse trace exports from other tools (Langfuse, LangSmith, Braintrust, Logfire, Phoenix, MLflow, ElevenLabs, Mastra, JSONL)
  - evaluators
- **TypeScript SDK and adapters** (`packages/`). These are not built in this image, but the source is there to read.

The server is the most important thing to audit, followed by the importers' parsers, which handle files from outside. Many self-hosted servers serve a single user or a small team, so for most deployments the realistic attacker is someone with network access and no account, which is why they come first below.

## Who the attacker is

In priority order:

1. **An unauthenticated network client** who can reach the server's HTTP port, when the server runs with `local` or `control_plane` authentication. They should only reach `/health`, `/api/v1/info`, the login and device-authorization routes, and the static UI files.
2. **A task token holder.** This is the agent code running inside a worker task. Its token is scoped to one task attempt and an allowlist of sessions and blobs. It must not read or write anything outside that grant, reach account-only routes, or keep working after its attempt is superseded.
3. **A worker token holder.** It must not act as an account.
4. **An authenticated non-admin account** (see the next section).
5. **Malicious content inside data Kitaru ingests**: trace export files given to importers, recorded payloads, and responses from provider APIs that importers call. Parsing these must not lead to code execution, path traversal, or unbounded resource use.
6. **A malicious page in a logged-in user's browser** (CSRF against cookie authentication).

## What the server deliberately allows

Kitaru's documented model is a **trusted-team deployment**: everyone authenticated can read and write everything; ownership records who created a resource but does not restrict access; operators run one server per trust boundary. **Do not report "authenticated account A can read or modify account B's sessions, agents, evaluations, connections or (non-internal) secret values". That is intended.**

The real boundaries, which we do want reported:

- **Authentication**: login bypass; forging or misusing JWTs, `KITKEY_` API keys or device codes; brute-forcing device codes past the attempt limit; CSRF bypass on cookie auth; any route reachable without authentication that should not be.
- **Admin-only account administration**: creating accounts, granting admin, changing another account. A non-admin doing any of these, an account changing its own admin flag, or a service account becoming admin, is a privilege escalation.
- **Scoped tokens**: task tokens and worker tokens escaping their scope (see above).
- **Internal secrets** must never be returned to a client. The server's secret encryption key, JWT signing key and database credentials must never leak.
- **The reserved `KITARU_` environment prefix**: a connection, secret or agent version must not be able to set `KITARU_*` variables in a task process, since the worker owns those (`src/kitaru/server/domain/connection.py`).
- **Server-side safety**: SQL injection through the JSON filter language (`src/kitaru/server/filtering.py`, `src/kitaru/server/adapters/db/filtering.py`); path traversal in blob or UI serving; blob uploads bypassing size limits or content-type protections; server-side request forgery from the server.

## What is trusted by design (out of scope)

- **Workers run user code.** An agent version's run command, setup hooks, script plugins and package plugins are executed on the worker on purpose. An authenticated account that can register agent versions or plugins can run code on workers. That is the product, not a vulnerability. Escaping a task's token scope (above) *is* in scope.
- **Admins and server operators** (anyone who sets `KITARU_SERVER_*` environment variables) are trusted. So is the PostgreSQL database.
- **The `none` authentication scheme** (`KITARU_SERVER_AUTH_SCHEME=none`) is for local single-user use; everything runs as the default account.
- **The external control plane**, when `control_plane` authentication is configured, is trusted.
- **Development and example material**: `docker-compose.yml` (default passwords), `devtools/`, `examples/`, `docs/`, `helm/` example values, `scripts/`, `release/`, `tests/`.
- **Vulnerabilities in third-party dependencies**, unless Kitaru uses them in a way that creates the problem.

## Which code matters most

- **Highest**:
  - `src/kitaru/server/` (REST routers in `adapters/rest/routers/`, authentication in `adapters/auth/` and the auth service, permissions, filtering, blob storage, secret encryption)
  - `src/kitaru/api_models/` (request validation)
  - `src/kitaru/worker/` and `src/kitaru/task/` (credential handling between worker, task and subprocess)
- **High**: the importer parsers in `plugins/packages/*-importer`.
- **Medium**:
  - `src/kitaru/mcp/` (especially whether read-only mode really prevents writes)
  - `src/kitaru/client/` (credential storage)
  - the recording adapters in `plugins/packages/`
  - `packages/` (TypeScript client)
- **Lower**: `src/kitaru/cli/` scaffolding and setup commands that run locally for the user who typed them.

## How to exercise it

The image has Kitaru and every extra installed from `/src` in `/src/.venv` (already on `PATH`), the plugin workspace in `/src/plugins/.venv`, and a local PostgreSQL 16. There is no network; `uv` is set to offline and frozen mode.

- **Start the database**: run `kitaru-db-start`. It listens on `localhost:5433` with user `postgres` and password `password`.
- **Start a server with real authentication**:

  ```
  kitaru-db-start
  KITARU_SERVER_DB_HOST=localhost KITARU_SERVER_DB_PORT=5433 KITARU_SERVER_AUTH_SCHEME=local \
  KITARU_SERVER_JWT_SIGNING_KEY=dev-signing-key-0123456789abcdef KITARU_SERVER_SECRET_ENCRYPTION_KEY=dev \
  KITARU_SERVER_DEFAULT_ACCOUNT_PASSWORD=admin-password \
  uvicorn kitaru.server.api.main:app --factory --port 8000
  ```

  The server bootstraps a `default` admin account on first start; create a non-admin account and a service account to test boundaries.
- **Tests**:
  - Core: `KITARU_TEST_REQUIRE_POSTGRES=1 pytest --ignore=tests/typescript -m "not mcp_fuzz"` (after `kitaru-db-start`). `tests/AGENTS.md` describes the layout, including the Schemathesis API fuzz tests and task-credential checks.
  - Plugins: `uv run --project plugins pytest -c plugins/pyproject.toml plugins/tests`.
  - Paths that install package plugins with `uv run --with` need PyPI and will not work offline.

## How we rate severity

- **Critical**:
  - unauthenticated remote code execution on the server
  - unauthenticated authentication bypass
  - unauthenticated read of secrets, API keys, or session data
- **High**:
  - a non-admin becoming admin
  - a task or worker token acting as an account or escaping its grant
  - reading internal secrets or server keys
  - code execution on the server host
  - SQL injection reachable by any authenticated principal
  - an importer parser executing code or writing files outside its working area from a crafted export file
  - SSRF from the server that returns the response
- **Medium**:
  - CSRF that performs a state-changing action
  - blind SSRF
  - setting reserved `KITARU_` variables in a task process
  - the MCP server writing data in read-only mode
  - unauthenticated denial of service needing only a few requests
  - a crafted import file causing unbounded memory or CPU use on a worker
- **Low**:
  - denial of service that needs an authenticated account
  - missing hardening headers or verbose errors
  - issues that need unusual, non-default configuration

## How reports should look

Reports of intended behavior (see "What the server deliberately allows" and "What is trusted by design") cost us the most time. Please:

- Only report what the reproducer actually demonstrates against an unmodified server with `local` authentication and default settings, or say exactly which non-default setting it needs.
- State which attacker from the list above the exploit assumes (no account, non-admin account, task token, worker token, crafted import file, and so on).

- One report per root cause. If the same missing check affects several routes, list them in one report.
- The reproducer should be a single Python script (using `httpx` or the Kitaru client) or a short sequence of `curl` commands against a local server started as above, with the expected and actual result. For importer bugs, include the crafted input file.
- Patches should be minimal and merge-ready for the `develop` branch, with a regression test under `tests/` or `plugins/tests/` where practical.
