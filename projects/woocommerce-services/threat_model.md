# Threat model: WooCommerce Tax (formerly WooCommerce Shipping & Tax)

## What this project does and where untrusted input enters

WooCommerce Tax (`woocommerce-services`, formerly WooCommerce Shipping & Tax) is a WordPress plugin that gives a
WooCommerce store automated sales tax: at cart, checkout and order time it asks TaxJar for the rates that apply to
the order's addresses and line items, writes the answer into WooCommerce's tax rate tables and applies it to the
order. The plugin never talks to TaxJar directly: every request goes through the WooCommerce Connect Server
(`api.woocommerce.com`, a private Automattic service), signed with the site's Jetpack blog token, and the server
holds the TaxJar and carrier credentials. Stores that bought a shipping label before shipping was deprecated
(grandfathered stores) keep the older shipping features: USPS and DHL label purchase, refund and printing, live
rates at checkout, carrier accounts, address normalization, saved payment methods on WooCommerce.com, and PayPal
Express request proxying. New installs are tax-only (`AGENTS.md`); `has_only_tax_functionality()` and
`should_load_shipping_features()` in `woocommerce-services.php` are the gates. This enrollment covers
`woocommerce-services.php`, `classes/`, `src/` and `client/` on the `trunk` branch. The Connect Server, TaxJar,
the carriers, PayPal and WordPress.com are out of scope, but every byte they send to the plugin is untrusted input
and the plugin's handling of it is in scope.

Untrusted input enters through:

- Tax calculation on the storefront, reachable by anyone with a cart: `classes/class-wc-connect-taxjar-integration.php`
  hooks `woocommerce_after_calculate_totals` (`maybe_calculate_totals`, `calculate_totals`) and builds a TaxJar
  request from the shopper's billing and shipping address, the line items and the shipping method, on the classic
  cart and checkout and on the Store API (`/wp-json/wc/store/v1/*`). The answer is cached in transients
  (`smartcalcs_cache_request`, keys `tj_tax_<hash>` and `tj_tax_<zip>_<state>`), written into
  `wp_woocommerce_tax_rates` (`create_or_update_tax_rate`) and applied through the `woocommerce_calc_tax`,
  `woocommerce_cart_totals_get_item_tax_rates` and `woocommerce_order_item_after_calculate_taxes` filters. The same
  class recalculates tax for orders edited in wp-admin (`calculate_backend_totals`), through the REST API and the
  mobile apps (`preserve_order_taxes_on_recalculation`), and for admin-ajax carts that a phone-order plugin opts in
  (`record_admin_ajax_user`, `is_opted_in_admin_ajax_cart`, checked against `edit_shop_orders`).
- The Store API extension and storefront notices: `src/StoreApi/Extensions/StoreNoticesExtension.php` adds a
  `notices` field to the cart response, `src/StoreNotices/StoreNoticesController.php` renders the same notices on
  the classic cart and checkout, and `classes/class-wc-connect-cart-validation.php` adds cart errors. The text comes
  from the plugin and from server error responses.
- The merchant-facing REST API under `/wp-json/wc/v1/connect/*`, one controller per route in
  `classes/class-wc-rest-connect-*-controller.php`, all extending `classes/class-wc-rest-connect-base-controller.php`.
  `check_permission` is `WC_Connect_Functions::user_can_manage_labels()` (`classes/class-wc-connect-functions.php`:
  `manage_woocommerce` or the custom `wcship_manage_labels` capability, filterable); `check_store_permission` adds
  `manage_woocommerce` for routes that act on the whole store (account settings, services, carriers, subscriptions,
  self-help, migration flag); `connect/tos` also needs `install_plugins`, `activate_plugins` and Jetpack connection
  ownership. The label routes (`connect/label/<order_id>` GET and POST, status, refund, rates, preview, print,
  packages, address normalization, carrier accounts) register only when shipping features load;
  `tests/php/test-class-wc-connect-loader-rest-routes.php` lists every route for each store type.
- Admin AJAX and `admin-post.php` actions, reached by logged-in users: the notice, terms and connection actions in
  `classes/class-wc-connect-nux.php` (`wp_ajax_wc_connect_dismiss_notice`, the nonce-checked `wcs-nux-*` query
  actions, `admin_post_register_woocommerce_services_jetpack`); `wp_ajax_wcs_download_tax_backup` in
  `classes/class-wc-connect-help-view.php` (streams a tax rate CSV from uploads by a regex-validated file name); the
  survey actions in `classes/class-wc-connect-migration-survey.php`; the store address apply and dismiss actions in
  `src/Tax/StoreAddressNotice.php`; the PayPal `reroute_requests` switch in `classes/class-wc-connect-paypal-ec.php`.
- WP-Cron: `wc_connect_fetch_service_schemas` (`classes/class-wc-connect-service-schemas-store.php`),
  `wc_connect_fetch_sift_config`, and the store address check in `src/Tax/StoreAddressVerifier.php`. Each sends
  store data to the server and stores what comes back.
- The Connect Server round trip (`classes/class-wc-connect-api-client.php`,
  `classes/class-wc-connect-api-client-live.php`). Outbound: `authorization_header` signs with the Jetpack blog
  token, `request_headers` and `request_body` attach the store address, versions, a store GUID, active services
  and, when present, the WooCommerce.com helper access token; `proxy_request` forwards TaxJar and PayPal NVP calls.
  Inbound: service schemas (checked by `classes/class-wc-connect-service-schemas-validator.php`), label purchases
  written to the order's `wc_connect_labels` meta (`classes/class-wc-connect-service-settings-store.php`), payment
  methods, carrier accounts, shipping rates (`classes/class-wc-connect-shipping-method.php::calculate_shipping`),
  label PDFs streamed to the browser, address suggestions, tax data and Sift configuration, rendered in wp-admin by
  the React app in `client/` and in tracking lines added to customer emails (`add_tracking_info_to_emails`).
- Inbound from WordPress.com: the last line of `woocommerce-services.php` initializes the Jetpack Connection
  package's `Rest_Authentication`, which lets WordPress.com authenticate signed REST requests to this site. The
  package lives in `vendor/` and is out of scope; the plugin registers no route for the server to call.
- The WordPress admin screens the plugin adds, reached by shop managers and administrators: the automated taxes
  section of WooCommerce > Settings > Tax (`add_tax_settings`, `sanitize_tax_option`), shipping settings
  (`classes/class-wc-connect-settings-pages.php`), the label meta box on orders
  (`classes/class-wc-connect-shipping-label.php::meta_box`), the WooCommerce Tax tab under WooCommerce > Status, the
  debug tools (`classes/class-wc-connect-debug-tools.php`) and the label reports tab.

### Actors

| Actor | How they get there | Trust |
|-------|--------------------|-------|
| Anonymous shopper | none needed; guest checkout is on by default | Untrusted. High band |
| Customer | self-registered at checkout or My Account (merchant-enabled; enabled in this image) | Untrusted. High band |
| Shop manager | admin-created; holds `manage_woocommerce`, not `install_plugins`, `edit_plugins` or `unfiltered_html` | Partly trusted. Low band |
| Label-only user | admin-created user granted `wcship_manage_labels` without `manage_woocommerce`; reaches the label routes, not the store-scoped ones | Partly trusted. Low band |
| Administrator | admin-created; also the Jetpack connection owner who accepts the terms | Fully trusted, including code execution. Not rated, except the secrets rules below |
| Connect Server, TaxJar, carriers, PayPal | the site's Jetpack blog token signs each request; responses are JSON over HTTPS | Trusted party, untrusted payload. A response the plugin accepts from anyone else is in scope only if the report shows how it got there |
| WordPress.com | signed REST requests through the Jetpack Connection package | Trusted party; the package is vendor code |

## Components that matter most / least

Most important:

- Tax as money: what the plugin writes into WooCommerce's tax tables and onto orders is charged to every shopper.
  A shopper-controlled field (address, postcode, item, shipping choice) that makes the plugin store a wrong rate for
  other shoppers, serve another shopper's cached answer (the transient keys in `smartcalcs_cache_request`), zero an
  order's tax, or skip a lookup the merchant turned on. `classes/class-wc-connect-taxjar-integration.php`, including
  `validate_taxjar_request`, `get_itemized_tax_rates`, `create_or_update_tax_rate`, `override_woocommerce_tax_rates`
  and the recalculation hooks.
- Label purchases and refunds charge the merchant's saved payment method at WooCommerce.com. `connect/label/<order_id>`
  POST takes the packages, rates, addresses and `payment_method_id` from the request
  (`classes/class-wc-rest-connect-shipping-label-controller.php`); status and refund check that the label belongs to
  the order (`get_order_for_label_request`, `is_label_on_order` in the base controller); print and preview forward
  label ids to the server. Whether a caller without the label capability can buy, refund or reprint, and whether a
  caller with it can act on an order or label that is not theirs.
- The capability model: `check_permission` (label capability) against `check_store_permission` (`manage_woocommerce`)
  on each controller, `connect/tos` on the owner, and the admin-ajax checks. A store-scoped action that a
  label-only user or a shop manager can reach when the code says otherwise is a finding.
- Secrets: the Jetpack blog token (read in `classes/class-wc-connect-jetpack.php`), the WooCommerce.com helper
  access token, the store GUID, and the payment method records the server returns (ids, card last four, names;
  card numbers never reach the plugin). Any path that shows them to a lower-privileged user, writes them to the
  WooCommerce logs (`classes/class-wc-connect-logger.php`; debug logging is a setting), or lets a non-administrator
  change `wc_connect_options` (`classes/class-wc-connect-options.php`) or the selected payment method.
- Where requests go: `WOOCOMMERCE_CONNECT_SERVER_URL` and the `wc_connect_server_url`, `wc_connect_request_args` and
  `wc_connect_jetpack_access_token` filters decide which host receives the signed request and the store's data. A
  lower-privileged path that moves them is a finding.
- Output escaping of server and shopper data: storefront notices (`src/StoreNotices/`, `src/StoreApi/`; they are
  session-scoped, so one shopper's notice reaching another is a finding), admin notices
  (`classes/class-wc-connect-error-notice.php`), tracking lines in emails, the order meta box, the status tab, and
  the data localized into the React app (`enqueue_wc_connect_script` in `woocommerce-services.php`).
- Files: the tax backup CSV written by `backup_existing_tax_rates` and streamed by `handle_tax_backup_download`
  (`classes/class-wc-connect-help-view.php`), and the label PDFs passed through to the browser.

In scope although copied: `client/calypso/` and `assets/stylesheets/shared/` are verbatim copies of WordPress.com
Calypso sources that ship in the plugin (`CREDITS.md`), so a bug there is this plugin's to fix.

Out of scope: `vendor/` (Composer packages, including the Jetpack Connection, Config and Status packages),
`node_modules/`, `dist/` (built output; patch `client/` instead), `tests/`, `bin/`, `docker/`, `tasks/`, `.github/`,
`translations/`, `wordpress_org_assets/`, `images/`, the Connect Server, TaxJar, the carriers, PayPal, Sift,
WordPress.com, and the WooCommerce Shipping plugin that succeeded the shipping features. WooCommerce core and
WordPress core findings belong to their own enrollments; report them only if this plugin's use of them creates the
bug.

## How to exercise it

- Run `wp-start` first. It starts MariaDB and Apache. The store is at `http://127.0.0.1/`, with pretty permalinks,
  Storefront, one simple product, a US (California) store address, automated taxes turned on, and the checkout,
  cart, shop and My Account pages installed. `wp-stop` stops both.
- PHP errors, warnings and deprecations from Apache and the CLI go to `/var/log/php-error.log`; Apache's own logs are
  under `/var/log/apache2/`. The plugin logs through WooCommerce's logger (wp-admin > WooCommerce > Status > Logs).
- Users: `admin` / `admin` (administrator), `shopmanager` / `shopmanager` (shop_manager), `customer` / `customer`
  (customer). Registration at checkout and on My Account is enabled. Guest checkout is enabled. For a label-only
  user, `wp user create` one and `wp user add-cap <user> wcship_manage_labels`.
- `wp --path=/var/www/html ...` (WP-CLI) sets up content, options, users and orders. `wp --path=/var/www/html wc
  ...` drives the WooCommerce REST API. `wp --path=/var/www/html eval '...'` runs PHP in a loaded WordPress.
- The plugin is at `/var/www/html/wp-content/plugins/woocommerce-services`, a symlink to `/src`, so a patch to
  `/src` takes effect on the next request. Client changes need `npm run dist` (offline: `node_modules` are already
  installed).
- There is no WordPress.com connection and the scan runs without network. Jetpack is in offline mode
  (`JETPACK_DEV_DEBUG` in `wp-config.php`) and the terms are recorded as accepted in `wc_connect_options`, which is
  what makes `WC_Connect_Loader::pre_wc_init` attach the plugin's hooks and routes, as the repository's own test
  environments do. Every request to the Connect Server stops in `authorization_header()` with a `missing_token`
  error before anything is sent, so tax lookups log an error and the cart shows no automated tax.
- To exercise a server-backed flow end to end, answer the server locally. The repository ships a test-only plugin
  for this, `tests/e2e-playwright/support/wc-services-e2e-tax-stub/`: copy it into `/var/www/html/wp-content/plugins/`,
  activate it, and `POST /wp-json/wc-services-e2e-tax-stub/v1/arm` as `admin`. It supplies a sentinel blog token
  through the `wc_connect_jetpack_access_token` filter, answers `taxjar/v2/taxes` and `taxjar/v2/addresses/validate`
  through `pre_http_request`, and fails every other request. For other endpoints, answer `pre_http_request` for
  `WOOCOMMERCE_CONNECT_SERVER_URL` in an mu-plugin of your own, or define `WOOCOMMERCE_SERVICES_LOCAL_TEST_MODE`,
  which swaps in `tests/php/class-wc-connect-api-client-local-test-mock.php` (fixtures in `tests/php/test_data/`).
- The image is a tax-only store (no connection and no labels), so the shipping label routes and screens are not
  registered. To scan them as a grandfathered store would see them, add an mu-plugin with
  `add_filter( 'wc_connect_has_only_tax_functionality', '__return_false' );`.
- PHPUnit: `cd /src && vendor/bin/phpunit --configuration phpunit.xml.dist --filter <TestName>`, with MariaDB
  running (`composer test` expects a Docker Compose database and does not work here). Tests use the `wcs_tests`
  database, the WordPress copy in `/tmp/wordpress` and WooCommerce's test bootstrap in `/tmp/woocommerce`. The
  suite mocks `WC_Connect_API_Client_Live` with PHPUnit's mock builder (`tests/php/test-class-wc-connect-api-client.php`)
  and drives the REST controllers through `WC_REST_Unit_Test_Case` (`tests/php/classes/`); copy those patterns.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate administrator would: create users at their real roles, set real options, add
products and orders. Drive the attack as the claimed actor, through the normal interface. Do not mint a nonce as an
administrator, grant the attacker `manage_woocommerce` or `wcship_manage_labels` when the claim is that they do
not need it, write tax rates or label meta through WP-CLI, or feed the plugin a server response without showing
how an attacker gets one accepted (the stub and the filters above are for your own setup, not the attack).
Reading the database to observe the outcome is fine. For XSS, show the payload executes in a browser context in the
victim's role, not only that it appears in the HTML.

## How you rate severity

Two questions settle the band, in this order: (1) can the attacker act without a merchant-created account
(anonymous or self-registered customer is the high band; shop manager and label-only user are the low band;
administrator is not rated), and (2) is the chain real and unconditional in a default configuration with
automated taxes on, or, for the shipping features, on a grandfathered store.

### Anonymous shopper, or a self-registered customer

| Finding | Severity |
|---|---|
| Buying, refunding or reprinting a shipping label, or changing the payment method that is charged for one | Critical |
| Disclosure of the Jetpack blog token, the WooCommerce.com access token, or saved payment method data | Critical |
| Proven RCE, unchained, no preconditions | Critical |
| Changing the tax other shoppers or the merchant's orders are charged: a wrong or zero rate written to the tax tables, a poisoned cache entry served to someone else, or a merchant-enabled lookup skipped for an order | High |
| Redirecting the plugin's signed requests, or the store's data, to a host of the attacker's choosing | High |
| XSS or SQL injection, unchained, reaching a shop manager or administrator session | High |
| Reading another customer's order, address, label, tracking or tax data through an order id, label id, session or REST route | High |
| Anything else with real security impact (IDOR on non-public data, SSRF with a demonstrated read, a shopper's notice shown to another shopper) | Medium |
| Blind SSRF, open redirect without a token leak, missing rate limiting | Low |
| No real security impact | Informative |

### Shop manager, or a label-only user

| Finding | Severity |
|---|---|
| Reaching secrets, code execution, file writes, or `install_plugins` / `edit_plugins` / `unfiltered_html` | Medium to High |
| A label-only user reaching a store-scoped route (`check_store_permission`), or either role acting on the Jetpack connection or the terms as only the owner may | Medium |
| Stored XSS, SQL injection, IDOR | Low |
| Most other findings | Low |

### Rules by class

- **Validity comes before severity.** Name the actor, what they can already do through the normal interface, and
  the specific thing they gain. No gain means no finding, however real the code defect.
- **Offline and test modes:** a finding that works only with Jetpack offline mode, `WOOCOMMERCE_SERVICES_LOCAL_TEST_MODE`,
  the test stub, or `WP_DEBUG` is one band lower. The image uses offline mode because there is no connection; say
  whether the chain also holds on a connected store.
- **Server payloads:** a finding that needs the Connect Server, TaxJar or a carrier to be malicious is out of
  scope; a finding that needs a third party to get a response accepted by the plugin is in scope and must show how
  (the host, the filters, the transport), not assume it.
- **CSRF:** needs realistic cross-origin exploitation under default `SameSite` cookie behaviour. A missing nonce on
  an action only an administrator can reach, where the attacker gains nothing they could not get by asking, is not
  a vulnerability.
- **Deserialization:** needs a real gadget in installed code; name it.
- **Race conditions** (double label purchase, double refund) count only with a demonstrated outcome.
- **Logging:** the blog token, the WooCommerce.com access token or payment method data written to the WooCommerce
  logs or the database in plain text is High regardless of actor.
- **Telemetry:** the store address, versions and usage events the plugin sends to Automattic by design (Tracks,
  Sift, the settings header) are documented behaviour, not a finding, unless a lower-privileged user can add to or
  redirect them.

## How reports and patches should look

- One-sentence claim: *<actor> can <action> against <target>, which they otherwise could not.*
- An explicit actor / already holds / gains line, the least privileged role that triggers the issue, whether it
  needs registration, a grandfathered store, offline mode, a non-default setting, or a particular server response,
  and the severity from the tables above.
- Name the affected file and function, and give a self-contained reproducer: WP-CLI setup plus `curl`, or a PHPUnit
  test under `tests/php/` that mocks `WC_Connect_API_Client_Live` or arms the stub. When the chain depends on a
  server response, include the response.
- Write patches as `git diff` against `/src`. Follow WordPress coding standards (`composer check-all` runs
  `phpcs.xml.dist`; `composer check-security` runs the security sniffs in `.phpcs.security.xml`) and use core APIs
  (`esc_html()`, `esc_attr()`, `wp_kses()`, `$wpdb->prepare()`, `current_user_can()`, `wp_verify_nonce()`,
  `rest_ensure_response()`). For a REST route, fix `check_permission`, not the callback. Tax calculation is reached
  from the cart, the Store API, the REST API, admin-ajax, cron and WP-CLI: check that the same fix is needed on each
  path. The global `WC_Connect_*` classes and the `wc_connect_*`, `wc_services_*` and `wcship_*` hooks are public
  contracts (`AGENTS.md`): say what a patch changes for third-party code that uses them.

## Anything to leave alone

- Anything an administrator can already do, including running PHP, installing plugins, reading the stored tokens,
  and connecting or disconnecting the site.
- Findings that need `WP_DEBUG` / `display_errors` on, a plugin not installed in this image, a server
  misconfiguration, or an already-compromised host.
- Behaviour of the Connect Server, TaxJar, the carriers, PayPal, Sift and WordPress.com, and findings that require
  them to be malicious.
- The Jetpack Connection package itself (signed-request handling, token storage) and the other Composer packages.
- The WooCommerce Shipping plugin and the migration to it, except where this plugin's compatibility code
  (`classes/class-wc-connect-compatibility-wcshipping-packages.php`) creates the bug.
- The data the plugin sends to Automattic by design, listed above.
- Version disclosure, order-number enumeration without data access, username enumeration, missing security
  headers, missing rate limiting on checkout or login, and clickjacking without security impact.
- Self-XSS, CSRF on login or logout, brute force, denial of service, phishing, social engineering.
- Vulnerabilities in Composer or npm `devDependencies`, unless practically exploitable remotely.
- Theoretical issues with no demonstrated, significant security impact.
