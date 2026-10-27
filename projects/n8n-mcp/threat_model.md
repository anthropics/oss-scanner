# Threat model: n8n-mcp

The full STRIDE threat model is in the repository at `docs/THREAT_MODEL.md`, and the disclosure scope is in
`SECURITY.md`. This file summarises what matters for an automated scan.

## What this project does and where untrusted input enters
n8n-mcp is a Model Context Protocol server. It serves n8n node documentation and workflow validation from a
bundled read-only SQLite database (`data/nodes.db`), and, when configured with an n8n URL and API key, proxies
workflow, execution, credential, datatable and folder management to the n8n REST API.

Deployment modes:
- **stdio**: launched by a local AI client. The caller is trusted; there is no network surface.
- **HTTP single-tenant** (`MCP_MODE=http`): Express server gated by a bearer `AUTH_TOKEN`.
- **HTTP multi-tenant** (`ENABLE_MULTI_TENANT=true`): each request carries its own n8n URL and API key in
  headers (`x-n8n-url`, `x-n8n-key`, `x-instance-id`, `x-session-id`). One process serves many tenants.
- **Embedded**: other services import `N8NMCPEngine` / `N8NDocumentationMCPServer` and pass an instance
  context per call (`src/mcp-engine.ts`).

Untrusted input:
- Anything reaching the HTTP server before authentication (headers, body, path, session ids).
- In multi-tenant mode, every tenant is untrusted with respect to every other tenant, and tenant-supplied
  n8n URLs are attacker-controlled (SSRF target selection).
- MCP tool arguments. The AI client may be acting on prompt-injected workflow text, so treat tool arguments
  as attacker-influenced (workflow JSON, node parameters, expressions, URLs, ids, search strings).
- Responses from the n8n instance and from api.n8n.io (templates) are data, not code.

## Components that matter most
- `src/http-server-single-session.ts`, `src/http-server.ts`, `src/utils/auth.ts`: authentication, session
  creation/restore, session-to-credential binding, rate limits.
- Tenant isolation: anything keyed by session or instance id (`src/mcp/`, `src/services/n8n-api-client.ts`,
  instance context handling, the `workflow_versions` local store, caches).
- `src/utils/ssrf-protection.ts` and every outbound request built from a user-supplied URL.
- Secret handling: `src/utils/redaction.ts`, `src/services/node-sanitizer.ts`, error sanitisation, logs,
  and `src/telemetry/` (opt-in anonymous telemetry must never carry credentials, workflow content or
  user-identifying strings).
- `src/database/`: SQL built from tool arguments (FTS5 queries, filters).
- `src/services/workflow-diff-engine.ts` and validators: they process attacker-shaped workflow JSON
  (prototype pollution, ReDoS, unbounded recursion).

Less important, still in scope: `src/scripts/` (maintenance CLIs run by the maintainer), `ui-apps/`
(self-contained HTML cards rendered by the MCP client; XSS from tool output into the card is in scope).

## How to exercise it
- `npm run build` compiles `src/` to `dist/`. `npm start` runs stdio mode; `MCP_MODE=http AUTH_TOKEN=<32+ chars>
  npm run start:http` runs HTTP mode on port 3000; add `ENABLE_MULTI_TENANT=true` for multi-tenant.
- `npm run test:unit` runs the offline vitest suite (`tests/unit/`). A single file:
  `npx vitest run tests/unit/<path>.test.ts`.
- Management tools need a live n8n; in this image there is none. Reproducers for management-path bugs can
  use a local stub HTTP server as the n8n URL (tests under `tests/unit/` show the pattern with msw).

## How we rate severity
- **Critical**: unauthenticated access to the HTTP server's tools, or one tenant obtaining another tenant's
  n8n API key in multi-tenant mode.
- **High**: one tenant reading or modifying another tenant's data or routing calls to another tenant's
  n8n instance; authenticated RCE in the n8n-mcp process; disclosure of `AUTH_TOKEN` or n8n API keys to the
  MCP client, logs at default level, or telemetry.
- **Medium**: SSRF that bypasses `ssrf-protection.ts` to reach private or cloud-metadata addresses;
  leakage of workflow content or other user data into telemetry; stored XSS in UI app cards.
- **Low**: DoS through crafted input (ReDoS, unbounded memory) on the HTTP server; information disclosure
  of non-secret internal state.
- stdio-mode issues where the only attacker is the process that launched the server are not
  vulnerabilities.

## Anything to leave alone
- Capabilities n8n itself grants through its REST API (creating Code nodes, executing workflows, reading
  credentials the API key can read). n8n-mcp adds no privilege beyond the configured API key.
- Generic LLM prompt-injection risk that applies to every MCP server.
- `data/*.db` content (public n8n documentation and templates).
- `tests/`, `scripts/` at the repository root, `docker/` test compose files, and dev dependencies.
- Dependency CVEs without a reachable path through n8n-mcp code.
- Please keep patches minimal, in the existing style, with a regression test under `tests/unit/`.
