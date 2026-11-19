# Threat model

## What this project does and where untrusted input enters

Kaneo is a self-hosted project manager: workspaces, projects, Kanban boards, tasks, comments, and integrations. It is a pnpm monorepo:

- `apps/api`: Hono API on Node.js with PostgreSQL (Drizzle), better-auth, WebSockets, and optional Redis for fan-out across instances.
- `apps/web`: React app that talks to the API through the typed client in `packages/libs`.
- `packages/mcp`: stdio MCP server; the API also serves MCP over HTTP with its own OAuth flow (`apps/api/src/mcp`).
- `packages/permissions`: built-in workspace roles (`owner`, `admin`, `member`, `viewer`) and the permission vocabulary.

One instance hosts many users and workspaces. Workspace members must never see or change data in workspaces they do not belong to, and members limited to selected projects must not reach other projects. Treat every authenticated user, including anonymous guest accounts, as a possible attacker against everything outside their own access.

Untrusted input enters through:

- every route under `/api`, authenticated by session cookie, bearer token, or API key (`x-api-key`); API keys can carry a narrower permission scope
- `/api/auth/*` (better-auth: email and password, magic link, email OTP, social sign-in, anonymous guests, device authorization)
- MCP OAuth: dynamic client registration, PKCE, consent, and redirect URIs
- WebSocket upgrades at `/api/ws/:projectId` and `/api/ws/user`
- inbound webhooks from GitHub, GitLab, Gitea, and the Creem billing provider
- endpoints that need no session: public projects and their description pages, invitations by id, assets, avatars, calendar feeds by token, health, config, and OpenAPI
- task descriptions and comments, stored as markdown and rendered with TipTap in other users' browsers, plus titles and names shown throughout the UI
- uploads through presigned S3 URLs, finalized and served by the API
- URLs that users configure for outbound webhooks, notification deliveries, and Gitea, GitLab, Slack, Discord, and Mattermost integrations

Trusted: the instance operator (environment variables, Helm values), PostgreSQL, Redis, S3, and instance admins.

## Components that matter most / least

Most important:

- Authorization: `apps/api/src/utils/workspace-access-middleware.ts`, `validate-workspace-access.ts`, `require-workspace-permission.ts`, and `apps/api/src/project-access/`. A route that loads a resource by id without confirming it belongs to a workspace and project the caller can access is the bug class we care about most.
- Authentication: `apps/api/src/auth.ts`, `apps/api/src/utils/authenticate-api-request.ts`, API key scopes, MCP OAuth in `apps/api/src/mcp/`, and the registration and guest policy flags.
- Realtime: `apps/api/src/events/` and `apps/api/src/ws/`. Events and WebSocket messages must reach only users who can see the underlying data, and revoked access must take effect on open connections.
- Outbound requests: the SSRF guard in `apps/api/src/utils/assert-public-destination.ts` and `outbound-request.ts`, and every integration in `apps/api/src/plugins/` that makes requests.
- Webhook verification in `apps/api/src/plugins/{github,gitlab,gitea}` and `apps/api/src/billing`.
- Asset access: `apps/api/src/utils/authorize-asset-access.ts` and `apps/api/src/storage/`.
- Secrets: integration tokens, webhook secrets, API keys, OAuth tokens, and session tokens must never appear in API responses, logs, events, WebSocket payloads, or MCP output.
- Rendering of user content in `apps/web/src/components/editor/` and `apps/web/src/components/task/extensions/`.

In scope, lower priority: billing and entitlements (`apps/api/src/billing`), which only run on the hosted cloud edition (`KANEO_CLOUD=true`); the Helm chart in `charts/kaneo`; `Dockerfile.kaneo`.

Out of scope: `apps/site`, `apps/docs`, `packages/cli`, `packages/planka-import`, `scripts/`, `tests/`, and `.github/`.

## How to exercise it

- Dependencies are installed and the API, web app, and MCP package are built in `/src`.
- PostgreSQL is installed but not running when the container starts. Run `service postgresql start`. `DATABASE_URL` already points at the `kaneo_test` database (user `postgres`, password `postgres`).
- `pnpm test` runs the unit tests. `pnpm test:integration` runs `tests/api-integration/`, which boots the Hono app in-process against PostgreSQL; `tests/api-integration/setup.ts` sets every environment variable it needs.
- The easiest way to reproduce an API bug is a new test file in `tests/api-integration/` that uses the helpers in `tests/api-integration/helpers/` (users, sessions, workspaces, projects, API keys). Run one file with `cd /src/apps/api && pnpm exec vp test run --config vitest.integration.config.ts <file>`.
- S3 and Redis are not available offline. Storage is mocked in the tests, and Redis is optional.

## How you rate severity

- Critical: remote code execution; reading or changing any workspace's data without authentication; taking over another user's account without their interaction; a regular user becoming instance admin; leaking secrets that grant access to other users' accounts or to another workspace's integrations.
- High: an authenticated user, including a guest, reading or changing data in a workspace they do not belong to or a project they were not granted; raising one's own role in a workspace (for example member to admin or owner); an API key acting beyond its scope; stored XSS in content other users view; SSRF from a non-admin account that reaches loopback, private, or cloud metadata addresses; forging an inbound webhook; events or WebSocket messages delivered to users who cannot access the data.
- Medium: leaking metadata (names, emails, workspace or project names) across workspaces; a role performing a low-impact action in its own workspace that its permissions forbid; CSRF on a state-changing endpoint; bypassing the registration, guest, or workspace-creation policy flags; revoked access that keeps working on an open WebSocket; bypassing billing entitlements on the cloud edition; a single small request that crashes the API or exhausts its memory or CPU.
- Low: anything that requires instance-admin or workspace-owner privileges and only affects that same workspace; self-XSS; timing side channels with no practical attack shown; verbose errors without sensitive data.
- A finding that depends on an insecure operator configuration is rated one level lower, unless Kaneo's defaults or documentation lead operators to that configuration.

## Anything to leave alone

- Instance admins bypass workspace membership, role checks, and project restrictions on purpose.
- The first non-anonymous user to register becomes instance admin on purpose.
- Invitation ids, calendar feed tokens, and device codes are bearer capabilities. Report them only if they are guessable, leaked, or accepted after they should have expired.
- Public projects, their description pages, and the images in those descriptions are readable without authentication on purpose.
- `KANEO_ALLOW_PRIVATE_WEBHOOK_DESTINATIONS=true` turns the SSRF guard off on purpose.
- CORS reflects any origin in non-production builds that have no configured origins.
- Denial of service through request volume, missing hardening headers with no demonstrated impact, dependency advisories with no working path through Kaneo, and anything that needs a compromised host, database, Redis, or S3 bucket.

## Reports and patches

- Include a reproducer as an integration test in `tests/api-integration/` when the bug is in the API.
- Keep route handlers thin and put fixes in controllers or the shared authorization helpers, following `AGENTS.md`.
