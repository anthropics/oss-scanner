# Threat model

Aictiq is a self-hostable, multi-tenant work-tracking and agent-orchestration platform.
The repository's own [SECURITY.md](https://github.com/Aictiq/Aictiq/blob/main/SECURITY.md)
and [docs/security.md](https://github.com/Aictiq/Aictiq/blob/main/docs/security.md) describe
the controls in detail; both are in /src.

## What this project does and where untrusted input enters

- `backend/src/Api`: ASP.NET Core (.NET 10) REST API, MCP endpoint and the server for the
  built SPA. Every HTTP request is untrusted, authenticated or not. Authentication is
  cookie (browser) or bearer (JWT, personal access tokens, runner secrets).
- `backend/src/Modules`: domain modules (Identity, Tenancy, WorkItems, Wiki, Automation,
  Integrations, Notifications, Analytics, Billing). EF Core on PostgreSQL.
- `backend/src/Workers`: background jobs (outbox, mail, webhook delivery, link previews,
  storage cleanup). Webhook targets and link-preview URLs are user-supplied.
- `frontend-vue`: Vue SPA, same-origin with the API. It renders member-authored Markdown
  (work items, comments, wiki pages).
- `cli`: the `aictiq` CLI, factory runner and MCP client. The runner receives work from the
  API and starts coding agents on the runner's machine.

All member-authored content (titles, descriptions, comments, wiki pages, playbooks, CSV
imports, uploaded files, link previews) is untrusted, including content from members of
the same organization.

## Components that matter most / least

Most important:
- Cross-tenant isolation: any way for one organization (or a user without the right
  project role) to read or change another organization's data. Out-of-scope reads are
  meant to return 404.
- Authentication and session handling: JWT and refresh-token rotation, PAT scopes and
  organization binding, runner credentials (`jrn_` secrets valid only under
  `/api/v1/runner/*`), per-run agent tokens, OAuth linking, lockout, CSRF header rule.
- Injection: SQL, stored XSS through Markdown or uploads, SSRF in webhooks and link
  previews (private, loopback and link-local destinations must be rejected).
- Upload handling: type and size enforcement, image decoding, served content types.
- The runner: anything that lets the API or item content make the runner execute
  commands or leak credentials beyond what the design allows.

Less important: `backend/src/AppHost` (local development orchestration only),
`perf/`, `docs/`, `deploy/` scripts.

## How to exercise it

- Backend builds with `dotnet build Aictiq.slnx`. The integration tests in
  `backend/tests/IntegrationTests` need Docker (Testcontainers Postgres and Garage), so
  they cannot run in the scan image, but they are the best map of intended behavior:
  each security control in SECURITY.md has a test there.
- `cd frontend-vue && pnpm test` and `cd cli && pnpm test` run the unit tests offline.

## How we rate severity

- Critical: unauthenticated remote code execution; unauthenticated or cross-tenant access
  to another organization's data; authentication bypass; theft of runner or agent tokens
  that leads to command execution on a runner machine.
- High: authenticated cross-tenant read or write; privilege escalation within an
  organization (member to admin, read scope doing writes); stored XSS reachable by
  another user; SSRF to internal addresses; SQL injection by any authenticated user.
- Medium: information disclosure within one organization beyond the user's role;
  CSRF; rate-limit or lockout bypass; open redirects.
- Low: denial of service needing authentication, missing hardening headers, issues only
  reachable by an organization owner against their own organization.

## Anything to leave alone

- Development-only configuration (AppHost, Aspire parameters, the Vite dev CSP
  relaxations) is not deployed and is out of scope.
- A coding agent started by the runner runs as the runner's OS user with no sandbox by
  design (see "Factory runners and prompts" in docs/security.md). Report only ways around
  the documented token and organization boundaries, not the absence of a sandbox.
- Prompt injection that only makes an agent misbehave within the permissions its run
  token already has is not a finding on its own.
