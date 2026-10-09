# Threat model: Onetime Secret

Onetime Secret shares sensitive text through a single-use link. Creating a secret produces two capabilities: the
secret link, which the creator passes to a recipient, and the receipt link, which the creator keeps. The recipient
opens the secret link once and the secret is destroyed. Most of what follows exists to protect that property.

Stack: Ruby/Rack backend (`apps/`, `lib/`), Vue 3 SPA (`src/`), Valkey/Redis for secrets, receipts and sessions
(Familia ORM), SQLite or Postgres for full-mode authentication (Rodauth), RabbitMQ for background jobs. Routes are
declared in `apps/**/routes.txt`. The `auth=` column lists the authentication strategies a route accepts (`noauth`
allows anonymous callers) and `sensitive=true` marks routes that take a bearer identifier.

## Who holds what

| Party | Holds | May |
|---|---|---|
| Anyone | nothing | create anonymous secrets when guest routes are enabled |
| Recipient | secret link, plus the passphrase if one is set | view the secret once |
| Creator | receipt link, and an account if signed in | see the secret's state and metadata, burn it; see a *generated* secret's value once, within `generated_value_display_ttl` (default 60 s) of creation |
| Account user | session cookie or API token (HTTP Basic) | act on their own account, secrets and receipts |
| Organization member, admin, owner | a role in one organization, optionally scoped to one custom domain | what the role grants, inside that organization and domain only |
| Custom-domain owner | DNS for a domain pointed at the service; tenant branding and SSO settings | act on their own tenant. Untrusted toward every other tenant and toward the canonical site |
| Colonel (site admin) | colonel role | trusted |
| Operator | environment, `etc/config.yaml`, proxy configuration, Valkey and database | trusted |

Secret and receipt identifiers are high-entropy (`Familia::VerifiableIdentifier`). Guessing one is not a viable
attack. Moving one to a party that should not hold it is.

## Where untrusted input enters

Every part of an HTTP request: path, query, body, cookies, and headers including `Host`, `Origin`, `Referer`,
`Forwarded` and `X-Forwarded-*`. `Host` selects the tenant on custom domains (`lib/middleware/detect_host.rb`,
`lib/onetime/middleware/domain_strategy.rb`). Forwarded headers are attacker-controlled unless the immediate peer is a
configured trusted proxy, and trusted-proxy handling is off by default (`TRUSTED_PROXY_ENABLED`).

Also untrusted:
- tenant-supplied branding and settings: logos, icons, colours, text, SSO configuration;
- identity-provider responses: SAML assertions, OIDC tokens and claims, including `email_verified`;
- DNS answers and HTTP responses fetched during custom-domain verification and SSO connection tests;
- Stripe webhook bodies until their signature is verified.

Entry points:
- `apps/api/v1`, `v2`, `v3`: the secret API (create, reveal, burn, receipts, status), anonymous or with an API token
- `apps/api/incoming`: incoming secrets
- `apps/api/account`, `organizations`, `invite`, `domains`: account, organization, invitation and custom-domain management
- `apps/api/colonel`: the admin API
- `apps/web/auth`: full-mode authentication (passwords, MFA, WebAuthn, magic links, SAML and OIDC SSO)
- `apps/web/core`: simple-mode authentication and server-rendered pages
- `apps/web/billing`: Stripe checkout and webhooks
- `apps/internal/acme`: on-demand TLS checks for custom domains
- `lib/`: middleware (sessions, host detection, CSRF, CSP, cookie tossing), models, encryption, rate limiters
- `src/`: the SPA, which handles bearer identifiers in the browser

## Deployment to assume when rating

Rate against the hosted service at onetimesecret.com: full authentication mode with MFA, WebAuthn, magic links and
SSO; organizations, custom domains, regions and Stripe billing enabled; nonce-based CSP on; behind a reverse proxy
that is configured as a trusted proxy. Self-hosted installs default to simple mode with most of these features off
(`etc/defaults/*.defaults.yaml`).

- Holds under shipped defaults (`etc/defaults/`) or shipped examples (`etc/examples/`, including
  `Caddyfile-example`): in scope at full severity. Self-hosters run them unchanged.
- Needs a non-default setting that the hosted service does not use: one level lower. Name the setting.
- Needs the operator to misconfigure something (trust every proxy, disable CSP, set a weak `SECRET`): out of scope.

## What matters most

1. Secret contents: readable only by someone holding the secret link, and the passphrase when one is set.
2. Burn after reading: a secret is revealed at most once, and reveal, burn and expiry leave nothing readable.
3. Bearer values: secret and receipt identifiers, session IDs, API tokens, magic-link, reset, invitation and
   verification tokens, MFA secrets and recovery codes. Any path that hands one to a party that should not hold it:
   responses, redirects, `Referer`, shared caches, cross-origin reads, another tenant, logs, error telemetry, or an
   emailed link whose host came from a request header.
4. Isolation between organizations, between custom domains, and between a custom domain and the canonical site.
5. Authentication and sessions: login, MFA, WebAuthn, magic links, SSO account linking and just-in-time account
   creation, session rotation at each authentication step, password reset.
6. Authorization in `apps/api/*` and `lib/onetime/logic/`: role checks, domain-scope checks, entitlement checks.
7. Script execution on any origin the app serves, including custom domains.

Lower priority, still in scope: the production image (`Dockerfile`, `docker/`); GitHub workflows that an outside
contributor can trigger (`pull_request_target`, `issue_comment`, `workflow_run`); getting paid features without
paying; resource exhaustion.

Out of scope: `spec/`, `try/`, `tests/`, `e2e/`, `bin/`, `scripts/`, `docs/`, `generated/`, `.devcontainer/`, and
built assets under `public/`. Repository content, including `locales/`, is trusted.

## How to exercise it

- `ots-test-services` starts Valkey (127.0.0.1:2163), RabbitMQ (127.0.0.1:2156, management API on 12156) and
  Postgres (127.0.0.1:2154).
- Run tests only through `tests/lanes/run`. It clears the environment and points the app at the test services.
  Calling `rspec` or `try` directly inherits the wrong environment.
- `tests/lanes/run --list` lists the lanes. Every lane runs in this image, including the Postgres lanes (`full-pg`,
  `full-pg-agnostic`, `migrations-pg`) and the `browser` lane (Playwright Chromium, Firefox and WebKit are
  installed).
- `tests/lanes/run --only <path>:<line>` runs one example; the lane is inferred from the path. `*_try.rb` files are
  Tryouts, everything else is RSpec. See `tests/lanes/README.md`.
- The integration specs drive the full Rack middleware stack with rack-test. A new spec in that style is the
  preferred reproducer.

## How to rate severity

**Critical**
- Reading a secret's contents without its link, or without its passphrase when one is set (other than by guessing
  within the rate limits).
- Remote code execution, command injection, template injection or unsafe deserialization reachable by any untrusted
  party.
- Signing in as another account, or gaining the colonel role.
- Reading or changing another organization's or custom domain's secrets, receipts, members, SSO settings or billing.
- Code execution with repository write access or publishing secrets from an outside contributor's pull request.

**High**
- Revealing a secret more than once, or a secret that stays readable after reveal, burn or expiry.
- Script execution on an origin the app serves, demonstrated with CSP enabled.
- Account takeover that needs one victim action, such as a reset or magic link built from an attacker-controlled
  host.
- A bearer value from "What matters most" item 3 reaching an unauthorized party through a response, redirect,
  `Referer`, cache, cross-origin read or another tenant.
- Completing login with fewer factors than the account requires.
- Escalating role inside an organization, or from one custom domain's scope to the whole organization.
- Server-side request forgery that reaches internal addresses with a readable response.
- A forged or replayed Stripe webhook being accepted.

**Medium**
- Guessing a passphrase, password, one-time code or recovery code faster than the rate limiters allow. Precedent: an
  authenticated API caller with a known secret identifier and no per-secret passphrase limit was rated Medium.
- Account enumeration through a distinguishable response.
- Cross-site request forgery on a state-changing endpoint.
- HTML injection that CSP stops from running script, or XSS that needs a separate CSP bypass.
- Server-side request forgery without a readable response.
- Denial of service from one or a few unauthenticated requests, unbounded storage growth, or mail sent to
  attacker-chosen addresses in volume.
- A session ID that survives an authentication step, when exploiting it needs a separate cookie-planting primitive.
- Paid features or plan limits available without payment.
- Bearer values written to application logs or error telemetry.

**Low**
- Missing hardening headers, verbose errors, version disclosure.
- Email addresses or IP addresses in logs.
- Enumeration through timing only.
- Values stored unencrypted or unhashed where reading them needs Valkey or database access.

Rate what the reproducer demonstrates. If impact depends on a step the reproducer does not perform (a browser
behaviour, a chained bug, a specific deployment), give the demonstrated rating and list the undemonstrated step under
"Not demonstrated". Do not raise a rating on an assumed chain.

## Report format

Start every report with this block, then one sentence of impact, then the detail:

```
ID:            OTS-<AREA>-<slug>
Severity:      <level>, per "<the rubric line it matches>"
Attacker:      <party from "Who holds what"> holding <what>
Preconditions: <auth mode, features, settings; "shipped defaults" if none>
Demonstrated:  <what the reproducer shows>
Not demonstrated: <steps assumed, or "none">
Locations:     <path:line at the scanned commit>
Introduced:    <commit, if bisected>
Register:      <RISK-... if it matches docs/security/active-risk-register.md, else "none">
```

- `AREA` is one of AUTH, AUTHZ, REDIS, API, SPA, SUPPLY, RUNTIME, LOGIC, CRYPTO, OBS. The slug names the weakness,
  not the file, so the same weakness found again gets the same ID.
- Quote code and line numbers from the scanned commit only.
- When a claim rests on a standard (OWASP ASVS, NIST SP 800-63, an RFC), cite the version and section. "Best
  practice" is not a basis (see `docs/adr/adr-048-evidence-basis-for-security-decisions.md`).
- Keep the explanation short. The reproducer and the patch carry the detail.

## Proof of concept

In order of preference:
1. An RSpec integration spec through the full Rack stack, placed beside the related specs, with the exact
   `tests/lanes/run --only` command that runs it.
2. A Tryouts `*_try.rb` file, with its command.
3. A shell script of HTTP requests against a server started in the image, for behaviour that only shows end to end.

The reproducer must run offline in this image and must fail on the scanned commit. For browser-only behaviour (script
execution, cookie handling), drive Chromium, Firefox or WebKit with Playwright against a server started in the
image; `tests/browser/saml_callback_spec.rb` shows the pattern. List any browser left untested under "Not
demonstrated".

## Patches

- The smallest change that removes the root cause, plus a regression spec that fails before the patch and passes
  after it.
- No refactors, renames, formatting changes or dependency bumps unless the bump is the fix.
- Say so explicitly when the patch changes a response shape in `apps/api/v1`, `v2` or `v3`, or changes a default in
  `etc/defaults/`. Self-hosted operators and API clients depend on both.

## Deduplication

- One report per root cause. The same missing check in v1, v2 and v3 handlers, or in several routes sharing one
  code path, is one report listing every location.
- Separate reports when the fixes differ, even if the symptom looks the same.
- A weakness already in `docs/security/active-risk-register.md`: report it only with a higher demonstrated impact
  or a location the register entry does not cover, and put its RISK ID in the header.

## Not vulnerabilities

- Anything that needs the attacker to already hold the secret link or receipt link for that secret. The link is the
  capability.
- The receipt showing a generated secret's value once within `generated_value_display_ttl` of creation.
- A reveal or burn request without `continue=true`: it returns the same response for any passphrase and records no
  attempt. The passphrase is checked, and attempts counted, only with `continue=true`.
- Status endpoints returning a secret's state and metadata to a caller who supplies its identifier.
- Anonymous access to guest routes when guest routes are enabled.
- Attacks that require guessing a secret or receipt identifier.
- Actions taken by a colonel or the operator.
- Missing rate limits on endpoints that guard no guessable value, send no mail and do no expensive work.
- Dependency advisories with no reachable path from this code.
- Infrastructure outside this repository: CDN, DNS, the hosted Sentry instance.
- The conventions listed in `AGENTS.md` under "Repo conventions (not defects; do not flag in review)", unless the
  finding shows the mechanism enforcing one of them is broken.
