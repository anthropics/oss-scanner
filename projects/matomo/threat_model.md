# Threat model: Matomo

The scanner reads this file before it starts. It covers Matomo Analytics as developed on the `6.x-dev` branch of
https://github.com/matomo-org/matomo, including the plugins that branch pins as git submodules. Severity follows
Matomo's published security policy ([SECURITY.md](https://github.com/matomo-org/matomo/blob/6.x-dev/SECURITY.md) and
the [HackerOne program](https://hackerone.com/matomo)).

## What this project does and where untrusted input enters

Matomo is a self-hosted web analytics platform written in PHP on MySQL/MariaDB. It has two halves. The **tracker**
receives data from the browsers of every visitor to every tracked website. The **reporting side** (web UI and HTTP
API) is used by Matomo users with different roles on different websites. A typical installation is reachable from the
internet, because the tracker has to be.

Untrusted input enters through:

- **The Tracking API**: `matomo.php` / `piwik.php` (`core/Tracker/`, plus every plugin's tracker dimensions in
  `plugins/*/Columns/` and `plugins/*/Tracker/`), including bulk tracking (a JSON body of many requests), and the
  tracker JavaScript endpoints `js/index.php` and `js/tracker.php`. Anyone can send any value for any `idsite`. Site
  IDs are not secret. Overriding the visitor IP (`cip`), or a timestamp older than a day (`cdt`, see
  `tracking_requests_require_authentication_when_custom_timestamp_newer_than`), needs a `token_auth` with write, admin
  or Super User access to that site (`Tracker\Request::authenticateSuperUserOrAdminOrWrite`). Setting the visitor ID
  (`cid`) does not.
- **Tracked data shown later to logged-in users.** Page URLs and titles, referrers, campaign names, site search
  keywords, event categories, actions and names, content names, custom dimensions, custom variables, ecommerce item
  names and SKUs, user IDs, and device data. All of it is attacker-controlled and ends up in reports, the Visitor Log,
  the Visitor Profile, Transitions, Overlay, row evolution, exports (including the HTML format), scheduled email and PDF
  reports, and alerts. **Stored XSS from a tracking request into a logged-in user's session is the most common serious
  Matomo vulnerability.**
- **The reporting web UI**: `index.php?module=<Plugin>&action=<method>` (each plugin's `Controller.php`). It is
  authenticated by session cookie. State-changing actions must check a nonce or require a POST with `token_auth`.
- **The Reporting API**: `index.php?module=API&method=<Plugin>.<method>` (each plugin's `API.php`), with
  `API.getBulkRequest`, the generic filters (`filter_*`, `showColumns`, `hideColumns`, `flat`, `expanded`,
  `label`), segments (`segment=`), `idSite=all` and lists of sites, `period=range` and date parsing, and every output
  format renderer (`format=json|xml|csv|tsv|html|rss|original`). It is authenticated by `token_auth` (GET or POST,
  POST-only for secure tokens) or by the session with `force_api_session=1`.
- **Embedding**: Widgetize iframes (`module=Widgetize&action=iframe`) with a `token_auth` in the URL (view-only
  tokens by default; `enable_framed_allow_write_admin_token_auth=0`), the tracking opt-out (`module=CoreAdminHome&action=optOut`
  and `optOutJS`), and websites to which the `anonymous` user has been given view access.
- **Authentication flows**: login, logout, password reset, user invitations (`Login` plugin, `acceptInvitation`),
  two-factor authentication (`TwoFactorAuth`), password confirmation before sensitive actions, sessions, and app
  tokens (`UsersManager`). In 6.x a token can carry an access level lower than its user's role. A token restricted
  to `view` must not be able to do what `write` or `admin` can.
- **Content created by lower-privileged users and shown to others**: segment definitions and names, annotations, goal
  names and patterns, custom dimension names, scheduled report and alert definitions, dashboard layouts, site names
  and URLs set by site admins, user names and emails, and Tag Manager containers, tags, triggers and variables.
- **Server-side fetches and generated files**: Marketplace and update checks, GeoIP database download, AI provider
  connections (`AIProviders`), SMTP, fetches of a tracked website's own URL (`core/SiteContentDetector.php`, the goal
  recommendation scanner in `plugins/Goals/Recommendations/`), ImageGraph and sparkline images, PDF generation
  (TCPDF), and the Tag Manager container files that are written into `js/` and served to every visitor of the tracked
  sites. Every URL Matomo fetches was configured on purpose by an admin or Super User, so fetching it is by design,
  whoever triggers the fetch. Fetches of user-configured URLs go through `core/Http/EgressHostValidator.php`, which
  refuses private, loopback and reserved addresses unless `allowed_private_egress_ranges` allows them; getting past
  that check is the SSRF finding to look for.

### Actors

| Actor | Trust |
| --- | --- |
| Visitor of a tracked website / tracking client | Untrusted. Can send any tracking request to any site. |
| Anonymous web user | Untrusted. Has no access by default. A site may grant the `anonymous` user view access (idsite 2 in this image). |
| User with **view** access | Untrusted beyond reading the reports of the sites they have access to. |
| User with **write** access | View, plus creating and editing shared content for their sites (goals, annotations, segments, scheduled reports, and so on). Untrusted beyond that. |
| User with **admin** access | Write, plus site settings, managing users' access, and the GDPR tools (finding, exporting and deleting raw visits). The GDPR tools need admin access on some site and then work on the visits the user can already see; the data they return is what the Visitor Log shows to any view user, so reaching it through them is not a finding. Must not reach other sites' data or settings, Super User access, or the server. |
| Capabilities | Extra rights on top of a role. Some are included in a role by design: write includes `tagmanager_write`; admin includes `tagmanager_publish_live_container` and `tagmanager_use_custom_templates`. A user must not get the effect of a capability that neither their role nor an explicit grant gives them. |
| **Super User** | Trusted with all data and all settings, and with installing plugins through the documented paths (Marketplace, and plugin upload only when `enable_plugin_upload=1`). Remote code execution or SQL injection by a Super User through any other path is still a finding (ceiling High). |
| Holder of a `token_auth` | Has exactly the rights of that token: its user's role, capped by the token's access level. A token is a password by design. |
| Server operator | Trusted: config files (`config/config.ini.php`), the CLI (including `./console`), the file system and the database. |

## Components that matter most / least

Highest priority:

1. **Access control in the API and controllers.** `Piwik::checkUserHasViewAccess($idSite)`, `checkUserHasWriteAccess`,
   `checkUserHasAdminAccess`, `checkUserHasSuperUserAccess` and `checkUserHasCapability`. Watch for object IDs
   that belong to another site (`idGoal`, `idSegment`, `idReport`, `idAlert`, `idContainer`, `idDimension`,
   annotation IDs, `idSubtable`), `idSite=all` and lists of sites, and secondary paths that reach the same data
   without the same check: `API.getBulkRequest`, `API.getProcessedReport`, `API.getRowEvolution`, `Widgetize`,
   `ImageGraph`, the export and scheduled-report paths, and controller actions that call another plugin's API.
   Check token access levels and secure-only tokens on every path.
2. **XSS.** `Common::getRequestVar()` and the tracker HTML-encode request values on the way in. Vulnerabilities
   usually appear where a value is decoded again (`Common::unsanitizeInputValue()`, `piwikHelper.htmlDecode`,
   `html_entity_decode`) and then reaches an unescaped sink: Twig `|raw`, Vue `v-html` without Matomo's sanitizer,
   jQuery `.html()` / `.append()` of strings, `$.parseHTML`, `title` tooltips rendered as HTML, the HTML export, and
   email or PDF report templates. Tracked data is the most important source (see above).
3. **SQL injection.** Segment parsing and SQL generation (`core/Segment.php`, `core/Segment/`, the
   `plugins/*/Segment*` and `Columns/` definitions), `core/DataAccess/` (log aggregation, `LogQueryBuilder`,
   archive selection), `core/RankingQuery.php`, `Live` queries, and any `Db::query()` / `Db::fetchAll()` built by
   concatenation instead of bound parameters.
4. **CSRF and authentication.** Nonce checks on controller actions, `token_auth` checks on session API calls,
   password confirmation (`passwordConfirmation`) before changing users, Super User access, tokens or 2FA,
   password-reset and invitation tokens, session handling, and 2FA bypass.
5. **Code execution, deserialization and files.** `unserialize()` on anything an attacker can influence
   (`Common::safe_unserialize()` with allowed classes is the expected pattern), file uploads (custom logo, plugin
   upload), path traversal in anything that turns a request parameter into a file path (languages, themes, plugin
   assets, report or font files), and template injection.
6. **Tag Manager** (`plugins/TagManager`, the `matomo-org/tag-manager` submodule). How tag, trigger and variable
   values are escaped into the generated container JavaScript and into preview/debug mode, and the capability checks
   between `tagmanager_write`, `tagmanager_publish_live_container` and `tagmanager_use_custom_templates`.
   In this image: `TagManager.getContainers&idSite=1` lists the default container, `TagManager.enablePreviewMode`
   turns preview on, the generated files are `js/container_<id>*.js`, and the debug UI is
   `index.php?module=TagManager&action=debug`.

In scope, normal priority: every other plugin in `plugins/`, including all submodule plugins (CustomAlerts,
QueuedTracking, LoginLdap, MarketingCampaignsReporting, Provider, CustomVariables, SecurityInfo,
TreemapVisualization, TasksTimetable, LogViewer, Bandwidth, DeviceDetectorCache, AnonymousPiwikUsageMeasurement,
VisitorGenerator). `misc/log-analytics` is a command-line tracking client and is out of scope itself; how the tracker
handles the requests it sends is covered by the review of Matomo.

Out of scope:

- `vendor/` and the bundled third-party code in `libs/` and `node_modules/`. Report these only where Matomo's own use
  of the library creates the vulnerability.
- `tests/`, `plugins/TestRunner`, the `plugins/Example*` sample plugins, and test-only configuration
  (`config/environment/test.php`, `plugins/*/config/test.php`). The release package does not include them.
- The CLI, including every `./console` command, `misc/cron/archive.php` and other command-line scripts.
- Third-party plugins, meaning plugins not written by Matomo or InnoCraft.

## How to exercise it

- Run `matomo-start` first. It starts MariaDB, Redis and Apache (there is no init system in the container) and is
  safe to run again. `matomo-stop` stops all three. The site is at `http://127.0.0.1/`, served from `/src`, so a
  PHP or Twig patch to `/src` takes effect on the next request. JavaScript is served merged and cached: after changing
  a `plugins/*/javascripts/*.js` or `plugins/*/vue/dist/*.umd.min.js` file, run `matomo-console core:clear-caches`.
  Use `127.0.0.1`, not `localhost`: it is the only trusted host
  (`trusted_hosts[]` in `config/config.ini.php`). With any other `Host`, Matomo still answers, but the UI shows an
  "untrusted host" warning and builds its links and redirects for `127.0.0.1`. That is by design, not a finding.
- Matomo is installed, with two websites and one user per role. Each password is `<login>-password`:

  | Login | Access |
  | --- | --- |
  | `admin` | Super User |
  | `siteadmin` | admin on idsite 1 |
  | `writer` | write on idsite 1 |
  | `viewer` | view on idsite 1 |
  | `viewer2` | view on idsite 2 only |
  | `anonymous` (no login) | view on idsite 2 only |

  Each of these users has an app token in `/root/matomo-tokens.txt`, as `<login> <token>` lines. These tokens have
  their user's full role and are not secure-only, so they work in GET as well as POST requests (tokens created in the
  UI are POST-only by default). For a scoped or POST-only token, call `UsersManager.createAppSpecificTokenAuth` with
  `accessLevel=view|write|admin` or `secureOnly=1`.
- Visits were tracked and archived when the image was built: on idsite 1 for the build day and the two days before,
  on idsite 2 for the build day. Request them with `period=day&date=last30`, or with `Live.getLastVisitsDetails`.
- API calls: `curl -s -d "token_auth=$TOKEN" 'http://127.0.0.1/index.php?module=API&method=SitesManager.getSitesWithAtLeastViewAccess&format=json'`,
  or with the header `Authorization: Bearer $TOKEN`.
- UI session: `curl -c jar 'http://127.0.0.1/index.php?module=Login'`, take the `form_nonce` value from the HTML, then
  `curl -b jar -c jar 'http://127.0.0.1/index.php?module=Login' -d form_login=viewer -d form_password=viewer-password
  -d form_nonce=<nonce>` (302 on success). Pages then work with `-b jar`. For API calls with that session, send
  `force_api_session=1` and `token_auth=<the piwik.token_auth value printed in any page>`; calls that change users or
  tokens additionally need `passwordConfirmation=<that user's password>`.
- Database: `mariadb matomo` works as root (tables are prefixed `matomo_`); PHPUnit uses `matomo_tests`.
- There is no mail server. Every email Matomo sends (invitations, password resets, scheduled reports, alerts) is
  written to `/var/mail/matomo/` as a `.eml` file. Scheduled reports and alerts are sent by the scheduler, which has no
  cron here: run `matomo-console scheduled-tasks:run` (it exits 1 because a few tasks try to reach the internet; that
  is expected), or force one report with `ScheduledReports.sendReport&idReport=<id>&force=1`.
- Tracking: `curl 'http://127.0.0.1/matomo.php?idsite=1&rec=1&url=http://example.com/x&action_name=Title'`. Browser
  archiving is on, so today's reports update when they are requested. `matomo-console core:archive --url=http://127.0.0.1/`
  archives everything.
- `matomo-console` runs `./console` as `www-data`, the Apache user, so the files it writes stay writable by the site.
  Use it rather than `./console` directly. `matomo-console config:set 'General.<key>="<value>"'` changes configuration
  (string values need the double quotes). `as-www-data <command>` runs any other command as `www-data`. If the site
  starts failing with permission errors after `./console` was run as root, run `matomo-start` again.
- These submodule plugins are active: TagManager, CustomAlerts, MarketingCampaignsReporting, CustomVariables,
  TreemapVisualization, TasksTimetable, LogViewer, Bandwidth and SecurityInfo. LoginLdap, QueuedTracking, Provider,
  DeviceDetectorCache, AnonymousPiwikUsageMeasurement and VisitorGenerator are present but inactive, because they
  replace the login, move tracking onto a Redis queue, do reverse DNS for every visit, or exist only for development.
  To test one, run `matomo-console plugin:activate <Plugin>` and then `matomo-console core:update --yes` (Matomo
  answers "Please run the update process first" until the update has run). Redis is running for QueuedTracking, but
  its queue is off until `matomo-console config:set 'QueuedTracking.queueEnabled=1'`; then
  `matomo-console queuedtracking:process` replays queued requests. LoginLdap has no LDAP server to talk to here, so
  it can only be reviewed from its code.
- Two-factor authentication: no user has it. To test it, log in, open
  `index.php?module=TwoFactorAuth&action=setupTwoFactorAuth&idSite=1&period=day&date=yesterday`, confirm the
  password, and read the base32 secret from the page; compute TOTP codes (SHA-1, 30 s, 6 digits) with `python3` and
  its `hmac` module to finish the setup and to log in.
- PHPUnit: `matomo-phpunit <path>` runs as `www-data` with MariaDB running, against the `matomo_tests` database, which
  the tests drop and recreate. Integration tests (`plugins/<Plugin>/tests/Integration/`, `tests/PHPUnit/Integration/`)
  are the preferred reproducers, for example `matomo-phpunit plugins/UsersManager/tests/Integration/APITest.php`.
  System tests make HTTP requests to this Apache through `tests/PHPUnit/proxy/`.
- PHP errors and warnings are not shown in responses, as on a production server. They go, with Apache's own errors, to
  `/var/log/apache2/error.log`. Lines saying "client denied by server configuration" for `.git`, `config/`, `lang/`
  and `tmp/` come from Matomo's own system check, which probes them on purpose, and are expected.
- **Differences from a production install.** The web root is a git checkout, so `tests/` (including the test entry
  points under `tests/PHPUnit/proxy/`), `composer.json` and other
  development files are reachable over HTTP here (`.git/` is not: Matomo writes a deny-all `.htaccess` into it). A
  release package does not contain them. Anything reachable only
  through them is out of scope. Outbound internet access is not available while scanning, so the Marketplace, update
  checks and AI provider calls fail.

### Reproducers

Set up only what a legitimate administrator would: create users at their real roles, set real configuration, track
data through `matomo.php`. Then carry out the attack **as the claimed actor**, through the web UI or the HTTP API,
with that actor's session or token. Do not give the attacker the right they are supposed to gain, edit the database or
config to create the precondition, or drive the attack from a Super User session (unless the claimed actor is the
Super User). Reading the database to observe the
outcome is fine. For XSS, there is no browser here: show the exact response bytes and explain why they execute (a
`<script>` or event handler outside any attribute value, or an unquoted or JavaScript attribute context). A value that
reaches the page HTML-encoded is not a finding.

A bypass must gain the actor something. A missing second check that another check already covers, an escaping layer
in output no user sees, or an API that allows the same user what the UI hides, is a hardening suggestion, not a
finding, unless you show the data or action it unlocks for someone who did not have it.

## How you rate severity

Give a CVSS 3.1 vector and score with every report. Everything inside one Matomo installation (its users, roles,
websites, sessions, tokens and plugins) is one security scope: use **S:U** even for a Super User takeover, and **S:C**
only for a demonstrated effect outside it, such as the server, another system, or the browsers of the tracked sites'
visitors (for example through a Tag Manager container). Rate C, I and A on Matomo's own data and state; what an
attacker could do on a tracked website is described in the report and expressed through Scope, not through the C/I/A
values.

The table gives the **highest** rating a finding of that kind normally gets, by the attacker's starting position. It
follows Matomo's published policy and how its security team has rated reports in practice. Rate within the ceiling
with CVSS; the modifiers below say what lowers a rating.

| Finding | Anonymous or tracking client | Authenticated below Super User | Super User |
| --- | --- | --- | --- |
| Remote code execution or SQL injection, unchained, on a default installation | Critical | Critical | High |
| Remote code execution or SQL injection that needs a chain, a race, or a plugin that is not in the release package | High | High | Medium |
| Stored XSS that runs in another user's session | High | High (view or write); Low when the attacker needs admin | Low |
| Reflected or DOM XSS | High | High | — |
| CSRF that runs attacker-chosen API methods or leaks a `token_auth` | High | High | — |
| CSRF limited to one fixed action the attacker cannot vary (for example deleting a given item) | Medium | Medium | — |
| Authentication bypass or account takeover, including 2FA bypass when the password is known | High | High | — |
| Escalation to admin or Super User, or JavaScript reaching the tracked sites' visitors without the capability that allows it | — | High | — |
| Other bypass of a capability or publish right inside a site the user already has access to (preview, drafts, templates the user could not create) | — | Medium | — |
| Reading or changing data of a site the user has no access to | — | Medium; High when systemic (all sites) or chained to takeover | — |
| Limited disclosure across a permission boundary (names, ids, configuration) | Low | Low | — |
| Fetch past the egress check that returns response content | Medium | Medium | not a finding |
| Open redirect, CSV or formula injection, HTML injection without script execution | Low | Low | — |
| Uncontrolled resource consumption: one request that makes Matomo do unbounded work (recursion, unbounded date or label ranges, corrupt archives) | High | Medium | — |
| Denial of service: volumetric attacks, brute force, flooding, ReDoS | out of scope | out of scope | out of scope |

Modifiers:

- **What lowers a rating within its ceiling.** The victim has to perform specific steps (hover a particular tooltip,
  open a specific popover or export, pivot a report); the page or state is uncommon; the sanitiser leaves only HTML
  injection without script; CSP keeps the payload from sending data away; a plugin that few installations have is
  needed (the submodule plugins in this image are common and do not lower a rating); a hard limit on the sink (a short
  database column, a numeric-only field) stops a meaningful payload; an existing mitigation such as SameSite cookies
  applies; or the attacker gains little beyond what their role already gives.
- **XSS is rated as XSS.** A chain that ends in a Super User's session or in installing a plugin stays at High; the
  victim's role does not raise the rating.
- **2FA.** A bypass that needs nothing but the victim's password is High; one that also needs the victim's pending
  session cookie, or only yields view access, is Medium.
- **Races.** A race condition counts only when the attacker can trigger both sides at will. One that needs the
  victim, a Super User or a scheduled task to act inside the window is not a finding.
- **No self-registration.** Every account below Super User was created or invited by an admin, so "authenticated"
  always means an admin-created account.
- **Configuration.** A finding that needs a configuration against Matomo's security best practices is out of scope.
  One that needs another non-default setting (anonymous view access, `enable_plugin_upload=1`, `logme`, a login
  plugin's web-server or LDAP mode) is rated one band lower and the report must say so.
- A finding needs a working exploit against the running instance. A code pattern alone, with no demonstrated exploit,
  is not a finding.

## How reports and patches should look

- State the affected component or plugin, the required authentication level (unauthenticated, tracking client,
  view, write, admin, a capability, or Super User), and any non-default configuration the finding depends on,
  including anonymous view access to a website (idsite 2 here), which a default installation does not grant.
- Include step-by-step reproduction against this instance (`curl` requests, or a PHPUnit integration test), the
  real-world impact in one or two plain sentences, and the CVSS 3.1 vector.
- Write patches as `git diff` against `/src`. For a submodule plugin (for example `plugins/TagManager` or
  `plugins/CustomAlerts`), write the patch against that plugin's own repository, as a diff inside
  `/src/plugins/<Plugin>`, and name the repository.
- Matomo's Vue components live in `plugins/<Plugin>/vue/src/` and are compiled into `vue/dist/<Plugin>.umd.min.js`
  by `vue:build`, which needs Node and is not available here. Write the patch against `vue/src`; to check it, apply
  the equivalent change to the `vue/dist` file by hand and run `matomo-console core:clear-caches`.
- Follow Matomo's conventions: put access checks in the plugin's `API.php` (`Piwik::checkUserHas*Access()`,
  `checkUserHasCapability()`), use bound parameters with `Common::prefixTable()` for SQL, `Nonce::checkNonce()` for
  controller actions, Twig autoescaping and Matomo's sanitizer for Vue `v-html`, and `Common::safe_unserialize()`.
  When a check is missing on one path, check whether the same fix is needed on the other paths to the same data.

## Anything to leave alone

These are out of scope or known, accepted behaviour in Matomo's program:

- Anything a Super User can already do by design: running JavaScript on the tracked sites through Tag Manager custom
  templates, configuring outbound URLs (SMTP host, GeoIP download URL, AI provider endpoints, including local ones),
  and installing plugins through the Marketplace.
- Matomo fetching a URL that an admin or Super User configured on purpose (a tracked website's URL for site content
  detection or goal recommendations, SMTP, GeoIP, AI providers), even when a lower-privileged user triggers the
  fetch. The finding would be getting past the egress check, not the fetch itself.
- `token_auth` behaving as a password, and `token_auth` in Widgetize iframe URLs.
- `module=Login&action=logme`, which is off by default (`login_allow_logme=0`) and documented as a convenience for
  operators who accept the risk.
- Clickjacking, Cross-Window Forgery, text injection, missing security headers (CSP, HSTS, X-Frame-Options, and so on),
  missing flags on non-sensitive cookies, version or path disclosure, open directory listings, and application errors.
- Attacks that need a man-in-the-middle position, control of DNS, the local network or a dangling subdomain under a
  trusted host, access to the victim's device, browser profile, extensions or clipboard, an outdated browser, or a
  Matomo served without HTTPS.
- Vulnerabilities that come from outdated infrastructure (PHP, MySQL/MariaDB, the web server, the operating system).
- CSRF on login, logout, unauthenticated forms, or actions that have no security-relevant effect.
- Brute force, volumetric denial of service, rate limits, and race conditions that get around limits or quotas.
  One request that makes Matomo do unbounded work is rated in the severity table, not excluded here.
- Host or forwarded-header injection (including password-reset link poisoning) that depends on proxy header settings
  or on trusted hosts not being configured.
- Analytics pollution: sending fake tracking data, authenticated or not, without further impact.
- Blind SSRF where the result comes back only as a boolean, an error, a timing or a length difference.
- The installer before installation has finished, which is an operator responsibility, and the updater
  (`CoreUpdater.runUpdaterAndExit`) being reachable without a login while an update a Super User started is pending:
  it only runs the migrations that update needs anyway.
- Email addresses never being verified (invitations or email changes), the invitation link itself being the
  authorization to claim the invited account, login and password-reset responses that differ for existing accounts,
  and the default password policy accepting weak passwords.
- Matomo needing write access to its own directories for updates and plugin installation, and world-writable files
  in a shared hosting environment.
- Findings that need CLI, config file, file system or database access, or a configuration that goes against
  [Matomo's security best practices](https://matomo.org/docs/security-how-to/) (for example
  `enable_trusted_host_check=0`).
- Information disclosure that stays inside the attacker's own authorization scope.
- Built-in Tag Manager integration tags that load a third-party script from a configured host (the Matomo, Livezilla,
  Etracker and similar templates), and preview mode running a container's draft content: that is what they are for.
  The boundary is the custom-template capability, not the templates themselves; a user who can publish a container
  live has the same trust as one who can author custom templates.
- Alert and report deliveries to a URL or address the configuring user chose (webhooks, email): the request is a
  blind send whose response that user never sees, so it is not SSRF. (In this image nothing sends webhooks; the
  sender is a separate Marketplace plugin.)
- Anything inside a website the Super User has given the `anonymous` user view access to (visits log, visitor ids,
  user ids): granting that access publishes the site's reporting data on purpose.
- Requests authenticated with a `token_auth` (not a session) skipping the password-confirmation prompt: the token is
  the credential. A session that reaches a confirmation-guarded action without the password is a finding (Medium),
  because it turns a stolen session into persistence (a new user or token that outlives the session).
- Findings that presume the attacker already holds the victim's session cookie or token and end with exactly the
  access that credential already gives for as long as it is valid. Secure-only tokens protect a user's own token
  from leaking through GET requests; they are not an authorization boundary.
- Reading a site's own configuration (goals, segments, custom reports, excluded parameters) with view access:
  intended. Credentials, API keys, tokens and Super User-only global settings are not part of that.
  Settings such as "turn off the visits log", URL exclusion lists or `enable_users_admin` are reporting or hardening
  toggles, not permission boundaries.
- Identity asserted by the web server, an LDAP directory or a SAML identity provider when a login plugin is
  configured to trust it: the operator chose that trust, and it is not a severity multiplier for other findings.
  These plugins may also be configured to skip Matomo's password-confirmation step for their users, which is a
  documented compatibility option; do not count the access that gives toward another finding.
- Values served by the Matomo Marketplace (plugin metadata, licence texts) are trusted.
- Tracking code and opt-out embed snippets that a site owner copies onto their own website: markup in them does not
  execute inside Matomo. (Markup that executes inside Matomo's own pages is still a finding.)
- Debug and development modes (Tag Manager debug, tracker debug, development mode): off by default and documented as
  developer tools.
- API requests authenticated with a `token_auth` are not asked for a second factor. Creating a token already requires
  2FA, so a token request is the account owner acting; 2FA guards the login, not every API call.
- Getting around a privacy or data-quality control (IP anonymisation, referrer or URL-parameter stripping, the
  excluded-parameter lists, the opt-out) on its own. These controls reduce what Matomo stores; bypassing one is a
  finding only when it exposes data to someone who could not see it, or lets them change data they could not change.
- Self-XSS, and anything that needs the victim to paste code into their own browser console.
- OAuth2 scopes resolving to a Matomo role rather than a list of permitted operations, so a read scope can reach
  state-changing methods that role may call (a documented limitation).
