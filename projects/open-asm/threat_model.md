# Threat model: Open-ASM (oasm-platform/open-asm)

Open-ASM is an AI-powered, open-source Attack Surface Management platform
(https://oasm.dev). It discovers and monitors internet-facing assets (domains,
IPs, ports, services, technologies), runs distributed vulnerability scans via
pluggable tool connectors, and exposes results through a web console, REST API,
and an MCP endpoint for AI assistants. Three tiers: `console/` (React 19 +
Vite), `core-api/` (NestJS 11 REST + gRPC orchestration), `worker/` (Go 1.26
agent that spawns connector containers through the Docker Engine API).
Companion repos: `oasm-connectors` (tool images), `oasm-docker` (production
deploy). License: GPL-3.0 (repo states MIT in package.json; code headers and
GitHub license detection say GPL-3.0 — confirm with maintainers if it matters).

## What this project does and where untrusted input enters

- **REST API consumers** (`core-api/src/modules/*`, 30+ domains: assets,
  vulnerabilities, workspaces, connectors, integrations, storage, mcp, auth,
  apikeys, audit): every request body, query, path param, header, and uploaded
  file is attacker-controlled. DTOs use class-validator, but a validation
  bypass, mass-assignment, or tenant-scoping miss (`@getWorkspaceId`) is in
  scope.
- **Authentication boundary** (`core-api/src/modules/auth/`, better-auth;
  `src/modules/apikeys/`, `src/modules/users/`): session cookies, API keys,
  workspace RBAC roles, audit log. Auth bypass, session fixation/confusion,
  key leakage, or cross-workspace access is critical by definition.
- **MCP endpoint** (`core-api/src/mcp/`: `GET /mcp` + `POST /mcp/message`,
  guarded by `McpGuard`): AI assistants query asset data in natural language.
  Prompt-injection content stored in asset fields (hostnames, service banners,
  tech fingerprints) that escapes its context, or a guard bypass, is in scope.
- **Scan targets and tool output**: the worker pulls connector images
  (`worker/internal/runtime/docker.go`) and runs them against targets; results
  flow back over the connector callback gRPC (`:26276`,
  `worker/internal/connector/`). Malicious target responses (DNS, HTTP
  banners, TLS certs, JS) and hostile tool stdout that break parsing,
  inject commands, or escape containers are in scope.
- **Cloud integrations** (AWS, Cloudflare, Vercel asset pulls; Slack/Telegram
  webhooks; S3-compatible RustFS storage; PDF reports): third-party payloads,
  webhook secrets, signed URLs, and stored scan artifacts are untrusted.
- **Go worker host surface** (`worker/internal/{runtime,execution,grpcclient,
  security,telemetry}`): needs the host Docker socket (root-equivalent),
  persists join identity on disk, auto-sizes concurrency from cgroups. Socket
  misuse, identity confusion after token loss, or command injection into
  spawned containers is in scope.
- **Console** (`console/src/`, TanStack Router + orval-generated Query hooks):
  DOM XSS via asset data rendered in dashboards, maps, graphs, markdown, or
  the AI chat stream is in scope.

## Components that matter most / least

- Most: `core-api` auth/apikeys/workspaces RBAC + tenant scoping, MCP guard,
  file upload/storage paths, `worker/internal/runtime/docker.go` (container
  spawn), connector callback handling, integration secret handling
  (`ENCRYPTION_KEYS` KEK rotation — last key encrypts, rest decrypt-only).
- Less: reporting/PDF rendering, statistics dashboards, Geo-IP enrichment,
  i18n, notification formatting.
- Out of scope: `oasm-connectors` tool images themselves (separate repo),
  third-party dependency CVEs unless reachable through first-party code,
  `console/e2e/` and `**/*.spec.ts` test suites, generated code
  (`console/src/services/apis/gen/`, `routeTree.gen.ts`,
  `worker/internal/gen/`, `.open-api/*`,
  `core-api/resources/connectors/manifest.json`).

## How to exercise it

The image holds the checkout at `/src` with all deps installed and all three
tiers compiled (core-api `dist/`, worker binaries, console `dist/`).
Network is off; Postgres/Redis/RustFS are NOT in the image.

```bash
cd /src
pnpm --filter core-api run test        # jest unit tests (mocked externals)
pnpm --filter core-api run test:e2e    # needs live postgres + redis — will fail offline, shows wiring
cd worker && go test ./...             # Go unit tests
pnpm --filter console run test:run     # vitest single pass
```

`core-api/example.env`, `console/example.env`, `worker/.example.env` show
required config. `docker-compose.yml` is the reference topology (API `:6276`,
gRPC `:16276`, console `:3000`, connector callback `:26276`). DB layer changes
only via TypeORM migrations (`core-api/src/database/migrations/`); `task`
wrappers carry the RAM/CPU limits — run tests through them where possible.

## How you rate severity

- Critical: auth bypass (session, API key, workspace RBAC), cross-workspace
  data access, RCE via connector spawn / tool output / target response,
  container escape from worker-spawned containers, MCP guard bypass leading
  to data exfiltration.
- High: stored XSS via asset/scan data, SSRF through integrations or scan
  config, secrets (API keys, KEKs, webhook tokens) in logs/errors/responses,
  mass-assignment or tenant-scoping miss, path traversal in storage/report
  paths, Docker socket misuse.
- Medium: reflected XSS, information disclosure in default error responses,
  ReDoS / resource exhaustion needing sustained traffic, missing rate limits
  where documented.
- Low: issues needing a malicious operator config, self-XSS, DoS needing a
  privileged caller, defects only in `examples/` or docs.

Prompt injection stored in asset fields is out of scope as model behaviour;
in scope when the MCP/API layer fails to apply an access control it promises.

## Anything to leave alone

- Do not report "the operator mounted docker.sock" — the worker requires the
  host Docker socket by design (documented root-equivalent, trusted images
  only); report socket *misuse*, not its presence.
- Do not report missing auth on `GET /api/health` or the docs endpoints.
- Do not report `test:e2e` failing offline — it needs live Postgres + Redis.
- Do not report findings in generated code or vendored connector manifests;
  patch the generator source instead.
- Reports should include a minimal reproducer (jest spec, `curl` sequence, or
  Go test) against this image and a patch where possible.
