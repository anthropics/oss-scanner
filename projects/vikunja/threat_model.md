# Vikunja threat model

## What this project does and where untrusted input enters

Vikunja is a self-hosted to-do app: a Go API server (`pkg/`) with an embedded Vue 3 frontend (`frontend/`). One instance usually serves many users who don't trust each other, so treat every registered user as a potential attacker against every other user.

Attacker positions, from strongest to weakest assumption:

- **Unauthenticated**: anyone who can reach the HTTP port. Login, registration, password reset, OpenID Connect/LDAP login, link share auth, public info endpoints.
- **Link share holder**: someone with a project's share link (optionally password protected). Gets read, write or admin rights on that one project only.
- **Registered user**: can create their own projects and teams, and be invited to others' projects. Must never see or change anything they weren't shared.
- **API token holder**: tokens are scoped to specific permissions. Using a token beyond its scopes is a vulnerability.
- **Remote content**: CalDAV clients, migration imports (Todoist, Trello, Microsoft To-Do, TickTick, Planka, Wekan, Vikunja export zip, CSV), webhook targets, avatar and Unsplash downloads, OIDC provider responses.

The instance admin (config file, CLI commands, plugins) is trusted.

## Components that matter most

- **Permissions** (`pkg/models/*_permissions.go`): every `Can*` check on projects, tasks, attachments, comments, labels, teams, saved filters, webhooks, link shares, API tokens. Sub-project and team permission inheritance is a common bug source. Both `/api/v1` and `/api/v2` (`pkg/routes/`) are in scope.
- **Auth** (`pkg/modules/auth/`, `pkg/user/`): JWT and session handling, TOTP, password reset and email confirmation tokens, OpenID Connect, LDAP, and Vikunja acting as an OAuth2 provider (`oauth2server/`).
- **Filter query parser** (saved filters, task search): user input becomes SQL. Test it on sqlite; SQL injection there likely applies to Postgres and MySQL too.
- **Outgoing requests** (`pkg/utils/httpclient.go`): blocks non-routable IPs unless `outgoingrequests.allownonroutableips` is set. Any bypass (DNS rebinding, redirects, IPv6 tricks, alternate IP notations) is in scope.
- **File handling**: attachments, avatar and background uploads, image processing (`pkg/modules/imageutils`), migration import zips (path traversal, decompression bombs).
- **Rich text** (task descriptions, comments): stored XSS that runs in another user's browser. The frontend keeps the auth token where scripts can read it, so XSS means account takeover.
- **CalDAV** (`pkg/caldav`) and **websocket** (`pkg/websocket`): same permission rules as the REST API.
- **MCP** (`pkg/modules/mcp`): tools must not reach beyond the caller's permissions.

## Components that matter least

- `pkg/license/`: gates paid features. Bypassing it is not a security issue; don't report it.
- `pkg/plugins/`, `pkg/yaegi_symbols`: plugins are installed by the admin and run with full trust.
- CLI commands are admin only, but a crafted dump file attacking `vikunja restore` is in scope.
- `desktop/` (Electron wrapper) is in scope: XSS escalating to code execution there has been critical before.
- `veans/`: low priority.

## How to exercise it

- Use mage for Go tests: `mage test:filter <TestName>`, `mage test:feature`, `mage test:web`. Plain `go test` runs need `-p 1` because tests share a database. The default test DB is in-memory sqlite.
- `pkg/webtests/` has end-to-end HTTP tests against the full router with fixture users. Write reproducers there. Fixtures live in `pkg/db/fixtures/`.
- The built server is `/src/vikunja`. Run it with `VIKUNJA_DATABASE_TYPE=sqlite VIKUNJA_DATABASE_PATH=/tmp/vikunja.db VIKUNJA_SERVICE_PUBLICURL=http://127.0.0.1:3456 /src/vikunja` and register users through `POST /api/v1/register`.
- Frontend unit tests: `cd /src/frontend && pnpm vitest run <file>`.

## How we rate severity

- **Critical**: unauthenticated RCE, authentication bypass, or unauthenticated access to other users' data. SQL injection reachable without authentication. Code execution through the desktop app.
- **High**: a registered user or link share holder reading or changing another user's projects, tasks, attachments or account. Privilege escalation inside a shared project (read to write, write to admin). Stored XSS that triggers in another user's session. SSRF guard bypass. SQL injection reachable by any registered user. API tokens working beyond their scopes. A single request (authenticated or not) that crashes or OOM-kills the server.
- **Medium**: cross-project disclosure of limited data (one comment, a related task's title). Access that survives revocation (removed collaborators, deleted shares, revoked sessions). Missing rate limits on auth endpoints. Reflected HTML injection.
- **Low**: email addresses shown to members of a shared project, cross-project writes with no disclosure and little impact.
- Issues that need instance admin access or a non-default insecure config are out of scope unless the docs recommend that config.

## Report requirements

Include the attacker position, required config, and a reproducer, ideally a test in `pkg/webtests/` or a curl sequence against a fresh instance. A finding needs a reachable route; a missing check in one function is not enough if the route or another layer enforces it.

## Recurring bug classes

These were reported and fixed several times. Look for remaining instances and incomplete fixes instead of re-reporting the fixed ones:

- An ID from the request body or URL (`task_id`, `project_view_id`, `bucket_id`, link share ID) is used without checking it belongs to the resource whose permission was checked. Kanban bucket moves and task positions had this repeatedly.
- Link share hashes readable by read-only members, letting them escalate to the share's permission level (fixed three times).
- Link share principals confused with user IDs, since both are numeric.
- Access that outlives revocation: link share JWTs, webhooks, favorites, websocket sessions.
- `/api/v2` endpoints missing a check or rate limit that their `/api/v1` twin has.
- Unbounded work from one request: image decoding, import archives, filter nesting, CSV rows.

## Not vulnerabilities

Each of these was reported and closed. Don't report them:

- The OAuth2 server accepting any `client_id` and showing no consent screen. It only serves public PKCE clients, so there is no client registry by design.
- Telling registered emails apart through password reset, login or registration responses.
- Sessions created before a user enabled TOTP remaining valid.
- Image EXIF metadata not stripped from attachments.
- Writes to archived projects. Archiving is not an access control.
- Webhooks reaching internal hosts when `outgoingrequests.allownonroutableips` is enabled or a proxy is configured.
- XSS through admin-controlled config values (custom logo URL, Sentry DSN).
- CSRF against CalDAV and feed endpoints through cached BasicAuth credentials.
- Unauthenticated websocket upgrades holding connections open.
- Date overflows in repeating tasks a user created for themselves.
- User search returning other users by username, so they can be invited to projects.
- Link shares granting whatever rights the project owner chose to anyone holding the link.
