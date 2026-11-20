# GROWI threat model for scanner reports

## What this project does and where untrusted input enters

GROWI is a self-hosted team wiki (Next.js frontend, Express/Node.js server, MongoDB, optional Elasticsearch/OpenSearch).
Organizations run it on-premises or in their own cloud, often exposed to the Internet.

Untrusted input enters through:

- HTTP API (`apps/app/src/server/routes`, mainly `/_api/v3/*`) and page routes, from anonymous visitors, guests, and
  logged-in users of every role.
- Markdown page bodies, comments, inline comments, templates, and page paths written by users, which are rendered to
  HTML for every reader (remark/rehype pipeline, `packages/remark-*`, drawio / mermaid / PlantUML / Marp presentation).
- Attachments and images uploaded by users and served back to other users.
- Real-time collaborative editing (Yjs over WebSocket) and Socket.IO events.
- Authentication flows: local, LDAP, SAML, OIDC, GitHub/Google OAuth, and personal access tokens.
- Integrations: Slack (slash commands and events, also via `apps/slackbot-proxy`), GROWI-to-GROWI transfer (g2g),
  imports, and outgoing webhooks / global notifications.
- AI features (`features/ai-tools`, `features/mastra`): user content and prompts passed to an LLM provider.

## Components that matter most / least

Most important:

- Authorization: page grants (public / restricted link / only me / user group), ACL, user groups and external user
  groups, share links, admin-only routes, and access-token scopes. Reading or changing a page, attachment, revision,
  comment, or setting that the caller's role and the page grant should not allow is the core concern.
- Authentication and session handling, including account linking with external IdPs, password reset, invitation and
  activation flows.
- XSS in rendered Markdown, page titles/paths, comments, notifications, and attachments served inline.
- SSRF and file-system access from features that fetch URLs or write files (g2g transfer, imports, PlantUML/drawio,
  file uploaders, bulk export, plugin installation).
- Injection into MongoDB queries (operator injection), Elasticsearch queries, or shell commands.

Less important but in scope: `apps/pdf-converter`, `apps/slackbot-proxy`, `apps/growi-vault-manager`, and the
workspace packages under `packages/`.

Out of scope: test code, `apps/app/playwright`, `.devcontainer`, CI workflows, and documentation.

## How to exercise it

The image contains `/src` with all dependencies installed and `apps/app` built (`.next/` and `dist/`).

- Unit tests: `cd /src/apps/app && pnpm run test:unit` (or `pnpm vitest run <file name>`).
- Integration tests use mongodb-memory-server with the pre-downloaded MongoDB 6.0.9 binary:
  `cd /src/apps/app && pnpm vitest run --project=app-integration <file name>`. Elasticsearch is not available.
- Running GROWI locally: start MongoDB as a single-node replica set
  (`mkdir -p /tmp/db && mongod --replSet rs0 --dbpath /tmp/db --bind_ip 127.0.0.1 --fork --logpath /tmp/mongod.log`),
  initiate it from Node with the `mongodb` driver (`replSetInitiate`; `mongosh` is not installed), then run
  `cd /src/apps/app && MONGO_URI='mongodb://127.0.0.1:27017/growi?replicaSet=rs0' pnpm run server` and complete the
  installer at `http://localhost:3000/installer` to create the first admin.

## How we rate severity

- Critical: unauthenticated RCE; unauthenticated full account takeover or admin takeover; unauthenticated read of
  arbitrary non-public pages or attachments at scale.
- High: authenticated RCE; privilege escalation to admin; bypass of page grants or user-group restrictions that lets a
  user read or modify pages they should not; stored XSS that runs for other users without unusual interaction; SSRF that
  reaches internal networks or cloud metadata.
- Medium: reflected XSS; stored XSS that needs admin-only input or unusual victim interaction; IDOR limited to metadata;
  CSRF on state-changing endpoints; DoS reachable by an unauthenticated user.
- Low: information disclosure with little impact, DoS requiring authentication, issues that need a malicious
  administrator.

Administrators are trusted: issues that require admin privileges (installing plugins, editing customize scripts/CSS,
configuring external services) are normally out of scope unless they cross a tenant or privilege boundary.

## Anything to leave alone

- Vulnerabilities only in third-party dependencies with no GROWI-specific reachable path.
- Missing security headers or rate limits without a concrete exploit.

## How we would like reports

A reproducible request sequence or test case, the minimal role needed (anonymous / guest / read-only / user / admin),
required settings, and a proposed patch. English or Japanese are both fine.
