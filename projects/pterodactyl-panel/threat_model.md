# Threat model

## What this project does and where untrusted input enters
Pterodactyl Panel is the web control plane for a game server hosting platform (Laravel backend, React frontend). It manages users, servers, nodes and eggs, and tells Wings daemons on each node what to run. Untrusted input enters through:
- The Client API (`/api/client`, `routes/api-client.php`), used by end users and subusers. Access is per server, through subuser permissions in `app/Models/Permission.php`. Most users of a hosted panel are untrusted customers.
- Authentication: login, two-factor checkpoint, password reset, OAuth-style session flows (`app/Http/Controllers/Auth`).
- The Remote API (`/api/remote`, `routes/api-remote.php`), called by Wings with a node token. A node is trusted with its own servers only, never with other nodes' servers or the panel itself.
- The Application API (`/api/application`), authenticated by admin API keys scoped through `app/Services/Acl/Api/AdminAcl.php`. Treat a key as trusted only for the resources and permissions it was granted.
- Egg imports, server startup variables (validated in `app/Services/Servers/VariableValidatorService.php`), file names and paths passed on to Wings, and extension packages installed by an admin.

## Components that matter most / least
- Most: authorization between users, subusers and servers (IDOR, missing permission checks), authentication and 2FA bypass, the Remote API's node scoping, startup variable and egg handling that reaches Wings, and anything that gives a non-admin user admin access.
- Also in scope: SSRF from the panel to arbitrary hosts, stored XSS in the SPA, CSRF on session-authenticated routes, mass assignment.
- Less: the admin area itself. Admins are trusted to configure the panel; an admin hurting their own panel is not a vulnerability unless an API key's limited permissions are exceeded.
- Out of scope: `vendor/`, `node_modules/`, generated API clients in `resources/scripts/api/generated` and `packages/sdk/types`, and third-party extensions.

## How to exercise it
- Start MariaDB with `service mariadb start`, then run `composer test:integration`. A single test: `php -d memory_limit=2G vendor/bin/pest tests/Integration/Path/To/SomeTest.php`. Integration tests build users, servers and API keys with factories and are the quickest way to reproduce an authorization bug.
- Unit tests: `composer test:unit`. Frontend tests: `npm test`.
- Wings is not in this image; calls to it go through `app/Services/Daemon` and are mocked in tests.

## How you rate severity
- Critical: unauthenticated or customer-level access to other users' servers, accounts or the panel host; remote code execution on the panel; admin takeover from a non-admin account.
- High: a subuser exceeding their granted permissions on a server in a way that reaches files, databases, backups or credentials; 2FA bypass; a node token reaching another node's servers; stored XSS that runs in an admin's session.
- Medium: stored XSS limited to the attacker's own server views, information disclosure of non-secret metadata about other servers, CSRF with limited impact.
- Low: rate limiting gaps, user enumeration, missing hardening headers.
- Issues that need an admin account or admin API key with full permissions are low at most.

## Anything to leave alone
- Do not report that admins can run arbitrary code through eggs, startup commands or extensions. That is intended.
- Do not report findings that only apply to the development docker setup or `APP_DEBUG=true`.
