# Threat model

## What this project does and where untrusted input enters

Dockhand is a self-hosted web application for managing Docker: containers, images,
volumes, networks, Compose stacks (local and deployed from git), scheduled updates,
vulnerability scans and backups. It is a SvelteKit app running on Node.js (`server.js`,
`src/hooks.server.ts`, API routes under `src/routes/api/**/+server.ts`), with SQLite or
PostgreSQL through Drizzle, and a small Go worker in `collector/`.

Dockhand talks to Docker daemons with full Docker API access: the local socket, a remote
daemon over TCP/TLS, or the Hawser agent (outbound edge WebSocket, or an agent Dockhand
connects to). **Docker API access is root on that host.** Anyone Dockhand allows to create
or edit a container or a Compose stack can therefore act as root on the target host. That
is the product, not a vulnerability.

Untrusted input enters through:
- HTTP requests to `/api/*` and the WebSocket endpoints (terminal, Hawser edge), from
  unauthenticated clients and from authenticated users of every permission level;
- the login flows: local password, LDAP, OIDC (id_token, userinfo), passkeys (WebAuthn);
- webhook endpoints (`/api/git/stacks/{id}/webhook`, `/api/git/webhook/{id}`), which
  authenticate with an HMAC signature or token instead of a session;
- responses from servers Dockhand calls: container registries (auth realms, manifests,
  tag lists, redirects), git remotes, secret providers (Vault, Infisical, Doppler,
  1Password, Psono, and others), notification endpoints, OIDC/LDAP servers, Hawser agents;
- data coming back from Docker itself: container names, labels, environment, logs,
  Compose files, which are rendered in the UI;
- files read and written on the host for stacks and backups (paths supplied by users).

The unauthenticated surface is listed in `src/lib/server/public-paths-core.ts`; everything
else under `/api/` must reject a request without a valid session or `dh_` API token
(`src/hooks.server.ts`). Authorization is in `src/lib/server/authorize.ts`.

## Deployment assumptions

- Authentication is OFF on a fresh install until the operator turns it on (setup mode).
  With authentication off, everything is allowed by design. Findings should assume
  authentication is ENABLED unless they concern the transition itself.
- Free edition: every signed-in user may do everything. Enterprise edition adds roles
  with a permission matrix, optionally scoped to environments (`role.environmentIds`).
- Secrets (registry passwords, stack secrets, provider tokens, Hawser tokens, TLS keys)
  are stored encrypted at rest and should never be returned to a client in plaintext,
  except where the UI explicitly reveals a value to a user allowed to see it.
- Operator-set environment flags deliberately open some surfaces and are not findings
  when set: `ALLOW_WEBHOOKS_WITHOUT_SECRET`, `EXPORT_METRICS_PUBLIC`, `FEAT_API_DOCS`.

## Components that matter most / least

Most:
- authentication and session handling, API tokens, OIDC/LDAP/passkey login, MFA;
- the global auth gate in `src/hooks.server.ts` and every `/api/**/+server.ts` handler's
  permission check (`authorize()`, `auth.can(...)`, environment scoping);
- Hawser connection handling and the edge WebSocket protocol (token checks, request
  forwarding), and the terminal WebSocket (`containers:exec`);
- anything that returns secrets or decrypts them;
- outbound requests built from user input (SSRF guards in `src/lib/server/url-safety.ts`
  and the registry/secret-provider/notification clients);
- file paths for stacks, stack files, container file browsing and backup/restore
  (`src/lib/server/fs-guard.ts`, `src/lib/server/stacks.ts`, `src/lib/server/backups/`);
- rendering of Docker-sourced strings in the UI (stored XSS).

Least / out of scope:
- `tests/`, `scripts/`, `docs/` and other development tooling;
- the Dockerfiles and image build;
- outbound requests to private LAN addresses from registry, git, secret-provider and
  notification URLs: allowed on purpose (homelab registries and services live there).
  Loopback and cloud-metadata addresses must stay blocked.

## How to exercise it

- Build: `npm run build` (already done in the image). Run: `DATA_DIR=/tmp/dockhand
  PORT=3000 node server.js` (SQLite, no Docker daemon needed to reach the API, login,
  settings and RBAC; Docker-backed endpoints return errors without a daemon).
- Turn authentication on through the API (`/api/auth/settings`) after creating a user
  (`/api/users`) to test the authenticated surface.
- Unit tests: `bun test tests/`.
- Go worker: `collector/` (`go test ./...`).

## How you rate severity

- Critical: unauthenticated access to any non-public `/api/*` action or WebSocket with
  authentication enabled; authentication bypass; unauthenticated RCE; theft of a Hawser
  token or session that gives control of a Docker host.
- High: privilege escalation in the Enterprise RBAC (a user acting outside their
  permissions, or a role scoped to one environment reaching another); disclosure of
  plaintext secrets to a user not allowed to see them; SSRF to loopback or cloud
  metadata; stored XSS from Docker-sourced data that runs in another user's session;
  path traversal that reads or writes outside the stack/backup locations for a user
  without host-level access.
- Medium: disclosure of non-secret configuration to users lacking `settings:view` or
  similar; CSRF on state-changing endpoints; denial of service by an authenticated
  low-privilege user.
- Low: issues that need an admin; information disclosure of version or build details.

## Anything to leave alone

- "A user who can create/edit containers or stacks can mount the host filesystem, run a
  privileged container, or reach the Docker socket": by design (Docker API = root).
- Everything an admin can do, and everything allowed with authentication disabled.
- The Free edition granting every signed-in user full access.
- Requests to private LAN addresses from user-configured URLs (see above).
- Missing rate limits on authenticated endpoints, unless they enable a real attack.
