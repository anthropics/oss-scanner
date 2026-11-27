# PostHog threat model

## What this project does and where untrusted input enters

PostHog is a multi-tenant product analytics platform: product and web analytics, session replay, feature flags,
experiments, surveys, error tracking, a data warehouse, data pipelines (CDP), workflows and messaging, LLM
observability, and AI agents. PostHog Cloud (US and EU) runs this code for many organizations. Others self-host it.

Main parts of the repository:

- `posthog/`, `ee/`, `products/*/backend/`: the Django and DRF application. PostgreSQL holds organizations, projects
  (called teams in code), users and configuration. ClickHouse holds events, persons, sessions and recordings.
  `ee/` has a different license but ships in PostHog Cloud and is in scope.
- `posthog/hogql/`, `common/hogvm/`: HogQL (a SQL dialect compiled to ClickHouse SQL) and Hog (a language with
  Python, TypeScript and Rust virtual machines). Customers write both.
- `nodejs/`: event ingestion, the CDP (customer-written Hog functions and destinations), session replay ingestion,
  and workflows.
- `rust/`: capture (the public ingestion endpoint), feature flag evaluation, error tracking symbolication (cymbal),
  property definitions, person services and other workers.
- `posthog/temporal/`, `products/data_warehouse/`, `products/batch_exports/`: Temporal workers that import from and
  export to customer-supplied databases, warehouses, buckets and SaaS APIs.
- `services/`: the MCP server, the LLM gateway, the agent proxy, and the OAuth, integration and credentials services.
- `frontend/`, `products/*/frontend/`: the React application, the toolbar (runs inside customers' websites), and the
  pages for shared and exported resources.

Who is trusted:

- Anonymous: anyone who sends events, calls the flags endpoint, opens a shared dashboard, insight, recording or
  notebook, or uses signup, login, password reset, invite, 2FA, SSO, SAML, SCIM and OAuth endpoints. Signup on
  PostHog Cloud is open, so an attacker always has an organization of their own.
- Organization members: organization levels (member, admin, owner) plus project-level and resource-level access
  control (`posthog/rbac/`, `ee/api/rbac/`). A finding is a member who does what only a higher level, another
  project or another organization can do.
- Credentials: session cookies, personal API keys with scopes and optional project or organization limits, project
  secret API keys, OAuth access tokens, sharing tokens, and the public project token (`phc_...`). The project
  token is public by design. Every other credential must stay inside its scopes, project and organization.
- Trusted: PostHog staff users (`is_staff`, Django admin, impersonation) and the operator of a self-hosted instance.

Where untrusted input enters:

- Capture endpoints (`/e`, `/i/v0/e`, `/batch`, `/s`, error tracking, logs and LLM event intake). They need no
  authentication by design. The server stores the payload and later shows it to project members in the app, in
  exports and in emails. It also passes the payload to customer Hog functions and to LLM prompts.
- The flags endpoints (`/flags`, `/decide`) and the remote config endpoints.
- The REST API under `/api/`, where `posthog/api/routing.py` scopes nested routes to a project or organization, and
  the query API, which accepts HogQL and query JSON from any member or API key with query access.
- Shared and exported resources (`posthog/api/sharing.py`, `/shared/`, `/embedded/`, `/exporter`).
- Customer-written code and templates: Hog functions, transformations, workflows, HogQL, SQL in the data warehouse,
  survey and message content, notebook and dashboard text.
- Customer-supplied connection details: warehouse sources, batch export destinations, webhooks, integrations, OAuth
  apps (including dynamic client registration), SAML and SCIM configuration, and proxy domains.
- Inbound webhooks and callbacks from third parties, and uploaded files (source maps, symbol sets, images, CSV).
- Content that reaches an LLM: events, recordings, tickets, documents, tool outputs and MCP tool calls.
- `postMessage` and URL parameters handled by the toolbar and by embedded pages on customers' websites.

## Components that matter most / least

Most:

- Tenant isolation. `team_id` scoping is the primary boundary. Every object ID, slug, UUID or token from a request
  must resolve inside the caller's project or organization, on every viewset method, `@action`, bulk endpoint,
  export path, Temporal activity and agent tool. Serializer foreign keys that DRF generates without a
  project-scoped queryset are a recurring source of bugs.
- Authentication and authorization: `posthog/auth.py`, `posthog/permissions.py`, `posthog/api/routing.py`,
  `posthog/rbac/`, API key scopes, OAuth (`posthog/api/oauth/`), SSO, SAML, SCIM, 2FA, passkeys, invites, password
  reset, email verification, sessions, and impersonation limits.
- HogQL and the query layer: a customer query must never read another project's rows, system tables, or columns
  the caller cannot access, and must never reach ClickHouse table functions that read files or URLs.
- The Hog virtual machines and the CDP: customer code must stay inside the VM, inside its project, and inside the
  outbound request rules.
- Outbound requests to customer-chosen hosts (warehouse sources, batch exports, webhooks, integrations, image and
  URL fetches). Server-side decrypted credentials must never go to a host the customer does not own.
- Stored secrets: integration credentials, warehouse and export credentials, API keys, OAuth tokens and signing keys.
- Rendering of event data and customer content in the app, in shared and exported pages, in emails and in exports.
- The toolbar and other code that runs in customers' origins.
- AI agents, the MCP server and the LLM gateway: each tool call must enforce the end user's own authorization, and
  untrusted content in the model context must not cause data egress or a side effect that the user did not confirm.
- Security-relevant defaults in `posthog/settings/` for both Cloud and self-hosted deployments.

Least:

- Tests, fixtures, Storybook stories, demo data generators, benchmarks, and developer tooling (`tools/`, `bin/`,
  `.github/`), unless a workflow lets a pull request from a fork reach secrets or publish an artifact.
- Code that no route, task, consumer, workflow or command can reach, and code behind `DEBUG`, `TEST` or `E2E_TESTING`
  settings, unless a production deployment can enable that code by accident.
- `docs/` and other generated or published documentation content.

## How to exercise it

The checkout is at `/src`. The image has the Python environment (`/src/.venv`), the Node workspace dependencies, and
the Rust crates that the workspace needs, all fetched in advance. There is no network.

Run the application:

- `posthog-app start` runs PostHog from `/src` the way the hobby deploy runs it: the settings in `.env.services`,
  then `bin/migrate` and `bin/docker-server`. It starts PostgreSQL, Redis and ClickHouse first. The web server is at
  `http://localhost:8000`. Logs are in `/var/log/posthog`.
- The first start in a new container applies every database migration. That takes about 30 minutes. Later starts
  take about 3 minutes. Start it early and read the source while it runs.
- `posthog-app user` creates an organization, a project, a user and a personal API key. It prints the project token
  and the key.
- A tenant-isolation reproducer needs a second organization. Open signup is off in this deployment mode, so create
  it in `posthog-app run python manage.py shell` with
  `User.objects.bootstrap("Org B", "b@example.com", "<password>", first_name="B")`. It returns the organization,
  the project and the user. Log in with `POST /api/login/`.
- `posthog-app start <service>...` also starts the named services. `posthog-app start --all` starts all of them.
  `posthog-app status` shows what runs. The services are:
  - `capture`: the Rust capture service at `http://localhost:3000` (for example `POST /i/v0/e/`).
  - `flags`: the Rust feature flags service at `http://localhost:3001` (for example `POST /flags?v=2`).
  - `ingestion`: the Node ingestion consumer. It moves events from Kafka to ClickHouse.
  - `plugins`: the Node server with the CDP API at `http://localhost:6738`.
  - `worker`: the Celery worker and scheduler.
  - `kafka`: a Redpanda broker at `localhost:9092`. `capture`, `ingestion` and `plugins` start it.
  - `personhog`: the PersonHog replica and router (gRPC at `localhost:50052`). It always starts with the web
    server.
- All services together use about 7 GB of the 8 GB of memory. Start only the services that a reproducer needs.
- The Rust services are debug builds in `/src/rust/target/debug`. After an edit, run
  `cd /src/rust && cargo build --offline --bin <name>`. The Node services run from
  `/src/nodejs/dist`. After an edit, run `cd /src/nodejs && pnpm build`.
- `posthog-app run <command>` runs a command with the application settings, for example
  `posthog-app run python manage.py shell`. `posthog-app stop` stops the application.
- Edits under `/src` take effect after `posthog-app stop` and `posthog-app start`, so you can test a patch.
- The image has no frontend build. The API and the server-rendered pages work, and the React application does not
  load. Read `frontend/` as source.
- Temporal, object storage, session replay ingestion and the other Rust services do not run. Batch exports,
  warehouse imports and recording playback cannot be driven end to end. When a path needs one of them, say so in
  the report and show the data flow in the source.

Run the tests:

- `posthog-test-services start` starts PostgreSQL, Redis and ClickHouse without the application.
  `posthog-test-services stop` stops them. `posthog-test-services status` shows what runs.
- Python: `pytest path/to/test_file.py::TestClass::test_name` from `/src`. The first database-backed run creates the
  test database, which takes about 20 minutes. Later runs reuse it. Do not pass `--create-db`.
- Write reproducers as tests on the existing bases in `posthog/test/base.py` (`APIBaseTest`, `ClickhouseTestMixin`,
  `BaseTest`). `APIBaseTest` gives an organization, a project and a logged-in user. Create a second organization and
  project in the test to show a tenant crossover.
- HogQL: `posthog/hogql/test/` and `posthog/hogql/printer/test/` show how to print and execute queries.
- Hog VM: `common/hogvm/python/test/` (pytest) and `common/hogvm/typescript/` (`pnpm jest`). Both need no services.
- Node: `cd /src/nodejs && pnpm jest src/path/to/file.test.ts`.
- Rust: `cd /src/rust && cargo test --offline -p <crate>`. Start with `capture`, `feature-flags` and `cymbal`.
  The first build of a crate compiles its dependencies, which is slow on a small machine.
- Tests mock outbound HTTP, Kafka producers and third-party APIs, so nothing must leave the container.

## How we rate severity

Rate a finding by what an attacker reaches, with the lowest position that works. Treat PostHog Cloud as the
reference deployment and say when a finding applies only to self-hosted instances. When unsure between two levels,
choose the lower level and say why.

- Critical: remote code execution without authentication; read or write of another organization's data from an
  anonymous position or from a new account; full account takeover; authentication bypass; SQL or HogQL injection
  that reaches other tenants' data; escape from the Hog VM or an agent sandbox to the host; indirect prompt
  injection that causes a destructive cross-tenant tool call without user confirmation.
- High: remote code execution with authentication; a member, API key or OAuth token that crosses its project,
  organization or scopes; privilege escalation inside an organization (member to admin, bypass of project or
  resource access control); 2FA or SSO enforcement bypass; stored XSS that anonymous event data can plant in a
  logged-in user's session; a path that sends stored credentials to an attacker-chosen host; an agent tool that
  accepts another tenant's IDs; SQL injection limited to the caller's own tenant.
- Medium: stored XSS that needs a project member to plant it; SSRF that reaches internal services from a path that
  does not use the egress controls; sensitive data shown to members of the same organization who lack access; CSRF on
  an important state change; secrets in logs, error reports or API responses; denial of service that one cheap
  anonymous request can cause.
- Low: reflected XSS that needs unusual user interaction; open redirect; verbose errors; a missing hardening control
  with a demonstrated but minor impact.

A status-code or timing difference that lets a caller enumerate another tenant's objects with sequential IDs is a
finding. Rate it one level below the read it would enable.

## Anything to leave alone

- Fake, spammed or forged events and persons. Capture needs no authentication and the project token is public.
  Report these only when they reach another project's data, a logged-in user's session, or server-side code.
- Denial of service through volume, and missing rate limits. Report a missing rate limit only where it defeats an
  authentication control, such as 2FA codes, password reset or login.
- Raw SSRF to internal addresses or cloud metadata from code that goes through the proxy-based egress controls.
  PostHog Cloud sends that traffic through a filtering proxy. Report paths that skip those controls, paths that
  trust the response of an attacker-controlled server, and paths in workers that have direct egress.
- Actions of a verified staff user in Django admin or during impersonation. Report these only when a non-staff
  user reaches them or when impersonation exceeds its documented limits.
- What an organization owner or admin can do to their own organization, and what the operator of a self-hosted
  instance can configure. Insecure defaults are in scope.
- Prompt injection that only changes an agent's tone, quality or refusals, without data egress, an unauthorized
  action or a privilege change.
- Vulnerable dependencies without a reachable path through PostHog code, and vendored third-party code.
- Missing security headers, missing cookie flags and other hardening gaps without an exploit chain.
- Self-XSS, clickjacking on pages with no sensitive action, and reports that need a compromised browser or
  device.
- Proposals to add validation, monitoring or defense in depth without a specific bypass.

## How reports should be grouped

Send one report per root cause. When one missing check affects several routes, actions or services, list all of
them in the same report. Mark what you ran and what you read from the source.
