# Threat model: EZiL-OS

Derived from the project's public SECURITY.md. The severity section is a proposal and needs confirmation from the
lead maintainer before the pull request is opened.

## What this project does and where untrusted input enters
EZiL-OS gives each signed-in user a real Linux container with a desktop, browser and editor, streamed to a web
browser. Source is TypeScript (Bun and Node). Untrusted input enters through:
- HTTP routes of the Next.js app in `app/src/app/api/` (including `/api/shell/*` and `/api/cron/*`) and the tRPC
  procedures in `app/src/server/`;
- the Cloudflare Worker in `worker/src/` (preview and bridge requests, tokens, cookies, WebSocket relays);
- the browser sidecar in `worker/sidecar/` (verbs sent by the Worker);
- the desktop shell in `shell/` (messages between windows and the host page);
- the `sdk/` client and the `mcp/` connector (responses from the service, tool arguments).

## Components that matter most / least
Most: authentication and authorisation in `app/src/server/auth/`, `worker/src/hmac.ts` (signed, short-lived preview
tokens), cookie handling for the editor bridge, `worker/src/preview-bridge.ts`, `worker/src/sandbox-control.ts`,
`worker/sidecar/`, and the cron routes. Next: `shell/`, `sdk/`, `mcp/`. Lowest: `local/` and `native/` (local
developer modes).

Out of scope: `e2e/`, `infra/`, `artifacts/`, `docker/`, `macos/`, `macos-electron/`, `deploy/`, `docs/`,
`extensions/` (tooling and packaging, not the service), vendored or packaged upstream software listed in
`ATTRIBUTIONS.md` (Chrome, code-server, Neko, Guacamole and similar; report those upstream). A weakness in how EZiL
configures one of them that makes it exploitable here is in scope.

## How to exercise it
Run unit tests per component with `bun test` in `worker/`, `sdk/`, `mcp/`, `local/`, `native/`, `tools/` and
`extensions/ezil-models/`, and `bun run test` (vitest) in `app/`. Dependencies are installed in the image. No
database, cloud account or Docker socket exists in the scan environment, so tests that need them (for example
`worker/src/*.container.test.ts`) will fail; that is expected. Reproducers should be unit-level or local-process
demonstrations; do not attempt calls to any hosted EZiL, Cloudflare, Vercel or Supabase service.

## How you rate severity (proposed, needs maintainer confirmation)
- Critical: escaping a user's container; reaching another user's container or data; forging or bypassing the signed
  preview token or the sandbox-bound editor cookie; unauthenticated access to code-server; remote code execution
  on the Worker or app.
- High: authentication or authorisation bypass in app routes, tRPC procedures or cron routes; a sidecar verb that
  runs outside the closed allowlist; secrets disclosed to an unauthorised party.
- Medium: cross-site scripting or request forgery with a demonstrated path to user impact; telemetry that carries
  identities, file contents, secrets or full URLs; denial of service from a single small request.
- Low: hardening gaps with no demonstrated impact on the above.
Prefer findings that come with a failing test or a minimal reproducer. Patches should be minimal and include a
regression test.

## Anything to leave alone
These are deliberate and documented in SECURITY.md:
- Running arbitrary code inside the user's own container is the product, not a vulnerability.
- `code-server --auth none` inside the container is gated by the bridge and its signed cookie; only reaching it
  without that cookie is a finding.
- `GET /health` and `GET /sandbox/:name/status` are unauthenticated by design and return no user data.
- Missing hardening headers, TLS grades and scanner output with no demonstrated impact.
- Denial of service by brute volume against a hosted deployment.
- Findings that need a compromised Cloudflare, Vercel or Supabase account, or physical access.
