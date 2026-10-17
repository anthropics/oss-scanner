# Threat model

## What this project does and where untrusted input enters
- Ingressi is a web UI and REST API (Next.js, TypeScript, Bun) that manages a Caddy reverse proxy: proxy hosts, TLS certificates, access lists, WAF, forward auth, L4 proxies.
- Untrusted input: HTTP requests to the admin UI and `/api/v1/` (Bearer token or session), OAuth/OIDC callbacks, and forward-auth requests. Caddy access and WAF logs are parsed by the web app, and those fields come from internet clients. Proxy-host settings an admin enters become Caddy JSON config.
- Admin users are trusted to manage proxy hosts, but non-admin users and unauthenticated visitors are not.

## Components that matter most / least
- Most: authentication and authorization (`src/lib/api-auth.ts`, `proxy.ts`, next-auth setup, API tokens, MFA), Caddy config generation (`src/lib/caddy*.ts`), log parsers (`src/lib/log-parser.ts`, `src/lib/waf-log-parser.ts`), secret handling (`src/lib/secret.ts`), forward-auth and sign-in bypass logic, instance sync.
- Less: analytics queries, UI components.
- `docker/caddy` builds Caddy with plugins and is thin glue; third-party code is out of scope.
- `ee/` is source-available (ELv2) and in scope.

## How to exercise it
- Unit and integration tests: `bun run test` (Vitest, in-memory SQLite). Route handlers are under `app/api/`. E2E tests need the full Docker Compose stack and aren't expected here.

## How you rate severity
- Authentication or authorization bypass, privilege escalation, SSRF, injection into generated Caddy config, secret disclosure, or RCE is high or critical.
- Stored XSS in the admin UI is high. DoS needing authentication is low; unauthenticated DoS is medium.

## Anything to leave alone
- Admin-only features that can by design change proxy behaviour, and the default behaviour of the proxied upstreams.
- Dev-only code in `tests/`, `scripts/` and `site/`.
