# Threat model: WordPress core

## What this project does and where untrusted input enters

WordPress is a PHP content management system. This enrollment covers WordPress core as developed in
`wordpress-develop`: everything under `src/`, including the bundled default themes (`src/wp-content/themes/twenty*`).
The scan is of `trunk`.

The block editor is also in scope, but core does not carry its source. Core ships code from the Gutenberg project
(https://github.com/WordPress/gutenberg), and it arrives outside the usual package managers: `package.json` pins a
Gutenberg commit under `gutenberg.sha`, and the build downloads a prebuilt artifact of that commit into `/src/gutenberg`
and copies it into `src/wp-includes/` (`build/`, `blocks/` and related directories). Those copied files are what sites
run. The Gutenberg source of the same commit is at `/opt/gutenberg`. Trace a finding in shipped block editor code back
to it, and write the patch against Gutenberg when the fix belongs there.

Untrusted input enters through:

- Front-end requests from anonymous visitors: `index.php` and the template loader, query vars, search, feeds,
  sitemaps, `wp-comments-post.php`, `wp-login.php` (login, registration, password reset), `wp-trackback.php`,
  `wp-cron.php`, and `wp-activate.php` / `wp-signup.php` on multisite.
- The REST API (`src/wp-includes/rest-api/`, routes under `/wp-json/`), including endpoints anonymous visitors can
  reach.
- XML-RPC (`src/xmlrpc.php`, `src/wp-includes/class-wp-xmlrpc-server.php`) and pingbacks.
- `admin-ajax.php` and `admin-post.php`, including their `nopriv` actions.
- wp-admin screens reached by users who are not fully trusted (see the actor table below).
- Content from lower-privileged users that is later rendered to higher-privileged users or to visitors: post
  content, comments, block markup and attributes, shortcodes, oEmbed responses, uploaded media and its metadata,
  user profile fields.
- Data fetched from remote servers: oEmbed providers, pingback sources, feeds, and the HTTP API.

### Actors

Severity depends first on who the attacker is, and above all on **whether they can create their own account**.
Self-registration (`users_can_register`) is off by default; say in every report whether the finding needs it.

| Actor | How they get the account | Trust |
|-------|--------------------------|-------|
| Anonymous visitor | none needed | Untrusted. High band (see severity) |
| Subscriber | self-registration, when the site allows it | Untrusted. High band |
| Contributor, Author | only an administrator can create them | Untrusted beyond their capabilities. Low band |
| Editor (single site) | admin-created | Trusted with raw HTML (`unfiltered_html`). XSS from an Editor is not rated, and neither is XSS an Editor turns into RCE through an Administrator's session. RCE or other escalation an Editor reaches by **any other means** (a file write, an upload bypass, deserialization, a capability check that should have stopped them) crosses a boundary and is in scope. Rate it with the Contributor or Author table and say plainly that the actor is an Editor |
| Administrator (single site) | admin-created | Fully trusted, including code execution. Not rated, except for the hardening constants below |
| Administrator of a site on a multisite network | created by a Super Admin | Partly trusted. Does **not** hold `unfiltered_html`, `install_plugins`, `edit_plugins`, `edit_themes` or, by default, `create_users`; only the Super Admin does. Reaching any of those crosses a boundary |
| Super Admin (multisite) | — | Fully trusted |

Treat `edit_theme_options` as admin-equivalent on single site: an actor holding it who reaches code execution, file
writes or path traversal has crossed no boundary.

**Hardening constants.** When `DISALLOW_FILE_EDIT` is `true`, nobody, Administrators included, should be able to edit
plugin or theme files from inside WordPress. A way to edit files anyway is in scope; say that the finding depends on the
constant.

**Translations are trusted**, like code. A finding that needs a malicious translation file (`.po`, `.mo`, `.l10n.php`,
or JSON script translations) or translated string is out of scope.

## Components that matter most / least

Most important:

- Capability checks (`current_user_can()`, `map_meta_cap()`), nonce checks, REST permission callbacks, and the
  Abilities API (`src/wp-includes/abilities-api/`, `src/wp-includes/abilities/`) and its permission callbacks. A
  common real defect is a permission callback that checks a **global** capability instead of **per-object**
  ownership; compare against a sibling route that does it correctly.
- **Secondary read paths.** A per-object authorization check enforced on the primary path is often missing from
  RSS/Atom feeds, REST search and collection endpoints, sitemaps, oEmbed, and the AJAX and REST twins of the same
  operation. Check each one separately; fixing one path often does not fix the other.
- Output escaping and `kses` (`src/wp-includes/kses.php`), the HTML API (`src/wp-includes/html-api/`), block parsing
  and rendering, shortcodes, and anything that turns stored content into HTML. Recurring real sinks include
  `dangerouslySetInnerHTML`, jQuery `.html()`, `unescape()` and `html_entity_decode()` on user data.
- Authentication, sessions, cookies, password reset, application passwords.
- SQL built through `$wpdb`, `WP_Query`, `WP_Meta_Query`, `WP_Tax_Query` and related classes.
- File uploads and media handling, including MIME and extension checks.
- `unserialize()` of anything a lower-privileged user can influence.
- Multisite boundaries: site admin to Super Admin, and one network reaching another. Cross-network access is a real
  boundary when the actor is not a Super Admin.

Out of scope: third-party libraries vendored into core (for example `src/wp-includes/ID3/`, `SimplePie/`,
`PHPMailer/`, `Requests/`, `sodium_compat/`), except where the way WordPress uses them creates the vulnerability.
`tests/`, `tools/` and build tooling are out of scope, unless they introduce a vulnerability into the built product
that sites run.

## How to exercise it

- Run `wp-start` first. It starts MariaDB and Apache (the container has no init system) and is safe to run again. The
  site is then at `http://127.0.0.1/`, with pretty permalinks. `wp-stop` stops both.
- The site is a single-site install with one user per default role. Each password is the same as the username:
  `admin` (administrator), `editor`, `author`, `contributor`, `subscriber`. Registration is off, as it is by default.
- `wp --path=/src/src ...` (WP-CLI) sets up content, options, users and roles. `wp --path=/src/src eval '...'` runs
  PHP in a loaded WordPress. To test multisite behaviour, `wp --path=/src/src core multisite-convert` converts the
  site to a subdirectory network.
- The PHP code Apache serves is `/src/src`, so a patch to `/src` takes effect on the next request.
- PHPUnit: `cd /src && vendor/bin/phpunit --group <group>` or `vendor/bin/phpunit --filter <TestName>`, with MariaDB
  running. Tests use the `wordpress_test` database. `vendor/bin/phpunit -c tests/phpunit/multisite.xml` runs the
  multisite suite.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate administrator would: create users at their real roles, set real configuration
options, add content. Then drive the attack **as the claimed actor**, through the normal interface. Do not mint a
nonce as an administrator, flip the target option through the database or WP-CLI, grant the attacker the capability
they are supposed to gain, or drive the action from an administrator's session. Reading the database to observe the
outcome is fine. If the attack only works through such a shortcut, it is not a finding.

For XSS, show that the payload executes in a browser context, not only that it appears in the HTML. Reflected input
inside an escaped attribute value does not execute.

## How you rate severity

Two questions settle the band, in this order:

1. **Can the attacker create their own account?** Anonymous or Subscriber (self-registerable) is the high band.
   Contributor and Author (admin-created) is the low band. On single site, XSS from an Editor or Administrator is
   not rated, and neither is anything else an Administrator does; an Editor's non-XSS escalation is rated in the low
   band (see the actor table).
2. **Is the chain real and unconditional?** "Unchained, no preconditions" earns the top of a band. **XSS that leads
   to RCE is still XSS** and is rated as XSS.

### Anonymous visitor, or a self-registerable account

| Finding | Severity |
|---|---|
| Proven RCE, unchained, no preconditions | Critical |
| XSS or SQL injection, unchained | High |
| XSS that leads to RCE, or any other valid, viable chained RCE | High |
| RCE through a POP chain whose gadget is in default core | Medium to High |
| RCE through a POP chain with any other gadget | Low |
| Disclosure of full private posts or their titles, with no brute forcing or guessing | High |
| Anything else with real security impact | Medium |
| Blind SSRF that cannot read responses | Low |
| Other low-impact issues | Low |
| No real security impact | Informative |

### Contributor or Author

| Finding | Severity |
|---|---|
| RCE, unchained, no preconditions | Medium to High |
| Stored XSS, XSS that leads to RCE, SQL injection | Low |
| IDOR, broken access control | Low |
| Most other findings | Low |
| No real security impact | Informative |

### Multisite

- XSS by an actor who holds `manage_options` or more on a sub-site is **Low**, even when it fires in a Super Admin's
  session.
- A sub-site administrator reaching `unfiltered_html`, `install_plugins`, `edit_plugins` or `edit_themes` is **Low**.

### Rules by class

- **Validity comes before severity.** A finding counts only if it names the actor, what that actor can already do
  through the normal interface, and the specific capability they gain. No gain means no finding, however real the
  code defect. A low severity is not a hedge for a finding that has not been shown to be real.
- **Deserialization:** `maybe_unserialize()` only unserializes strings that already look serialized. Phar
  deserialization through file-stat functions is dead on PHP 8+. A POP chain needs a real gadget in installed code;
  name it, because its location sets the severity. Object injection with no valid, available gadget chain is
  Informative.
- **SSRF:** needs proof that a real internal or localhost host returned different data. Requests only to cloud
  metadata, or blind requests to attacker-controlled public URLs, do not count.
- **CSRF:** needs realistic cross-origin exploitation under default `SameSite` cookie behaviour. A missing nonce on an
  action only an administrator can reach, where the attacker gains nothing they could not get by asking, is not a
  vulnerability.
- **CSS injection:** valid only if it escapes the declaration context (breaking out of the rule with `}`), reaches a
  site-wide store (Global Styles, `theme.json`), or bypasses a capability check. Allowed declarations on the
  attacker's own element are Informative.
- **IDOR:** valid only when it crosses a real authorization boundary to non-public data.
- **Sanitizer or encoding bypasses** with no demonstrated sink are Informative.
- **Open redirects** are Informative unless they leak a token or credential, or chain into a proven exploit.
- **Race conditions** are Informative without practical, demonstrated impact.

## How reports and patches should look

- State the claim as one sentence: *&lt;actor&gt; can &lt;action&gt; against &lt;target&gt;, which they otherwise could
  not.*
- Give an explicit **actor / already holds / gains** line, the least privileged role that triggers the issue,
  whether it needs self-registration, multisite or any non-default setting, and the severity from the tables above.
- Write the impact as one short sentence naming what the attacker can **do** (read X, write Y, become Z), then two
  plain-language sentences with no function names or payloads: who can do it, what account they need, what they get,
  and whether a default install is affected.
- Name the affected file and function, and give a self-contained reproducer: WP-CLI setup plus `curl`, or a PHPUnit
  test.
- Write patches as `git diff` against `/src`. Follow the WordPress PHP coding standards (`vendor/bin/phpcs` checks
  them), and use core APIs (`esc_html()`, `esc_attr()`, `esc_url()`, `wp_kses()`, `$wpdb->prepare()`,
  `current_user_can()`, `check_admin_referer()` / `wp_verify_nonce()`) rather than ad hoc escaping or checks. When
  the defect is on a secondary path, check whether the same fix is needed on its twins.

## Anything to leave alone

- Anything an Administrator (single site) or Super Admin can already do, including running PHP, editing files, and
  installing plugins or themes, except where a hardening constant such as `DISALLOW_FILE_EDIT` forbids it.
- XSS by an Editor or Administrator on single site, including XSS an Editor turns into RCE through an Administrator.
- Anything an actor holding `edit_theme_options` on single site can reach.
- The custom CSS / `edit_css` family: Informative.
- Username and author enumeration, by any mechanism.
- Intentionally public data, and client-side identifiers sent to every visitor by design.
- Version disclosure, the `readme.html` and `license.txt` files, full path disclosure from errors, warnings or
  notices, missing security headers, and missing rate limiting on login or XML-RPC.
- Self-XSS, including script execution in wp-admin by a user who holds `unfiltered_html`, and CSRF on login or
  logout.
- Brute force, denial of service, memory exhaustion, phishing, text injection and social engineering.
- XML-RPC being available, without a demonstrated security impact beyond brute force or DoS.
- Mixed-content warnings for passive assets such as images and video, and clickjacking with minimal security impact.
- Vulnerabilities in Composer or npm `devDependencies`, unless there is a practical way to exploit them remotely.
- Theoretical issues with no demonstrated, significant security impact.
- Findings that need `WP_DEBUG` or `display_errors` on, a plugin or theme not bundled with core, a server
  misconfiguration, or an already-compromised host.
- Getting malicious code past plugin or theme directory review.
