# Postiz

Postiz is a social media management platform. This enrollment covers the source
in gitroomhq/postiz-app: its Next.js frontend, NestJS backend, Temporal
orchestrator, and shared libraries. It stores users, organizations, scheduled
posts, media, and credentials for connected social accounts.

## Security boundaries and priorities

- Anonymous clients reach authentication, OAuth, callback, webhook, public API,
  and MCP endpoints. Check authentication, signature verification, token scope,
  redirect validation, and replay handling where applicable.
- Authenticated users and API clients supply organization, user, integration,
  post, and media identifiers. Verify organization isolation and role checks on
  reads, writes, background jobs, and exports. A user must not access another
  organization's data or publish through its connected accounts.
- OAuth tokens, session tokens, API keys, and social-account credentials must
  stay confidential and must only authorize the intended user, organization,
  application, and operation.
- Media uploads, imported URLs, provider responses, post content, webhook URLs,
  and self-hosted provider addresses are untrusted input. Review SSRF defenses
  including redirects and DNS resolution, path traversal, upload validation,
  injection, and XSS across rendering and preview paths.
- Inspect the boundary between HTTP requests and Temporal workflows/activities,
  especially how organization and integration ownership is carried into jobs.

Useful starting points are apps/backend/src/services/auth,
apps/backend/src/api/routes, apps/backend/src/public-api,
libraries/nestjs-libraries/src/chat,
libraries/nestjs-libraries/src/database/prisma,
libraries/nestjs-libraries/src/integrations,
libraries/nestjs-libraries/src/upload, apps/orchestrator/src, and
apps/frontend/src. The Prisma schema is at
libraries/nestjs-libraries/src/database/prisma/schema.prisma.

## Build and offline reproduction

The checkout and all development dependencies are retained at /src. The image
uses Node.js 22 and pnpm 10.6.1, generates Prisma's client before building,
and runs the upstream build for the frontend, backend, and orchestrator.
The frontend uses its existing Webpack configuration. Outputs are in
apps/frontend/.next, apps/backend/dist, and apps/orchestrator/dist.
From /src, repeat the build with
pnpm -r --workspace-concurrency=1 --filter ./apps/backend --filter ./apps/orchestrator run build
and pnpm --filter ./apps/frontend run build --webpack; repeat the upstream test
command with pnpm run test --runInBand. Test failures are reported
as warnings during the image build and must not be interpreted as passing tests.

The image provides dummy local environment settings, but does not start
PostgreSQL, Redis, or Temporal. Runtime and integration tests require local
services or mocks. Social APIs, cloud storage, email, billing, and AI providers
must be mocked during the offline audit; use synthetic accounts, tokens, and
media. No real credentials or access to production services are required.

## Findings and scope

Follow the checked-out SECURITY.md for the project's current policy. Focus on
demonstrable confidentiality, integrity, availability, or authorization impact
in supported code and shipped defaults. Dependency issues need an independently
exploitable Postiz call path. Operator misconfiguration, self-XSS, hardening
suggestions without exploitable impact, and resource exhaustion without a
missing common defense are outside that policy's vulnerability definition.

Explain severity using the actual attacker's access, required configuration,
affected organizations and credentials, and demonstrated impact; do not assume
severity solely from a bug class. Include a minimal offline proof of concept,
reproduction steps, affected source locations, and a focused patch with a
regression test where feasible. Keep findings private through the enrollment's
primary contact and CC; do not publish an unpatched issue.
