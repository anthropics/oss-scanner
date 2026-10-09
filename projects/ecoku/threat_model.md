# Ecoku threat model

## Project and scope

Ecoku is an MIT-licensed, self-hosted, multi-site plain-text comment system for
static blogs and personal websites. A Go/Gin server stores comments, private
visitor email addresses, administrator sessions, and notification state in SQLite.
The TypeScript browser SDK renders public discussions; the Vue administrator UI
manages sites, comments, CAPTCHA, and notification settings.

Prioritize `server/`, `packages/client/`, and `packages/admin/`. Deployment files
and the root Dockerfile are relevant when a finding affects the documented runtime.
`docs/internal/constraints.md` describes intended product, security, and privacy
boundaries; confirm actual behavior against source. `designs/` contains prototypes,
and `docs/progress/` contains historical records, not production implementations.

## Attackers, inputs, and trust boundaries

- Anonymous remote clients control HTTP paths, query parameters, request bodies,
  headers, comment text, nicknames, email addresses, website URLs, page keys, and
  parent IDs. Comments are published immediately; there is no moderation queue or
  ordinary user account system. A supplied email address is not proof of identity.
- Public comment DTOs must not expose private email addresses, administrator
  fields, credentials, IP addresses, user agents, or full database models. Check
  both errors and successful responses, including deleted-comment tombstones.
- Site/page identifiers and reply relationships must not allow cross-site or
  cross-page access or mutation. Public comments are intentionally readable;
  CORS is a browser boundary, not authentication for confidential content.
- One trusted instance administrator manages all sites. A configured server-side
  `Authorization: EcokuSite` credential is restricted to tombstone deletion on
  its own site, and must not grant reads, permanent deletion, settings access,
  or access to other sites. There is no per-site administrator RBAC promise.
- Review administrator login, initial setup, cookie origin/CSRF enforcement,
  registered sessions, revocation, expiration, and bearer authentication. Browser
  credentials belong in host-only HttpOnly cookies, not JavaScript or URLs.
- Treat stored comment data as attacker-controlled in SDK/admin rendering and
  HTML email/Telegram output. Comments are plain text, not HTML or Markdown.
  Author URLs must remain HTTP(S); notification article links must stay on the
  configured site. Check Smoji URL/source restrictions and context-specific escaping.
- CAPTCHA results, upstream failures, redirects, DNS answers, and notification
  delivery responses are untrusted. CAPTCHA must fail closed when enabled. Review
  request deadlines, replay handling, outbound request destinations, and secret
  handling. Use local mock providers, not real Turnstile, Cap, SMTP, or Telegram.
- The administrator may intentionally configure SMTP and other supported outbound
  integrations. Distinguish that authority from a visitor redirecting requests or
  bypassing explicit destination restrictions, especially Cap's public-IP checks.
- Private visitor identity may be encrypted in IndexedDB for seven days, isolated
  by server URL and site ID. It must not leak into localStorage, cookies, URLs,
  public output, or another configured site. This storage does not claim protection
  against malicious JavaScript already executing in the embedding page's origin.
- SQLite migrations/imports, bounded thread traversal, rate limiting, cancellation,
  and notification outbox/delete coordination matter for integrity and availability.
  Proxy headers are trusted only through explicitly configured direct peers.
  IP/UA/location must not be persisted, returned, or logged by the application.

## Offline environment and useful commands

The enrollment Dockerfile keeps the checkout at `/src`, installs Go 1.27.2,
Node.js 24.19.0, pnpm 11.24.0, runtime-package development dependencies, and
Playwright Chromium plus its system dependencies. Go modules remain cached in the
image. `CGO_ENABLED=0` matches production; `GOTOOLCHAIN=local` prevents an implicit
toolchain download. The Go binary retains debug information at
`/usr/local/bin/ecoku-server`; SDK and admin outputs are in their respective
`packages/*/dist` directories. This is a development/audit image, not the production
container; the production image's fixed paths and non-root user are separate.

From `/src`, the existing checks available to an offline scanner are:

```sh
cd /src/server
GOPROXY=off go test -count=1 ./...
GOPROXY=off go vet ./...
cd /src
pnpm verify:client
pnpm verify:admin
pnpm -C packages/client test:browser
```

These commands describe how to exercise the project, not a claim that every check
was run for enrollment. Documentation-site dependencies are not installed.
Go tests provide temporary SQLite databases and local HTTP/provider fixtures;
frontend tests cover rendering and browser identity storage. Prefer extending
those fixtures to using a real instance. An isolated network namespace may use
loopback for test servers. Never contact production, use real credentials, send
real notifications, or import real user data. The published homepage is context,
not authorization to scan it.

## Severity and reports

- Critical: demonstrated unauthenticated remote code execution or comparable
  instance-wide compromise, with realistic prerequisites and attacker control.
- High: administrator authentication/authorization bypass, meaningful disclosure
  of private emails or credentials, arbitrary cross-site mutation, or stored XSS
  that can execute in an administrator or another visitor's browser.
- Medium: a reproducible availability or integrity violation with bounded impact,
  including an inexpensive request that exhausts shared resources. Escalate only
  with evidence of sustained, broadly reachable impact; ordinary load alone is
  insufficient. Describe exploit cost, concurrency, duration, and recovery.
- Low: limited-impact hardening issues without a demonstrated confidentiality,
  integrity, or availability boundary violation. State uncertainty explicitly.

Administrator/host control and intentional public posting are not themselves
vulnerabilities. Still report a concrete violation of a documented restriction
that remains meaningful under those privileges. A dependency advisory alone is
not proof of a reachable Ecoku vulnerability; identify the affected call path.

For each finding, include the exact commit, relevant files/functions, attacker
capabilities, violated boundary, safe minimal reproducer, observed versus expected
result, and practical impact. Distinguish confirmed behavior from hypotheses.
Deduplicate by root cause. Prefer a minimal patch with a regression test, preserving
API contracts, private-email handling, transactional migrations, and existing data.
Do not rewrite published migrations or disable validation to make a test pass.
