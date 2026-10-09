# Windmill threat model

The repository carries a longer threat model at `backend/THREAT_MODEL.md` (assets, entry points, a threat table
with the advisories behind each row, accepted risks). Read it first. This file adds what a scan needs on top of it:
what counts as a finding, how to run the instance in this image, and how we rate severity.

## What this project does and where untrusted input enters

Windmill is a platform for scripts, flows, apps and triggers: a Rust API server (`backend/windmill-api*`), workers
that execute user-written code in many languages (`backend/windmill-worker`), a Postgres database that is both the
store and the job queue, and a Svelte frontend (`frontend/`) served by the API server. It also stores the
credentials of every system its users connect to, so one instance is both a code execution engine and a secret
vault.

**Running code on a worker is the product, not a vulnerability.** Any workspace member with the developer role can
run arbitrary code on a worker by design. A finding has to cross a boundary that Windmill claims to enforce:

- unauthenticated to anything: public app endpoints (`apps_u`, `jobs_u`, `scripts_u`, `settings_u`,
  `resources_u`), HTTP routes and webhooks (`/api/r/*`, `capture_u`), OAuth/OIDC callbacks, MCP OAuth
  registration, email and message-queue triggers
- one workspace to another, and to instance (superadmin) level
- within a workspace: operator to developer to admin, folder and group ACLs, row-level security, `on_behalf_of`
- a scoped or job token (`WM_TOKEN`) to more than its scopes, owner or lifetime allow
- an anonymous or public app viewer to the runnables, resources and job results behind the app
- stored content (app HTML, markdown, job results with a chosen content type, S3 downloads) to another user's
  browser session on the instance origin
- user-controlled URLs fetched by the server itself (AI proxy, MCP, webhooks, object storage tests, git, npm
  proxy) to the internal network
- user-controlled identifiers or values spliced into SQL or into the generated job wrapper code
- job code to the worker host and to other jobs, when nsjail sandboxing is enabled (see below)

## Components that matter most / least

Most: authentication and authorization (`backend/windmill-api-auth`, the per-route checks across
`backend/windmill-api*`), token and session lifecycle, secret and resource resolution (`windmill-store`, the AI
proxy, MCP in `windmill-mcp`), trigger ingestion (`windmill-trigger`, `windmill-native-triggers`), the worker's
sandbox configuration and wrapper generation (`windmill-worker`, the `nsjail` config templates), SQL built from
user input, and the frontend paths that render stored content.

In scope but lower priority: the CLI (`cli/`), the client SDKs (`typescript-client/`, `python-client/`,
`go-client/`, `rust-client/`, `powershell-client/`), `lsp/`, `debugger/`, `multiplayer/`, the Docker images under
`docker/`.

Out of scope: `benchmarks/`, `examples/`, `ai_evals/`, `integration_tests/`, test fixtures, and developer tooling
(`wm-ts-nav/`, `scripts/`, `.claude/`, `.github/` unless a workflow is exploitable from a fork pull request).
Enterprise features are not in this repository, so an enterprise code path cannot be assessed from here.

## How to exercise it

- `wm-start` starts the bundled Postgres and a standalone instance (API server plus one worker) on
  `http://127.0.0.1:8000`. The first login is `admin@windmill.dev` / `changeme`, a superadmin. Create
  lower-privileged users, further workspaces and scoped tokens through the API to test a boundary: a finding
  demonstrated only as the superadmin is not one.
- `wm-db start` / `wm-db stop` run Postgres alone, at `postgres://postgres:changeme@127.0.0.1:5432/windmill`.
- The binary is a debug build at `/src/backend/target/debug/windmill`, built with the features in `$WM_FEATURES`.
  Rebuild after a patch with `cd /src/backend && cargo build --features "$WM_FEATURES"`. Every dependency is
  already fetched and cargo is set offline.
- Backend tests: `cd /src/backend && DATABASE_URL=postgres://postgres:changeme@127.0.0.1:5432/windmill cargo test
  -p <crate> --features "$WM_FEATURES"`. They are not precompiled, and the full suite is large: test one crate.
- Frontend: dependencies are installed in `/src/frontend`; `npm run test:unit` runs the unit tests.
- The API is described in `backend/windmill-api/openapi.yaml`.
- Job runtimes present offline: bun, deno, python 3.12 (through uv), bash. A script that imports a package it has
  to download cannot run here.
- Sandboxing is off by default, as it is in a default install. `DISABLE_NSJAIL=false wm-start` turns nsjail on; the
  binary is at `/bin/nsjail`.
- Not built: the DuckDB engine (`backend/windmill-duckdb-ffi-internal`, the `duckdb` feature). Its sources are in
  the checkout for reading.

## How we rate severity

- **Critical**: an unauthenticated attacker, or an authenticated one from a different workspace, executes code,
  reads secrets, resources or tokens, or takes over an account or the instance. Escaping nsjail to the worker host
  or to another job's data when nsjail is enabled. Pre-auth SQL injection or SSRF that reaches credentials.
- **High**: the same outcomes within one workspace by a role that should not have them (an operator or a scoped
  token gaining developer or admin capabilities, reading a folder's secrets without access to it). SQL injection
  or SSRF that needs an authenticated low-privilege user. Stored XSS that runs in another user's session on the
  instance origin without that user doing anything unusual. Authentication bypass on a webhook or trigger. Reading
  arbitrary files of the server.
- **Medium**: information disclosure without credentials (job arguments, results or logs across a permission
  boundary, user enumeration that matters), XSS that needs unusual interaction, missing audit of a sensitive
  action, an open redirect usable for token theft, memory unsafety with no demonstrated path to exploitation.
- **Low**: defense-in-depth gaps and hardening suggestions without a demonstrated crossing of a boundary.

Post-authentication SQL injection is high, and critical when it crosses workspaces or reaches the instance
database with the server's privileges. A report without a working reproduction against the running instance is
capped at medium.

## Anything to leave alone

Do not report these; they are documented, by design, or accepted:

- A developer running arbitrary code on a worker, reading the worker's environment, or reaching the network from
  a job when nsjail is disabled. Without nsjail, the model is that the instance trusts its script authors.
- Anything that requires being a superadmin, a workspace admin of the workspace concerned, or having direct
  database access.
- The default `admin@windmill.dev` / `changeme` login, the `changeme` database password and other choices of this
  image or of the sample `docker-compose.yml`.
- `NO_AUTH` / the `no_auth` cargo feature: it disables authentication on purpose.
- Denial of service by an authenticated user (heavy jobs, queue flooding, large uploads), and the absence of rate
  limiting on login.
- Jobs started by someone who can legitimately publish to a broker or queue a trigger listens on.
- Instance settings stored unencrypted in the database under the default secret backend.
- A vulnerable dependency version with no reachable path shown in Windmill.

## How reports and patches should look

One issue per report, with the role and workspace of the attacker, the exact requests (curl or a script) against
`wm-start`, and what was obtained that should not have been. Patches should be minimal, fix the check at the place
that enforces it instead of at one caller, and say whether sibling routes have the same gap.
