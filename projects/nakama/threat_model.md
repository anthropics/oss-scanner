# Threat model

The full model is `THREAT_MODEL.md` at the repo root (the image drops `*.md`
files through `.dockerignore`, so read it from the repo). This is the short version.

## What Nakama does and where untrusted input enters
- A multi-tenant agent server (Bun + Hono, SQLite). Orgs are tenants; each holds profiles, sessions, tools, MCP servers, skills and secrets.
- Untrusted input: HTTP API (`apps/server/src/http/`), channel webhooks and bots (`apps/platform/{telegram,whatsapp,discord,slack,teams}`), uploaded files and attachments, public artifact share links, and model output (prompt injection from web pages, email and documents the agent reads).

## Components that matter most
- Tenant boundary: `X-Org-Id` / `active_org_id` handling in `org-middleware.ts` and `org-guards.ts`. Any read or write of another org's data is in scope.
- Auth and roles: `routes/auth.ts`, `requireOrgAdmin` / `requireOrgMember`, platform-admin routes under `/v1/platform/*`.
- Tool execution: `packages/core/src/tools/`, `apps/server/src/tools/`, `buildToolExecutionContext`. Path escapes out of the profile workspace (`~/.nakama/orgs/{orgId}/profiles/{profileId}/`) are in scope.
- Secrets: provider API keys, channel tokens, Composio and MCP credentials. Any leak across orgs or to a non-admin user is in scope.
- Public artifact shares and file serving.

## Out of scope
- Code that an org admin deliberately runs: the `bash` tool, custom JS/Python tools, stdio MCP servers, plugins and coding agents run with host rights by design. Report only when a user without that permission can trigger them.
- Bugs inside external providers (LLM, channel, SaaS, MCP).
- `docs/`, `design-plans/`, test fixtures.

## How to exercise it
- `bun test` runs the unit and route tests. Route tests build the Hono app in-process, so you can call endpoints without a network.
- `bun run dev:server` starts the API on the local host.

## How we rate severity
- Critical: unauthenticated access to any org data or secrets, or unauthenticated command execution.
- High: cross-org read or write by an authenticated user; a member gaining admin or platform-admin rights; secret leak to another org; a non-admin running shell or custom tools.
- Medium: same-org privilege issues (member reading admin-only data), stored XSS in the dashboard, SSRF from tools that need admin setup.
- Low: information leaks with no secrets, DoS.
