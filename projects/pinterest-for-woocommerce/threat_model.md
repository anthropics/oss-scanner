# Threat model: Pinterest for WooCommerce

## What this project does and where untrusted input enters

Pinterest for WooCommerce (`pinterest-for-woocommerce`) is a WordPress plugin that connects a WooCommerce store to
the merchant's Pinterest business account: it generates a product catalog feed that Pinterest fetches, prints the
Pinterest Tag on the storefront and sends Conversions API events for visits, searches, add-to-cart and checkout,
adds Rich Pins Open Graph tags and a Save-to-Pinterest button, verifies the store's domain with Pinterest, and
manages ad credits and billing status, all from a React app inside WooCommerce admin. This enrollment covers the
plugin code under `src/`, `includes/`, `views/`, `assets/source/`, `class-pinterest-for-woocommerce.php`,
`pinterest-for-woocommerce.php` and `uninstall.php` on the `trunk` branch.

The plugin has two external parties and no Jetpack connection:

- The Woo Connect server (`https://api.woocommerce.com/`, `PINTEREST_FOR_WOOCOMMERCE_WOO_CONNECT_URL` in
  `class-pinterest-for-woocommerce.php`) holds the Pinterest app credentials. The merchant is sent to
  `integrations/connect/pinterest-v5` with a `state` (a nonce stored in a transient by `get_middleware_url()`),
  authorizes on Pinterest, and comes back to `/wp-json/pinterest/v1/oauth/callback` carrying the tokens and account
  info. Token renewal POSTs the refresh token to `integrations/renew/pinterest-v5` (`src/RefreshToken.php`).
- Pinterest's API (`https://api.pinterest.com/v5`, `src/API/APIV5.php` over `src/API/Base.php`) is called directly
  with the merchant's bearer token for everything else: feeds and their processing results, advertisers, tags,
  businesses, account data, domain verification, Conversions API events, ad credits.

Both are out of scope, but every byte they send to the plugin is untrusted input and the plugin's handling of it is
in scope. Tokens are stored encrypted (`src/Crypto.php`, defuse/php-encryption with a key derived from `AUTH_KEY`)
in the `pinterest_for_woocommerce_data` option; settings and account data in `pinterest_for_woocommerce`.

Untrusted input enters through:

- The OAuth return `GET /wp-json/pinterest/v1/oauth/callback` (`src/API/Auth.php`). Its only authentication is the
  `state` parameter matching the transient set when the merchant started the flow; the base64 `token_data` and
  `info` parameters are then decoded and saved as the connection (access and refresh tokens, advertiser id, tag
  id, feature flags). Treat it as the boundary: what can a third party who reaches it while a state is live, or
  with no state at all, make the store do?
- The public analytics beacon `admin-ajax.php?action=pinterest_for_woocommerce_page_visit`
  (`src/Tracking/PageVisit.php`), reachable by anyone, without a nonce by design. It accepts `event_id` and
  `event_source_url` and forwards a Conversions API event with the visitor's IP and user agent.
- Storefront state read by the trackers (`src/Tracking.php`, `src/Tracking/Conversions.php`,
  `src/Tracking/Tag.php`, `src/Tracking/Data/`): the `epik` click id from the query string, the search query, the
  product or category being viewed, cart changes, and the order on the thank-you page. The Tag tracker prints
  inline scripts in `wp_footer` built from settings and this data; with enhanced match on, it also prints the
  hashed email and external id of the current customer.
- The domain verification page served from `parse_request` (`verification_request()` in
  `class-pinterest-for-woocommerce.php`) and the `p:domain_verify` meta tag printed in `wp_head`.
- Rich Pins Open Graph tags and the Save button (`src/RichPins.php`, `src/SaveToPinterest.php`), which render
  product and post data into attributes on every product and post page.
- The merchant-facing REST API `/wp-json/pinterest/v1/*` (`src/API/`: `tagowners`, `tagowner`,
  `auth_disconnect`, `businesses`, `domain_verification`, `feed_state`, `feed_issues`, `tags`, `health`,
  `settings`, `sync_settings`, `user_interaction`), every route guarded by `manage_woocommerce` in
  `src/API/VendorAPI.php` except the OAuth return above. Also the Google category search
  (`wp_ajax_woocommerce_json_search_google_category`, `src/Product/GoogleCategorySearch.php`, `edit_products`
  plus the WooCommerce `search-products` nonce), the Pinterest tab on the product edit screen
  (`src/Admin/Product/Attributes/AttributesTab.php`, `edit_post` plus the `woocommerce_meta_nonce`), and the
  redirect into the connect flow (`maybe_redirect_to_middleware()` in
  `includes/admin/class-pinterest-for-woocommerce-admin.php`, `manage_woocommerce` plus a nonce).
- Responses from Pinterest's API: feeds and feed processing results and item issues (`src/Feeds.php`,
  `src/FeedStatusService.php`, `src/API/FeedIssues.php`), advertisers, tags, businesses, account data, ad
  credits and billing (`src/AdCredits.php`, `src/Billing.php`), all stored in options or transients and rendered
  in the admin app, and the recommendations JSON fetched from woocommerce.com in `src/AdCredits.php`.
- Action Scheduler jobs with arguments stored in the database: feed generation (`src/FeedGenerator.php`, chained
  batches through the vendored `woocommerce/action-scheduler-job-framework`), feed registration
  (`src/FeedRegistration.php`), product sync (`src/ProductSync.php`), the heartbeat (`src/Heartbeat.php`), token
  refresh, commerce integration (`src/CommerceIntegration.php`).
- The generated feed: XML written to `wp-content/uploads/pinterest-for-woocommerce-<id>.xml`
  (`src/LocalFeedConfigs.php`, `src/FeedFileOperations.php`, `src/ProductsXmlFeed.php`), where `<id>` is a
  six-character random string, and served by the web server at that URL for Pinterest to fetch. It carries
  titles, descriptions, prices, links and image links of published products.
- WP-CLI `wc pinterest feed` (`src/CLI/FeedCommand.php`), and the marketing channel the plugin registers with
  WooCommerce's multichannel marketing (`src/MultichannelMarketing/`).

### Actors

| Actor | How they get there | Trust |
|-------|--------------------|-------|
| Anonymous visitor | none needed: storefront, the beacon, the feed URL, the verification page | Untrusted. High band |
| Customer | self-registered at checkout or My Account (merchant-enabled; enabled in this image) | Untrusted. High band |
| Shop manager | admin-created; holds `manage_woocommerce`, which is all the plugin's REST API and settings require, not `install_plugins`, `edit_plugins` or `unfiltered_html` | Partly trusted. Low band |
| Administrator | admin-created | Fully trusted, including code execution. Not rated, except the secrets rules below |
| Woo Connect server (OAuth return, renewal response) | the `state` transient; the renewal response body | Trusted party, untrusted payload. A forged or replayed return that is accepted is High band |
| Pinterest (API responses, feed fetches) | the merchant's bearer token | Trusted party, untrusted payload |

## Components that matter most / least

Most important:

- The connection and its tokens: the `state` check in `src/API/Auth.php` (`permissions_check`, single use,
  `hash_equals`), `save_token_data()` in `class-pinterest-for-woocommerce.php`, `src/Crypto.php`,
  `src/RefreshToken.php`. Anything that lets a non-administrator read, replace or revoke the access or refresh
  token, or swap the advertiser id or tag id so that the store's conversion data and catalog flow to an
  attacker's Pinterest account.
- Authorization on the REST controllers in `src/API/`: a route that drops or weakens `permissions_check`, or that
  forwards requests to Pinterest with the merchant's token on behalf of a lower-privileged caller. `settings`
  only accepts an allow-list of keys (`src/API/Settings.php`); `auth_disconnect` resets the connection.
- Customer data leaving the site: the Conversions API payload (`src/Tracking/Conversions.php`,
  `src/Tracking/Data/`) carries the visitor's IP, user agent, hashed email, external id, order id and value; the
  consent filters (`src/WPConsentAPI.php`, `woocommerce_pinterest_disable_tracking`) gate it. Data of another
  customer, or data the visitor did not generate, reaching Pinterest is in scope.
- The feed: which products end up in the public XML (`src/FeedGenerator.php` selects published products,
  `src/ProductsXmlFeed.php` skips password-protected ones), what is written to `wp-content/uploads` and under what
  name (`src/LocalFeedConfigs.php`, `src/FeedFileOperations.php`), and the batch jobs that build it.
- Output escaping in the admin app and `views/` for data that came from Pinterest (feed issue messages, item
  issues, account and advertiser names) and in the storefront output (`src/Tracking/Tag.php` builds inline
  scripts with `wp_json_encode(..., JSON_HEX_TAG)` and `sanitize_key()`; `src/RichPins.php` and
  `src/SaveToPinterest.php` use `esc_attr()` and `wp_kses_post()`).
- The verification page and meta tag: what a visitor can make the site claim, and whether the handler in
  `verification_request()` can be reached for other paths.
- Action Scheduler arguments and hooks executed from the database (`src/FeedGenerator.php`,
  `src/CommerceIntegration.php`): deserialization, hook name injection, a job that runs with stale ids.
- Logging (`src/Logger.php`): `log_request()` deliberately logs only the URL path; tokens, Pinterest responses
  or customer data landing in WooCommerce logs is a finding regardless of actor.

In scope although vendored: `vendor/woocommerce/action-scheduler-job-framework/` and `vendor/woocommerce/grow/`,
which WooCommerce maintains (https://github.com/woocommerce/action-scheduler-job-framework,
https://github.com/woocommerce/grow) and which drive the feed batch jobs and the plugin's compatibility checks.

Out of scope: the rest of `vendor/` (Composer packages), `node_modules/`, `assets/build/`, `assets/js/` and
`assets/css/` (built output; patch `assets/source/` instead), `i18n/` (generated), `tests/`, `bin/`, `tools/`,
`docs/`, `wordpress_org_assets/`, `.github/`, Pinterest's API, the Pinterest Tag script and pixel served from
Pinterest's domains, and the Woo Connect server. WooCommerce core, Action Scheduler and WordPress core findings
belong to their own enrollments; report them only if this plugin's use of them creates the bug.

## How to exercise it

- Run `wp-start` first. It starts MariaDB and Apache. The store is at `http://127.0.0.1/`, with pretty permalinks,
  Storefront, one simple product, and the checkout, cart, shop and My Account pages installed. `wp-stop` stops both.
- PHP errors, warnings and deprecations from Apache and the CLI go to `/var/log/php-error.log`; Apache's own logs are
  under `/var/log/apache2/`.
- Users: `admin` / `admin` (administrator), `shopmanager` / `shopmanager` (shop_manager), `customer` / `customer`
  (customer). Registration at checkout and on My Account is enabled. Guest checkout is enabled.
- `wp --path=/var/www/html ...` (WP-CLI) sets up content, options, users and orders. `wp --path=/var/www/html wc
  ...` drives the WooCommerce REST API, and `wp --path=/var/www/html wc pinterest feed ...` the plugin's own
  command. `wp --path=/var/www/html eval '...'` runs PHP in a loaded WordPress.
- The plugin is at `/var/www/html/wp-content/plugins/pinterest-for-woocommerce`, a symlink to `/src`, so a patch
  to `/src` takes effect on the next request. Client changes need `npx wp-scripts build` (the React admin app,
  into `assets/build/`) or `npx gulp build` (`assets/source/js` and `assets/source/sass` into `assets/js` and
  `assets/css`); both work offline, `node_modules` are already installed.
- The store is not connected to Pinterest and the scan runs without network. The options
  `pinterest_for_woocommerce_data` and `pinterest_for_woocommerce` hold the connection; to exercise connected
  code paths, seed them the way the OAuth return would (`tests/E2e/PinterestConnectE2eTest.php` shows the shape,
  `src/API/Auth.php` the keys) and answer the plugin's HTTP calls with a `pre_http_request` filter, as the whole
  test suite does (`tests/Unit/Api/TransportContractTest.php`, `tests/E2e/LocalFeedConfigsE2eTest.php`). Calls
  through `src/API/Base.php` and `src/RefreshToken.php` fail without network; reason about the request the plugin
  would send and the response it would accept. The OAuth return, the beacon, the feed file, the verification page
  and every admin route can be exercised end to end with `curl` against `http://127.0.0.1/`.
- PHPUnit: `cd /src && vendor/bin/phpunit --configuration phpunit.xml.dist --filter <TestName>`, with MariaDB
  running (`composer test-unit` is the maintainers' alias). Tests use the `pin4wc_tests` database, the WordPress
  copy in `/tmp/wordpress` and the WooCommerce source checkout under its `wp-content/plugins/woocommerce`.
  `PINTEREST_FOR_WOOCOMMERCE_TEST_ORDER_STORAGE=hpos` runs the suite against WooCommerce's order tables instead
  of posts, as one CI row does. Look in `tests/Unit/` for how the suite mocks Pinterest responses.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate administrator would: create users at their real roles, set real options, add
products and orders, connect the store by seeding the options an OAuth return would have written. Drive the attack
as the claimed actor, through the normal interface. Do not mint a nonce or a `state` as an administrator, read the
stored token through WP-CLI and then "replay" it, give the attacker a capability they are supposed to gain, or call
the OAuth return without showing how the `state` check is passed. Reading the database to observe the outcome is
fine. For XSS, show the payload executes in a browser context in the victim's role.

## How you rate severity

Two questions settle the band, in this order: (1) can the attacker act without a merchant-created account
(anonymous or self-registered customer is the high band; shop manager is the low band; administrator is not
rated), and (2) is the chain real and unconditional in a default configuration with the store connected to
Pinterest and tracking on, which is how merchants run it.

### Anonymous visitor, or a self-registered customer

| Finding | Severity |
|---|---|
| Reading, replacing or revoking the stored access or refresh token, or swapping the advertiser id or tag id so the store's conversion data or catalog flows to another Pinterest account | Critical |
| Disclosure of secrets: tokens, the encryption key, or bulk customer data (orders, emails, addresses) through the feed, the beacon, a REST route or a log | Critical |
| Proven RCE, unchained, no preconditions | Critical |
| Accepted forged or replayed OAuth return that changes the connection, tokens or settings | High (Critical if it reaches the first row) |
| XSS or SQL injection, unchained, reaching a shop manager or administrator session, including through Pinterest API data the admin app renders | High |
| Non-public product data (draft, private, hidden or password-protected products) in the public feed, or another customer's order or email in a tracking payload | High |
| Arbitrary file write or path traversal through the feed file operations; SSRF with a demonstrated read | High |
| Making the store send attacker-chosen events or data to Pinterest under the merchant's account beyond what a visit would | Medium |
| Anything else with real security impact (IDOR on non-public data) | Medium |
| Blind SSRF, open redirect without a token leak, missing rate limiting on the beacon | Low |
| No real security impact | Informative |

### Shop manager

| Finding | Severity |
|---|---|
| Reaching the tokens or the encryption key, code execution, file writes outside the feed files, or `install_plugins` / `edit_plugins` / `unfiltered_html` | Medium to High |
| Stored XSS, SQL injection, IDOR | Low |
| Most other findings | Low |

### Rules by class

- **Validity comes before severity.** Name the actor, what they can already do through the normal interface, and
  the specific thing they gain. No gain means no finding, however real the code defect.
- **Connected state:** a finding that needs the store to be connected is rated as if it were, since connected is
  the normal state; one that needs a non-default setting (enhanced match, Rich Pins on posts, debug logging) says
  so and is one band lower.
- **Third-party payloads:** a finding that needs Pinterest or the Woo Connect server itself to be malicious is out
  of scope; a finding that needs a third party to reach the OAuth return with a forged payload is in scope and
  must show how the `state` check is passed (no state live, a predictable or leaked nonce, a replay window).
- **CSRF:** needs realistic cross-origin exploitation under default `SameSite` cookie behaviour. A missing nonce on
  an action only an administrator can reach, where the attacker gains nothing they could not get by asking, is not
  a vulnerability. The beacon has no nonce by design; a finding about it must show an outcome from the tables.
- **Deserialization:** needs a real gadget in installed code; name it.
- **Race conditions** (double feed registration, concurrent feed writes) count only with a demonstrated outcome.
- **Logging:** tokens, the encryption key or customer PII written to WooCommerce logs or the database in clear is
  High regardless of actor.
- **Consent:** tracking that fires although a consent filter disabled it is a privacy bug for the maintainers,
  not a security finding, unless data of another user leaks.

## How reports and patches should look

- One-sentence claim: *<actor> can <action> against <target>, which they otherwise could not.*
- An explicit actor / already holds / gains line, the least privileged role that triggers the issue, whether it
  needs the store to be connected, a specific setting, or the merchant to have started the connect flow, and the
  severity from the tables above.
- Name the affected file and function, and give a self-contained reproducer: WP-CLI setup plus `curl` (for the
  OAuth return, include how the `state` was obtained), or a PHPUnit test under `tests/Unit/` that answers
  Pinterest's API with `pre_http_request`.
- Write patches as `git diff` against `/src`. Follow WordPress coding standards (`vendor/bin/phpcs` checks them,
  `vendor/bin/phpstan` runs at level 8) and use core APIs (`esc_html()`, `esc_attr()`, `wp_kses()`,
  `$wpdb->prepare()`, `current_user_can()`, `wp_verify_nonce()`, `hash_equals()`). For a REST route, fix the
  `permission_callback`, not the callback. Check whether the same fix is needed in the `admin-ajax`, REST and
  WP-CLI twins of the same operation.

## Anything to leave alone

- Anything an administrator can already do, including running PHP, installing plugins and reading the stored
  tokens.
- Findings that need `WP_DEBUG` / `display_errors` on, a plugin not installed in this image, a server
  misconfiguration, or an already-compromised host.
- The Pinterest Tag script, the pixel and the Save button widget as served from Pinterest's domains, Pinterest's
  API and dashboard, and the Woo Connect server, and findings that require any of them to be malicious.
- The feed URL, the verification page and the `p:domain_verify` meta tag being public: they are meant to be
  fetched by Pinterest. The feed carrying published products' public data is by design.
- Version disclosure, product-id or order-number enumeration without data access, username enumeration, missing
  security headers, missing rate limiting on the beacon or login, and clickjacking without security impact.
- Self-XSS, CSRF on login or logout, brute force, denial of service, phishing, social engineering.
- Vulnerabilities in Composer or npm `devDependencies`, unless practically exploitable remotely.
- Theoretical issues with no demonstrated, significant security impact.
