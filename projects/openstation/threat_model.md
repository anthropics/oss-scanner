# Threat model: OpenStation

The scanner reads this file before it starts. It covers the OpenStation WordPress plugin as developed in this
repository (slug `desktop-mode` on WordPress.org). The scan is of `trunk`.

## What this project does and where untrusted input enters

OpenStation is a WordPress plugin that renders the admin (`wp-admin`) as a desktop operating system: admin screens become
windows on a desktop with a dock, virtual desktops ("workspaces"), a command palette, files and folders on the desktop,
notes, widgets, an optional AI assistant, optional AI agents, optional games, and an optional "OpenStation Network" that
pairs separate WordPress installs into one site switcher. Existing admin pages are loaded inside iframes in a
"chromeless" mode; purpose-built windows ("apps", under `apps/`) render through the App Framework (`includes/framework/`)
and one REST dispatch route. The plugin and the shell talk across frames with `postMessage`.

It runs on top of WordPress core, which is enrolled separately. Report defects in OpenStation's own code, including the way
it uses core APIs; a defect that is entirely core's belongs to the WordPress enrollment.

**Everything is opt-in per user.** A logged-in user who holds `read` (every default role, Subscriber included) can switch
OpenStation on for themselves from the admin bar (`admin-ajax.php?action=save-openstation`, user meta
`desktop_mode_mode`). With it off, the plugin still loads on every request (REST routes, hooks, the activity recorder) but
renders nothing. So the attack surface is mostly **authenticated**, and the question that matters most is what a
low-privileged logged-in user reaches once they have switched it on.

Untrusted input enters through:

- **The REST API**, namespace `desktop-mode/v1` (about 115 routes). `includes/rest/README.md` is the route → handler →
  permission map; start there. Routes are registered next to the code they serve, mostly under `includes/` and
  `apps/*/parts/`. Permission callbacks are the boundary: most routes are gated only on "logged in + OpenStation enabled"
  (`openstation_rest_require_enabled()`), others on a WordPress capability; the handler is then expected to do per-object
  checks itself.
- **`POST /desktop-mode/v1/apps/{app}/dispatch`** (`includes/framework/wordpress.php`): the one route every `.os.php` app
  is served by. Its gate is the app's own `capabilities()` / `can()`; the body (`action`, `state`, `args`) is attacker
  controlled.
- **`admin-ajax.php`** actions registered by the plugin (`save-openstation`, `openstation_about_feed`, and the plugin
  install/update proxies) and the admin screens the plugin adds or wraps, including the Preferences app, Extended
  options, Developer mode and Code Blue (the error-log reader).
- **Anonymous entry points.** Few, by design:
  `GET /desktop-mode/v1/network/identity` (public; publishes the install's name, URL and Ed25519 public key; registered
  only while the `network` extended option is on), `GET /desktop-mode/v1/oauth/callback` (public; the OAuth relay's
  return leg, authenticated by its `state` nonce), the PWA manifest and service worker, and the Pulse Monitor's visitor
  counting on the front end when an administrator turns on the `pulse_visitors` extended option. Anything else reachable without a login is a finding in
  itself if it does something.
- **Cross-frame messages.** The shell (`src/`) and the pages inside its iframes (`src/chromeless-bridge.js`,
  `src/iframe-bridge-standalone.ts`, `src/drag-bridge.ts`, `src/gutenberg-drop-receiver.ts`, `src/oauth-relay.ts`)
  exchange typed `postMessage` events: titles, navigation, drag & drop payloads, OAuth results, REST nonces. The origin and the shape of every message is untrusted until checked. A
  message a third-party page in an iframe can send that makes the shell navigate, fetch, inject HTML or act on the user's
  behalf is in scope. `docs/bridge-protocol.md` describes the protocol.
- **Content from other users rendered in the shell**: post titles and excerpts, comments, user profiles, media metadata,
  notes, file and folder names, workspace names, agent definitions and conversation transcripts, desktop theme
  manifests, and anything the AI assistant or an agent reads. The shell paints much of this with JavaScript; look for
  `innerHTML` and template literals that interpolate it.
- **Data from other installs and services**: the OpenStation Network (hub and member exchange signed lists over HTTPS),
  the OAuth relay's token exchange, the AI provider responses, the About feed, Jetpack Stats, WooCommerce data, and the
  WordPress.org plugin API.
- **The AI assistant and agents**: a language model reads text it did not write (site content, search results, tool
  output) and chooses tools. Every tool runs through an ability with its own `permission_callback`, and an agent run is
  ceilinged at the invoker's capabilities. `docs/agents-security.md` is the trust model; a way for prompt text to reach
  an action the invoking user could not take themselves is in scope.

### Actors

Severity depends first on who the attacker is, and above all on **whether they can create their own account**.
Self-registration (`users_can_register`) is off by default; say in every report whether the finding needs it. All the
actors below can switch OpenStation on for themselves.

| Actor | How they get the account | Trust |
|-------|--------------------------|-------|
| Anonymous visitor | none needed | Untrusted. High band |
| Subscriber | self-registration, when the site allows it | Untrusted. High band. Holds only `read`, so **anything OpenStation lets a Subscriber do beyond reading their own profile is suspect**: uploading or storing files, reading other users' notes, files, sessions or presence, listing users, reading post content they could not see on the front end, using the AI assistant on site content |
| Contributor, Author | only an administrator can create them | Untrusted beyond their capabilities. Low band. They hold `edit_posts` (and Authors `upload_files`), which is the gate of many OpenStation routes (folder sharing, the content graph, the AI assistant, invoking agents, the Users and Comments apps' read routes): check that the handler then scopes what they get to what core would let them read or edit |
| Editor (single site) | admin-created | Trusted with raw HTML (`unfiltered_html`). XSS from an Editor is not rated. Escalation an Editor reaches by any other means (a file write, a capability check that should have stopped them, reaching Developer-mode tools) is in scope; rate it in the low band and say plainly that the actor is an Editor |
| Administrator (single site) | admin-created | Fully trusted, including code execution. Not rated, except for the hardening constants below |
| Administrator of a site on a multisite network | created by a Super Admin | Partly trusted. Does **not** hold `unfiltered_html`, `install_plugins`, `edit_plugins`, `edit_themes` or, by default, `create_users`. Reaching any of those through OpenStation crosses a boundary. OpenStation's network admin shell, Extended options and Developer mode are Super Admin territory on multisite (`manage_network_options`) |
| Super Admin (multisite) | — | Fully trusted |
| Agent (AI) | a real `wp_users` row created by someone holding `edit_users` | Not an attacker. It can never authenticate (`includes/agents/guard.php`); a way to log in as one, or for a run to exceed the invoker's capabilities, is a finding against the invoker's actor row |
| Another OpenStation install | paired by an administrator on both sides | Untrusted. A hub or member whose key is pinned may send signed lists; an install that is not pinned, or whose key changed, should get nothing. A member reaching anything on the hub (or the hub on a member) beyond the documented list exchange, or acting as a user of the other install, is in scope |

**Hardening constants.** When `DISALLOW_FILE_EDIT` or `DISALLOW_FILE_MODS` is `true`, nobody, Administrators included,
should be able to edit or install plugin or theme files from inside WordPress; OpenStation's Plugins window and its
install/update proxies must honour that. Say that the finding depends on the constant.

**Translations are trusted**, like code.

## Components that matter most / least

Most important:

- **REST permission callbacks and per-object checks** (`includes/rest/README.md` maps them). The recurring real defect is
  a permission callback that checks a **global** capability (or only "logged in") where the handler then acts on an
  object the caller does not own or could not read: another user's note, desktop file, folder share, session, workspace,
  presence record, agent conversation, game score or challenge; a post, comment, media item or user whose core capability
  (`read_post`, `edit_post`, `edit_user`, `moderate_comments`, `delete_post`) was never asked. Compare against a sibling
  route that does it correctly; the README names the intended gate for each route.
- **Files on the desktop** (`includes/desktop-files/`): uploads, downloads, stored files, the media library bridge, folder
  and file sharing between users, and the recycle bin. The intended gates are `upload_files` for storage and `edit_posts`
  for sharing; a Subscriber storing or fetching files, a share recipient reaching items the share does not cover, path or
  filename handling on download, and MIME/extension checks on upload matter most.
- **The App Framework dispatch route** and each app's `capabilities()` / `can()` and action handlers under `apps/*/`,
  especially the Users app (create users, bulk role change, bulk delete, password resets, application passwords), the
  Comments app, Plugins, and Code Blue (reads the PHP error log; Developer mode + `manage_options`).
- **Cross-frame `postMessage` handling** in `src/` and `src/chromeless-bridge.js`: origin checks, message validation, and
  what the shell does on a `navigate`, `open-url`, `title`, `notification`, `drag`/`drop` or OAuth message. Also the
  REST nonce injection and method override that the shell performs for pages inside its iframes.
- **Output escaping** in PHP (`esc_*`, `wp_kses`) and in the TypeScript shell (`innerHTML`, `insertAdjacentHTML`,
  `createContextualFragment`, attribute interpolation) wherever another user's content or an external service's response
  is rendered: window titles, dock labels, the palette, notifications, Station Home, the content graph, desktop theme
  manifests, agent and AI output.
- **Agents and the AI assistant** (`includes/agents/`, `includes/ai-copilot/`): the authentication guard, the
  capability ceiling on runs, ability permission callbacks, provider credentials and where they can leak, rate limits,
  and what a hook- or cron-driven run (no invoker) can do.
- **The OpenStation Network** (`includes/network/`): signature verification, key pinning, replay, what a signed list may
  change on the receiving install, SSRF through the addresses an administrator enters and the follow-up fetches.
- **The OAuth relay** (`includes/oauth-relay.php`): `state` binding to the user, the callback's handling of `code` and
  `error`, where tokens go, and what the opener window trusts from the popup.
- **Session, workspace and preference storage** (`includes/session.php`, `os-settings.php`, workspaces): user-scoped data
  that must stay user-scoped; shared workspaces must only be released by the sending administrator.
- SQL built through `$wpdb` (activity, presence, content changes, pulse counters, stored files), `unserialize()` or
  `json_decode()` of anything a lower-privileged user can influence, and the migrations in `includes/migrations.php`.
- **Multisite boundaries**: a site administrator reaching network options, other sites' data, or the network shell.

Less important, still in scope: the dock, window manager, drag and resize, wallpapers and visual effects (`src/`,
`assets/css/`), where the only likely issue is DOM XSS; the games (`includes/games/`, opt-in, scores and challenges
between users); the Pulse Monitor and widgets (aggregate statistics; check what a low-privileged caller learns);
`extensions/` (sibling plugins developed in this repository but shipped separately: Code Editor, Cron Manager, phpMyAdmin,
Popup Siege, Feed Buddy, the Electron adapter; the first three are administrator-only developer tools by design, so only a
missing or bypassable gate there is a finding; `extensions/base/` is their shared library).

Out of scope: `node_modules/`, `vendor/`, `assets/vendor/` (PixiJS) and other third-party code, except where the way
OpenStation uses it creates the vulnerability. `tests/`, `bin/`, `tools/`, `docs/`, `reports/`, the GitHub workflows and
the build tooling are out of scope unless they introduce a vulnerability into the built plugin that sites run.

## How to exercise it

- Run `wp-start` first. It starts MariaDB and Apache (the container has no init system) and is safe to run again. The
  site is then at `http://127.0.0.1/`, with pretty permalinks. `wp-stop` stops both.
- The site is a single-site install of the latest WordPress release with one user per default role, OpenStation
  activated and switched on for each of them. Each password is the same as the username: `admin` (administrator),
  `editor`, `author`, `contributor`, `subscriber`. Registration is off, as it is by default. The desktop is at
  `http://127.0.0.1/wp-admin/`; a page inside a window is the same admin page with `?openstation_chromeless=1` (or loaded
  as a same-origin iframe, which the `Sec-Fetch-*` headers reveal; see `includes/core/routing.php`).
- `wp --path=/var/www/html ...` (WP-CLI) sets up content, options, users and roles. `wp --path=/var/www/html eval '...'`
  runs PHP in a loaded WordPress. The opt-in modules are extended options:
  `wp --path=/var/www/html option patch insert desktop_mode_extended_options agents true` (likewise `games`, `network`),
  or the Preferences → Features → Extended options screen as an administrator. To test multisite behaviour,
  `wp --path=/var/www/html core multisite-convert` converts the site to a subdirectory network.
- REST calls as a user: create an application password for the actor,
  `wp --path=/var/www/html user application-password create subscriber scanner --porcelain`, then
  `curl -u subscriber:<password> http://127.0.0.1/wp-json/desktop-mode/v1/session`. Application passwords work over
  plain HTTP here because the environment type is local. For a cookie session, log in with
  `curl -c jar -d 'log=subscriber&pwd=subscriber' http://127.0.0.1/wp-login.php` and take the `wp_rest` nonce from a
  page that user can load (`/wp-admin/`, in `wpApiSettings.nonce`). Minting a nonce with WP-CLI as a different user is
  the kind of shortcut a reproducer must not take (see below).
- The plugin Apache serves is `/src` (symlinked at `/var/www/html/wp-content/plugins/desktop-mode`), so a PHP patch
  takes effect on the next request. A change under `src/` or `apps/` needs `npm run build` (or one `build:<target>`
  script from `package.json`) to reach `assets/js/`.
- PHPUnit: `cd /src && vendor/bin/phpunit --configuration tests/phpunit/phpunit.xml.dist --filter <TestClass>`, with
  MariaDB running. Tests use the `wordpress_test` database and the WordPress test library at `/wordpress-phpunit`
  (`WP_TESTS_DIR`). `WP_MULTISITE=1` in front of the same command runs the suite against a network install. Tests are
  tagged `@group openstation`.
- Vitest (the TypeScript shell, in jsdom): `cd /src && npm run test:js`, or `npx vitest run <file>`.
- PHPCS: `vendor/bin/phpcs -n` checks the WordPress coding standards the project gates on.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate administrator would: create users at their real roles, set real options, add content,
pair a network as an administrator would. Then drive the attack **as the claimed actor**, through the normal interface:
their own login, their own application password, their own nonce obtained from a page they can load. Do not mint a nonce
as an administrator, flip the target option through the database or WP-CLI, grant the attacker a capability, switch
OpenStation on for a user who could not do so, or drive the action from an administrator's session. Reading the database
to observe the outcome is fine. If the attack only works through such a shortcut, it is not a finding.

For XSS, show that the payload executes in a browser context (the shell is a single page; a payload that lands in a
window title or a dock label must actually run there), not only that it appears in the HTML or in a JSON response.

## How you rate severity

Two questions settle the band, in this order:

1. **Can the attacker create their own account?** Anonymous or Subscriber (self-registerable) is the high band.
   Contributor and Author (admin-created) is the low band. On single site, XSS from an Editor or Administrator is not
   rated, and neither is anything else an Administrator does; an Editor's non-XSS escalation is rated in the low band.
2. **Is the chain real and unconditional?** A finding that needs an opt-in module (agents, games, network, the AI
   assistant with a configured provider, Developer mode, Pulse Monitor visitor counting) is one notch lower than the same
   finding on a default activation, and the report must say which option it needs. **XSS that leads to RCE is still
   XSS.**

### Anonymous visitor, or a self-registerable account

| Finding | Severity |
|---|---|
| Proven RCE, unchained, no preconditions | Critical |
| XSS or SQL injection, unchained | High |
| A Subscriber reading or writing another user's private data (notes, files, sessions, conversations, application passwords), or reading post content, user data or site configuration they could not otherwise see | High |
| A Subscriber uploading or storing files, or deleting or modifying content | High |
| XSS that leads to RCE, or any other valid, viable chained RCE | High |
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
| IDOR, broken access control (another user's files, notes, shares, conversations; posts they cannot edit; user management) | Low |
| Most other findings | Low |
| No real security impact | Informative |

### Multisite

- XSS by an actor who holds `manage_options` or more on a sub-site is **Low**, even when it fires in a Super Admin's
  session.
- A sub-site administrator reaching `unfiltered_html`, `install_plugins`, `edit_plugins`, `edit_themes`, network options
  or another site's data is **Low**.

### Rules by class

- **Validity comes before severity.** A finding counts only if it names the actor, what that actor can already do through
  the normal interface, and the specific capability or data they gain. No gain means no finding, however real the code
  defect.
- **Permission callbacks:** "logged in + OpenStation enabled" is the intended gate for a user's **own** data (session,
  preferences, presence, their own notes and files). It is a finding only when the handler then reaches someone else's
  data or a core object without the core capability check.
- **`postMessage`:** a finding needs a sender that an attacker can realistically control: a page inside an OpenStation
  window from another origin (an oEmbed, an iframe a plugin embeds, a Customizer preview) or a page the attacker can
  make the shell open. Messages from the site's own origin by a script already running there are not a boundary.
- **Deserialization:** a POP chain needs a real gadget in installed code; name it. Object injection with no valid,
  available gadget chain is Informative.
- **SSRF:** needs proof that a real internal or localhost host returned different data to the attacker. The network
  module and the OAuth relay fetch addresses administrators enter; an administrator pointing their own site at an internal
  host is not a finding unless the response is disclosed to a lower actor.
- **CSRF:** needs realistic cross-origin exploitation under default `SameSite` cookie behaviour. REST routes require a
  valid `X-WP-Nonce` for cookie authentication; `admin-ajax.php` handlers must call `check_ajax_referer()`.
- **Prompt injection** against the AI assistant or an agent is a finding only when it makes the model take an action the
  invoking user could not take themselves, or discloses data the invoking user could not read.
- **IDOR:** valid only when it crosses a real authorization boundary to non-public data.
- **Open redirects** are Informative unless they leak a token (the OAuth `state` or `code`) or chain into a proven
  exploit.
- **Race conditions** are Informative without practical, demonstrated impact.

## How reports and patches should look

- State the claim as one sentence: *&lt;actor&gt; can &lt;action&gt; against &lt;target&gt;, which they otherwise could
  not.*
- Give an explicit **actor / already holds / gains** line, the least privileged role that triggers the issue, whether it
  needs self-registration, multisite, an extended option or any other non-default setting, and the severity from the
  tables above.
- Write the impact as one short sentence naming what the attacker can **do**, then two plain-language sentences with no
  function names or payloads: who can do it, what account they need, what they get, and whether a default activation is
  affected.
- Name the affected file and function (or the route and its handler from `includes/rest/README.md`), and give a
  self-contained reproducer: WP-CLI setup plus `curl` with an application password, or a PHPUnit test in the project's
  style (`tests/phpunit/tests/`, `@group openstation`, `WP_UnitTestCase`, users created through the factory and set with
  `wp_set_current_user()`).
- Write patches as `git diff` against `/src`. Follow the WordPress PHP coding standards (`vendor/bin/phpcs -n` checks
  them) and the project's conventions (`AGENTS.md`), and use core APIs (`esc_html()`, `esc_attr()`, `esc_url()`,
  `wp_kses()`, `$wpdb->prepare()`, `current_user_can()`, `check_ajax_referer()` / `wp_verify_nonce()`,
  `rest_ensure_response()`) rather than ad hoc escaping or checks. A permission fix usually belongs in the permission
  callback or at the top of the handler, next to the sibling routes that already do it right. Update
  `includes/rest/README.md` when a route's gate changes.

## Anything to leave alone

- Anything an Administrator (single site) or Super Admin can already do, including running PHP, editing files, reading
  the error log (Code Blue), using the Code Editor, Cron Manager and phpMyAdmin extensions, installing plugins, or
  configuring an AI provider, except where a hardening constant such as `DISALLOW_FILE_EDIT` forbids it.
- XSS by an Editor or Administrator on single site.
- A Subscriber switching OpenStation on for themselves, and everything that renders only their own data once they have:
  the shell, their session, their preferences, their presence record, their own notes and workspaces.
- The intentional public surface: `/network/identity` publishing the install's name, URL, shell URL and public key while
  the network option is on; the PWA manifest and service worker; the Pulse Monitor counting a page view.
- Username and author enumeration, by any mechanism, and the presence feature showing which logged-in users are active
  to other logged-in users who can already list them.
- Version disclosure, the plugin's `readme.txt`, full path disclosure from errors, warnings or notices, missing security
  headers, and missing rate limiting on login.
- Self-XSS, CSRF on login or logout, and anything that only works with `WP_DEBUG` or `SCRIPT_DEBUG` on.
- Telemetry and feedback: the deactivation and usage feedback forms forward what the user typed to openstation.blog only
  when the user submits them, and the About feed is fetched from openstation.blog by the server. Report only a way for
  another actor to trigger or read them.
- Reports of outdated npm or Composer development dependencies with no path into the shipped plugin.
