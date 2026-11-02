# Threat model: Akismet Anti-spam

## What this project does and where untrusted input enters

Akismet (`akismet`) is a WordPress plugin that sends comments, pingbacks and contact-form submissions to the Akismet
service (`rest.akismet.com`) for spam classification, stores the verdict and a per-comment history in comment meta,
and lets moderators report missed spam and false positives back. It also adds an admin settings and stats screen,
a dashboard widget, a "Check for spam" queue recheck, a front-end widget, WP-CLI commands, Abilities API
registrations, a Connectors registration, and integrations with Jetpack Contact Form, Gravity Forms, Contact Form 7,
Formidable and Fluent Forms. This enrollment covers the plugin code in the
`Automattic/akismet-plugin-wordpress` mirror on the `trunk` branch. The Akismet service itself is out of scope, but
everything it sends back to the plugin is input the plugin must handle safely.

Untrusted input enters through:

- Comment submission: `wp-comments-post.php`, the REST comments endpoint (`rest_pre_insert_comment`) and XML-RPC
  pingbacks (`xmlrpc_call`). `Akismet::auto_check_comment()` in `class.akismet.php` reads the comment fields,
  `$_POST` (including `akismet_comment_nonce` and the `ak_*` hidden fields the front-end script adds) and
  `$_SERVER`, and stores them in comment meta.
- Hidden form fields and values injected into third-party contact forms (`inject_custom_form_fields`,
  `prepare_custom_form_values`), and `_inc/akismet-frontend.js`.
- The REST namespace `/wp-json/akismet/v1/` (`class.akismet-rest-api.php`):
  - `key`, `settings`, `stats`, `stats/(?P<interval>...)`: require `manage_options`.
  - `alert` and `webhook`: called by the Akismet servers and authorised only by the caller supplying the site's
    API key (`remote_call_permission_callback`). The webhook body names comments by `guid` plus optional query
    fields and changes their status to spam or approved. Treat the body as attacker-controlled, and the key check as
    the boundary.
- Admin AJAX and actions in `class.akismet-admin.php`: `akismet_recheck_queue`, `comment_author_deurl`,
  `comment_author_reurl`, the settings form, and the Jetpack connect flow.
- Responses from the Akismet API (`Akismet::http_post`): bodies and `X-akismet-*` headers, including alert codes and
  messages that are stored in options (`akismet_alert_*`) and rendered in wp-admin, and the `X-akismet-pro-tip` and
  `recheck-after` headers.
- The admin screens in `views/`, which render stored comment history, alert messages, stats and account data.
- Abilities (`class-akismet-abilities.php`, `abilities/`), which require `moderate_comments`.

### Actors

| Actor | How they get there | Trust |
|-------|--------------------|-------|
| Anonymous visitor / commenter | none needed; commenting on the sample post is open | Untrusted. High band |
| Subscriber | self-registered (enabled in this image) | Untrusted. High band |
| Contributor, author | admin-created | Partly trusted. Medium band |
| Editor | admin-created; has `moderate_comments` and `unfiltered_html`, not `manage_options` | Partly trusted. Low band |
| Administrator | admin-created; holds `manage_options` | Fully trusted. Not rated |
| Akismet service (API responses, webhook, alert calls) | API key | Trusted party, untrusted payload. A request accepted without the key is High band |

## Components that matter most / least

Most important:

- Anything an anonymous commenter controls that ends up rendered unescaped in wp-admin: comment meta, comment
  history (`akismet_history`), the "As submitted" data, author URLs, user agent, referrer, the `ak_*` fields.
  Stored XSS reaching a moderator or administrator is the classic Akismet-plugin bug.
- Authentication of the `webhook` and `alert` REST routes: anything that lets a caller without the API key change
  comment status, alerts or settings, or that leaks the key.
- The API key itself (`wordpress_api_key` option or `WPCOM_API_KEY`): any path exposing it to a non-administrator
  (page source, REST responses, logs, error messages, the stats iframe URL).
- Spam-check bypass: a way for an anonymous commenter to get a comment published that Akismet classified (or would
  classify) as spam, for example by tampering with the nonce or hidden fields, racing the recheck, or abusing the
  fallback paths when the service is unreachable.
- Authorization and nonces on admin AJAX and actions: comment author URL removal/restore, queue recheck, settings.
- SQL built for the webhook comment lookup, scheduled deletes, and queue recheck.
- Handling of API response headers and bodies that are stored and later displayed.

Out of scope: the Akismet service and its dashboards, Jetpack and the third-party form plugins themselves (only
Akismet's integration code is in scope), WordPress core (it has its own enrollment), and the offline mock
mu-plugin this image adds (`wp-content/mu-plugins/oss-scanner-akismet-mock.php`, which is test scaffolding and not
part of Akismet).

## How to exercise it

- Run `wp-start` first. It starts MariaDB and Apache. The site is at `http://127.0.0.1/`, with pretty permalinks and
  the default "Hello world!" post open for comments. `wp-stop` stops both.
- PHP errors go to `/var/log/php-error.log`; Apache's logs are under `/var/log/apache2/`.
- Users: `admin`, `editor`, `author`, `contributor`, `subscriber`, each with the password equal to the username.
  Registration is enabled; comment moderation is off, so ham comments are approved immediately.
- The plugin is at `/var/www/html/wp-content/plugins/akismet`, a symlink to `/src`, so a patch to `/src` takes effect
  on the next request. There is no build step and no test suite in this repository.
- `wp --path=/var/www/html ...` (WP-CLI) sets up content and options; `wp --path=/var/www/html akismet ...` runs the
  plugin's CLI commands; `wp --path=/var/www/html eval '...'` runs PHP in a loaded WordPress.
- The API key is `0123456789ab`. There is no network, so the image includes a must-use plugin that answers
  `rest.akismet.com` locally: `verify-key` is valid for that key, `comment-check` returns spam when the author is
  `akismet-guaranteed-spam` or the content contains `akismet-guaranteed-spam` and ham otherwise (with a random
  `X-akismet-guid` header, as the real service sends; the webhook matches comments by that guid), and
  `submit-spam`/`submit-ham` succeed. Other endpoints (stats, token, etc.) fail as if the service were down. Turn the
  mock off with `wp option update oss_scanner_akismet_mock off` to exercise the "server unreachable" paths. The last
  request the mock saw is stored in the option `oss_scanner_akismet_mock_last`. To test how the plugin handles a
  hostile API response, write your own `pre_http_request` filter that returns it; say so in the report.
- Post a comment as an anonymous user with
  `curl -X POST http://127.0.0.1/wp-comments-post.php --data-urlencode comment_post_ID=1 --data-urlencode author=... --data-urlencode email=... --data-urlencode comment=...`.
  WordPress's comment flood check rejects a second comment from the same IP within 15 seconds.
- The webhook takes `POST /wp-json/akismet/v1/webhook` with `key`, `endpoint` and `comments[]`.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate administrator would: users at their real roles, real options, posts. Drive the
attack as the claimed actor through the normal interface (comment form, REST, AJAX with a nonce that actor can
obtain). Do not write comment meta or options directly to plant a payload, mint a nonce as an administrator, or
call the webhook with the key unless you show how the attacker obtained it. Reading the database to observe the
outcome is fine. For XSS, show the payload executing in a browser context in the victim's role.

## How you rate severity

Two questions settle the band: (1) can the attacker act without an admin-created account (anonymous or subscriber is
the high band), and (2) does it work in a default configuration with Akismet active and a valid key.

### Anonymous commenter, or a self-registered subscriber

| Finding | Severity |
|---|---|
| Proven RCE, or SQL injection that reads or writes arbitrary data | Critical |
| Stored XSS that executes in an administrator's session in wp-admin without unusual interaction | Critical |
| Disclosure of the API key | High |
| Calling the `webhook` or `alert` routes successfully without the key; changing other users' comment status | High |
| Stored XSS that executes only for editors/moderators, or needs significant interaction | High |
| Publishing a comment the service classified as spam (spam-check bypass) | Medium |
| Reading other commenters' non-public data (email, IP, user agent) | Medium |
| CSRF on an Akismet admin action with real impact | Medium |
| Open redirect, blind SSRF, missing rate limiting | Low |
| No real security impact | Informative |

### Contributor, author or editor

| Finding | Severity |
|---|---|
| Reaching `manage_options`, the API key, code execution or file writes | Medium to High |
| Stored XSS, IDOR or SQL injection | Low (editors already have `unfiltered_html`) |
| Most other findings | Low |

### Rules by class

- **Validity comes before severity.** Name the actor, what they can already do, and the specific thing they gain.
- **Akismet service payloads:** a finding that needs the Akismet service itself to be malicious is one band lower
  than the same issue from an attacker, unless it also works without the key (then rate it as the attacker case).
- **Timing-based key guessing** needs a demonstrated practical attack over the network.
- **Spam evasion** by crafting content that the service misclassifies is not a plugin vulnerability; only bypasses
  of the plugin's own handling count.

## How reports and patches should look

- One-sentence claim: *<actor> can <action> against <target>, which they otherwise could not.*
- The least privileged role that triggers it, whether it needs a non-default setting, and the severity from the
  tables above.
- Name the file and function, and give a self-contained reproducer: WP-CLI setup plus `curl`.
- Write patches as `git diff` against `/src`. Follow WordPress coding standards and use core APIs (`esc_html()`,
  `esc_attr()`, `esc_url()`, `wp_kses()`, `$wpdb->prepare()`, `current_user_can()`, `wp_verify_nonce()`,
  `hash_equals()`). For a REST route, fix the `permission_callback`. Keep compatibility with the plugin's stated
  minimums (WordPress 5.8, PHP 7.2).

## Anything to leave alone

- Anything an administrator can already do.
- Findings that need `WP_DEBUG` / `display_errors` on, a plugin not installed in this image, a server
  misconfiguration, or an already-compromised host.
- The behaviour of the Akismet service, its classification quality, and the offline mock in this image.
- Version disclosure, missing security headers, clickjacking without impact, self-XSS, CSRF on login or logout,
  brute force, denial of service, phishing.
- Theoretical issues with no demonstrated, significant security impact.
