# Threat model

The scanner reads this file before it starts. It covers `ibexa/core`, the kernel of Ibexa DXP (formerly eZ Platform and
eZ Publish): the content repository and its permission system, persistence, search, IO and the Symfony MVC layer that
every Ibexa DXP edition runs on. The security checks follow Ibexa's
[security checklist](https://doc.ibexa.co/en/latest/infrastructure_and_maintenance/security/security_checklist/), and
severity follows the way [Ibexa security advisories](https://developers.ibexa.co/security-advisories) rate issues.

## What this project does and where untrusted input enters

Ibexa DXP is a PHP/Symfony content management platform. Sites built on it are public web applications, so treat all
HTTP input as untrusted: paths (URL aliases, SiteAccess matching on host, port and URI), query strings, form
submissions, uploaded files, cookies and headers, REST and GraphQL payloads, and content that one user stores and
other users later see (content names, field values, URLs, image alternative text, user profiles, and so on).

### Where the code is

| Path | What it is |
| --- | --- |
| `/src` | The `ibexa/core` git checkout on its default branch, where development of the next release happens (`6.0` at the time of enrolment; `/etc/ibexa-version` holds the version, for example `6.0.x-dev`). Patches belong here. |
| `/opt/ibexa` | A working Ibexa DXP Open Source site on the same development version, installed with Ibexa's procedure for development branches, in the `prod` environment, served by Apache, on MariaDB, with the Legacy search engine. |
| `/opt/ibexa/vendor/ibexa/core` | A symlink to `/src`. The site runs the checkout itself, so a patch to `/src` takes effect on the site straight away (clear the cache with `ibexa-console cache:clear` after changing configuration or service definitions). |
| `/opt/ibexa/vendor/ibexa/*` | The other Ibexa Open Source packages (`admin-ui`, `rest`, `graphql`, `user`, `fieldtype-richtext`, `http-cache`, ...). They make the site realistic but are **out of scope** for this enrolment: report only issues whose root cause is in `ibexa/core` code. |

The main parts of `ibexa/core`:

- `src/lib/Repository`: the public PHP API (`ContentService`, `LocationService`, `UserService`, `RoleService`,
  `SearchService`, `TrashService`, `URLAliasService`, ...) and the permission system
  (`src/lib/Repository/Permission`, `PermissionResolver`, the `sudo()` mechanism).
- `src/lib/Limitation`: the Limitation types (Subtree, Section, Owner, Language, ContentType, ObjectState,
  SiteAccess, ...) that narrow down what a policy grants.
- `src/lib/Persistence/Legacy` and `src/lib/Search/Legacy`: SQL storage and the Legacy search engine (criterion
  and sort clause handlers that build SQL from queries).
- `src/lib/FieldType`: the built-in field types (User, BinaryFile, Media, Image, ImageAsset, Url, EmailAddress,
  TextLine, Relation, ...) and their validation.
- `src/lib/IO` and `src/bundle/IO`: binary file storage, upload filtering (`file_type_blacklist`) and serving.
- `src/lib/MVC`: SiteAccess matching, routing and URL aliases, the content view and preview controllers, the
  download controller, Twig helpers and the security integration (user provider, login, user context hash).

### Trust model

- **Anonymous visitors** are untrusted. In the default install they hold the Anonymous role (`content/read` on the
  Standard section, `content/view_embed` for images and files, `user/login` on the `site` SiteAccess only).
- **Authenticated users** must stay within the policies of their roles, including every Limitation on those policies.
  The `editor` test user (Editor role: `content/*` limited to the Content and Media subtrees, `url/*`, back office
  login) and the `member` test user (Guest accounts group, Anonymous role: front-end login only) are untrusted for
  anything their roles don't grant.
- **The Administrator role is trusted**, as is any user holding `role/*` (who can grant themselves any policy) or
  `setup/*` policies. An issue that needs one of these is **not** a security issue unless it lets the attacker do
  something those policies don't already allow, such as executing code on the server or reading files outside the
  repository. Other powerful policies (`class/*` to edit content types, `section/*`, `state/*`, `user/*`) are
  **not** trusted: issues reachable with them are in scope, rated lower because they need back office privileges.
- **Hiding is not access control.** Location visibility (hidden content) filters the front end but doesn't restrict
  read access. Hidden content that is readable through the REST API, GraphQL or the PHP API by a user who holds
  `content/read` is not a finding. Content that a user can read *without* holding `content/read` for it is.
- Configuration (`config/`, SiteAccess-aware settings, `.env.local`), Twig templates, the file system and the
  environment are trusted operator input.

## Components that matter most / least

Highest priority:

1. Access bypass in the repository: a service method that returns or changes data without the right
   `PermissionResolver::canUser()` / `hasAccess()` check, Limitations that are evaluated wrongly (for example Subtree
   or Language Limitations on create, copy, move, swap or translate operations), list methods (`loadLocationList`,
   `loadContentInfoList`, relations, reverse relations, versions, trash) that don't filter out what the user may not
   read, the permission criterion added to searches, and `sudo()` calls that let user input reach data the user can't
   read.
2. Access bypass in MVC: the content view, preview (`/content/versionview/...`: draft and archived versions need
   `content/versionread`) and download (`/content/download/...`) controllers, SiteAccess matching that lets a request
   reach a SiteAccess it shouldn't, and user context hash / HTTP cache variations that leak one user's content to
   another.
3. SQL injection in Legacy storage and the Legacy search engine: criterion and sort clause handlers, field type
   storage gateways, and any query built with string concatenation instead of bound parameters.
4. Remote code execution, object injection and file handling: `unserialize()` on stored or user-controlled data,
   upload validation against `file_type_blacklist` (extension tricks, double extensions, case), path traversal in IO
   handlers and binary file paths, image variation handling, and XML parsing with external entities enabled (XXE).
5. XSS where core renders or escapes values: field type templates in core, Twig functions and filters core provides,
   content names built from name patterns, URL alias generation, and attributes built from field values.
6. Authentication: password hashing and verification in the User field type and `UserService`, login, user
   enabling and disabling, password expiry, and the tokens core issues (`TokenService`).

Lower priority or out of scope:

- `vendor/` and every other Ibexa package under `/opt/ibexa/vendor/ibexa/` (the back office UI, REST, GraphQL,
  RichText, user registration and password reset forms, ...). Report these upstream only when `ibexa/core` code is
  the cause.
- Test code and fixtures (`tests/`, `src/contracts/Test`), `src/bundle/Debug`, and the installer
  (`src/bundle/RepositoryInstaller`) except where it ships insecure defaults into an installed site.
- The `/opt/ibexa` site's generated files (`.env.local`, `var/`, `public/assets`).

## How to exercise it

- Run `ibexa-start` first. It starts MariaDB and Apache (the container has no init system) and is safe to run again.
  The site is then at `http://127.0.0.1/`, and the back office at `http://127.0.0.1/admin`. `ibexa-stop` stops both.
- The site is pre-installed with the clean Open Source data set and these users:
  - `admin` / `publish`: the Administrator role, fully trusted
  - `editor` / `Editor1234!`: in the Editors group with the Editor role, useful for access bypass and XSS
  - `member` / `Member1234!`: in the Guest accounts group (Anonymous role), logged in on the front end, no back
    office access
  - anonymous: no login
- `ibexa-console <command>` runs `bin/console` in `/opt/ibexa` as `www-data`, the Apache user, so the cache and
  files it writes stay usable by the site.
- The REST API is at `http://127.0.0.1/api/ibexa/v2/` and GraphQL at `http://127.0.0.1/graphql`. Both use session
  authentication: log in with `POST /api/ibexa/v2/user/sessions` and send the session cookie plus the CSRF token.
- The database is `mysql://ibexa:ibexa@127.0.0.1/ibexa`. `mariadb ibexa` opens a client as root.
- PHP errors go to Apache's error log on stderr, not into responses, as on a production site.
- In `/src`, `composer unit` runs the unit tests, and `vendor/bin/phpunit -c phpunit-integration-legacy.xml <path>`
  runs integration tests against the PHP API on an in-memory SQLite database, without the site or MariaDB
  (`composer integration` runs both integration suites in about three minutes). The `*AuthorizationTest.php` files
  depend on their service's main test, so run the two together, for example
  `vendor/bin/phpunit -c phpunit-integration-legacy.xml tests/integration/Core/Repository/ContentServiceTest.php tests/integration/Core/Repository/ContentServiceAuthorizationTest.php`.
  They show how to set up a user with a given role and Limitation. An integration test
  in this style is the preferred reproducer for access bypass in the repository; `curl` against the site is preferred
  for anything that goes through HTTP.

## How you rate severity

Ibexa advisories use four levels: **Critical**, **High**, **Medium** and **Low**. Give the level, the least privileged
user that can trigger the issue (anonymous, `member`, `editor`, or an untrusted admin-type policy such as `class/*`),
and a CVSS 3.1 vector with every report.

- **Critical**: remote code execution, SQL injection, or authentication bypass reachable anonymously or by a
  front-end user; privilege escalation to the Administrator role or to `role/*` from anonymous or `member`.
- **High**: the same issues when they need back office access (`editor` or similar); privilege escalation from
  `editor` to Administrator; access bypass that lets anonymous or `member` read unpublished drafts, content in
  restricted sections, user data or protected files; stored XSS that a back office user can plant for others,
  including administrators; XXE.
- **Medium**: access bypass that needs back office access and exposes or changes a limited amount of data; XSS that
  needs an untrusted admin-type policy (`class/*`, `section/*`) to plant; reflected XSS; CSRF on a state-changing
  action; open redirects; cache poisoning that serves one user's page to another.
- **Low**: user or content enumeration; information leaks of non-sensitive metadata; denial of service that needs
  authentication, or a single anonymous request that only slows the site.

Rules of thumb:

- An issue that needs the Administrator role, `role/*` or `setup/*` is not a vulnerability. Leave it out.
- Volumetric denial of service is out of scope.
- A Limitation that is ignored is an access bypass, rated by what it exposes.

## How reports and patches should look

- Name the branch, the level and CVSS vector, the affected file and method, the least privileged user that can
  trigger it, and a self-contained reproducer: a PHPUnit integration test in `/src`, or `ibexa-console` commands plus
  `curl` against the site.
- Write patches as `git diff` against `/src`. Use the existing APIs rather than ad hoc fixes:
  `PermissionResolver::canUser()` with the right targets, Doctrine query builder parameters instead of
  concatenation, Twig auto-escaping, and the Limitation types' own evaluation. Keep to Ibexa's coding standards
  (`composer check-cs`).

## Anything to leave alone

- Missing security headers, the `X-Powered-By` header and other version disclosure, and the default `admin` /
  `publish` password of this test image.
- Hidden content that is readable by users who hold `content/read` for it (see the trust model).
- Findings that depend on the `dev` environment, on turning on `display_errors`, on removing entries from
  `file_type_blacklist` (for example allowing `svg`), or on other configuration changes away from the defaults.
- Files under `public/var/*/storage/images`, which the web server serves directly by design (image variations are
  public once the content is published).
