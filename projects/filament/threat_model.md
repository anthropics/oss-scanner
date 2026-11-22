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

### Query controls, relationship actions, and custom data

Client-controlled table filters, tabs, and query-builder rules are not mandatory
access restrictions. A `SelectFilter`'s `options()` limits its displayed options,
not the values accepted by its query. An over-limit query-builder tree is ignored
rather than applied. Mandatory restrictions belong in the underlying resource or
table query or applicable global scopes, independently of these controls.
See `packages/tables/docs/03-filters/` and
`docs/03-resources/02-listing-records.md`.

For attach/associate actions, do not confuse the existing relation manager's
table query, or an attachment picker's display query, with the allowed related
record query. `recordSelectOptionsQuery()` is applied when resolving submitted
records for attachment/association; the relation table's `modifyQueryUsing()`
restricts existing rows, not candidates outside the relationship. Attach,
associate, detach, and dissociate actions do not infer model-policy abilities;
the relation manager's read-only check is not per-record authorization. See
`docs/03-resources/07-managing-relationships.md` and
`packages/actions/src/AttachAction.php` / `AssociateAction.php`.

Nested resources require ancestor resource access and relationship-chain
scoping, not each ancestor record's `view()` or `update()` permission. The child
operation has its own policy checks. Do not infer an ancestor-record policy
guarantee from nesting alone; see `docs/03-resources/08-nesting.md`.

Array/API-backed tables do not gain Eloquent scopes or model policies. Their
application-owned data callbacks and action handlers must restrict data and
operations. An upstream API credential authenticates the application, not the
current user's permission; see `packages/tables/docs/09-custom-data.md`.

### Imports, exports, and spreadsheet output

Importers and exporters do not run model policies for each processed record.
Applications must authorize importing and exporting, restrict export queries,
and add importer lifecycle checks where individual permissions are needed.
Tenant-aware imports restore their panel/tenant context, but do not inherit
custom resource query restrictions or substitute for per-record authorization.

Export files and import failure CSVs preserve data by default. Spreadsheet
formula neutralization is opt-in: `ExportColumn::preventFormulaInjection()` or
the importer's `preventFormulaInjection()` setting. This avoids changing valid
data and breaking failure-CSV correction/re-import. When protection is enabled,
sign-led numeric strings such as `-5` intentionally remain unchanged. Distinguish
this documented default from a bypass of enabled protection or an unexpected
attacker path. See the security sections in `packages/actions/docs/11-import.md`
and `packages/actions/docs/12-export.md`.

Download controllers separately check the initiating user or a configured
`view()` policy. This does not protect files served directly from public storage;
storage visibility is an application deployment choice, not equivalent to
controller authorization. Bypassing the controller's ownership/policy check
remains in scope.

### Panel access and MFA

Custom panel pages default to allowing authenticated panel users unless their
`canAccess()` method restricts them. Hiding a resource from navigation is not a
route authorization check. Conversely, do not assume every visibility setting
is merely cosmetic: action visibility/disabled state and inline-column disabled
checks have server-side enforcement. Inspect the owning execution path before
claiming that direct RPC bypasses a configured restriction.

Filament's login flow challenges users with an enabled MFA provider. The
required-MFA middleware enforces provider setup, not a fresh challenge for a user
already authenticated elsewhere in the application. Other authentication routes
need their own MFA enforcement. Standalone `MultiFactorChallenge` callers must
re-check `hasEnabledProviders()` immediately before validation and apply challenge
rate limiting: an empty challenge schema validates successfully without proving
factor possession. Validating an enabled provider's challenge does not itself
authenticate the user or authorize a protected operation. See
`docs/07-users/02-multi-factor-authentication.md`.

### Browser-visible model state

Edit/view forms expose non-`$hidden` model attributes unless removed by
`mutateFormDataBeforeFill()`. Browser visibility alone does not demonstrate that
an extra model attribute can be saved: distinguish data disclosure from a proven
write through form dehydration. Applications must hide sensitive attributes;
see `docs/09-advanced/06-security.md` and the comments in
`packages/panels/src/Resources/Pages/EditRecord.php` / `ViewRecord.php`.

### Form state and component RPC

A `Hidden` input or `readOnly()` field is still client-writable; neither is a
server-side integrity boundary. In contrast, disabled fields are not saved by
default, and server-hidden fields have their own saving/dehydration rules.
Trace `saved()` / `dehydrated()` overrides, shared state paths, and whether the
application persists schema `getState()` or raw public state. None of these
settings makes browser-held data confidential or replaces authorization. See
`packages/forms/docs/01-overview.md`, `02-text-input.md`, and `21-hidden.md`,
plus `packages/schemas/src/Components/Concerns/HasState.php`.

Schema component RPC dispatch allows `#[Exposed]` methods, but exposure is not
operation authorization. Disabled components may expose read methods; evaluate
individual mutation methods' checks rather than expecting blanket RPC denial.
For custom Livewire components using `InteractsWithSchemas`, upload targeting is
not restricted to registered upload fields unless
`RestrictsFileUploadsToSchemaComponents` is enabled. Do not confuse that default
with bypasses of enabled target restrictions or file validation/storage checks.
See `packages/schemas/docs/09-custom-components.md` and the security guide.

### Existing file paths and rich-editor attachments

Storage directories, private visibility, existence checks, and disabled controls
do not by themselves authorize client-supplied existing file paths or attachment
IDs. Distinguish the default shared-disk behavior from enabled
`preventFilePathTampering()` / `preventFileAttachmentPathTampering()` guards.
These guards use original record content and explicit allow callbacks; callbacks
approve the exact submitted string, so application prefix-only checks are not
safe against filesystem path normalization. Check metadata/URL generation and
removal as well as submission when evaluating enabled protection.

With default disk storage, neither the rich-editor provider nor the standalone
renderer infers attachment ownership. The Spatie media-library provider scopes
URL resolution to the record's media collection, which is different from
rejecting IDs during form validation. A standalone renderer does not inherit a
field's original-content guard. See `packages/forms/docs/09-file-upload.md`,
`10-rich-editor.md`, and
`packages/forms/src/Components/RichEditor/RichContentRenderer.php`.

### Rendering and sanitization scope

The default HTML sanitizer deliberately permits inline `style`; it does not
promise CSS isolation, prevention of external CSS requests, or prevention of
overlays. This does not permit first-party CSS generation to accept arbitrary
untrusted fragments: color values, rich-text colors, grid counts, and image
dimensions have separate sanitization/coercion boundaries. Distinguish preserved
user-authored inline CSS from injection into a generated single-value CSS slot.

Do not generalize the sanitization applied by text-column/entry `html()` to
every HTML option: `allowHtml()` on selects and trusted `Htmlable`, view, or
custom-block output have different contracts. Application-supplied JavaScript
such as `actionJs()` is executable trusted configuration; ordinary field values
are not trusted executable code merely because that configuration reads them.

`Str::sanitizeUrl()` checks allowed URL schemes and returns accepted input
unchanged; attribute escaping is a separate step. It is not a host allowlist,
same-origin guarantee, open-redirect defense, or SSRF defense. General URL
configuration methods do not automatically call it; `FileUpload` does for its
preview/open/download URLs. Test those promises and any separately configured
destination restriction. See `docs/09-advanced/06-security.md`,
`packages/tables/docs/02-columns/02-text.md`, and
`packages/forms/docs/03-select.md`.

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
