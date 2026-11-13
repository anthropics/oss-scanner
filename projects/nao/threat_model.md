# Threat model

## What this project does and where untrusted input enters

nao is a self-hosted framework for building and deploying analytics agents. A data team describes a
"context" (database connections, metadata, documentation, rules, skills, MCP servers) with the `nao-core`
Python CLI, then deploys a chat UI where business users ask questions in natural language. An LLM agent
answers by reading the context, running SQL against the customer's data warehouse, executing Python in a
sandbox, drawing charts and calling MCP tools.

Three kinds of actors interact with a deployment:

- **Administrators / data team** run the CLI (`cli/nao_core`), author the context and manage the
  organisation, projects, members, warehouse credentials and LLM keys through the settings UI.
- **Authenticated end users** (members of an organisation, possibly in different user groups with
  different permissions) chat with the agent through the web UI, Slack, Microsoft Teams, Telegram,
  WhatsApp or Mattermost, and through the MCP server nao exposes. They may also view shared chats and
  published "stories" (dashboards).
- **Unauthenticated parties** reach the login/sign-up pages, SSO/OIDC callbacks, public share links,
  embed endpoints, the Stripe webhook, automation webhooks, messaging platform webhooks and the
  `cli-auth` device flow.

Untrusted input enters through:

- Every HTTP route under `apps/backend/src/routes/` and every tRPC procedure under
  `apps/backend/src/trpc/`. Authentication is better-auth (`apps/backend/src/auth.ts`); organisation,
  project and user-group scoping is enforced in services and queries.
- The agent loop (`apps/backend/src/services/agent.ts`, `apps/backend/src/agents/`). User prompts, chat
  attachments, and anything the LLM reads (warehouse data, context files, web search results, MCP tool
  output) are untrusted and may contain prompt injection. The LLM's tool calls are therefore also
  untrusted input to the tool implementations in `apps/backend/src/agents/tools/`.
- Agent tools that touch the filesystem (`read`, `write`, `str-replace`, `grep`, `list`, `search`,
  `load-skill`) must stay inside the project's context directory; path traversal out of it is a
  vulnerability.
- Agent tools that run code or queries: `execute-sql` and `execute-semantic-query` (run against the
  customer's warehouse through the FastAPI sidecar in `apps/backend/fastapi/` and `cli/nao_core`),
  `execute-python` / `execute-sandboxed-code` (run in a sandbox, see
  `apps/backend/src/services/sandbox-runtime.ts`), `query-app-db` (read-only, allow-listed access to
  nao's own application database), `mcp-call` / `mcp-connect` (outbound calls to configured MCP servers),
  `web-search`.
- The MCP server nao exposes to external clients (`apps/backend/src/mcp/`), including its OAuth flow and
  JWT verification.
- Messaging integrations (`apps/backend/src/routes/{slack,teams,telegram,whatsapp,mattermost}.ts`,
  `apps/backend/src/utils/messaging-provider.ts`): webhook signature verification and mapping of
  external identities to nao users.
- Git-backed context (`NAO_CONTEXT_SOURCE=git`, GitHub/GitLab routes) and context editing from the UI
  (`context-explorer` routes and services): writes must stay within the project repository.
- The Python CLI parses `nao_config.yaml`, connects to warehouses through ibis, syncs metadata from
  Notion/Confluence/dbt, and renders Jinja templates. Config files and synced content are
  administrator-controlled but should not enable template injection or arbitrary code execution beyond
  what the administrator intends.
- Rendering of agent output in the frontend (`apps/frontend/`): markdown, charts, maps, HTML stories and
  custom chart modules are LLM-generated and must not lead to XSS in other users' browsers, in particular
  on shared chats, published stories and embeds.

## Components that matter most / least

Most important, in order:

1. Authorization boundaries: organisation and project isolation, user-group permissions, admin-only
   settings, share-link and embed access control, backoffice API key, billing routes.
2. Secret handling: warehouse credentials, LLM API keys, SSO client secrets and license keys stored in
   the application database or environment; they must never be exposed to end users, the LLM, or logs.
3. Tool sandboxing: filesystem tools confined to the context directory, Python execution confined to
   the sandbox, SQL execution limited to the configured warehouse connection, `query-app-db` limited to
   its allow-list.
4. Authentication: better-auth configuration, OIDC/SSO flows, CLI device-auth flow, MCP OAuth, webhook
   signature checks.
5. Stored/reflected XSS and CSRF in the frontend and in server-rendered content (chart images, story
   HTML, email templates).
6. SSRF from server-side fetches driven by user or LLM input (MCP connect, web search, image/attachment
   fetching, Notion/Confluence sync).

Lower priority or out of scope:

- `sandbox/`, `example/`, `skills/`, `helm/`, `docker/`, `scripts/` are development, deployment and
  sample assets, not runtime attack surface.
- Third-party dependencies in `node_modules` and the Python virtualenv are out of scope unless nao
  misuses them.
- Denial of service by an authenticated user issuing expensive LLM or SQL requests is expected
  behaviour (deployments are internal, usage is metered); only report DoS that is unauthenticated or
  crashes the server for everyone with a single request.
- The agent producing wrong analytics is a quality issue, not a security one.

## How to exercise it

- JS dependencies are installed at `/src/node_modules`; the Python environment is at `/src/cli/.venv`
  (`cd /src/cli && uv run ...`).
- Backend unit tests: `cd /src && npm run -w @nao/backend test` (vitest, uses SQLite, no services needed).
- CLI tests: `cd /src/cli && uv run pytest`.
- Start the API: `cd /src/apps/backend && bun src/index.ts` (port 5005, SQLite at
  `/src/apps/backend/db.sqlite`, configuration read from `/src/.env`, migrations already applied).
  The frontend bundle is in `/src/apps/frontend/dist`; `cd /src && npm run dev:frontend` serves the
  frontend with HMR on port 3000.
- Start the SQL sidecar: `cd /src && npm run dev:fastapi` (port 8005, uses the bundled example project
  at `/src/example`, which includes a DuckDB file so queries work offline).
- No LLM key works offline. Tool implementations and the agent loop can be exercised directly from
  tests or small Bun scripts rather than through a live model.

## How you rate severity

- Critical: unauthenticated remote code execution; reading or writing another organisation's data;
  retrieval of stored warehouse credentials, LLM keys or SSO secrets by a non-admin; authentication
  bypass.
- High: authenticated escape from the context directory or the Python sandbox onto the host; SQL
  execution against a warehouse the user is not entitled to; privilege escalation from member to admin
  within an organisation; SSRF reaching internal networks with response disclosure; stored XSS that
  fires for other users (shared chats, stories, embeds).
- Medium: cross-project information disclosure within one organisation; CSRF on state-changing
  endpoints; missing webhook signature verification; blind SSRF; self-XSS that requires a crafted
  share link.
- Low: information disclosure limited to non-sensitive metadata, missing rate limiting, verbose
  errors, issues that require an already-compromised administrator.

Prompt injection that merely changes the agent's answer is not a vulnerability. Prompt injection that
makes a tool cross one of the boundaries above is rated by the boundary it crosses.

## Anything to leave alone

- Do not report that administrators can configure arbitrary warehouse connections, MCP servers, LLM
  endpoints or context repositories: that is the product.
- Do not report `NAO_LICENSE_PUBLIC_KEY` being overridable in development builds; the production Docker
  image strips that code path (`docker/lock-license-key.mjs`).
- Do not report the development `sandbox/` tooling or the seeded test databases.
- Reports and patches: a reproduction as a vitest or pytest test, or a curl sequence against a
  locally started backend, is ideal. Patches should follow the repository conventions in `CLAUDE.md`.
  The project's disclosure policy is in `SECURITY.md`.
