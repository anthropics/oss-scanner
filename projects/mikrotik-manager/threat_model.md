# Threat model

## What this project does and where untrusted input enters

MikroTik Manager (MTM) is a self-hosted web app for managing fleets of MikroTik RouterOS
devices. It stores an admin login for every managed router (and optionally SSH keys), polls the
routers over the RouterOS API, and can push configuration, run commands, upgrade firmware, restore
backups and open an SSH terminal to them. Anyone who takes over MTM controls every network it
manages, so it is the crown jewel in a deployment.

It runs in Docker Compose: an Express/TypeScript backend (`backend/`), a React frontend served by
nginx (`frontend/`, `nginx/`), PostgreSQL, Redis and InfluxDB.

Untrusted input enters through:

- **The HTTP API (`/api/*`)** and the Socket.IO SSH terminal (`/terminal` namespace). Callers
  range from anonymous (login, OIDC callback) to authenticated users with different roles.
- **Data the managed routers report.** Treat everything read from a device as attacker-controlled:
  a compromised or malicious router, or anyone who can set a value on one, controls interface
  names, comments, identities, log lines, certificates, DHCP lease hostnames, LLDP/CDP/MNDP
  neighbour names, wireless registrations and so on. These end up in the database and in the UI.
- **NetFlow/IPFIX on UDP** (`backend/src/services/netflow/`), unauthenticated packets from the
  network.
- **Clients on the network:** DHCP hostnames, MAC/vendor data and similar flow in through the
  routers and are shown in the UI.
- **Outbound fetches:** the NVD CVE feed and MikroTik's firmware download site, and HTTP(S)
  replies from routers.
- **Identity providers (OIDC)** and **webhook/alert channel** settings, which admins configure.

## Components that matter most / least

Most important:

- **Authentication and sessions:** `backend/src/middleware/auth.ts`, `routes/auth.ts`,
  `routes/oidc.ts`. JWT sessions (revocable), scoped API tokens (`mtm_…`, hashed at rest; read
  scope is viewer, write scope is operator), TOTP 2FA, OIDC login.
- **Authorization:** roles are admin > operator > viewer, plus per-site roles
  (`middleware/site.ts`). Viewers and read-scope tokens must not change anything or see device
  secrets (`utils/redactSecrets.ts`). Site-scoped users must not reach devices in other sites. A
  bypass of either is in scope.
- **Stored secrets:** router passwords and SSH private keys are encrypted with AES-256-GCM
  (`utils/crypto.ts`, key from `ENCRYPTION_KEY`). Anything that discloses them, or the key, matters.
- **Command and config execution on routers:** RouterOS API calls (`services/mikrotik/`), SSH
  commands (`services/sshExec.ts`, `services/CommandRunner.ts`), bulk commands and templates,
  firmware upgrades, backup restore. Injecting extra RouterOS commands or parameters through any
  user- or device-supplied value is in scope.
- **Change Guard** (`services/changeGuard/`): predicts and auto-reverts changes that would cut off
  management. Ways to bypass its checks or its write lock are in scope.
- **Change preview** (`middleware/changePreview.ts`, `utils/changePreview.ts`): a request with
  `X-Preview-Changes: 1` must never apply anything to a device or the database.
- **The frontend**: stored XSS via device- or client-supplied data rendered in the UI.

Less important:

- The documentation site (`docs/`, MkDocs) and helper scripts in `scripts/`.
- Charts and purely presentational components.

## How to exercise it

The image has both halves built and their unit tests run:

- `cd /src/backend && npx jest` (135 suites, no database or network needed)
- `cd /src/frontend && npx vitest run`

To run the API: `mtm-start` starts PostgreSQL, Redis and the backend on `http://127.0.0.1:3001`.
Migrations run at startup and seed the account `admin` / `admin`, which must change its password
before anything else works (`PUT /api/auth/password` with `currentPassword` and `newPassword`). InfluxDB is absent, so metrics
writes fail harmlessly. There are no routers to manage offline; device-facing code is best
exercised through its unit tests and fixtures (`backend/src/services/mikrotik/__fixtures__`).

## How you rate severity

- **Critical:** unauthenticated remote code execution; unauthenticated access to the API;
  disclosure of stored router credentials, SSH keys or `ENCRYPTION_KEY`; injecting commands that
  run on managed routers without being an operator or admin.
- **High:** a viewer, read-scope token or site-scoped user changing configuration, reaching
  another site's devices, or reading device secrets; stored XSS from device- or network-supplied
  data (it runs in an admin's session); authenticated RCE on the MTM host; SSRF that reaches
  internal services; authentication or 2FA bypass with some precondition.
- **Medium:** stored XSS that needs an admin to enter the payload; CSRF on state-changing
  endpoints; information disclosure without secrets (inventory, topology, logs) across roles or
  sites; denial of service from the network (for example a malformed NetFlow packet crashing the
  backend).
- **Low:** issues that need admin access to exploit against the same admin; missing hardening
  without a demonstrated impact.

Admins are trusted to configure the system, including running arbitrary commands on routers they
manage, so "an admin can run a RouterOS command" is by design. An admin escaping to the MTM host
OS is in scope.

## Anything to leave alone

- RouterOS itself and MikroTik's firmware are out of scope; report MTM's handling of them.
- Self-signed TLS by default, the seeded `admin`/`admin` account (a password change is forced on
  first login) and the Docker host's own security are documented deployment choices.
- Dependencies' known CVEs are tracked by Dependabot; report one only when MTM's use of it is
  exploitable.
- The test secrets in this image's `mtm-start` are not real.
