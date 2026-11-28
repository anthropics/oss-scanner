# Threat model

## What this project does and where untrusted input enters

Archestra is a self-hosted platform for running AI agents inside a company. One deployment serves one
organization (a single-tenant model; organization scoping exists in the code but only one organization is
provisioned). It is deployed as a Docker image or a Helm chart: a Fastify backend (port 9000, metrics on 9050),
a Next.js frontend (port 3000), PostgreSQL, and Kubernetes for the workloads it starts (MCP servers, agent
runtimes).

The platform holds high-value secrets: LLM provider API keys, MCP server credentials and OAuth tokens, identity
provider configuration, session and API tokens, and the content of conversations, tool calls and knowledge
bases.

The enrolled code is everything under `platform/`:

- `platform/backend`: the API server, LLM proxy, MCP gateway, A2A gateway, OAuth server, chat, knowledge base,
  webhooks and the built-in Archestra MCP server.
- `platform/frontend`: the Next.js web application.
- `platform/shared`: code shared by both, including the route permission map (`shared/access-control.ts`).
- `platform/archestra-rs`: Rust crates loaded into the backend as N-API addons (sandbox, app runtime, image
  handling, model router, OpenAPPA guardrails bindings).
- `platform/archestra-cli`: the `archestra` command-line program (Rust).
- `platform/helm`, `platform/docker`, `platform/Dockerfile`: how it is deployed.

Attackers we care about, from least to most privileged:

1. **Anonymous network clients.** They reach the routes that the authentication middleware exempts
   (`backend/src/auth/fastify-plugin/middleware.ts`): sign-in and Better Auth routes under `/api/auth`,
   invitation checks, the OAuth authorization server and its `.well-known` metadata, public identity-provider
   listing, client-connection setup and polling, CLI downloads, the skill marketplace, health checks, and
   webhooks (chat platforms, incoming email, Jira). Each exempt route has its own authentication contract
   (signature, token, one-time code); a route that is exempt and then fails to enforce its contract is a finding.
2. **Holders of a gateway credential.** The MCP gateway (`/v1/mcp/...`), the LLM proxy and the A2A gateway
   authenticate with their own bearer tokens, virtual API keys, OAuth access tokens or workload identity, not
   with a session. A token must only reach the agent, gateway, tools and provider keys it was issued for.
3. **Authenticated members.** Sessions (Better Auth) and API keys. Access is governed by roles (predefined and
   custom), per-route permissions, teams and scoped grants. A member must not read or change resources of a
   team they are not in, raise their own role, grant a permission they do not hold, or read stored secrets.
4. **Content the agents process.** Model output, MCP tool results, knowledge-base documents, chat attachments,
   incoming email and chat-platform messages are all untrusted, and may be written by someone outside the
   organization. See "Prompt injection" below for what counts.
5. **Code inside a sandbox or workload.** Skill sandbox commands, MCP server pods and agent runtime pods run
   code the platform does not trust. It must not reach the backend's secrets, the database, another user's
   sandbox, or the host.

Administrators are trusted. An administrator can install MCP servers, configure providers and identity
providers, and run code in the cluster by design.

## Components that matter most / least

Most important:

- **Authentication and authorization**: `backend/src/auth`, the exemption list in the middleware, the
  permission map in `shared/access-control.ts`, custom roles, teams, scoped grants, API keys, service accounts,
  SSO and identity providers, two-factor enforcement, invitations.
- **The OAuth server and OAuth clients**: `backend/src/routes/oauth*.ts` and related code. Redirect URI
  validation, issuer binding, PKCE, token audience and scope, dynamic client registration, consent.
- **MCP gateway and proxies**: `backend/src/routes/mcp-gateway`, `mcp-proxy.ts`, `mcp-server-proxy.ts`,
  `mcp-app-proxy.ts`. Token-to-agent binding, tool access checks, credential resolution for the upstream
  server (one user must never use another user's upstream credential), and the built-in Archestra MCP tools,
  which enforce role permissions per tool (`backend/src/archestra-mcp-server/rbac.ts`).
- **LLM proxy**: `backend/src/routes/proxy` and `llm-proxy`. Virtual key and provider key handling, cost limits,
  request and response translation between providers, streaming.
- **Secret storage and encryption**: `backend/src/secrets-manager`, `backend/src/content-encryption`. Secrets
  must not appear in API responses, logs, audit records, telemetry or error messages.
- **Outbound requests with a user-supplied destination**: remote MCP server URLs, OAuth discovery, knowledge
  connectors, webhooks, catalog and image fetches, git hosts. Server-side request forgery to cluster-internal
  services or cloud metadata, including through redirects and DNS, matters here.
- **Sandboxes and workloads**: `backend/src/skills-sandbox`, `backend/src/sandbox-runtime`, `backend/src/k8s`,
  `archestra-rs/sandbox-core`, `archestra-rs/app-runtime-core`. Escape, cross-user access, path traversal in
  file upload and download, and what Kubernetes objects a member can cause the backend to create.
- **Guardrails**: `backend/src/openappa` and `archestra-rs/openappa-rs`. A way to make the proxy or gateway skip
  a policy that is configured and should apply is a finding.
- **Webhooks and channels**: `backend/src/routes/chatops*`, `incoming-email.ts`. Signature verification, replay,
  and the mapping from an external identity to an Archestra user.
- **Rust code that parses untrusted bytes**: `archestra-rs/image-core` (images from chat and tools) and
  `archestra-rs/router-core`. Memory safety matters in any `unsafe` block and at the N-API boundary; a panic
  that takes down the backend process is a denial of service.
- **Frontend**: cross-site scripting through rendered model output, tool results, MCP app content (which must
  stay inside its sandboxed frame), Markdown, and white-label settings; cross-site request forgery; open
  redirects in sign-in flows.

Less important, still in scope:

- `platform/archestra-cli`, `platform/helm` defaults, `platform/docker`.

Out of scope:

- `platform/e2e-tests`, `platform/benchmarks`, `platform/dev`, `platform/tools`, `platform/docs-screenshots`,
  test files and fixtures, and everything outside `platform/` (`ai-labs/`, `docs/`, `mcp-catalog/`,
  `migration-kit/`).
- `platform/archestra-rs/vendor/` (a vendored third-party SDK) unless Archestra's own use of it is exploitable.
- The OpenAPPA core, which lives in its own repository (https://github.com/archestra-ai/OpenAPPA) and is fetched
  by cargo. Only the bindings in `archestra-rs/openappa-rs` are in scope here.
- Third-party MCP servers, LLM providers and identity providers themselves.
- Development-only code paths that are disabled when `NODE_ENV=production`, such as the dev auto-login plugin
  (`backend/src/auth/dev-auto-login.ts`). A way to reach one in a production build is in scope.
- The quickstart defaults: `ARCHESTRA_AUTH_SECRET`, the `admin@example.com` / `password` administrator and the
  database password in `.env.example` are documented placeholders for local use.

## Prompt injection

Agents read untrusted content, so a model can be talked into calling a tool. That alone is not a vulnerability
in Archestra: it is the problem the guardrails exist to manage. Report it only when the platform breaks a
boundary it claims to enforce, for example:

- a tool call runs although a configured guardrail policy should have blocked it;
- untrusted content makes the platform use a credential, tool, agent or team resource that the acting user or
  token may not use;
- model output or a tool result leads to script execution in the web application, a request to an internal
  address, or a write outside the sandbox.

## How to exercise it

The checkout is at `/src`; work from `/src/platform`. The image has Node.js 24, pnpm, the Rust toolchain from
`rust-toolchain.toml`, every npm and cargo dependency, and PostgreSQL 18 with pgvector. There is no Kubernetes,
Docker or Dagger, so MCP server installs, agent runtimes and sandbox execution cannot run end to end; review
that code statically or through its unit tests. LLM providers, identity providers and remote MCP servers must
be mocked.

Already built: `backend/dist` (start with `backend/dist/server.mjs`), `frontend/.next` with a standalone server
in `frontend/.next/standalone/frontend`, and the five N-API addons (`archestra-rs/*-rs/*.node`).

Run the stack:

```bash
archestra-db start                      # PostgreSQL as archestra@127.0.0.1:5432/archestra_dev, already migrated
cd /src/platform/backend && node dist/server.mjs &                # API on :9000, reads /src/platform/.env
cd /src/platform/frontend/.next/standalone/frontend \
  && PORT=3000 HOSTNAME=127.0.0.1 NODE_ENV=production node --env-file=/src/platform/.env server.js &
```

The seeded administrator is `admin@example.com` with password `password`. API keys are sent as
`Authorization: <key>` (no `Bearer`); gateway tokens as `Authorization: Bearer <token>`. `/openapi.json` on the
backend lists the API.

Tests:

```bash
cd /src/platform/backend && pnpm exec vitest run src/routes/api-key.test.ts   # one file; uses in-memory PGlite
cd /src/platform/shared && pnpm test
cd /src/platform/archestra-rs && cargo test --locked -p image_core            # any workspace crate
```

Backend tests use a real in-memory database (PGlite) and fixtures from `backend/src/test`; a proof of concept
is most convincing as a test next to the route or model it attacks. Rebuild the backend after a change with
`cd /src/platform/backend && ./node_modules/.bin/tsdown`.

## How you rate severity

Rate by what the attacker starts with and what they end with, not by the class of bug.

- **Critical**: an anonymous client, or a holder of only a gateway or proxy token, gets administrator access,
  remote code execution in the backend, or stored secrets (provider keys, MCP credentials, OAuth tokens,
  signing or encryption secrets). Authentication bypass on the API. Sandbox or workload escape to the backend,
  the database or the cluster.
- **High**: an authenticated member does any of the above, or reads or changes another team's or user's
  agents, conversations, credentials, knowledge bases or logs. Use of another user's upstream credential.
  Server-side request forgery that reaches cluster-internal services or cloud metadata. Stored cross-site
  scripting that runs in another user's session. A guardrail policy bypass with no user interaction. Memory
  corruption in the Rust addons reachable from untrusted input.
- **Medium**: authorization gaps limited to metadata or to resources of the same team; reflected cross-site
  scripting or request forgery needing user interaction; secrets written to logs, audit records or telemetry;
  denial of service of the whole backend by one unauthenticated or low-privilege request (including a Rust
  panic or unbounded memory use); cost-limit or usage-limit bypass.
- **Low**: information disclosure without security impact, missing hardening with a plausible but unproven
  attack, denial of service that needs administrator rights or only affects the attacker's own session.

Anything that needs administrator rights is at most low unless it crosses out of the product (for example, an
administrator of Archestra gaining control of the Kubernetes cluster beyond what the configured service account
allows).

## Anything to leave alone

- Vulnerable dependency versions without a call path in Archestra that reaches the flaw. Dependencies are
  tracked separately (Dependabot, image scanning, `pnpm-workspace.yaml` overrides, `archestra-rs/deny.toml`).
- Missing rate limiting, missing security headers or weak password policy on their own.
- Self cross-site scripting, and issues that need a compromised administrator, database or Kubernetes cluster.
- Findings that depend on the documented placeholder secrets of a local quickstart.
- Enterprise-licensed files (`*.ee.ts` and code marked per `LICENSE.md`) are in scope; do not treat the
  license check itself as a security boundary.
