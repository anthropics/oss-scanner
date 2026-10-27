# Filament security scan

## Project and scope

Filament is an MIT-licensed Laravel UI framework built on Livewire and Alpine.js.
It supplies panels, resources, forms, tables, actions, schemas, infolists,
notifications, and widgets. Downstream applications use it to administer sensitive
data and to build user-facing and multi-tenant interfaces.

Scan the checked-out default branch. The first-party implementation is in
`packages/`; tests and fixtures are in `tests/`. Do not report vulnerabilities
solely in Composer/npm dependencies, example credentials, or intentionally
permissive test fixtures as vulnerabilities in Filament itself. A vulnerability
in Filament's integration with a dependency remains in scope.

## Trust boundaries

Application developers and their PHP configuration, Blade templates, closures,
registered custom blocks, and explicit trusted-HTML objects are trusted. Browser
users are not, including authenticated panel users with limited permissions,
users in other tenants, and authors of stored content.

Treat routes, query strings, Livewire method arguments, client-writable state,
action arguments, record selections, uploads, stored content, and attachment
identifiers as potential adversarial inputs. Establish which values an attacker
can actually control: do not assume arbitrary mutation of Livewire's signed
snapshots or locked properties without demonstrating a bypass. A valid snapshot
does not establish continued authorization after access changes.

Read `docs/09-advanced/06-security.md`, `docs/07-users/03-tenancy.md`, and the
owning feature's documentation before classifying a finding. Documentation
explains intended contracts, not proof that their implementation is correct.
Check enforcement through direct Livewire requests, not just visible UI controls.

## Priority areas

- Authentication, panel access, MFA, and repeated authorization on subsequent
  Livewire requests, including changes in permission since initial rendering.
- Built-in resource operations, action execution, record resolution, relationship
  queries, bulk operations, and tenant isolation where Filament promises it.
- Tampering with component state and invoking methods through Livewire RPC.
- File upload and attachment handling: access to another user's files, traversal,
  unintended deletion, unsafe storage, and server-side file operations.
- Stored/reflected XSS and unsafe HTML, Markdown, rich-content, URL, or CSS
  rendering where Filament promises escaping or sanitization.
- Imports, exports, downloads, queued actions, and query construction where
  untrusted values cross a first-party security boundary.

Do not dismiss a finding merely because the attacker is authenticated: a
low-privilege user crossing into another user's, tenant's, or administrator's
permissions is a relevant attacker model.

## Avoid configuration-only false positives

Demonstrate a failure of a documented Filament guarantee under an otherwise
correct configuration. Missing application-owned authorization, deliberately
disabled safeguards, and intentional trusted-code escape hatches are not by
themselves bypasses. In particular:

- Missing resource policies/methods allow operations by default unless denied
  elsewhere; strict authorization is opt-in. Custom actions and inline editable
  columns have their own documented authorization requirements.
- Record query scoping and policy authorization are distinct. Do not assume
  every listed record or bulk operation has an individual policy check.
- Tenant scoping has documented model, panel, request-lifecycle, and query
  boundaries. Application-owned properties and passed-in models do not all
  inherit a parent resource's record-binding guarantees.
- Trusted configuration such as `url()`, extra attributes, custom block HTML,
  and explicit raw HTML is not interchangeable with untrusted field content.
  Test actual sanitization/escaping promises rather than requiring all trusted
  developer configuration to be sanitized automatically.
- Public storage, preserved original upload names, and custom attachment
  providers have documented security implications. Show the attacker path and
  the violated guarantee instead of assuming these options are always safe.

If a default or documented limitation nevertheless creates a practical exploit,
describe the exact deployment assumptions and impact so maintainers can assess
it; do not silently exclude a demonstrated exploit as mere misconfiguration.

## Exercising the project offline

The image contains PHP 8.4, Composer dependencies, Node.js, built frontend assets,
and Playwright Chromium. The checkout and working directory are `/src`. SQLite
tests need no external database. No production credentials or services are needed.

Use the existing Testbench/Pest fixtures rather than requiring a separate demo
application:

```sh
vendor/bin/pest --configuration=phpunit.sqlite.xml tests/src/Forms/Components/FileUploadTest.php
vendor/bin/pest --configuration=phpunit.sqlite.xml tests/src/Forms/Components/RichEditorTest.php
vendor/bin/pest --configuration=phpunit.sqlite.xml tests/src/Panels/Tenancy
npm run test:js
```

The broader non-serial suite is `composer test:sqlite`; serial tests run with
`composer test:serial:sqlite`. Browser tests are also in `tests/src/` and use Pest
Browser. MySQL, PostgreSQL, SQL Server, and external integrations are not provisioned
in this image; do not present SQLite coverage as proof about those backends.

## Reports and severity

Prefer a small runnable reproducer or regression test through a public API or a
real HTTP/Livewire request. Include the scanned commit, affected component,
attacker permissions, required configuration, exact steps, expected versus actual
results, and demonstrated impact. Distinguish observed behavior from hypotheses.
Group the same root cause across components into one report with affected paths.

Use severity based on realistic reachability and demonstrated impact. Clearly
distinguish unauthenticated attacks, low-privilege authenticated attacks,
cross-tenant access, and attacks requiring trusted application-code control.
Do not inflate severity from a hypothetical exploit chain.

Proposed patches should be minimal, preserve documented extension points, and
include a behavior-focused regression test where practical. Do not silently
remove supported developer configuration to make a reproducer pass.

Keep findings private. Filament's existing security reporting channel is GitHub
private vulnerability reporting, as documented in `SECURITY.md`.
