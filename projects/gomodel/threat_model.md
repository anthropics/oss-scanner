# Threat model: GoModel

## What this project does and where untrusted input enters

GoModel (`github.com/enterpilot/gomodel`, the `main` branch) is an AI gateway: one Go binary that exposes OpenAI-compatible and Anthropic-compatible HTTP APIs and routes each request to an upstream provider (OpenAI, Anthropic, Gemini, Bedrock, Azure, Ollama, vLLM and others). It also has an admin API with an embedded Svelte dashboard, an MCP gateway that aggregates upstream MCP servers, budgets, rate limits, response caching, guardrails, audit and usage logs, and a plugin system. Teams deploy it as the single place that holds provider keys, so the gateway's job is to keep those keys, other tenants' data and the admin plane away from callers.

Treat as attacker-controlled:

- **API clients holding a managed key** (`sk_gom_...`, `internal/authkeys`). A key can be bound to a user path, a model allowlist, an expiry, and flags for dashboard and passthrough access. Its holder is an attacker who wants more than the key allows.
- **Unauthenticated network clients** when a credential is configured (`GOMODEL_MASTER_KEY` or managed keys), including browsers on other origins (DNS rebinding, cross-site requests and WebSockets).
- **Every request part**: JSON bodies for chat, responses, embeddings, messages and batches; multipart uploads (files, audio, image edits); batch JSONL; gzip/zstd request bodies; the realtime WebSocket and WebRTC SDP; `/mcp` JSON-RPC; and the passthrough route `/p/{provider}/*`.
- **Headers the gateway acts on**: `Authorization`, `x-api-key`, `X-GoModel-User-Path`, session headers (`X-Session-Id` and the other client-specific ones), `X-GoModel-Interaction-Parent`, `X-MCP-Servers`, `X-MCP-Tool-Discovery`, tagging headers, `x-litellm-tags`, `X-Forwarded-For` and the configured client-IP header.
- **Upstream provider and MCP server responses**: SSE streams, JSON bodies, error bodies, and realtime frames. A compromised or hostile upstream must not be able to read another tenant's data, corrupt state, or exhaust the gateway.
- **Content shown in the dashboard**: prompts, responses, tool calls and headers from audit logs and live logs. The dashboard keeps the bearer credential in `localStorage`, so XSS there is credential theft.

Trusted: the operator, environment variables and config files, the master key holder, `.so` plugins loaded from `PLUGINS_SEARCH_PATHS`, the storage backend (SQLite, PostgreSQL, MongoDB), proxies listed in `SERVER_TRUSTED_PROXIES`, and the host filesystem.

### Defaults decide severity

- **No credential configured means open mode.** If `GOMODEL_MASTER_KEY` is unset and no managed keys exist, every route is open, including `/admin/*` and `/mcp`, and the gateway logs a warning. This is intended and is not a finding. `MASTER_KEY_DISABLED=true` makes the gateway fail closed.
- **Open without authentication, by design:** `/health`, `/health/ready`, `/version`, and the dashboard's static assets. Also, only when the operator enables them: the metrics path, `/swagger/*` and `/debug/pprof/*`.
- **Inbound limits:** `BODY_SIZE_LIMIT` is 10M and applies after decompression. `ReadTimeout` is 30s, `ReadHeaderTimeout` 10s, `STREAM_STALL_TIMEOUT` 60s.
- **Forwarding headers:** `SERVER_TRUSTED_PROXIES` is empty, so forwarding headers are ignored.
- **Off by default:** CORS (there is none), TLS (terminate at a proxy), and plugins (`PLUGINS_ENABLED`).
- **On by default:** passthrough, realtime, MCP, LiteLLM tags, and request and response body logging (with header redaction).
- **Encryption at rest is opt-in** (`GOMODEL_ENCRYPTION_KEY`). Plaintext secrets in the database without it are documented and are not a finding.

## What GoModel promises (a violation is a finding)

1. **Authentication.** With a credential configured, no route outside the open list above answers without a valid credential. A credential that the master key, a managed key or an extension authenticator rejects never reaches a provider.
2. **Key scoping.** A managed key never exceeds what it was granted. That covers its model allowlist and every ancestor's allowlist on its user path, provider access for model-less calls (`ValidateProviderAccess`), passthrough access, dashboard access, MCP `allowed_tools`, expiry and enabled state, budgets, and rate limits. A key bound to a user path cannot change that path with `X-GoModel-User-Path`.
3. **Admin plane.** Without `DashboardAccess`, a key gets nothing from `/admin/*`. A key scoped to a user path cannot read or change anything outside its subtree: keys, users, budgets, usage, audit logs, files and media. It also cannot reach gateway-wide settings (`RequireGlobalScope`): provider credentials, MCP servers, guardrails, workflows, runtime settings and virtual models. When a master key is set, only the master key can create or repoint secret references (`${env:...}`, `${file:...}`).
4. **Tenant isolation.** Files, batches, stored responses, conversations, sessions, response-cache entries (exact and semantic) and media belong to the user path that created them. Another user path cannot read, list, replay or evict them, including through a cache key collision.
5. **No secret disclosure.** Provider API keys, the master key, managed key tokens, MCP and guardrail credentials, proxy passwords, encryption keys and resolved secret-reference values never appear in a response, an error, a log line, an audit entry, a metric or the dashboard. Upstream base URLs are not shown to API clients.
6. **The MCP origin guard.** `/mcp` refuses any request that carries `Origin` or `Sec-Fetch-Site` from an origin not in `MCP_ALLOWED_ORIGINS`.
7. **Bounded work.** No single request, upstream stream or MCP response can make the gateway use memory or goroutines without bound, hang past its timeouts, or panic the process.
8. **Translation fidelity.** Translating between OpenAI, Anthropic and provider-native formats never lets a client smuggle a field past a check. That includes duplicate JSON keys, a `model` that differs between the check and the upstream request, and a passthrough body that the gateway and the provider read differently.

The documentation in `docs/` states intended behavior. Where it says something is the operator's responsibility or a documented caveat (for example the audio.cpp passthrough exposing server-local paths when opted in), that is not a finding.

## Components that matter most / least

Most important, in order:

1. **Authentication and authorization**: `internal/server/auth.go`, `internal/server/http.go` (route wiring and skip lists), `internal/authkeys`, `internal/users`, `internal/virtualmodels/authorize.go`, `internal/admin/scope.go`, `internal/admin/routes.go`, `ext/auth.go`, `config/secrets_writer.go`.
2. **The MCP gateway and realtime**: `internal/mcpgateway` (origin guard, tool filtering, internal headers stripped from clients), `internal/realtime`, `internal/server/realtime_*`.
3. **Passthrough and translation**: `internal/server/passthrough_*`, `internal/anthropicapi`, `internal/server/messages_*`, `internal/providers/*`, `internal/streaming`.
4. **Per-tenant stores and caches**: `internal/filestore`, `internal/batch`, `internal/responsestore`, `internal/conversationstore`, `internal/session`, `internal/responsecache`, `internal/blobstore`, `internal/mediastore`.
5. **Budgets, rate limits and client IP**: `internal/budget`, `internal/ratelimit`, `internal/server/clientip.go`, `config/clientip.go`.
6. **Logging and redaction**: `internal/auditlog`, `internal/usage` (including the SQL readers), `internal/core/credential_headers.go`, `internal/core/url_redaction.go`, and the admin secret redaction.
7. **The dashboard** (`web/dashboard`): any path where log or model content is rendered as HTML.

Less important but in scope: `internal/guardrails`, `internal/workflows`, built-in plugins in `internal/plugins/builtin`, `internal/encryption`, `internal/litellmmigrate`, `internal/modeldata`, `internal/versioncheck`.

Out of scope: `_test.go` files, `tests/`, `internal/echotest`, `internal/testconventions`, `docs/`, `helm/`, `tools/`, `recordapi/`, `cmd/recordapi`, `.github/`, generated code (`cmd/gomodel/docs`, `docs/openapi.json`), and the built dashboard bundle `internal/admin/dashboard/static/dist`.

Not findings:

- Anything that requires the master key, a global-scope admin credential, operator config or a malicious `.so` plugin. For example, an admin pointing a provider `base_url`, an MCP server or a guardrail URL at an internal address is intended.
- Anything that requires open mode.
- Prompt injection against the upstream model.
- Flaws wholly inside a third-party module, unless a default GoModel deployment is exposed. Then report it here, name the module, and give the reproducer against GoModel.

## Bug classes seen here (hunt for variants)

Pull request numbers appear in commit subjects (`git log --grep '#1096'`); the full history is in `/src/.git`.

1. **An identity or user path not enforced on one surface.** #1096 (MCP, realtime, audio), #536 (user path in MCP headers), #868 (admin scoping), #804 (model allowlists), #1156 (`allowed_tools` on Responses), #1230 (`ValidateProviderAccess`). Siblings: every handler that reads `X-GoModel-User-Path` or the authenticated identity; batches, files and passthrough; new routes added since.
2. **Cross-origin access to an authenticated surface.** GHSA-2qr4-ww3x-mq4g (DNS rebinding against `/mcp`; see the `retract` in `go.mod`). Siblings: the realtime WebSocket, which accepts any origin; the admin API; extension cookie authentication.
3. **Secret-reference privilege escalation.** #1166, #1169, #1162, #1167, #1148. Siblings: any admin write that stores or resolves `${env:...}` or `${file:...}`, and every path that echoes a resolved value back.
4. **Credential leaks into responses or logs.** #452, #850, #967. Siblings: error wrapping in provider adapters, MCP dial errors, audit capture of upstream requests, live logs.
5. **Resource exhaustion.** #94, #497, #258. Siblings: stream converters, decompression, batch JSONL parsing, multipart parsing, the semantic cache.
6. **Cache isolation.** #971. Siblings: cache keys that leave out the user path, the model allowlist, guardrails or tools.
7. **A route shadowed by a configurable path.** The metrics path could shadow API routes (the guard is in `http.go`). Siblings: other operator-chosen paths, extension skip paths, the legacy `/admin/api/v1` alias.

## How to exercise it

- `/src/bin/gomodel` is built. `go run ./cmd/gomodel` starts it on `:8080` with SQLite at `data/gomodel.db`. Set `GOMODEL_MASTER_KEY` to leave open mode and `GOMODEL_OFFLINE=true` to skip outbound catalog and version calls. Without provider keys, point a provider's `base_url` at a local fake server.
- Unit tests: `go test ./cmd/... ./config/... ./ext/... ./internal/... ./run/...`.
- End-to-end tests run fully offline against an in-process mock provider, mock MCP server and fakes: `go test -tags=e2e ./tests/e2e/...`. `tests/e2e` is the best starting point for writing a reproducer.
- Contract tests replay golden fixtures: `go test -tags=contract ./tests/contract/...`.
- Dashboard tests: `cd web/dashboard && npm test`.
- `-tags=integration` needs Docker and `-tags=live` needs real provider keys; neither works offline.

## How we rate severity

- **Critical**: unauthenticated access, with a credential configured, to provider calls, the admin API or `/mcp`; disclosure of provider keys, the master key or other tenants' keys to a caller who should not have them; remote code execution.
- **High**: a managed key escaping its scope to reach another user path's data, gain admin or global-scope access, use models or providers it was not granted, or bypass its budget; a cross-origin attack that acts with a victim's credential; stored XSS in the dashboard.
- **Medium**: bypassing rate limits or budgets by a bounded amount, cross-tenant cache poisoning without data disclosure, a pre-auth crash or resource-exhaustion DoS of the whole gateway, secrets written to logs at default settings.
- **Low**: information leaks without credentials (internal URLs, versions, model names), authenticated DoS that needs a valid key and is bounded by its rate limit, hardening gaps with no demonstrated impact.

## Reports and patches

Give a reproducer as a Go test, preferably in `tests/e2e` style against the in-process server, or as a curl sequence against `/src/bin/gomodel` with the config it needs. Patches should be minimal and follow the repository's conventions (`AGENTS.md`). Deduplicate by root cause: one report for one missing check, even if several routes reach it.
