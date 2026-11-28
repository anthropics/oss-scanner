# Threat model: Flathub website (`flathub-infra/website`)

## What this project does

The Flathub website is the public storefront and account system for the Flathub Flatpak
repository. The repository contains three deployables that share one image in this enrollment:

- `backend/` — FastAPI application (`app.main:app`) and Dramatiq worker/scheduler. It serves the
  public API under `/api/v2`, user accounts, OAuth/OIDC login, passkeys, app metadata, search,
  moderation and permission review, app verification, upload-token management, the Stripe wallet,
  and a small OIDC provider.
- `backend-node/` — Hono service on port 8001 that renders and sends transactional email through
  SMTP. The compose file publishes that port and the backend calls it over the compose network.
- `frontend/` — Next.js application that renders the public site and protected account/admin pages,
  proxies browser requests to the API, and exposes a few server-side route handlers (OG images,
  badges, sitemap).

Data stores and external systems: PostgreSQL (primary and replica), Redis (cache and state),
Meilisearch (app search), Stripe (payments), SMTP, Sentry, GitHub/GitLab/GNOME/KDE/Google OAuth
providers, `flat-manager` (build and upload tokens), `dl.flathub.org` (appstream/ostree data),
imgproxy, and DNS/HTTP for publisher verification.

This model describes the enrolled revision and the compose topology in
`backend/docker-compose.yml`. Production deployment may differ; statements that depend on
deployment configuration are marked as assumptions.

## Trust boundaries and adversarial input

Treat the following as attacker-controlled unless stated otherwise.

1. **Anonymous internet → FastAPI.** Every path, query parameter, JSON/form body, header, cookie
   and uploaded value on the public API is untrusted. This includes app IDs, locales, search
   queries and Meilisearch filter values, pagination, review and moderation text, OIDC request
   parameters, verification tokens and redirect/return targets.
2. **Anonymous internet → Next.js.** Server components and route handlers process request paths,
   query parameters, cookies and forwarded headers. The `proxy.ts` authentication check is a UX
   redirect only; authorization is enforced in the API. Server-side fetches in the OG-image, badge
   and sitemap handlers are in scope when their target is derived from request data; fixed
   upstream URLs remain third-party dependencies.
3. **Authenticated users.** Session cookies are signed by Starlette `SessionMiddleware`
   (`SESSION_SECRET_KEY`). User identity, role, developer status and app ownership are
   authorization inputs. A user may be a normal user, an app developer, a moderator, an uploader
   (`direct-upload` permission) or an administrator. Session fixation, CSRF, recent-authentication
   bypass (`auth-time` freshness), passkey/session binding and horizontal/vertical privilege
   escalation are in scope.
4. **OAuth/OIDC identity providers.** Authorization codes, state, `returnTo`/`return_to` values,
   provider tokens and profile claims are untrusted until verified. The OIDC provider endpoints
   (`/oidc/authorize`, `/oidc/token`, `/oidc/userinfo`, consent) accept untrusted clients,
   redirect URIs, PKCE verifiers, scopes and client credentials.
5. **Stripe.** Browser-supplied payment data and the Stripe webhook body/`Stripe-Signature` are
   untrusted. `stripewallet.py` verifies the signature with `STRIPE_WEBHOOK_KEY`; any path that
   changes transaction state without that verification is a finding. Wallet transaction IDs, card
   metadata and transfer/recipient fields are authorization inputs.
6. **`flat-manager` and GitHub/GitLab APIs.** Responses from these services are treated as
   untrusted data: malformed JSON, unexpected fields, redirects and error bodies must not crash the
   process or bypass checks. `flat-manager` secrets (`FLAT_MANAGER_SECRET`,
   `FLAT_MANAGER_BUILD_SECRET`, `UPDATE_TOKEN_SECRET`) must never reach clients.
7. **Publisher-controlled data.** AppStream XML, manifests, app IDs, summaries, descriptions,
   screenshots, icons, URLs, review comments and OAuth profile fields ultimately come from app
   developers and are rendered in the frontend or email. They must be treated as untrusted for
   XSS, SSRF, path traversal, XML entity expansion and HTML/mail-header injection.
8. **Internal services.** The compose file publishes the email service on port 8001 and Redis on
   ports 6379/6380, so exposure depends on host and network policy. Treat the email endpoint as an
   unauthenticated mail-sending interface whenever anything untrusted can reach port 8001; its
   request body (recipient, subject, HTML, message info) would then allow arbitrary mail and HTML
   injection. Likewise, if Redis is reachable by an untrusted party, cache keys/values become
   untrusted input rather than trusted infrastructure.
9. **Verification inputs.** DNS TXT records and publisher websites used for app verification are
   attacker-controlled. Redirects, very large responses, slow responses and DNS rebinding are in
   scope for SSRF and resource-exhaustion findings.

## Components that matter most

Highest priority:

- `backend/app/logins.py`, `login_info.py`, `email_login.py`, `oauth_providers.py` — session,
  OAuth, email-login and reauthentication logic.
- `backend/app/routes/oidc.py`, `backend/app/oidc.py` — OIDC provider authorization, PKCE,
  redirect allowlists, client-secret verification, token issuance and rate limiting.
- `backend/app/routes/upload_tokens.py` — upload-token creation, scope/repo restrictions and
  `flat-manager` interaction.
- `backend/app/wallet/` — Stripe customer/transaction handling and webhook verification.
- `backend/app/moderation/`, `backend/app/moderation/permission_assessment_api.py`,
  `backend/app/routes/quality_moderation.py` — review decisions, permission rules and the
  shared-secret assessment API.
- `backend/app/cache.py` and route cache decorators — private/public cache separation.
- `backend/app/search.py` — Meilisearch query/filter construction and indexed document handling.
- `backend/app/verification.py` — outbound website/DNS verification.
- `backend/app/apps.py`, `frontend/app/api/`, `frontend/proxy.ts` — public metadata and SSR
  boundaries.
- `backend-node/src/index.ts`, `src/mail.ts` — email recipient, subject, HTML and SMTP handling.

Lower priority but still in scope: statistics ingestion, year-in-review, feeds, sitemaps, static
data files and build scripts used for production. Test-only code is lower priority unless it
affects a production path. Generated OpenAPI clients under `frontend/src/codegen*` are generated
code; report a vulnerability there only when the generated call site creates a real weakness, and
describe the source route instead.

## Security goals

- No authentication or authorization bypass; no cross-user data access (IDOR).
- Session cookies cannot be forged, fixated or reused after logout/revocation; passkey sessions are
  bound to the credential that created them.
- OIDC clients cannot obtain tokens for other clients/users or redirect them to unregistered URIs.
- Stripe webhooks are authenticated and cannot be replayed to change another transaction.
- Upload tokens cannot be created for apps the user does not develop, cannot exceed allowed
  scopes/repos, and cannot leak `flat-manager` secrets.
- Untrusted app metadata and user text cannot execute script in the site origin or in emails.
- No SSRF from verification, appstream, image or upstream metadata URLs built from request data to
  internal services or cloud metadata.
- Private/authenticated responses are never stored in shared caches or served to another user.
- SQL, Meilisearch filters, file paths and redirect targets cannot be injected.
- Secrets, tokens, email-login links and other users' email addresses do not leak through logs,
  errors, Sentry payloads, cached responses or email headers.
- Resource use is bounded for expensive endpoints (search, stats, appstream parsing, image
  generation).

## How to exercise the project

The image contains all three projects, development dependencies and a local PostgreSQL cluster.
The Dockerfile runs the tests below during the image build; test failures are warnings, not build
failures. Start the database again for a reproducer:

```bash
service postgresql start
redis-server --port 6380 --daemonize yes
DB="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/flathub"
export DATABASE_URL="$DB" DATABASE_REPLICA_URL="$DB" \
       MAINTENANCE_TEST_DATABASE_URL="$DB" \
       PERMISSION_ASSESSMENT_TEST_DATABASE_URL="$DB" \
       STATS_TEST_DATABASE_URL="$DB"

cd /src/backend
uv run alembic upgrade head
uv run pytest -vvvv --ignore=tests/main.py \
  --ignore=tests/test_storefront_smoke.py \
  --ignore=tests/test_year_in_review_smoke.py --ignore=tests/api_smoke

cd /src/backend-node && pnpm test
cd /src/frontend && pnpm test
```

The Dockerfile also runs `cd /src/frontend && pnpm build` and
`cd /src/backend-node && pnpm build`; both outputs stay in the image.

Limitations:

- The excluded smoke suites (`tests/main.py`, `test_storefront_smoke.py`,
  `test_year_in_review_smoke.py`, `tests/api_smoke`) need the full docker-compose stack: backend,
  worker, scheduler, backend-node, two Redis instances, Meilisearch, PostgreSQL and an SMTP test
  server. They are not part of the baseline image.
- Meilisearch is not installed. The search unit tests do not require a live Meilisearch instance;
  exercising live filter behavior requires running Meilisearch separately.
- Redis is installed but not started. The baseline suite matches CI and does not require it.
  Start a state instance on port 6380 when a reproducer needs authentication state, or one on
  port 6379 for cache behavior.
- OAuth providers, Stripe, GitHub/GitLab, `flat-manager`, Sentry and the email service are
  generally mocked, faked or recorded in tests. Live integration is not available in this image.
  Use the fake wallet (`STRIPE_PUBLIC_KEY` unset) and local SMTP for end-to-end reproducers.
- Some tests use recorded cassettes/fixtures; they do not prove the live provider behaves the same.
- The Dockerfile builds the frontend with `CI=true` and no Sentry upload token, matching CI.
  Sentry source-map upload is inactive in this image.

## Severity guidance

The lists below are calibration examples, not automatic mappings. A finding takes its severity
from demonstrated impact, attacker position and prerequisites; when a finding needs a chain, rate
the chain rather than each step. If impact depends on an unverified deployment assumption, state
the assumption instead of assuming the worst case.

**Critical impact examples**

- Remote code execution, command injection, template injection with code execution, or arbitrary
  file write/read in the backend, worker, email service or a server-side frontend handler.
- Authentication bypass to any account, or authorization bypass to administrator, moderator,
  permission-review or uploader capabilities.
- Stripe webhook signature bypass, or any way to create/complete/refund/transfer a transaction or
  change its amount/recipient without the owner's payment intent.
- Pre-auth SQL injection, or Meilisearch access that exposes or modifies arbitrary indexed data.
- OIDC authorization-code or token theft, client impersonation, or redirecting a code/token to an
  attacker-controlled URI.
- Mass exfiltration of secrets, password/email-login tokens, session cookies or personal data.
- SSRF to cloud metadata or internal admin services with demonstrated credential or data impact.

**High impact examples**

- Stored XSS in the `flathub.org` origin, including via app metadata, reviews, moderation text,
  or server-rendered pages, where it can act with the victim's session.
- IDOR exposing another user's email, wallet/card metadata, transactions, passkeys, tokens or
  private app data; or a developer acting on an app they do not own.
- Upload-token scope/repo bypass that permits publishing to `stable`, another app's repo, or
  access beyond the documented `direct-upload` permission.
- Post-auth SQL injection, or a cache-poisoning path that serves private responses to other users.
- CSRF on a state-changing action that changes account, payment, app ownership, moderation or
  upload state (including login CSRF that binds the attacker's identity to the victim).
- Leaking `FLAT_MANAGER_*`/`UPDATE_TOKEN_SECRET`/OAuth client secrets, or a working email-login
  link to a third party.
- Reflected XSS that needs no non-standard browser or user interaction beyond opening a link.
- SSRF reaching internal HTTP services or arbitrary internal ports with demonstrated impact short
  of Critical.
- Email-service abuse that sends arbitrary mail from `flathub.org` at scale, or SMTP/header
  injection from a request field.

**Medium impact examples**

- Reflected XSS requiring an unusual browser, extension or multi-step interaction; DOM XSS limited
  to the attacker's own page.
- CSRF on a low-impact state change with demonstrated impact.
- Single-user or single-endpoint denial of service reachable with modest resources; regex or XML
  parsing that hangs one request.
- Limited information disclosure (internal hostnames, stack traces, non-secret config, whether an
  email is registered) without an account-takeover path.
- Open redirect after login/verification where the redirect is constrained to an external site but
  cannot steal tokens.
- Meilisearch filter injection limited to changing search results or filters, without access to
  other indexes or data.
- Post-auth permission checks that are too broad but expose only public app metadata.
- Email HTML injection without header injection and without a plausible phishing impact.

**Low impact examples**

- Missing security headers on a page with no sensitive content, verbose errors with no secret,
  rate-limit gaps with no practical abuse, self-XSS, clickjacking on a non-state-changing page.
- Best-practice findings (cookie flags, CSP report-only, dependency versions) without a reachable
  exploit path.

## Not a vulnerability / do not report

- Intentionally public API data, OAuth client IDs and Stripe publishable keys. Hard-coded defaults
  in `config.py`, compose and test fixtures are configuration risks, not leaked secrets; report
  them only with a deployment path that uses them and demonstrated impact.
- Volumetric DDoS, WAF/CDN evasion without a misconfiguration in this repository, spam without a
  code weakness, social engineering, physical access and compromised maintainer accounts.
- Missing rate limits or headers with no demonstrated security impact.
- Vulnerabilities in Stripe, GitHub, GitLab, Meilisearch, Sentry, imgproxy, the CDN, PostgreSQL,
  Redis or `flat-manager` itself. Report those upstream; report this project only if its use of
  them creates a distinct weakness.
- Build reproducibility, code style, test coverage, or dependency-version bumps without a
  demonstrated reachable vulnerability.
- Findings whose only affected code is tests, fixtures, cassettes or snapshots and has no
  production path.
- Findings whose impact depends only on a developer-local setup or test data, or that require the
  attacker to already control the server, database, Redis or `flat-manager` credentials.

## Reporting and patch expectations

- Reproduce against this image with the commands above. Include the exact request/response,
  affected route or file, and the trust boundary crossed. Redact real user data, cookies, tokens
  and Stripe keys.
- Proposed patches should be minimal and target `flathub-infra/website`, not generated code under
  `frontend/src/codegen*`, lockfiles, snapshots or CI configuration unless the fix requires it.
- Preserve existing behavior for public endpoints and do not weaken tests. If a fix needs a
  database migration, state it explicitly and include the migration.
- Prefer a failing regression test with the patch. Note any test that requires the full compose
  stack so maintainers can run it separately.
