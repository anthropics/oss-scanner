# Threat model

## Scope

The entire repository is in scope. Do not exclude any path. Review the SvelteKit
application in `src/`, the Go agent in `agent/`, the build and install tooling,
and the tests. Third-party dependencies are not themselves in scope, but report
them if ITCake code makes a vulnerability reachable.

## What ITCake is

Single-user, self-hosted application for a one-person IT business: invoicing,
tickets, uptime monitoring, RMM, and remote desktop. It is reachable over
HTTP(S), and its Go agent runs as root/SYSTEM on managed endpoints.

The authenticated operator is fully trusted. There is no multi-user/RBAC layer;
do not report missing RBAC or "operator can access their own data."

Untrusted input enters through:

- HTTP routes and form actions under `src/routes/`, especially `src/routes/api/`
- RMM agent requests to `/api/rmm/*` (enrollment, check-in, binary download)
- uploaded files, attachments, and backup ZIPs
- operator-configured outbound targets: HTTP/TLS/ping monitors, SMTP, Telegram, AI
- the Go agent's local environment and server-issued commands/updates

## Highest-value surfaces

- Auth, sessions, MFA, CSRF: `src/lib/server/auth.ts`, `mfa-step-up.ts`,
  `src/routes/api/auth/*`, `src/hooks.server.ts`
- Agent trust: `src/routes/api/rmm/*`, `src/lib/server/agent-auth.ts`, TLS pinning,
  enrollment tokens, update-manifest signature verification
- Crypto: `field-crypto.ts`, `backup-crypto.ts`, HMAC audit chain in `changes.ts`
- Files: attachment uploads, backup create/restore/verification, ZIP handling,
  path traversal and zip-bomb defenses
- Outbound requests: `pinned-https.ts`, `src/lib/server/checks/*`
- PDF/templates: `pdf.ts`, `template-renderer.ts`, `assets/templates/*`
- Go agent: command dispatch, HMAC verification, privileged file/package/service
  operations, self-update
- AI tool dispatch and redaction

## How to exercise it

The image is already built and all dependencies are installed. The
cross-platform agent binaries are in `data/agent-binaries/`, so the agent
download endpoint can be exercised too.

- Unit tests: `npm test -- --run tests/unit/`
- Integration tests: `PUPPETEER_NO_SANDBOX=true npm test -- --run tests/integration/`
  (starts Vite on 127.0.0.1:5298)
- Start the app manually:
  `SESSION_SECRET=$(openssl rand -hex 64) DATA_DIR=/tmp/itcake-data NODE_ENV=development PORT=3000 npx vite dev`
- Production mode:
  `NODE_ENV=production ORIGIN=http://127.0.0.1:3000 SESSION_SECRET=... DATA_DIR=/tmp/itcake-data node build/index.js`
- Go: `cd agent && go test ./... && go vet ./...`
- Rebuild the agent binaries: `npm run build:agent:all`

The preferred reproducer is a vitest test under `tests/unit/`, or an HTTP request
sequence against the dev server. The image is offline; use only existing
dependencies and the standard library.

`guacd`, an SMTP server, Telegram, and AI providers are not installed. Static
review of those paths is in scope; end-to-end dynamic tests of them are not
possible in this image.

## Severity

- Critical: pre-auth RCE or agent command execution, authentication/session
  bypass, arbitrary file read/write outside `DATA_DIR`, backup restore escaping
  `DATA_DIR`, key or plaintext credential compromise.
- High: stored XSS in the app origin, CSRF that bypasses step-up, SSRF to
  internal services, path traversal in uploads/downloads, agent update or TLS
  pinning bypass, audit-log forgery.
- Medium: secret disclosure, DoS from a single small request, rate-limit bypass
  with concrete impact.
- Low: hardening gaps, security headers, log injection without an exploit, DoS
  requiring large or repeated requests.

## Report guidance

One report per root cause; deduplicate variants. Include a minimal PoC, affected
commit/paths, and a suggested patch where practical. Deployment and
reverse-proxy configuration are out of scope.
