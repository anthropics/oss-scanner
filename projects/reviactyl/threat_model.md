# Reviactyl Panel

## Project and scope

Reviactyl is an MIT-licensed game-server management platform derived from
Pterodactyl, with an independently maintained Laravel backend, Filament admin
interface, React frontend, extension system, and a separate Go Agent. Operators
use the Panel to manage users, nodes, game servers, files, backups, databases,
schedules, and delegated server access. A Panel compromise can expose customer
data and grant control of the servers and nodes it manages.

This enrollment targets `reviactyl/panel`, on `develop`. Nothing within the
enrolled project is out of scope. All code, features, routes, configurations,
roles, and vulnerability classes are open to investigation, including inherited
code, development/build tooling, installation and upgrade paths, integrations,
and dependencies as used by the Panel. The priorities below are starting points,
not an exhaustive list or a restriction on what may be investigated or reported.

The image contains the Panel checkout. The Go Agent lives in the separate
`reviactyl/agent` repository and is not fetched by this enrollment. This is an
environment limitation, not an exclusion of Panel-Agent security issues.
Investigate authentication, token generation, callbacks, request construction,
and response handling across that boundary. Use a local fake Agent when useful,
and state when a finding needs additional Agent code or runtime validation.

For dependency-related findings, identify the affected dependency and explain
how the Panel reaches or exposes the vulnerable behavior. Distinguish findings
in Panel code from those whose root cause is in a dependency.

## Actors and trust boundaries

- Unauthenticated Internet users can reach login, account recovery, installation
  endpoints where applicable, public routes, and publicly reachable API routes.
- Authenticated customers are not administrators. A customer must not gain
  access to another customer's account, servers, files, backups, databases,
  credentials, or API tokens by changing identifiers or supplying crafted data.
- Server owners can grant subusers specific permissions. A subuser must not
  exceed those permissions, including through alternate routes, API calls,
  previews, impersonation state, background jobs, or stale shared frontend state.
- Application API keys and Client API keys have distinct scopes and privilege
  models. Check ownership, key abilities, IP restrictions, and revocation at
  the actual action, not only at the UI.
- Panel administrators are privileged and may intentionally configure nodes,
  database hosts, software sources, and executable extensions. This does not
  make CSRF, stored XSS, broken reauthentication, or actions reachable by a less
  privileged actor acceptable.
- Game-server workloads and customer-supplied data are untrusted. Agent/node
  credentials authorize specific infrastructure operations; possessing one
  node's credentials must not silently confer access to other nodes or users.

## Surfaces to prioritize

1. Authentication and session handling: password recovery, two-factor
   authentication, passkeys, OAuth linking, API authentication, session
   invalidation, cookie handling, and privileged account changes.
2. Authorization and tenant separation: route model binding, server ownership,
   subuser permissions, administrative actions, API key scopes, impersonation,
   and download or websocket tokens. Check direct backend requests even when
   the frontend hides the relevant control.
3. Files and archives: file paths, uploads, downloads, remote downloads,
   archive handling, backup access and restore requests, signed links, and
   database import/export. Distinguish Panel validation from operations that
   are actually implemented in the separate Agent.
4. Untrusted structured input: SQL imports, egg/catalog definitions, startup
   variables, schedules, extension manifests, and configuration imports.
   Examine injection, parser differences, archive traversal, secret disclosure,
   and unsafe handling of remote URLs or redirects.
5. Panel-Agent protocol: node authentication, request signing/token scope,
   callbacks, state transitions, backup completion, and replay or cross-node
   confusion. Establish the actual privileges of the attacker.
6. Frontend and Filament: stored/reflected/DOM XSS, unsafe HTML or URL rendering,
   cross-user data leakage, live component authorization, and backend actions
   that trust client-provided state.
7. Privileged maintenance: extension installation, updates, database-host
   credentials, mail/OAuth secrets, and sensitive environment variables.
   Verify that secrets remain protected in API responses, logs, exports,
   validation errors, and responses to subusers.

## Behavioral context, not scope exclusions

- An authorized customer executing commands inside their own game server is
  an intended capability. Investigate whether it can cross into another tenant,
  the Panel host, or an unauthorized node operation.
- An administrator installing a trusted extension may intentionally execute
  PHP code. Investigate the installation path, permissions, configured upload
  restrictions, and handling of malicious content, including attacks that
  require administrator interaction.
- Some authorized features intentionally connect to configured remote services
  or URLs. Investigate SSRF, redirects, destination validation, and unintended
  access to services or credentials, documenting the actor's permissions.
- Denial of service, configuration-dependent findings, administrator-only
  findings, and issues in less common features are all in scope. Explain the
  prerequisites and resulting impact so intended capabilities can be
  distinguished from exploitable behavior.
- Report potential issues even if severity is uncertain or the local image
  cannot fully reproduce them. State the affected revision/configuration,
  evidence, uncertainty, and any additional validation needed.

## Offline environment and reproduction

The checkout is at `/src`. The Dockerfile installs PHP 8.5 with the required
extensions, Node.js 24, the project's declared pnpm version, all locked Composer
and frontend development dependencies, and built web assets. Composer scripts
are initialized explicitly. The image uses Debian Trixie for a SQLite version
that supports the historical migrations, and a 1 GB PHP memory limit for tests.
No production credentials or production services
are used. The generated `.env` and application key are disposable local values.

SQLite is the default database, at `/src/database/testing.sqlite`, initialized
with the project's migrations and seeders. Cache, sessions, queued work, and
mail use array/synchronous drivers so tests do not require external services.
These test settings are not production deployment recommendations. For session
or cache persistence between HTTP requests, select an appropriate persistent
driver and initialize its backing store before interpreting the result.

Run these commands from `/src` after networking is disabled:

```sh
vendor/bin/pest tests/Unit
vendor/bin/pest tests/Integration
pnpm test
pnpm run build
php artisan migrate:fresh --force --seed --no-interaction
```

`migrate:fresh` destroys the disposable database. Tests also mutate local data;
use fresh fixtures when reproducing an issue. The image does not create an
administrator with a known password. Create accounts using test factories or
`php artisan p:user:make` when testing an HTTP flow.

For a local HTTP reproduction, use file sessions so login survives subsequent
requests, and bind only to the local loopback interface:

```sh
SESSION_DRIVER=file php artisan serve --host=127.0.0.1 --port=8000
```

MariaDB server/client, PDO MySQL/PostgreSQL drivers, SQLite tooling, and Redis
are installed for additional offline investigations. MariaDB and Redis are not
started automatically. SQLite tests alone do not establish behavior on MySQL,
MariaDB, or PostgreSQL. Database-specific issues need reproduction against the
affected backend; a PostgreSQL server is not included in this image.

Frontend unit tests use the project's configured DOM environment. Browser
automation binaries, a running Agent, real game servers, and external OAuth,
SMTP, S3, and database hosts are not provisioned. Use local fixtures/mocks or
explicitly initialize the needed local service; do not treat an unavailable
external service as a product vulnerability.

## Severity and report expectations

- Critical: demonstrated unauthenticated Panel-host code execution, broad
  administrative compromise, or an equivalent exploit with severe impact.
- High: demonstrated account takeover, privilege escalation, consequential
  cross-tenant access, or exposure of secrets that grants comparable access.
- Assess XSS according to the reachable victim and resulting privileges.
  A demonstrated administrative takeover can be high. Include self-XSS and
  user-interaction requirements where relevant to assessing a finding.
- State authentication requirements, granted subuser/API permissions, required
  user interaction, and affected configurations. Distinguish control of one
  game server from control of a node or the Panel host.

Provide the affected revision, root cause and code locations, a minimal local
reproducer or regression test, expected versus actual behavior, and a focused
patch where possible. Explain which security boundary is crossed. Deduplicate
reports sharing a root cause and list affected routes/call sites together.
Do not include real customer data or credentials. Reports should go privately
to the contacts in `project.yaml`, not public issues or pull requests.
