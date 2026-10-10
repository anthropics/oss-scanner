# Threat model: laravolt/laravolt (Laravolt Platform)

## What this project does and where untrusted input enters

Laravolt Platform is a Laravel package (monorepo) that turns a Laravel app into an admin/back-office
system: user, role and permission management ("Epicentrum"), ACL, password management, form and
table builders, auto CRUD, media upload and file manager, lookup/master data, mail keeper,
database monitor, Camunda-based workflow, Livewire UI components. It is installed into a host app
(see the CI workflow: `laravolt/laravel-starter-kit` + `php artisan laravolt:install`).

Untrusted input enters through HTTP routes registered by the package:

- `routes/epicentrum.php`: `/epicentrum/users`, `/account`, `/password/{id}/reset|generate`,
  `/roles`, `/permissions`, guarded by `config('laravolt.platform.middleware')` plus
  `can:` permission middleware (`Laravolt\Platform\Enums\Permission`).
- `routes/web.php`: `/platform/settings` (GET/PUT), `/platform/components/{component}`,
  `/platform/dump` (any method), playground views, and the public `/platform/preline` showcase.
- Package routes under `packages/*/routes` (file manager, media, lookup, auto-crud, workflow,
  database monitor, mailkeeper) and Livewire components in `src/Ui` and `packages/*/src`.
- Form/table builders (`packages/semantic-form`, `packages/preline-form`, `packages/suitable`) render
  values that ultimately come from end users (search, filters, sort columns, exported files).
- File uploads and file names (`packages/media`, `packages/file-manager`).

Attacker models, in order of importance:
1. Unauthenticated visitor of an app with the default middleware.
2. Authenticated user with no admin permissions.
3. Authenticated user with one permission (e.g. manage users) trying to gain another (e.g. manage
   permissions) or to act on users above them.

Trusted: config files, operators running artisan commands, the database schema, stubs used by code
generators (`packages/thunderclap`, `stubs/`).

## Components that matter most / least

- Most: `src/Epicentrum` (users/roles/permissions controllers and requests), ACL and permission
  checks (`src/Platform`, `Acl` / `Role::syncPermission`), password reset/generate flows, middleware in
  `src/Middleware`, `packages/media`, `packages/file-manager`, `packages/auto-crud`, `packages/suitable`
  (search/sort/filter/export), `packages/workflow` (BPMN/XML handling and form submission),
  `packages/database-monitor`, `/platform/settings` and `/platform/dump`.
- Less: `packages/semantic-form` / `packages/preline-form` HTML builders (still in scope for XSS),
  `packages/asset`, `packages/support`, `packages/lookup`, `packages/mailkeeper`.
- Out of scope: `tests/`, `stubs/`, `scripts/`, `.scratch/`, `.jules/`, `benchmark.php`,
  `resources/` front-end build tooling, `packages/pint`, and vulnerabilities that live entirely in
  third-party packages (Livewire, spatie/*, dompdf, debugbar, web-tinker) unless Laravolt enables or
  exposes them in a way their docs warn against.

## Risks we care about

- Authorization bypass / privilege escalation: reaching an Epicentrum or package route without the
  required `can:` permission, assigning yourself roles/permissions, editing or resetting the password
  of a more privileged user, IDOR on `{id}` parameters.
- SQL injection through table search, sort column, filters or auto-CRUD field definitions.
- Stored/reflected XSS through form/table builders, Livewire components, settings, lookup values,
  file names.
- Unrestricted file upload, path traversal or arbitrary file read/delete in media and file manager.
- SSRF/XXE in workflow (Camunda client, BPMN XML parsing) and any URL-fetching helpers.
- Sensitive data exposure: `/platform/dump`, database monitor, mail keeper, debug tooling enabled by
  the package in non-local environments.
- Mass assignment on users, roles, settings.
- CSRF on state-changing routes that do not use the `web` middleware group.

## How to exercise it

- The image has two installs:
  - `/src`: the package with its own dev dependencies; run `vendor/bin/pest` (tests in `tests/`,
    `DB_CONNECTION=sqlite`, `DB_DATABASE=:memory:` are set in the image environment).
  - `/app`: a `laravolt/laravel-starter-kit` app with the package symlinked at
    `vendor/laravolt/laravolt` -> `/src`, already `laravolt:install`-ed and migrated
    (`database/database.sqlite`). Run `php artisan test tests/Feature`, or
    `php artisan serve` and drive it with curl. `php artisan route:list` shows every route.
- Create users/roles with the app's seeders or tinker to test the three attacker models above.

## How you rate severity

- Critical: unauthenticated RCE, SQL injection, authentication bypass, or account takeover in a
  default install.
- High: privilege escalation from a normal authenticated user to admin (role/permission
  self-assignment, missing `can:` check), authenticated SQL injection, stored XSS that runs in an
  admin's session, arbitrary file read/write/delete, unrestricted upload leading to code execution.
- Medium: IDOR that reads or changes another user's non-admin data, reflected XSS, CSRF on
  state-changing routes, SSRF limited to internal HTTP GET, information disclosure of secrets through
  `/platform/dump` or monitors to authenticated users.
- Low: issues needing an admin to attack themselves, self-XSS, verbose errors with `APP_DEBUG=true`,
  open redirects without further impact, missing rate limiting.

## Report and patch format

- Please include the attacker model (1/2/3 above), the route or component, a reproducer (Pest test in
  `/src/tests` or a curl sequence against `/app`), and a patch against `src/` or `packages/`.

## Anything to leave alone

- Do not report that the host app ships with `APP_DEBUG=true`, a default `APP_KEY` from
  `phpunit.xml.example`, or demo credentials; those are test fixtures.
- Do not report the public `/platform/preline` showcase as exposure; it is a static view by design.
- Do not report vulnerabilities in dev dependencies (Pest, Pint, testbench, php-coveralls).
