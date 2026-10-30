# Threat model

The scanner reads this file before it starts. It covers Drupal core. Severity follows the Drupal Security Team's own process
([security risk levels](https://www.drupal.org/drupal-security-team/security-risk-levels-defined) and the
[security advisory process and permissions policy](https://www.drupal.org/drupal-security-team/security-advisory-process-and-permissions-policy)).

## What this project does and where untrusted input enters

Drupal is a PHP content management framework. Sites built on it are public web applications, so treat all HTTP
input as untrusted: paths, query strings, form submissions (including Form API `#ajax` callbacks and multi-step
form state), uploaded files, cookies and headers, JSON:API / REST / GraphQL-style payloads, and content that one
user stores and other users later see (node bodies, titles, field values, comments, menu links, URL aliases,
contact form messages, and so on).

### Where the code is

| Path | What it is |
| --- | --- |
| `/src` | The Drupal core git checkout (the `main` branch, Drupal 12.0-dev, where core development happens). Patches for core belong here. |
| `/opt/drupal` | A working site, built the way drupal.org documents (`composer create-project drupal/recommended-project`), on the current Drupal 12 development build, served by Apache with `.htaccess` enabled, on MariaDB. |
| `/opt/drupal/web/core` | Core as the site runs it: the current `dev-main` build (Drupal 12.0-dev), so it can be a few commits behind `/src`. Reproduce against the site, then confirm the code is unchanged in `/src` and write the patch there. |

Contributed modules and themes are out of scope.

### Trust model

- **Anonymous visitors** are untrusted.
- **Authenticated users** must stay within the permissions their roles grant, plus entity access, node
  grants, field access, text-format access and route access checks.
- **Permissions marked `restrict access: true`** in a module's `*.permissions.yml` (for example "administer site
  configuration", "administer users", "administer permissions", "administer account settings", "administer
  filters", "administer software updates") and uid 1 are trusted. Per the Drupal security advisory policy, a
  vulnerability that needs one of these permissions is **not** a security issue. Do not report it unless it lets
  the attacker do something that permission does not already grant. Check the `.permissions.yml` file (or
  `drush php:eval` on `user.permissions`) before treating a permission as restricted. Many "administer …"
  permissions are **not** restricted, for example "administer modules", "administer blocks", "administer menu",
  "administer taxonomy", "administer comments" and "administer url aliases" (the `content_editor` role has this
  one). Issues reachable with those are in scope and scored as A:Admin.
- **Text formats are a trust boundary.** A user allowed to use an unfiltered format (for example "Full HTML")
  can add arbitrary markup by design, which is not a finding. XSS through a *filtered* format (`basic_html`,
  `restricted_html`) or through `Xss::filter()` / `Xss::filterAdmin()` / Twig autoescaping *is* a finding.
- `settings.php`, `services.yml`, the environment and the file system are trusted operator input.

## Components that matter most / least

Highest priority:

1. Access bypass: route requirements (`_permission`, `_access`, `_entity_access`, `_csrf_token`), entity and
   field access handlers, node grants, query access tags (`node_access`, entity query `accessCheck()`), and
   Views access and argument handling.
2. XSS: render arrays (`#markup` and `#children` with unfiltered input, `#type => 'inline_template'`),
   `Markup::create()` and `ViewsRenderPipelineMarkup`, `|raw` in Twig, `t()` / `FormattableMarkup` misuse
   (`:url` placeholders outside an `href`, placeholders inside unquoted or JavaScript attributes, user input that
   has already been wrapped in a Markup object and is passed as `@`), JavaScript `Drupal.behaviors` that build
   HTML, `drupalSettings`, and attribute handling. Plain `@` and `%` placeholders escape their values.
3. SQL injection through the Database API (`condition()` with user-controlled operators or field names,
   `query()` with concatenation, `orderBy()`, `addExpression()`) and Views and Search API query building.
4. CSRF: state-changing GET routes without `_csrf_token`, and Form API token validation.
5. Remote code execution or object injection: `unserialize()` on user-controlled data, file upload
   validation (extensions, `.htaccess`, double extensions, SVG), the stream wrappers, the image toolkit, and
   private file access.
6. Open redirects (the `destination` parameter), session handling, the flood control and
   password reset / login flows, and cache poisoning (missing cache contexts that leak per-user content to
   other users).

Lower priority or out of scope:

- `vendor/`, the bundled third-party JavaScript libraries (jQuery, CKEditor 5 and others under
  `core/assets/vendor`), and npm assets. Report these upstream. Report them here only when Drupal's own code
  uses a library in a way that creates a vulnerability.
- Test code and test-only modules (`tests/`, `*_test` modules, `core/modules/system/tests`) and anything under
  `core/scripts`.
- Drupal 7 and earlier.
- The `/opt/drupal` site's generated files (`settings.php`, `sites/default/files`).

## How to exercise it

- Run `drupal-start` first. It starts MariaDB and Apache (the container has no init system) and is safe to run
  again. The site is then at `http://127.0.0.1/`. `drupal-stop` stops both.
- The site is pre-installed with the standard profile and a private file system at `/opt/drupal/private`:
  - `admin` / `admin`: uid 1, fully trusted
  - `editor` / `editor`: the `content_editor` role, useful for testing access bypass and XSS
  - anonymous: no login
- `drush` is on the `PATH` and runs as `www-data`, the Apache user, so files it writes stay writable by the site.
  `drush uli --name=editor` prints a working login link. Use `drush php:eval` to set up content, `drush pm:install`
  to enable more core modules (`jsonapi`, `rest`, `media`, `content_moderation`, and so on), and
  `drush role:perm:add` to give a role exactly the permissions a scenario needs.
- The database is `mysql://drupal:drupal@127.0.0.1/drupal`. `drush sql:cli` opens a client.
- PHP errors go to Apache's error log on stderr, not into responses, as on a production site.
- `drupal-phpunit <path>` runs PHPUnit from `/opt/drupal/web` as `www-data`, with `SIMPLETEST_DB` (MariaDB,
  database `drupal_test`) and `SIMPLETEST_BASE_URL` (the Apache site) already set. Unit, kernel and functional tests
  all run offline. Examples: `drupal-phpunit core/modules/user/tests/src/Kernel`,
  `drupal-phpunit core/modules/user/tests/src/Functional/UserLoginTest.php`. A kernel or functional test is the
  preferred reproducer.

## How you rate severity

Use the Drupal security risk calculator. Give the risk string with every report, for example
`AC:None/A:None/CI:Some/II:Some/E:Theoretical/TD:Default` (4+4+3+3+1+2 = 17, Critical). Each factor adds points:

- **Access complexity (AC)**: None (the user visits a page) 4, Basic (the user must follow a specific
  path) 2, Complex (a multi-step, unintuitive process with many dependencies) 1
- **Authentication (A)**, the least privileged role that can exploit it: None (anonymous) 4,
  User (basic, commonly assigned permissions) 2, Admin (broad permissions whose `restrict access` is false) 1.
  A permission with `restrict access: true` is trusted, so an issue that needs one is not scored (see above).
- **Confidentiality impact (CI)**: All non-public data 5, Some 3, None 0
- **Integrity impact (II)**: All data can be modified or deleted 5, Some 3, None 0
- **Exploit (E)**: Exploit (public exploit code exists) 4, Proof (public documentation of how to exploit it) 2,
  Theoretical 1. A newly found issue with a private reproducer is Theoretical.
- **Target distribution (TD)**: All module configurations 3, Default or common configurations 2,
  Uncommon configurations only 1

Total score: 0–4 Not critical, 5–9 Less critical, 10–14 Moderately critical, 15–19 Critical,
20–25 Highly critical.

Rules of thumb:

- Stored XSS any authenticated user can trigger is usually Moderately critical. Reflected XSS
  against anonymous visitors in a default configuration is usually Critical.
- Anonymous SQL injection or remote code execution in a default configuration is Highly critical.
- An access bypass that exposes unpublished content or private files is usually Moderately critical. An
  access bypass that grants a role or administrative access is Critical or higher.
- An issue that needs a `restrict access: true` permission is not a vulnerability. Leave it out.
- A denial of service that needs only a single anonymous request and little bandwidth is in scope, but rarely
  above Less critical. Volumetric DoS is out of scope.

## How reports and patches should look

- Name the core version, the risk string and score, the affected file and function, the least
  privileged role that can trigger it, and a self-contained reproducer: drush commands plus `curl`, or a
  PHPUnit kernel or functional test.
- Write patches as `git diff` against `/src`. Follow Drupal coding standards, use core APIs
  (`Html::escape()`, `Xss::filter()`, `UrlHelper::stripDangerousProtocols()`, `AccessResult`, placeholders
  in queries) rather than ad hoc escaping, and keep cacheability metadata correct.

## Anything to leave alone

- Missing security headers, `X-Powered-By`, version disclosure through `CHANGELOG.txt` or `core/install.php`,
  username enumeration through the login or password reset forms, and the self-XSS of a user editing their own
  account. Drupal treats all of these as known, public hardening issues.
- Findings that depend on turning on `display_errors`, on other `settings.php` changes, or on development modules
  (`devel`, verbose `dblog` output). The private file system configured in this image counts as a normal
  configuration, not a change.
