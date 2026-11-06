# Threat model: Action Scheduler

## What this project does and where untrusted input enters

Action Scheduler (`action-scheduler`) is a background job queue library for WordPress. A plugin or theme calls
`as_schedule_single_action()`, `as_schedule_recurring_action()`, `as_schedule_cron_action()` or
`as_enqueue_async_action()` (`functions.php`) with a hook name, arguments and a time; the library stores the action in
its own database tables; a queue runner later fires the hook with those arguments through `do_action_ref_array()`
(`classes/actions/ActionScheduler_Action.php`). It ships inside WooCommerce (which uses it for webhook delivery,
analytics imports, emails, subscription renewals and housekeeping), inside many other plugins, and as a standalone
plugin on wordpress.org. When several copies are active, the `ActionScheduler_Versions` registry
(`classes/ActionScheduler_Versions.php`) loads the newest. This enrollment covers the library on `trunk`:
`action-scheduler.php`, `functions.php`, `classes/`, `lib/` and `deprecated/`. In the image it is both the active
standalone plugin and the copy a WooCommerce store runs; the older copy bundled inside WooCommerce stays inert.

The library has almost no web surface of its own. It reads request data on one wp-admin screen and from WP-CLI, and
two things it registers are reachable by anyone on the internet. Most of what it handles is data a host plugin stored
on behalf of someone else, which executes later. Untrusted input enters through:

- The async queue runner, `wp-admin/admin-ajax.php?action=as_async_request_queue_runner`, registered for logged-in
  and logged-out callers (`wp_ajax_` and `wp_ajax_nopriv_`) in `lib/WP_Async_Request.php` and handled by
  `classes/ActionScheduler_AsyncRequest_QueueRunner.php`. The site dispatches it to itself as a non-blocking loopback
  POST at the end of an admin request (`ActionScheduler_QueueRunner::maybe_dispatch_async_request()` in
  `classes/ActionScheduler_QueueRunner.php`, rate-limited through `classes/ActionScheduler_OptionLock.php`), with a
  nonce for the action name and the dispatching user's cookies. `check_ajax_referer()` is the boundary. An accepted
  request runs the due queue in that user's request context.
- WP-Cron: `action_scheduler_run_queue` is scheduled every minute (`ActionScheduler_QueueRunner::init()`), and
  `wp-cron.php` can be triggered by any visitor. `wp action-scheduler run` is the third runner context
  (`classes/WP_CLI/ActionScheduler_WPCLI_QueueRunner.php`). Triggering the queue is not a privilege: anyone can make
  due actions run a little earlier. What matters is what runs and who chose it.
- Rows in the store: `{$wpdb->prefix}actionscheduler_actions`, `_claims`, `_groups` and `_logs`
  (`classes/schema/ActionScheduler_StoreSchema.php`, `classes/schema/ActionScheduler_LoggerSchema.php`, read and
  written by `classes/data-stores/ActionScheduler_DBStore.php` and `ActionScheduler_DBLogger.php`), or on sites that
  never migrated, `scheduled-action` posts and comments (`classes/data-stores/ActionScheduler_wpPostStore.php`,
  `ActionScheduler_wpCommentLogger.php`, bridged by `ActionScheduler_HybridStore.php` and `classes/migration/`).
  Each row is a hook name, JSON-encoded arguments, a group, a priority and a PHP-serialized schedule object. The
  arguments are whatever the host plugin passed, often shopper data (order ids, emails, URLs). The schedule is read
  back through `classes/ActionScheduler_ScheduleDeserializer.php`, which restricts `unserialize()` to the library's
  schedule classes plus an allowlist of nested classes, with filters a site can loosen; the legacy post store reads
  the raw meta (`ActionScheduler_wpPostStore::get_schedule_from_post_meta()`) and routes it through the same
  deserializer.
- The public API in `functions.php` (`as_*()`) and `deprecated/functions.php` (`wc_*()`), plus the classes third
  parties call directly: `ActionScheduler::store()` and `ActionScheduler_Store::query_actions()`
  (`classes/abstracts/ActionScheduler.php`, `classes/abstracts/ActionScheduler_Store.php`,
  `classes/ActionScheduler_ActionFactory.php`). Query arguments (`orderby`, `order`, `status`, `args`, `group`,
  `search`, `claimed`, `date`, `modified`) become SQL in `ActionScheduler_DBStore::get_query_actions_sql()`: the
  `orderby` value is matched against a fixed list, and `args` partial matching uses `JSON_EXTRACT` and `LIKE` with
  placeholders.
- The wp-admin screen (`classes/ActionScheduler_AdminView.php`). Tools > Scheduled Actions needs `manage_options`.
  WooCommerce > Status > Scheduled Actions is the same list table on WooCommerce's status page, which WooCommerce
  opens to `manage_woocommerce`, so shop managers reach it too. `classes/abstracts/ActionScheduler_Abstract_ListTable.php`
  and `classes/ActionScheduler_ListTable.php` read `orderby`, `order`, `status`, `s`, `filter_by`, `paged`, `ID[]`,
  `row_action`, `row_id` and `nonce` from the request, verify a nonce for the `run` and `cancel` row actions and the
  `delete` bulk action, and render the stored hook, arguments (`column_args()`), group, schedule and log messages
  (`get_log_entry_html()`) of every action to the viewer with `esc_html()`. The past-due notice and the per-row
  result notice (transient `action_scheduler_admin_notice`, `display_admin_notices()`) render hook names too.
  `classes/ActionScheduler_wcSystemStatus.php` adds a section to WooCommerce's System Status report.
- WP-CLI: `wp action-scheduler run`, `clean`, `migrate`, `wp action-scheduler action create|cancel|delete|generate|
  get|list|next|run` and `wp action-scheduler status|datastore|runner|version|source` (registered in `classes/abstracts/ActionScheduler.php`,
  implemented in `classes/WP_CLI/`; `--args` is JSON). These need a shell on the server and are not an attack
  surface, but they are the quickest way to create actions in a reproduction.
- The migration from posts to custom tables (`classes/migration/Controller.php`, `Runner.php`,
  `BatchFetcher.php`), scheduled on `wp_loaded` and runnable from WP-CLI, and the daily cleanup
  (`classes/ActionScheduler_QueueCleaner.php`), which read legacy rows and delete old ones.

### Actors

| Actor | How they get there | Trust |
|-------|--------------------|-------|
| Anonymous visitor | can request `wp-cron.php` and `admin-ajax.php?action=as_async_request_queue_runner`, and any host-plugin feature that schedules actions (checkout, webhooks, forms) | Untrusted. High band |
| Customer, Subscriber | self-registered at checkout or My Account (enabled in this image); no screen of this library | Untrusted. High band |
| Shop manager | admin-created; `manage_woocommerce` reaches the Scheduled Actions tab under WooCommerce > Status, so they can run, cancel and delete any stored action and read every argument and log | Partly trusted. Low band |
| Administrator | admin-created; `manage_options`, Tools > Scheduled Actions | Fully trusted, including code execution. Not rated |
| Site operator with a shell | WP-CLI commands | Fully trusted. Not rated |
| Host plugin code | calls `as_*()` | Trusted code, untrusted arguments: what it passes may come from a shopper |

The library runs stored hooks with whatever the host plugin scheduled. A finding that starts from a row's content
must show how a lower-privileged actor controls that content end to end: name the host plugin path that wrote it (in
this image, WooCommerce core's own uses of the API) or the surface of this library that lets them write or alter rows.

## Components that matter most / least

Most important:

- Execution of stored rows: `ActionScheduler_Action::execute()`,
  `ActionScheduler_Abstract_QueueRunner::process_action()` (`classes/abstracts/ActionScheduler_Abstract_QueueRunner.php`),
  `ActionScheduler_QueueRunner::do_batch()` and the claim logic in the stores (`stake_claim()`, `claim_actions()`,
  `get_claim_id()`). Whoever can insert or alter a row chooses which hook fires with which arguments. A path by which a
  lower-privileged actor creates a row, changes its hook, arguments or group, or re-points a pending action is the
  highest-value finding.
- Deserialization: `classes/ActionScheduler_ScheduleDeserializer.php` and every place a blob leaves the database
  (`ActionScheduler_DBStore::make_action_from_db_record()`, `ActionScheduler_wpPostStore::make_action_from_post()`,
  `ActionScheduler_Abstract_ListTable::set_items()` with `maybe_unserialize()`). The allowlist is the boundary; a
  bypass needs a gadget in installed code and a way for the attacker to write the blob.
- SQL built from query arguments: `ActionScheduler_DBStore::get_query_actions_sql()`, `query_actions()`,
  `bulk_cancel_actions()`, `save_action_to_db()` and its unique-key insert, the search and filters in
  `ActionScheduler_ListTable::prepare_items()` and `ActionScheduler_Abstract_ListTable`, the legacy store's
  `WP_Query` arguments, and the migration batch fetcher.
- Authorization on the admin screen: the capability WooCommerce's status page grants, the nonces on row and bulk
  actions, and the fact that `run` executes an action inside the viewer's request. A shop manager running, cancelling
  or deleting actions is by design; creating or editing one through this library's screens is not possible and must
  stay so.
- Output escaping of stored data on the admin screen and in notices: hook names, arguments, group slugs, log
  messages (which include exception messages thrown by callbacks) and schedule descriptions. Any of these can carry
  shopper-supplied strings through a host plugin.
- The async runner: the nonce check, the cookies forwarded in `WP_Async_Request::get_post_args()`, and the filters
  that let a site change the loopback URL and arguments (`as_async_request_queue_runner_query_url`,
  `as_async_request_queue_runner_post_args`).
- Locks and claims: `classes/ActionScheduler_OptionLock.php`, the `_claims` table, and the unique-action insert
  (`ActionScheduler_DBStore::save_unique_action()`). A double execution (a WooCommerce webhook delivered twice, a
  renewal charged twice) is a finding only with a demonstrated outcome.
- The cron expression parser in `lib/cron-expression/` (vendored and modified in this repository), which parses the
  expression a host plugin passes to `as_schedule_cron_action()`, and `classes/schedules/ActionScheduler_CronSchedule.php`.

Out of scope: `vendor/` (Composer packages), `tests/`, `docs/` (the actionscheduler.org site), `.github/`,
`phpcs.xml`, `AGENTS.md`, `composer.*` and `package*.json`. `deprecated/` ships and is in scope, but prefer fixes in
the live classes it delegates to. WordPress core, WP-Cron's own design (unauthenticated triggering, loopback
requests) and the callbacks host plugins attach to the hooks this library fires belong to those projects; report
them here only when this library's handling creates the bug. The copy of this library bundled inside WooCommerce in
this image is an older release that the version registry leaves inert; report and patch against `/src`.

## How to exercise it

- Run `wp-start` first. It starts MariaDB and Apache. The site is at `http://127.0.0.1/`, with pretty permalinks,
  WooCommerce and Storefront, one simple product, and the shop, cart, checkout and My Account pages installed.
  The image also seeds three sample actions in the `oss-scanner` group at build time. They may have run by the time
  scanning starts; the sample hook has no callback, so attempted runs are marked failed. For fresh pending rows,
  run `wp --path=/var/www/html action-scheduler action generate oss_scanner_sample_hook tomorrow --count=3 --interval=3600 --args='{"order_id":1,"note":"sample"}' --group=oss-scanner`.
  `wp-stop` stops both services.
- PHP errors, warnings and deprecations from Apache and the CLI go to `/var/log/php-error.log`; Apache's own logs are
  under `/var/log/apache2/`.
- Users (password equals username): `admin` (administrator), `shopmanager` (shop_manager), `customer` (customer),
  `subscriber` (subscriber). Registration at checkout and on My Account is enabled. Guest checkout is enabled.
- The admin screens: `/wp-admin/tools.php?page=action-scheduler` (administrator) and
  `/wp-admin/admin.php?page=wc-status&tab=action-scheduler` (shop manager or administrator). Row actions are links
  and bulk delete is a form on that page; capture a request as the role you claim and replay it with `curl`.
- `wp --path=/var/www/html action-scheduler action create <hook> <start> --args='{"k":"v"}' --group=<group>` creates
  an action; `generate` makes several; `list`, `get`, `run`, `cancel` and `delete` manage them; `wp action-scheduler
  run` processes the queue; `wp action-scheduler status` shows the store, logger and runner in use. `wp
  --path=/var/www/html eval '...'` runs PHP in a loaded WordPress, so `as_schedule_single_action()` and the rest of
  the API can be called directly, and `wp cron event run action_scheduler_run_queue` fires the WP-Cron runner.
- The plugin is at `/var/www/html/wp-content/plugins/action-scheduler`, a symlink to `/src`, so a patch to `/src`
  takes effect on the next request. There is nothing to build.
- The async runner can be exercised end to end offline: load a wp-admin page as an administrator so the `shutdown`
  hook dispatches the loopback request (needs due pending actions and the 60-second lock free), or compute a nonce
  with `wp eval 'echo wp_create_nonce( "as_async_request_queue_runner" );'` (no `--user`) and POST to
  `/wp-admin/admin-ajax.php?action=as_async_request_queue_runner&nonce=...` without cookies. A nonce made in WP-CLI
  has no session token, so it fails on a request that carries a logged-in user's cookies; the runner also answers
  logged-out requests.
- PHPUnit: `cd /src && vendor/bin/phpunit -c tests/phpunit.xml.dist --filter <TestName>`, with MariaDB running
  (`composer run test` is the same; `WP_MULTISITE=1` runs the multisite variant as CI does). Tests use the `as_tests`
  database and the WordPress copy in `/tmp/wordpress`. PHPUnit reports about 1,950 tests (data providers, and the base
  test case runs every test twice, in the Pacific/Fiji and Pacific/Tahiti timezones) and finishes in seconds. The
  image sets `WP_PLUGIN_DIR=/tmp/plugins` for `tests/bootstrap.php` and links `/src` into it as `/tmp/plugins/src`,
  so the suite sees the checkout inside a plugins directory as it does in CI; every test passes offline. Look
  in `tests/phpunit/jobstore/`, `tests/phpunit/runner/` and `tests/phpunit/helpers/` (which includes a
  deserialization gadget fixture) for how the maintainers drive the stores and the runner without WP-Cron.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate administrator or host plugin would: create users at their real roles, schedule actions
through the public API or WP-CLI with realistic hooks and arguments, set real options. Drive the attack as the
claimed actor, through the normal interface. Do not mint a nonce as an administrator for an anonymous request, edit
rows in the `actionscheduler_*` tables directly and then call the result a vulnerability, give the attacker a
capability they are supposed to gain, or loosen the deserializer's allowlist through its filters. Reading the
database to observe the outcome is fine. For XSS, show the payload executes in a browser context in the victim's
role, not only that it appears in the HTML.

## How you rate severity

Two questions settle the band, in this order: (1) can the attacker act without a merchant-created account
(anonymous, customer or subscriber is the high band; shop manager is the low band; administrator and the shell are
not rated), and (2) is the chain real and unconditional with this library active in a default configuration,
standalone or inside WooCommerce.

### Anonymous visitor, or a self-registered customer or subscriber

| Finding | Severity |
|---|---|
| Proven RCE, unchained, no preconditions, including a deserialization gadget reached through a blob the attacker wrote by a path this library exposes | Critical |
| Creating, altering or re-pointing a stored action (hook, arguments, group, schedule) so that the runner later executes something the host site did not schedule | Critical |
| SQL injection, unchained, through the query arguments a host plugin passes from shopper input, or through the async runner | High |
| Stored XSS reaching a shop manager or administrator through the admin screen, its notices or the WooCommerce status report, from hook names, arguments, groups or log messages a shopper can influence through a host plugin in this image | High |
| Bypassing the async runner's nonce so that the queue runs in another user's context or with attacker-chosen data | High |
| Reading another user's stored arguments or logs through a path that is not the admin screen | Medium |
| Anything else with real security impact | Medium |
| Blind issues, missing rate limiting, timing of the loopback request | Low |
| Making the queue run earlier, later or more often than WP-Cron would, without changing what runs; triggering `wp-cron.php` | Informative |
| No real security impact | Informative |

### Shop manager

| Finding | Severity |
|---|---|
| Creating or editing an action through this library's screens, or reaching code execution, file writes or `install_plugins` / `edit_plugins` / `unfiltered_html` | Medium to High |
| SQL injection or stored XSS reaching an administrator through the list table's parameters | Low |
| Running, cancelling or deleting stored actions, or reading every argument and log, from WooCommerce's status page | Not a finding: WooCommerce opens that page to this role |
| Most other findings | Low |

### Rules by class

- **Validity comes before severity.** Name the actor, what they can already do through the normal interface, and
  the specific thing they gain. No gain means no finding, however real the code defect.
- **Stored rows:** the hook and arguments of a row are chosen by the code that scheduled it. A finding that starts
  from a row the attacker could not have written is a finding against the host plugin that wrote it, unless this
  library mishandles what it stored (deserialization, escaping, SQL).
- **Running the queue** is not a privilege. WP-Cron and the loopback request exist so that anyone's page load runs
  due actions. Report the nonce only if bypassing it changes who runs the queue or what runs.
- **Deserialization:** needs a real gadget in installed code and a path that writes the blob; name both. Phar
  deserialization through file-stat functions is dead on PHP 8+. Loosening
  `action_scheduler_enforce_schedule_allowed_classes` or `action_scheduler_allowed_nested_schedule_classes` is a site
  decision, not a vulnerability.
- **CSRF:** needs realistic cross-origin exploitation under default `SameSite` cookie behaviour. A missing nonce on
  an action only an administrator can reach, where the attacker gains nothing they could not get by asking, is not a
  vulnerability.
- **Race conditions** (double claim, double execution, duplicate unique action) count only with a demonstrated
  outcome in a host plugin's terms.
- **Context of execution:** callbacks run as whoever triggered the runner (an administrator's cookies in the
  loopback request, no user under WP-Cron, the shell under WP-CLI). A host callback that trusts the current user is
  that plugin's bug; this library's bug would be letting an attacker choose that context.
- **Resource exhaustion** (huge queues, slow queries on large tables, the memory and time limits raised in
  `classes/ActionScheduler_Compatibility.php`) is performance, not security, unless an anonymous request triggers it
  without bound.

## How reports and patches should look

- One-sentence claim: *<actor> can <action> against <target>, which they otherwise could not.*
- An explicit actor / already holds / gains line, the least privileged role that triggers the issue, whether it
  needs WooCommerce active, the legacy post store, a migration in progress or a non-default filter, and the severity
  from the tables above.
- Name the affected file and function, and give a self-contained reproducer: WP-CLI setup (`wp action-scheduler
  action create ...`, `wp user create ...`) plus `curl`, or a PHPUnit test under `tests/phpunit/` extending
  `ActionScheduler_UnitTestCase`.
- Write patches as `git diff` against `/src`. Follow the WordPress coding standards (`vendor/bin/phpcs` with the
  repository's `phpcs.xml`) and the compatibility rules in `AGENTS.md`: the code must run on PHP 7.2, and every
  `as_*()` function, hook, filter, base class and stored data format is a public contract consumed by plugins nobody
  can enumerate, so deprecate rather than rename, add rather than change, and apply the same fix to the custom-table
  and legacy post stores. Use core APIs (`esc_html()`, `esc_attr()`, `$wpdb->prepare()`, `current_user_can()`,
  `wp_verify_nonce()`, `check_admin_referer()`). Add a line to the open block at the top of `changelog.txt` when the
  fix is ready for a pull request.

## Anything to leave alone

- Anything an administrator or a shell user can already do, including scheduling arbitrary hooks with WP-CLI and
  running PHP.
- Anyone being able to trigger `wp-cron.php`, or the queue running inside a visitor's request, which is how
  WordPress cron works.
- A shop manager seeing, running, cancelling or deleting actions on WooCommerce's status page.
- Findings that need `WP_DEBUG` / `display_errors` on, a plugin not installed in this image, a server
  misconfiguration, or an already-compromised host.
- The callbacks host plugins attach to scheduled hooks, and what WooCommerce does with the arguments it scheduled.
- Hook, group and argument values being visible to the roles that can open the admin screen.
- Version disclosure, username enumeration, missing security headers, missing rate limiting, and clickjacking
  without security impact.
- Self-XSS, CSRF on login or logout, brute force, denial of service, phishing, social engineering.
- Vulnerabilities in Composer `require-dev` packages (PHPUnit, WP-CLI, the sniffs), unless practically exploitable
  remotely.
- Theoretical issues with no demonstrated, significant security impact.
