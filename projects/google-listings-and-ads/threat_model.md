# Threat model: Google for WooCommerce

## What this project does and where untrusted input enters

Google for WooCommerce (`google-listings-and-ads`, the wordpress.org slug and the former name, Google Listings &
Ads) is a WordPress plugin that lists a WooCommerce store's products on Google: it syncs products, prices, shipping
rates and times, promotions and attribute mappings to Google Merchant Center, creates and reports on Google Ads
campaigns, verifies the site with Google, prints the Google tag with conversion tracking on the storefront, and
builds a conversion report for YouTube Shopping. This enrollment covers the plugin code under `src/`, `views/`,
`js/src/` and `google-listings-and-ads.php` on the `develop` branch.

The plugin never holds a Google credential. Every call to Google goes through the WooCommerce Connect Server
(`https://api.woocommerce.com`, `src/PluginHelper.php`), a private Automattic service that stores the merchant's
Google OAuth grant and proxies Merchant Center, Google Ads and Site Verification. The plugin authenticates to it
with the site's Jetpack blog token: `generate_auth_header()` in
`src/Internal/DependencyManagement/GoogleServiceProvider.php` signs each Guzzle request with an `X_JP_Auth` header,
and `src/API/Google/JetpackAuthCircuitBreaker.php` pauses syncing after a rejection. The Jetpack Connection library
that owns the token is not in this repository; WooCommerce bundles it. The Connect Server, Google and the Jetpack
library are out of scope, but everything they return to the plugin is untrusted input and the plugin's handling of
it is in scope.

Untrusted input enters through:

- The merchant-facing REST API under `/wp-json/wc/gla/*` (about sixty controllers in `src/API/Site/Controllers/`,
  registered by `src/API/Site/RESTControllers.php`): connect and disconnect routes for Jetpack, Google, Merchant
  Center, Ads and YouTube, plus settings, shipping, attribute mapping, product feed and visibility, issues,
  reports, campaigns, assets, budgets, incentives, notifications and onboarding. Every route's
  `permission_callback` is `can_manage()` (`src/API/PermissionsTrait.php`, through
  `src/API/Site/Controllers/BaseController.php`), which is `current_user_can( 'manage_woocommerce' )`, with one
  exception: `GET /wc/gla/ads/assets/image-proxy` (`src/API/Site/Controllers/Ads/AssetImageProxyController.php`)
  also accepts any logged-in user carrying a valid `wp_rest` nonce and fetches the URL it is given server-side
  (host allowlist `tpc.googlesyndication.com`, image content types, 10 MB; the allowlist is checked once, before
  `wp_remote_get` follows up to five redirects).
- Responses from the Connect Server and Google (`src/API/Google/`: `Merchant.php`, `Ads.php`, `MerchantReport.php`,
  `Connection.php`, `SiteVerification.php`, `Mapi/`, `Query/`): product statuses and issues, price benchmarks,
  campaigns, assets, account data, incentive credits. The plugin stores them in its tables (`src/DB/Table/`:
  `MerchantIssueTable.php`, `MerchantPriceBenchmarksTable.php`, `BudgetRecommendationTable.php`), in product meta
  (`src/Product/ProductMetaHandler.php`, keys prefixed `_wc_gla`) and in options (`src/Options/Options.php`, keys
  prefixed `gla_`), and renders them in wp-admin.
- The connection returns. `GET /wc/gla/google/connect` asks the Connect Server for an authorization URL carrying a
  `returnUrl` (`src/API/Google/Connection.php`, `src/API/Site/Controllers/Google/AccountController.php`, with `next`
  and referrer parameters from `src/API/Site/Controllers/ReferrerParamsTrait.php`), and Google sends the browser
  back to `wp-admin/admin.php?page=wc-admin&path=/google/...`; no token reaches the plugin.
  `src/API/Site/Controllers/Jetpack/AccountController.php` drives WooCommerce's Jetpack Connection `Manager`. No
  route in this plugin accepts an inbound call from Google or the Connect Server: there is no webhook, and the
  Jetpack-signed endpoints (`jetpack/v4/*`, XML-RPC) belong to the Jetpack Connection package inside WooCommerce.
- The storefront. `src/Google/GlobalSiteTag.php` prints the Google tag on every page once an Ads conversion ID is
  set, `view_item` and `page_view` events with product ids and names, and on the order-received page a `purchase`
  event with the order id, currency, tax, billing postcode, line items and, with enhanced conversions on, the
  customer's hashed contact data; `src/Google/ConsentGatedScriptTrait.php` gates loading on the WP Consent API.
  `src/Google/SiteVerificationMeta.php` prints the verification meta tag from the `gla_site_verification` option.
- Product, coupon and shipping data the plugin reads from WooCommerce and sends to Google (`src/Product/`,
  `src/Coupon/`, `src/Shipping/`), shaped by the attribute mapping rules (`src/Product/AttributeMapping/`,
  `src/DB/Table/AttributeMappingRulesTable.php`). The product editor tab and variation fields
  (`src/Admin/Product/Attributes/AttributesTab.php`, `VariationsAttributes.php`) read `$_POST` on
  `woocommerce_update_product`; the channel visibility meta boxes (`src/Admin/MetaBox/ChannelVisibilityMetaBox.php`,
  `CouponChannelVisibilityMetaBox.php`) and the coupon bulk edit (`src/Admin/BulkEdit/CouponBulkEdit.php`, on
  `save_post`) do the same for their fields.
- Background jobs: Action Scheduler jobs in the `gla` group (`src/Jobs/`: `UpdateAllProducts.php`,
  `UpdateProducts.php`, `DeleteProducts.php`, `UpdateCoupon.php`, `UpdateShippingSettings.php`,
  `UpdateMerchantProductStatuses.php` and others), started by `src/Jobs/JobInitializer.php` and the syncer hooks
  (`src/Product/SyncerHooks.php`, `src/Coupon/SyncerHooks.php`, `src/Shipping/SyncerHooks.php`), with arguments
  stored in the database (JSON) and run by WP-Cron or Action Scheduler's async runner; and the WP-CLI command
  `wc g4wc gtin-migration start` (`src/Utility/WPCLIMigrationGTIN.php`).
- The conversion report (`src/Jobs/CreateMerchantReportedConversionReport.php`,
  `src/Admin/Exports/Writer/CsvExportWriter.php`): a job writes order rows to a CSV under
  `wp-content/uploads/gla-exports/`, and the writer returns the file's public URL.
- A hidden Connection Test page (`src/ConnectionTest.php`, `admin.php?page=connection-test-admin-page`,
  `manage_woocommerce`, nonce-protected forms) that issues raw Connect Server and Merchant API calls from `$_GET`;
  it is registered on every site, so shop managers can reach it.
- The wp-admin screens: the React app in `js/src/` (built to `js/build/`) under WooCommerce > Marketing, the
  WooCommerce Admin notes (`src/Notes/`), the notifications system (`src/Admin/NotificationsSystem.php`,
  `src/Notification/`) and the task list (`src/TaskList/`), reached by shop managers and administrators.

### Actors

| Actor | How they get there | Trust |
|-------|--------------------|-------|
| Anonymous shopper | none needed; sees the storefront with the Google tag, the order-received page with an order key, and anything under `wp-content/uploads/` | Untrusted. High band |
| Customer | self-registered at checkout or My Account (merchant-enabled; enabled in this image); any logged-in user holds a `wp_rest` nonce | Untrusted. High band |
| Shop manager | admin-created; holds `manage_woocommerce`, the plugin's only capability check, so they connect, disconnect, configure, sync and spend by design | Partly trusted. Low band |
| Administrator | admin-created | Fully trusted, including code execution. Not rated, except the secrets rules below |
| Connect Server / Google (responses, authorization return) | TLS to `api.woocommerce.com`; Jetpack-signed requests from the site | Trusted party, untrusted payload. The plugin's validation and escaping of what it stores and renders is in scope; a finding that needs them to be malicious is not |
| WP-Cron / Action Scheduler runner | the site's own scheduled jobs | Same trust as the stored job arguments; a lower-privileged user who can shape them is the finding |

## Components that matter most / least

Most important:

- Authorization on `/wp-json/wc/gla/*`: a route that forwards a request to the Connect Server with the site's
  Jetpack token on behalf of a lower-privileged caller, or lets such a caller change what the store publishes to
  Google. Everything the Connect Server does for the site (edit listings, create or edit campaigns, spend the
  merchant's Ads budget, disconnect accounts) is reachable only through that token.
- Secrets: the Jetpack blog token WooCommerce holds and `generate_auth_header()` reads; Merchant Center and Ads
  account ids and the site verification token in options; anything written to WooCommerce logs through
  `src/Logging/DebugLogger.php`. Google OAuth tokens never exist on the site.
- Server-side fetches: the image proxy in `src/API/Site/Controllers/Ads/AssetImageProxyController.php` is the one
  place a caller supplies a URL the server fetches; `src/Utility/ImageUtility.php` and
  `src/Product/ProductImageSizeAudit.php` read product images.
- Storefront output and data leaving the site: the gtag snippets in `src/Google/GlobalSiteTag.php` (product
  names, order fields and options pass through `esc_js()`), the `purchase` event and enhanced conversions on the
  order-received page, the verification meta (`wp_kses()`), the consent gating, and the conversion report CSV
  under `wp-content/uploads/gla-exports/` (who can predict its name, who can read it).
- What is published to Google: channel visibility, attribute mapping, shipping, target audience, product data,
  promotions. A user below shop manager changing any of it, through the meta boxes, bulk edit, `save_post` hooks
  or a REST route, is the finding; a shop manager doing it is the product.
- Data stored from Google and rendered in wp-admin (`src/DB/Table/MerchantIssueTable.php`, product statuses,
  benchmarks, campaign and asset text) and the plugin's own SQL (`src/DB/Query.php`,
  `src/DB/ProductFeedQueryHelper.php`, `src/DB/ProductMetaQueryHelper.php`, with filters and ordering taken from
  REST parameters). The React app has no `dangerouslySetInnerHTML`; look at how server strings reach `views/` and
  the WooCommerce Admin notes.

Out of scope: `vendor/` (Composer packages, including the Google client and Guzzle the build prefixes into the
plugin's namespace), `node_modules/`, `js/build/` (built output; patch `js/src/` instead), `languages/`, `tests/`,
`bin/` (build tooling), `docs/`, `data/` (static budget recommendations), `wordpress_org_assets/`, `.github/`, the
WooCommerce Connect Server, Google's APIs and consoles, gtag.js in the browser, and the Jetpack Connection library
and WordPress.com side of the connection (bundled by WooCommerce; findings there belong to Jetpack's program).
WooCommerce core and WordPress core findings belong to their own enrollments; report them only if this plugin's use
of them creates the bug. `src/Integration/` (WPML, Yoast SEO, Brands, Product Bundles, Pre-Orders) only runs when
those plugins are installed; they are not in this image.

## How to exercise it

- Run `wp-start` first. It starts MariaDB and Apache. The store is at `http://127.0.0.1/`, with pretty permalinks,
  Storefront, one simple product, and the checkout, cart, shop and My Account pages installed. `wp-stop` stops both.
- PHP errors, warnings and deprecations from Apache and the CLI go to `/var/log/php-error.log`; Apache's own logs are
  under `/var/log/apache2/`; the plugin's debug logging goes to WooCommerce's logs in `wp-content/uploads/wc-logs/`.
- Users: `admin` / `admin` (administrator), `shopmanager` / `shopmanager` (shop_manager), `customer` / `customer`
  (customer). Registration at checkout and on My Account is enabled. Guest checkout is enabled.
- `wp --path=/var/www/html ...` (WP-CLI) sets up content, options, users and orders. `wp --path=/var/www/html wc
  ...` drives the WooCommerce REST API. `wp --path=/var/www/html eval '...'` runs PHP in a loaded WordPress. The
  plugin's REST routes answer to `curl` with an application password or a cookie plus `X-WP-Nonce`.
- The plugin is at `/var/www/html/wp-content/plugins/google-listings-and-ads`, a symlink to `/src`, so a patch to
  `/src` takes effect on the next request. Admin app changes need `NODE_ENV=production npx wp-scripts build`
  (offline: `node_modules` are already installed).
- The site has no Jetpack connection and the scan runs without network. `GET /wc/gla/jetpack/connected` reports
  the site as not connected, and every route that reaches the Connect Server fails through
  `src/API/Site/Controllers/ResponseFromExceptionTrait.php`. To drive the flows behind the connection, set the
  options onboarding would set (`gla_jetpack_connected`, `gla_google_connected`, `gla_merchant_id`, `gla_ads_id`,
  `gla_mc_setup_completed_at`, `gla_ads_setup_completed_at`; the list is `src/Options/OptionsInterface.php`), reason
  about the request the plugin would send and the response it would accept, and mock the Google services in a
  PHPUnit test: `tests/Framework/ContainerAwareUnitTest.php` and `tests/Framework/RESTControllerUnitTest.php` show
  how the suite swaps container services (`Merchant`, `Ads`, `Middleware`, `Connection`, the Guzzle client) for
  mocks, and `tests/mocks/mocking.md` documents the `woocommerce_gla_prepared_response_{route}` filter with sample
  responses. The storefront tag needs only the `gla_ads_conversion_action` option.
- PHPUnit: `cd /src && vendor/bin/phpunit --configuration phpunit.xml.dist --filter <TestName>`, with MariaDB
  running. The `unit` suite (`tests/Unit/`, the default) uses the `gla_tests` database, the WordPress copy in
  `/tmp/wordpress`, the test library in `/tmp/wordpress-tests-lib` and the WooCommerce source checkout symlinked
  at `/tmp/wordpress/wp-content/plugins/woocommerce`, whose test helpers `tests/bootstrap.php` loads. The
  `integration` suite directory is empty. JS unit tests: `npm run test:js` (Jest), offline.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate administrator would: create users at their real roles, set real options, add
products and orders. Drive the attack as the claimed actor, through the normal interface. Do not mint a nonce as an
administrator, grant `manage_woocommerce` to the attacker, write a Google response into the database by hand
without showing which route or job stores it, or call the Connect Server client with a token the attacker does not
hold. Reading the database to observe the outcome is fine. For XSS, show the payload executes in a browser context
in the victim's role, not only that it appears in the HTML.

## How you rate severity

Two questions settle the band, in this order: (1) can the attacker act without a merchant-created account
(anonymous or self-registered customer is the high band; shop manager is the low band; administrator is not
rated), and (2) is the chain real and unconditional in a default configuration with the plugin active and, where
the finding needs it, a connected Merchant Center or Ads account, which is the normal state of a live store.

### Anonymous shopper, or a self-registered customer

| Finding | Severity |
|---|---|
| Acting on the Connect Server or Google with the site's Jetpack token: editing listings, creating or changing campaigns or budgets, spending the merchant's Ads funds, connecting or disconnecting accounts | Critical |
| Disclosure of the Jetpack blog token or secret, or of Connect Server credentials | Critical |
| Proven RCE, unchained, no preconditions | Critical |
| Changing what the store publishes to Google (product data, visibility, prices, promotions, shipping, target audience, mapping rules) or the Google tag the storefront prints | High |
| XSS or SQL injection, unchained, reaching a shop manager or administrator session | High |
| Reading other customers' orders, emails, addresses or order totals through a report, an export file, an order key or a REST route | High |
| Anything else with real security impact (IDOR on non-public data, SSRF with a demonstrated read of a non-public resource) | Medium |
| Blind SSRF, open redirect without a token leak, missing rate limiting | Low |
| No real security impact | Informative |

### Shop manager

| Finding | Severity |
|---|---|
| Reaching the Jetpack token, code execution, file writes, or `install_plugins` / `edit_plugins` / `unfiltered_html` | Medium to High |
| Stored XSS, SQL injection, IDOR | Low |
| Most other findings | Low |

### Rules by class

- **Validity comes before severity.** Name the actor, what they can already do through the normal interface, and
  the specific thing they gain. No gain means no finding, however real the code defect. A shop manager
  connecting, disconnecting, syncing, exporting or spending on Ads is the product working.
- **Connect Server and Google payloads:** a finding that needs the Connect Server or Google to be malicious is out
  of scope; a finding where the plugin stores or renders a legitimately returned value unsafely is in scope and
  must name the route or job that stores it and the screen that renders it.
- **Jetpack Connection:** registration, authorization, token storage, signed requests, `jetpack/v4/*` and XML-RPC
  live in the Jetpack Connection package WooCommerce bundles. Report findings there to Jetpack through Automattic's
  program, not against this plugin, unless this plugin's use of the library creates the bug.
- **Consent and tracking:** the Google tag loading or firing before consent is a privacy or compliance matter, not
  a security finding, unless it sends data to a party the merchant did not configure.
- **CSRF:** needs realistic cross-origin exploitation under default `SameSite` cookie behaviour. A missing nonce on
  an action only an administrator can reach, where the attacker gains nothing they could not get by asking, is not
  a vulnerability.
- **Deserialization:** job arguments and options are JSON; a finding needs a real gadget in installed code; name it.
- **Race conditions** (double sync, duplicate jobs) count only with a demonstrated outcome.
- **Logging:** the Jetpack token or Connect Server credentials written to `wc-logs` or the database is High
  regardless of actor; customer PII in logs is Medium.

## How reports and patches should look

- One-sentence claim: *<actor> can <action> against <target>, which they otherwise could not.*
- An explicit actor / already holds / gains line, the least privileged role that triggers the issue, whether it
  needs a connected account, a non-default setting or an installed integration, and the severity from the tables
  above.
- Name the affected file and function, and give a self-contained reproducer: WP-CLI setup plus `curl` against
  `/wp-json/wc/gla/...` or the storefront, or a PHPUnit test under `tests/Unit/` extending
  `tests/Framework/RESTControllerUnitTest.php` that mocks the Google services.
- Write patches as `git diff` against `/src`. Follow WordPress coding standards (`vendor/bin/phpcs` checks them)
  and use core APIs (`esc_html()`, `esc_attr()`, `esc_js()`, `wp_kses()`, `$wpdb->prepare()`, `current_user_can()`,
  `wp_verify_nonce()`, `rest_ensure_response()`). For a REST route, fix the `permission_callback` in the
  controller's `register_routes()`, not the callback. Admin app fixes go in `js/src/` with a rebuild.

## Anything to leave alone

- Anything an administrator can already do, including running PHP, installing plugins and reading the stored
  options.
- Findings that need `WP_DEBUG` / `display_errors` on, a plugin not installed in this image, a server
  misconfiguration, or an already-compromised host.
- The Connection Test page being reachable by shop managers: it needs `manage_woocommerce` and nonces; a finding
  must show something a shop manager cannot already do through the normal UI.
- Behaviour of the WooCommerce Connect Server, Google Merchant Center, Google Ads, Site Verification and gtag.js,
  and findings that require them to be malicious.
- The site verification meta tag and the Google tag being visible on the storefront (they are meant to be).
- Version disclosure, product or order enumeration without data access, username enumeration, missing security
  headers, missing rate limiting on checkout or login, and clickjacking without security impact.
- Self-XSS, CSRF on login or logout, brute force, denial of service, phishing, social engineering.
- Vulnerabilities in Composer or npm `devDependencies`, unless practically exploitable remotely.
- Theoretical issues with no demonstrated, significant security impact.
