# Threat model

The scanner reads this file before it starts. It covers HumHub core (`humhub/humhub`). Reports go to the HumHub
security team (see `SECURITY.md` in the repository).

## What this project does and where untrusted input enters

HumHub is a self-hosted social network and collaboration platform written in PHP on Yii2. One instance is shared by
many users with different rights, organized in spaces (groups) with their own memberships, roles and privacy settings.
Treat all HTTP input as untrusted: paths, query strings, form submissions, AJAX/JSON endpoints, uploaded files,
cookies and headers, and content that one user stores and other users later see (posts, comments, rich text /
Markdown, profile fields, space descriptions, file names, notifications, activity and stream entries).

### Where the code is

| Path | What it is |
| --- | --- |
| `/src` | The HumHub git checkout, installed in place and served by Apache at `http://127.0.0.1/` with `.htaccess` and pretty URLs. Patches belong here. |
| `/src/protected/humhub` | Core framework code: `components/`, `controllers/`, `libs/`, `widgets/` and the core modules under `modules/`. |
| `/src/protected/config` | Generated instance configuration (`dynamic.php`). Must never be reachable over HTTP. |
| `/src/uploads` | User uploads and generated files. Must not allow script execution or direct access to files a user may not see. |

### Trust model

From least to most privileged:

- **Anonymous visitors** are untrusted. Depending on settings they may register, reset passwords, or (with guest
  access enabled) view public content.
- **Registered users** are untrusted beyond their own data. They must only see content whose visibility allows it
  (private vs. public content, space privacy, profile privacy, friendship), and only act with the permissions the
  permission system grants them (`BasePermission` subclasses, checked via `can()` / `permissionManager`).
- **Space members, moderators and space admins/owners** have rights limited to their space. Anything that lets a
  space admin affect another space, other users' accounts or global settings is in scope.
- **Group managers and users with partial admin permissions** (e.g. "Manage users", "Manage spaces", "Manage
  groups") must stay within the permission they were granted. Escalating from one of these to full system admin
  (e.g. adding oneself to the Administrator group, editing settings) is in scope.
- **System administrators** (members of the Administrator group) are fully trusted, including the ability to
  install modules and change any configuration. The server operator, `protected/config`, `.env`, the database and
  the console (`yii`) are trusted as well.

## Components that matter most / least

Highest priority:

1. Access control: content visibility and the `ContentContainer` / `Content` permission checks, stream queries
   (`modules/stream`), space membership and privacy (`modules/space`), profile and user directory privacy
   (`modules/user`, `modules/directory`), file download access (`modules/file`).
2. Authentication and sessions: login, registration and invites, password reset, remember-me, two-factor hooks,
   impersonation, LDAP (`modules/ldap`) and auth clients (`modules/user/authclient`), JWT handling.
3. XSS: rich text and Markdown rendering, `Html::encode` / `Html::raw` usage, widgets, JavaScript under
   `protected/humhub/resources/js` that builds HTML, notifications and activity rendering, oEmbed/URL previews.
4. CSRF on state-changing actions, including AJAX actions and GET actions that change state.
5. File upload and processing: extension and MIME checks, image conversion, SVG, file names, path traversal
   in the file storage (`fs` component, flysystem).
6. SQL injection through ActiveRecord / query builder misuse, stream and search filters (`content-search`).
7. SSRF via URL previews / oEmbed and other outgoing requests; open redirects (`returnUrl`, `redirect` parameters).
8. Unsafe deserialization (`unserialize`, cached/serialized data from the request) and remote code execution.

Lower priority or out of scope:

- `protected/vendor/` (third-party PHP libraries) and npm assets under `protected/vendor/npm-asset`. Report these
  only when HumHub's own code uses a library in a way that creates a vulnerability.
- Test code (`tests/` directories, `index-test.php`) — in production `index-test.php` is not used.
- The installer (`modules/installer`) once the instance is installed, unless it can be reached again.
- Marketplace module installation and module code outside this repository (each external module has its own
  repository).

## How to exercise it

- Run `humhub-start` first. It starts MariaDB and Apache (the container has no init system) and is safe to run
  again. The site is then at `http://127.0.0.1/`. `humhub-stop` stops both.
- Accounts:
  - `admin` / `admin`: system administrator, fully trusted
  - `alice` / `alice`, `bobby` / `bobby`: plain users, useful for access-control and XSS tests between two users
  - anonymous: no login
- `yii <command>` runs HumHub's console as `www-data`, the Apache user, e.g. `yii user/create`,
  `yii user/make-admin`, `yii space/...`, `yii cache/flush-all`. `as-www-data <cmd>` runs any other command as that
  user.
- The database is `mysql://humhub:humhub@127.0.0.1/humhub`; `mariadb -uroot -proot humhub` opens a client.
- `humhub-test` runs Codeception as `www-data` against the separate `humhub_test` database, e.g.
  `humhub-test unit`, `humhub-test functional`, `humhub-test -m space functional`. Unit and functional tests run
  offline; acceptance tests need Selenium and are not available. A unit or functional test is the preferred
  reproducer; otherwise HTTP requests (`curl`) against the instance.

## How you rate severity

Score every finding with CVSS 3.1 and report the vector. Rules of thumb:

- Unauthenticated remote code execution, SQL injection or authentication bypass in a default configuration:
  critical.
- Privilege escalation from a plain user to system administrator, or reading other users' private content in a
  default configuration: high.
- Stored XSS that any registered user can plant and that runs for other users (including admins): high.
  Reflected XSS: medium. XSS that needs a space admin or a partial admin permission: medium.
- Access bypass limited to metadata (e.g. names of private spaces, counts) or requiring an unusual
  configuration: low to medium.
- CSRF on an action with real impact: medium; on low-impact actions (e.g. like/unlike, marking notifications as
  read): low.
- Denial of service from a single cheap request: low to medium. Volumetric DoS is out of scope.

## How reports and patches should look

- Name the affected file and function, the least privileged role that can trigger it, the CVSS vector, and a
  self-contained reproducer (Codeception test, or `yii` setup commands plus `curl` requests).
- Write patches as `git diff` against `/src`, following the existing code style (PSR-12, see
  `.php-cs-fixer.php`). Fix the check where it is enforced rather than in a single caller, and say whether sibling
  actions have the same gap.
- The build leaves `.htaccess`, `.env`, `protected/config/dynamic.php`, `protected/humhub/resources/build/` and
  runtime/upload files changed or added in `/src`. Leave them out of patches.

## Anything to leave alone

- What system administrators can do by design: install modules, change settings, edit users and groups, run the
  console, execute code.
- Self-XSS, missing security headers, clickjacking on pages without sensitive actions, version disclosure, and
  username enumeration through login, registration or password reset.
- Findings that only work with `HUMHUB_DEBUG` / `YII_DEBUG` enabled or with `index-test.php`.
- The `admin`/`admin`, `alice`/`alice`, `bobby`/`bobby` accounts and other choices made only for this image.
