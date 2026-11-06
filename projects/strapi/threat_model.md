# Threat model

This file is for the OSS Scanner. It describes Strapi, the open-source headless CMS in the `strapi/strapi` monorepo. The security policy in `SECURITY.md` is the source of truth. This file repeats the parts that matter for a scan.

## What this project does and where untrusted input enters

Strapi is a Node.js server (Koa) with a React admin panel. Developers define content types. Strapi then exposes the content through three interfaces. The Content API uses REST, and GraphQL with the optional plugin. The Admin API is under `/admin`. The optional MCP server is at `/mcp`.

Untrusted input enters in these places:

- Content API requests from anonymous clients. The `public` role of the users-permissions plugin decides what they can do.
- Content API requests from signed-in end users. These users have the `authenticated` role or a custom role from the users-permissions plugin.
- Admin API requests from admin users that have a limited role (for example Editor or Author). These users are untrusted with regard to anything their role does not allow.
- Query parameters on every list and read endpoint: `filters`, `populate`, `sort`, `fields`, `pagination`, and the GraphQL equivalents. These reach the database layer.
- Request bodies that create or update documents, including components, dynamic zones, and relations.
- File uploads: the file content, the file name, and the metadata fields.
- Callbacks from OAuth providers and password-reset and email-confirmation tokens.
- Bearer tokens: Content API tokens, admin API tokens (also used for `/mcp`), and JWTs.

Trusted actors, which the scanner must not treat as attackers:

- The operator who deploys the application. This person controls the files in the project, the environment variables, the secrets, the database, the installed plugins, and the providers.
- The Super Admin role in the admin panel, for actions that the admin panel is designed to allow.
- The holder of a data transfer (DTS) token. See "Anything to leave alone".

## Components that matter most and least

Most important. Read these first:

- `packages/core/core`: the HTTP server, middlewares, routing, policies, the Content API, the Document Service, query parameter sanitizing, the session manager, and the MCP server (`src/services/mcp`).
- `packages/core/admin/server`: admin authentication, sessions, API tokens, users, and roles.
- `packages/core/permissions` and `packages/core/utils`: the permission engine, `sanitize`, `validate`, and the query parameter handling. A bypass here affects every endpoint.
- `packages/core/database`: query building for SQLite, PostgreSQL, and MySQL. Look for injection through filters, sort, populate, and raw query helpers.
- `packages/plugins/users-permissions`: login, registration, password reset, JWTs, and the provider callbacks.
- `packages/core/upload` and `packages/providers/upload-*`: file handling, file names, paths, and the MIME type rules.
- `packages/core/content-manager/server`: the admin read and write paths and the per-role permission rules.
- `packages/plugins/graphql`: the GraphQL schema and resolvers must enforce the same permissions as REST.
- `packages/core/admin/admin` (the React admin panel): cross-user XSS and the handling of tokens and cookies.

Still in scope, lower priority: `packages/core/content-releases`, `packages/core/review-workflows`, `packages/plugins/i18n`, `packages/plugins/documentation`, the email providers, and `packages/core/data-transfer`.

Out of scope:

- `examples/`: sandbox apps for developers. They use development defaults and sample data.
- `docs/`, `tests/`, `templates/`, `scripts/`, and `.github/`: the contributor website, test code, and repository tooling. A test fixture such as `tests/e2e/data/uploads/blocked-file.exe` is deliberate.
- `packages/cli/*` and `packages/utils/upgrade`: tools that run on a developer machine on files the developer owns.
- Third-party code in `node_modules`, and community plugins that Strapi does not publish.

## How to exercise it

The Dockerfile builds all packages with `yarn build:code`. The scan has no Internet access, so the build already holds every dependency.

To run a real application, use `examples/getstarted`. It uses SQLite, so it needs no other service.

1. Run `yarn build` in `examples/getstarted` to build the admin panel.
2. Start it with `NODE_ENV=production yarn start`. Do not use `yarn develop`.
3. Set `APP_KEYS`, `API_TOKEN_SALT`, `ADMIN_JWT_SECRET`, `TRANSFER_TOKEN_SALT`, and `ENCRYPTION_KEY` to random values. If `JWT_SECRET` is not set, the users-permissions plugin uses `ADMIN_JWT_SECRET`.
4. Create the first admin user at `/admin`. Then create roles and users with different permissions to test access control between roles.

`SECURITY.md` requires that a finding reproduces on a properly configured production application. A finding that only reproduces under `strapi develop` or with the default development secrets is out of scope.

Tests live in `__tests__` folders next to the code. Run them with `yarn test:unit` (server code) and `yarn test:front` (admin panel). The API tests in `tests/api` show the intended permission behavior of the Content API and the Admin API.

## How you rate severity

Rate by the privilege the attacker needs and by what the attacker gains. Use CVSS 4.0 as the base. Report the attacker's starting privilege in every finding: anonymous, end user, limited admin role, or Super Admin.

Critical:

- Remote code execution by an anonymous attacker or by any user without the Super Admin role.
- Authentication bypass that gives an anonymous attacker an admin session, a Content API token, or an account takeover.
- SQL injection or another query injection by an anonymous attacker that reads or writes data.
- Arbitrary file read or write on the host by an anonymous attacker.

High:

- SQL injection, path traversal, or remote code execution by an authenticated user with a limited role. A post-authentication injection is high, not critical.
- Privilege escalation: an end user becomes an admin, or a limited admin role becomes Super Admin.
- Broken access control that reads or writes data the role has no permission for. This includes bypassing `sanitize` so that private fields, password hashes, or tokens appear in a response, and permission differences between REST and GraphQL.
- Stored XSS in the admin panel that runs in the session of another admin with higher privileges.
- Server-side request forgery (SSRF) by a user without the Super Admin role that reaches internal hosts.
- A Super Admin who can read files or run commands on the host outside the Strapi application.
- Theft or forgery of sessions, refresh tokens, API tokens, or transfer tokens.

Medium:

- Denial of service by an anonymous attacker or a low-privilege user. A small request must cause a large cost. Resource exhaustion that needs access to your own instance is not a finding.
- Disclosure of limited sensitive data, such as another user's profile fields that the role does not allow.
- CSRF on a state-changing endpoint that has an exploit path.
- Open redirect with a demonstrated token theft.
- Stored XSS with a narrow reach, for example in the context of the same user.

Low or not a finding:

- Anything under "Anything to leave alone".
- A weakness that needs a misconfiguration that the documentation already describes.

If a finding sits between two levels, choose the lower level and explain the missing step.

## Anything to leave alone

Do not report the following. `SECURITY.md` lists them as out of scope.

- Behavior that only appears under `strapi develop` or with development defaults. Examples are open CORS, verbose errors, stack traces, the default admin URL, and the placeholder secrets in `examples/` such as `toBeModified1`. Upload MIME and extension limits that are not enforced by default are also in this group.
- Known vulnerabilities in a dependency, unless the report shows that Strapi uses the dependency in a way that creates a new vulnerability.
- Data transfer (DTS) payloads. A `push` or `pull` transfer token is issued by an administrator. Its purpose is to copy all data from one environment to another exactly as sent. This includes asset metadata (`hash`, `ext`) and rows of any content type, even `admin::user`, `admin::role`, and `admin::api-token`. Report only that the token can be forged, guessed, or obtained without an administrator.
- Self-XSS with no path to another user.
- Missing security headers, banner or version disclosure, clickjacking on pages without sensitive actions, and username or email enumeration, unless the report shows a concrete exploit.
- Missing rate limits on endpoints that do not change state and have no security impact.
- Attacks that need control of the victim's network, browser extensions, host machine, or developer environment.
- Problems that are caused by operator configuration, such as a weak secret that the operator chose or a role that the operator made too permissive.
- Third-party and community plugins, and the Content-Type Builder, which Strapi only enables in development mode.
- Theoretical issues with no working proof of concept.

## What a good report and patch look like

- Run the reproducer against the production setup in "How to exercise it". Give the exact HTTP requests, the roles and users that exist, and the response that shows the impact.
- Name the starting privilege of the attacker, the version, and the file and line of the root cause.
- Keep the patch small. Fix the root cause in the shared layer (for example `packages/core/utils` or `packages/core/permissions`) and not in one endpoint.
- Add a test in the `__tests__` folder of the package, and make sure that the test fails without the patch.
- Do not change `examples/`.
