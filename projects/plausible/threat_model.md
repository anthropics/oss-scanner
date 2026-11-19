# Plausible Analytics threat model

## What this project does and where untrusted input enters

Plausible is a multi-tenant web analytics service in Elixir/Phoenix. PostgreSQL holds users, teams and sites,
ClickHouse holds events and sessions, the dashboard is React (`assets/`) and LiveView, and the tracker script
(`tracker/`) runs on customers' websites.

Plausible Cloud (plausible.io) is the Enterprise Edition, built from `lib/` and `extra/lib/`. The self-hosted
Community Edition is `lib/` only (`MIX_ENV=ce`). `on_ee` and `on_ce` blocks compile different code into each, and an
`on_ee` block without `else` is absent from CE. `extra/` is proprietary but in scope.

Who is trusted:

- Unauthenticated: anyone sending events, visitors of public and shared-link dashboards, and the login,
  registration, password reset, 2FA, invitation, SSO and OAuth endpoints. Registration on Cloud is open.
- Team members: `owner`, `admin`, `editor`, `billing` and `viewer` per team, and guests with `viewer` or `editor` on
  single sites (`lib/plausible/teams/`). A finding is a role doing what only a higher role or another team may do.
- Tokens: Stats/Sites API keys with scopes (`stats:read:*`, `sites:read:*`, `sites:provision:*`), Plugins API tokens
  bound to one site, OAuth tokens for MCP. A token must stay within its scope, team and site.
- Trusted: super admins (Plausible staff, `/cs` and `/flags`) and the operator of a self-hosted instance.

Where untrusted input enters:

- `POST /api/event`, unauthenticated by design. The payload (name, url, referrer, props, revenue) and headers
  (User-Agent, client IP) are stored, then rendered to site owners in the dashboard, exports and emails.
- Public and shared-link dashboards (`/:domain`, `/share/:domain`) and their stats API (`/api/stats/:domain/...`),
  whose filters, segments and query JSON reach the ClickHouse query builder.
- Stats API (`/api/v1/stats`, `/api/v2/query`), Sites API (`/api/v1/sites`), Plugins API (`/api/plugins`), MCP
  (`/mcp`) and OAuth (`/login/oauth`).
- LiveView `mount/3`, `handle_params/3` and `handle_event/3`, including events and IDs the UI never sends.
- CSV and Google Analytics imports, CSV exports, Paddle (signature-verified), Postmark and HelpScout webhooks, SAML
  and Google OAuth callbacks.
- Installation verification, which fetches customer-supplied URLs through Browserless
  (`extra/lib/plausible/installation_support`).

## Components that matter most / least

Most:

- Tenant isolation: every site, team, segment, goal, funnel, shared link, invitation or membership ID from params or
  a LiveView event must be scoped to the caller. Trace the ID through validation, persistence and the later read
  path; the UI not offering an ID does not stop a crafted request. `conn.params["__team"]` is client-supplied.
- Authorization: `AuthPlug`, `AuthorizeSiteAccess`, `AuthorizeTeamAccess`, `AuthorizePublicAPI` and
  `AuthorizePluginsAPI` in `lib/plausible_web/plugs/`. `AuthorizeSiteAccess` with no role list admits `:public`,
  which is right for public stats and wrong anywhere else. HTTP plugs do not run on WebSocket events or on live
  navigation inside one `live_session`, so LiveViews rely on their `on_mount` hooks (`AuthContext`,
  `SuperAdminLiveAuth`) and on checks in `handle_event/3`.
- The query builder (`lib/plausible/stats/`), which turns filters, dimensions and segments into ClickHouse SQL.
- Authentication: passwords, 2FA and recovery codes, password reset, email verification, invitations, SSO
  (`extra/lib/plausible_web/sso`, `extra/lib/plausible/auth/sso*`), OAuth, sessions.
- Rendering of visitor-supplied data in the dashboard, LiveViews, emails and CSV exports.
- Security-relevant defaults in `config/runtime.exs`, for both editions.

Least: `test/`, `e2e/`, `fixture/` and `extra/fixture/` are out of scope, and so is `.github/` unless a workflow can be
exploited from a fork's pull request.

## How to exercise it

- `plausible-test-services` starts PostgreSQL and ClickHouse; both editions' test databases are already migrated.
  `mix test <file>` runs the EE tests and `MIX_ENV=ce_test mix test <file>` the CE tests.
- Write reproducers as ExUnit tests: `PlausibleWeb.ConnCase` with `setup [:create_user, :log_in, :create_site]` gives
  a logged-in conn, `test/support/factory.ex` builds users, teams, memberships, sites, API keys and events, and
  `Phoenix.LiveViewTest` drives LiveViews, including events the UI does not render.
- Outbound HTTP is mocked in tests (Mox and `Req.Test`), so nothing leaves the container.
- Starting points: `test/plausible_web/controllers/api/external_controller_test.exs` (ingestion),
  `test/plausible_web/controllers/api/external_stats_controller/` (Stats API), `test/plausible/stats/`.

## How we rate severity

Rate a finding by what it reaches, including any pivot.

- Critical: another team's data, sites or account from an unauthenticated or freshly registered account; account
  takeover; authentication or 2FA bypass; remote code execution; SQL injection in PostgreSQL or ClickHouse that
  reaches other tenants' data.
- High: crossing tenants with a role or token the attacker already holds (a guest or API key reaching another site
  or team); privilege escalation inside a team (viewer to editor or admin, guest to team member); stored XSS in a
  logged-in user's session, including from data an anonymous visitor sent to `/api/event`; SSRF that reaches
  internal services or cloud metadata.
- Medium: metadata the caller's role denies inside their own team; reflected XSS; CSRF on a state-changing action;
  SSRF that only reveals whether hosts or ports exist; secrets in logs or error reports.
- Low: hardening gaps with a demonstrated impact.

## Anything to leave alone

- Fake or spammed events: ingestion is unauthenticated by design. Report them only if they reach another site's data
  or break the application.
- Denial of service and missing rate limits.
- Client IP headers (`X-Plausible-IP`, `CF-Connecting-IP`, `X-Forwarded-For`, `B-Forwarded-For`, see
  `lib/plausible_web/remote_ip.ex`) are trusted; deployments run behind a proxy that overwrites them.
- What a verified super admin can do in `/cs` and `/flags`, including acting on any team. Report it only if a
  non-super-admin reaches it.
- Public routes (`/api/event`, public and shared-link dashboards, the Gravatar avatar proxy), unless they expose a
  protected operation or private data.
- Missing checks in functions nothing reachable calls, and defense-in-depth gaps without a demonstrated path, such as
  GitHub Actions `permissions` blocks or redirects that already go through Phoenix `redirect(to:)`.
- Settings a self-hosted operator chooses. Insecure defaults are in scope.
- Dev and test routes: `/dev`, `/plug-tests`, `/e2e-tests`, `/sent-emails`.
- Vulnerable dependencies without a reachable path through Plausible code.

## How reports and patches should look

One issue per report, with the route or LiveView event, the attacker's position (unauthenticated, role, token
scope), the edition (Cloud, CE or both), any settings needed, a reproducer and the observed result. Mark what you
demonstrated and what you read from the source. Fix the check where it is enforced (the plug, `on_mount` hook,
context function or query), and say whether sibling routes, LiveView events and the other edition have the same gap.
