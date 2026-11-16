# GOWA threat model

## Project and assets

GOWA is a self-hosted Go WhatsApp API server built with Fiber, whatsmeow, and
SQLite. The Go module lives in `src/`. REST, optional HTTP MCP, and browser
websockets share the device manager and business usecases. The dashboard is a
separate project, gowa-ui, whose released HTML GOWA downloads at runtime.

Protect WhatsApp session keys and pairing credentials, OAuth tokens, message
content, contacts, media, scheduled sends, webhook secrets, and Chatwoot API
credentials. An attacker must not gain unintended control of a linked WhatsApp
account, send or delete messages without authority, or read another device's data.

## Trust and deployment assumptions

Operators control configuration, local storage, reverse proxies, and outbound
integration destinations. Treat ordinary API credentials as instance-wide
administrator access. Device selection is routing and data isolation, not a
per-user ownership or role system. Selecting another configured device with valid
administrator credentials is expected behavior.

`APP_BASIC_AUTH` is optional. Without credentials, ordinary REST and MCP routes
are intentionally unauthenticated. Internet-facing installations need configured
authentication and HTTPS, commonly through a reverse proxy. Report bypasses of
configured controls separately from deployments that deliberately omit them.

When MCP OAuth is enabled, MCP accepts bearer tokens or existing Basic Auth.
OAuth uses the same administrator accounts and does not grant REST access.
Public OAuth discovery, registration, authorization, and token endpoints are part
of the protocol. Inspect PKCE, redirect matching, resource binding, token expiry,
refresh rotation, replay protection, and registration limits in
`src/ui/mcp/oauth/`, `src/cmd/mcp_oauth.go`, and `docs/mcp-oauth.md`.

`src/cmd/rest.go` registers static media, health, Chatwoot webhook, OAuth, and
ordinary authenticated routes in a deliberate order. `/health` is public, and
`/statics` is mounted before Basic Auth. Evaluate unintended sensitive-file
exposure and guessability against that actual media-serving contract.
Chatwoot webhooks also bypass Basic Auth and enforce
`CHATWOOT_WEBHOOK_SECRET` only when configured. An unset secret is an explicit
configuration state, not proof of a configured-secret bypass.

## Untrusted inputs and priorities

REST JSON, query parameters, device selectors, multipart files, and media URLs
are untrusted. MCP tool arguments and websocket connection parameters are also
untrusted. WhatsApp messages, contacts, history, and attachments can originate
from remote users without API credentials. Chatwoot webhook bodies, attachment
URLs, and remote metadata responses cross separate network boundaries.

Prioritize these paths:

- Authentication and route ordering in `src/cmd/`, `src/ui/rest/middleware/`, and
  `src/ui/mcp/`. Include websocket query authentication, origin handling, pairing
  data, token leakage, and routes mounted outside global authentication.
- Device isolation in `src/infrastructure/whatsapp/`, `src/usecase/`, and
  `src/infrastructure/chatstorage/`. Logged-in chat storage uses the WhatsApp
  client's non-AD JID, while registry slots and scheduled sends use device aliases.
  Preserve device scope in reads, writes, deletes, quotes, retries, and events.
- Media and URL processing in `src/usecase/send.go` and `src/pkg/utils/`.
  Examine SSRF, redirect handling, path traversal, arbitrary file access, unsafe
  subprocess arguments, oversized downloads, and decoder resource consumption.
  Media processing invokes ffmpeg, ffprobe, WebP tools, and pdftoppm.
- Chatwoot routing in `src/ui/rest/chatwoot.go` and
  `src/infrastructure/chatwoot/`. Check configured webhook-secret validation,
  account/inbox/device binding, attachment fetching, echo suppression, persistent
  message links, retries, and optional direct PostgreSQL history import.
- SQL parameterization, sensitive logs, storage cleanup, and scheduled-media
  lifecycle. SQLite files contain private content and session material.

The separate gowa-ui repository and vulnerabilities entirely inside upstream
libraries are outside this repository's patch scope. Unsafe use of those
components by GOWA remains in scope. Do not assume decrypted WhatsApp input or
Chatwoot payloads are safe merely because transport authentication succeeded.

## Severity and evidence

Rate findings by demonstrated access and impact. Unauthenticated remote code
execution or broad session-key theft can be critical. Configured-authentication
bypasses, unauthorized message actions, arbitrary sensitive-file reads, and
remote-triggered cross-device disclosure can be high. Authenticated SSRF or denial
of service needs evidence of reachable targets or meaningful resource exhaustion.
Do not classify administrator-only configuration changes as privilege escalation.

Provide the entry point, required configuration, attacker capability, affected
asset, and a local reproducer. Explain whether the issue requires API credentials,
a WhatsApp contact, or a trusted integration. Prefer a focused regression test and
a fix in the shared usecase or infrastructure owner when REST and MCP are affected.

## Offline checks

The image keeps the complete checkout at `/src`, the Go module at `/src/src`, and
the binary at `/usr/local/bin/whatsapp`. It retains the compiler, CGO toolchain,
module cache, SQLite dependencies, and media tools for offline investigation.
Run from `/src/src` with outbound networking disabled:

```sh
GOPROXY=off GOSUMDB=off go test ./...
GOPROXY=off GOSUMDB=off go vet ./...
GOPROXY=off GOSUMDB=off go build -o /tmp/whatsapp .
```

Tests use temporary SQLite databases, fake clients, and local HTTP servers.
Loopback networking must remain available for `httptest`. Keep tests that mutate
package globals serial. Use package tests under `src/ui/`, `src/usecase/`, and
`src/infrastructure/` for focused reproducers. The optional SQLite driver can be
checked with `GOPROXY=off GOSUMDB=off go test -tags purego ./...`.

Do not start `whatsapp rest`, pair a device, reuse real session databases, send
WhatsApp messages, or contact live Chatwoot/PostgreSQL services for a reproducer.
Use synthetic inputs and temporary storage. No live credentials are needed for
the local test suite.
