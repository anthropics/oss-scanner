# Threat model: Secure Custom Fields

## What this project does and where untrusted input enters

Secure Custom Fields (SCF, `secure-custom-fields`) is a WordPress plugin maintained by the WordPress.org community.
It lets site builders define field groups (text, rich text, media, relationship, user, repeater, flexible content
and more) that attach to posts, terms, users, comments, options pages, menus, widgets and blocks, and it registers
custom post types, taxonomies and options pages from the admin UI. Field values are stored in WordPress meta and
options. Themes and plugins read them through the template API (`get_field()`, `the_field()`, `have_rows()`), the
REST API, block bindings and SCF blocks. This enrollment covers the plugin code on the `trunk` branch: `includes/`,
`src/`, `pro/`, `assets/src/` and the plugin bootstrap `secure-custom-fields.php`. WordPress core is a dependency
with its own enrollment; report a core issue only when SCF's use of it creates the bug.

Untrusted input enters through:

- `admin-ajax.php` actions registered by SCF (`includes/ajax/`, the `ajax_query` handlers in `includes/fields/` and
  `pro/fields/`, `includes/validation.php`). Several are registered for logged-out users too (`wp_ajax_nopriv_*`:
  save validation, relationship / post object / select / oEmbed queries, gallery attachment get / update / sort,
  flexible content layout titles) so that front-end forms work. They are guarded by an `acf` nonce, which is the
  same for all logged-out visitors. What matters is whether the field key, post id or attachment id in the request
  lets the caller read or change something they otherwise could not.
- Front-end forms rendered with `acf_form()` (`includes/forms/form-front.php`), which can create or update posts
  and save field values as an anonymous visitor or a logged-in user, depending on how the site owner configured
  the form.
- The REST API (`includes/rest-api/`): the `acf` field on posts, pages, custom post types, terms, users and
  comments, its read and write paths, the per-field `show_in_rest` setting and embed links.
- Block content written by contributors and authors: SCF block attributes and field data stored in
  `post_content` (`includes/blocks.php`, `pro/blocks.php`), block previews fetched over AJAX, and the `acf/field`
  block bindings source (`includes/Blocks/`), which resolves a field from the block context.
- The `[acf]` shortcode (`includes/api/api-template.php`). It is disabled by default on new installs and enabled on
  sites first activated before 6.3; treat it as a non-default setting.
- Classic edit screens for posts, terms, users, comments, attachments, menus, widgets and the Customizer
  (`includes/forms/`), where `$_POST['acf']` is saved for the object being edited.
- Admin screens for field groups, post types, taxonomies and options pages, plus JSON import / export and local
  JSON sync (`includes/admin/`, `includes/local-json.php`). They need the SCF capability (`manage_options` by
  default).
- Abilities API registrations (`includes/abilities/`, `src/AI/`), which expose field group, post type and taxonomy
  operations. Their `permission_callback`s are the boundary.
- Stored field values themselves, which a lower-privileged user may have written, rendered later in wp-admin or on
  the front end through SCF's own output paths.

### Actors

| Actor | How they get there | Trust |
|-------|--------------------|-------|
| Anonymous visitor | none needed | Untrusted. High band |
| Subscriber | self-registered (registration is enabled in this image) | Untrusted. High band |
| Contributor | admin-created; writes posts but cannot publish, upload files or post unfiltered HTML | Partly trusted. Middle band |
| Author | admin-created; publishes own posts and uploads files, no unfiltered HTML | Partly trusted. Middle band |
| Editor | admin-created; edits others' posts and has `unfiltered_html` on single site | Mostly trusted. Low band |
| Administrator / holder of the SCF capability | admin-created | Fully trusted, including code execution. Not rated |

## Components that matter most / least

Most important:

- Authorization on every AJAX handler, nonce or not: the caller must be able to see or edit the post, term, user,
  attachment or option the request names. The field query handlers must not list private, draft or
  password-protected posts, other users' details or non-public attachments to a caller who cannot read them.
- Front-end form saving: which post id, post status, post type and fields an `acf_form()` submission can change,
  and whether submitted field keys are limited to the fields the form actually rendered.
- REST read and write of the `acf` field: values of a field group with `show_in_rest` off, of a draft or private
  object, or of an object the caller cannot edit.
- Block bindings and SCF blocks: a contributor using a binding, block attribute or block preview to read another
  post's fields, user fields or options-page values they cannot otherwise see, or to render unescaped HTML.
- Output escaping: `the_field()`, the shortcode, field `render_field()` / `format_value()` output, admin list
  tables, field group and post type admin screens, and JavaScript that builds HTML from field data
  (`assets/src/`).
- Saving through `$_POST['acf']` on core edit screens: writing fields of an object the user cannot edit, or fields
  outside the groups shown for that object.
- Options pages, whose capability is set per page by the site owner.
- PHP object injection through stored values, imported JSON or field settings; SQL built from field names or
  query arguments.

Least important: the WooCommerce order and HPOS integrations (`includes/forms/WC_Order.php`,
`includes/Meta/WooOrder.php`) are in scope but WooCommerce is not installed in this image.

Out of scope: `vendor/`, `node_modules/`, `wordpress/` (the WordPress copy WorDBless installs for the tests),
`assets/build/` (built output; patch `assets/src/` instead), `tests/`, `bin/`, `docs/`, `scripts/`, `release/`,
`.github/`, and WordPress core itself.

## How to exercise it

- Run `wp-start` first. It starts MariaDB and Apache. The site is at `http://127.0.0.1/`, with pretty permalinks
  and the default theme. `wp-stop` stops both. PHP errors, warnings and deprecations go to
  `/var/log/php-error.log`; Apache's logs are under `/var/log/apache2/`.
- Users: `admin` / `admin` (administrator), `editor` / `editor`, `author` / `author`, `contributor` /
  `contributor`, `subscriber` / `subscriber`. User registration is enabled.
- The field group `group_scanner` ("Scanner fields") is attached to posts with `show_in_rest` on. It holds one
  field of each common type (text, textarea, wysiwyg, url, link, image, file, gallery, oEmbed, select,
  post_object, relationship, page_link, taxonomy, user, repeater, flexible content). The published post "Scanner
  post" (`/scanner-post/`) has values for some of them. Build further fixtures as an administrator would:
  `acf_import_field_group()`, `acf_add_options_page()`, `update_field()`, or a small must-use plugin in
  `/var/www/html/wp-content/mu-plugins/` that renders `acf_form()` or registers a block, the way a theme would.
- `wp --path=/var/www/html ...` (WP-CLI) sets up content, options and users; `wp --path=/var/www/html eval '...'`
  runs PHP in a loaded WordPress.
- The plugin is at `/var/www/html/wp-content/plugins/secure-custom-fields`, a symlink to `/src`, so a PHP patch to
  `/src` takes effect on the next request. JavaScript changes need `npm run build` (offline: `node_modules` is
  already installed).
- `scanner-test` checks the image end to end: SCF loaded with the seeded field group, field values readable over
  REST on a published post, anonymous and subscriber REST writes denied, the post page loads, then the full PHPUnit
  suite and the Jest unit suite.
- PHPUnit: `cd /src && vendor/bin/phpunit --filter <TestName>`. The suite runs on WorDBless (an in-memory
  WordPress at `/src/wordpress`) and needs no database. Tests are in `tests/php/`; `tests/php/includes/ajax/`,
  `tests/php/includes/rest-api/` and `tests/php/includes/forms/` show how to drive the request handlers.
- Jest: `cd /src && npm run test:unit -- --ci`.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate administrator would: create users at their real roles, define field groups, set real
options, write posts. Drive the attack as the claimed actor, through the normal interface: log in through
`wp-login.php` with `curl`, fetch the nonce from a page that actor can load, then send the request. Do not mint a
nonce as an administrator for a lower-privileged user, call internal functions directly as proof of reachability,
or give the attacker a capability they are supposed to gain. Reading the database to observe the outcome is fine.
For XSS, show the payload executes in the victim's browser context at the victim's role.

## How you rate severity

Two questions settle the band, in this order: (1) the least privileged actor that triggers it (anonymous or
subscriber is the high band; contributor or author the middle band; editor the low band; administrator is not
rated), and (2) whether the chain works in a default configuration or needs a site-owner setting or theme code
that is plausible but not default (an `acf_form()` on a page, the shortcode enabled, a custom options-page
capability). A non-default but common precondition is one band lower; an unusual one is two lower.

### Anonymous visitor or subscriber

| Finding | Severity |
|---|---|
| Proven RCE, PHP object injection with a real gadget in installed code, or arbitrary file write | Critical |
| Privilege escalation to editor or administrator; changing site options or another user's role or credentials | Critical |
| SQL injection | High (Critical with a demonstrated data read) |
| Creating, editing or deleting posts, terms, users, attachments or field values they cannot otherwise change | High |
| Stored XSS that executes in an editor or administrator session | High |
| Reading private, draft or password-protected content, non-public field values, options-page values or other users' personal data | High (Medium for titles or ids only) |
| Reflected XSS | Medium |
| Anything else with real security impact | Medium |
| Information disclosure of non-sensitive data, open redirect without a token leak | Low |

### Contributor or author

| Finding | Severity |
|---|---|
| RCE, object injection with a gadget, arbitrary file write, privilege escalation | Critical |
| Stored XSS that executes in an editor or administrator session | High |
| Reading another user's personal data, options-page values or private posts' field values through bindings, blocks, REST or AJAX | Medium |
| Editing posts or field values of objects they cannot edit | Medium |
| Stored XSS against other contributors / authors, or on the front end | Medium |
| Most other findings | Low |

### Editor

| Finding | Severity |
|---|---|
| Code execution, file writes, or gaining an administrator capability (other than `unfiltered_html`, which editors already have) | Medium |
| Changing SCF field groups, post types, taxonomies or options-page settings without the SCF capability | Low |
| XSS (editors already hold `unfiltered_html` on single site) | Not a vulnerability unless it works on multisite without that capability |

### Rules by class

- **Validity comes before severity.** Name the actor, what they can already do through the normal interface, and
  the specific thing they gain. No gain means no finding, however real the code defect.
- **Nonces:** the `acf` nonce is a CSRF token, not authorization. A handler that checks only the nonce and then
  acts on an object the caller cannot access is a finding; a missing nonce on an action only an administrator can
  reach, where the attacker gains nothing, is not.
- **CSRF:** needs realistic cross-origin exploitation under default `SameSite` cookie behaviour, against a victim
  role that can perform the action.
- **Escaping:** values an administrator saved through the field group UI or code are trusted; values a lower role
  can store are not. `the_field()` and the shortcode are expected to escape; `get_field()` returns raw data and
  themes are responsible for escaping it, so a theme echoing `get_field()` is not an SCF finding.
- **Deserialization:** needs a real gadget in installed code; name it.
- **Race conditions** count only with a demonstrated outcome.

## How reports and patches should look

- One-sentence claim: *<actor> can <action> against <target>, which they otherwise could not.*
- An explicit actor / already holds / gains line, the least privileged role that triggers the issue, any
  non-default setting or theme code it needs, and the severity from the tables above.
- Name the affected file and function, and give a self-contained reproducer: WP-CLI setup plus `curl`, or a
  PHPUnit test under `tests/php/`.
- Write patches as `git diff` against `/src`. Follow WordPress coding standards (`vendor/bin/phpcs` checks them)
  and use core APIs (`esc_html()`, `esc_attr()`, `wp_kses_post()`, `$wpdb->prepare()`, `current_user_can()`,
  `check_ajax_referer()`). Keep existing `acf_` function names and `acf/` hook names for backward compatibility.
  Check whether the same fix is needed in the AJAX, REST, block and front-end form twins of the same operation.

## Anything to leave alone

- Anything an administrator or a holder of the SCF capability can already do, including running PHP, importing
  field groups, registering post types and editing local JSON.
- Findings that need `WP_DEBUG` / `display_errors` on, a plugin not installed in this image, a server
  misconfiguration, or an already-compromised host.
- Field keys, field names or field group structure being visible to logged-in users, and field values the site
  owner deliberately exposed with `show_in_rest` or on a public post.
- Version disclosure, username enumeration through WordPress core, missing security headers, missing rate
  limiting, and clickjacking without security impact.
- Self-XSS, CSRF on login or logout, brute force, denial of service, phishing, social engineering.
- Vulnerabilities in Composer or npm `devDependencies`, unless practically exploitable remotely.
- Theoretical issues with no demonstrated, significant security impact.
