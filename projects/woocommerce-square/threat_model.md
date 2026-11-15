# Threat model: Square for WooCommerce

## What this project does and where untrusted input enters

Square for WooCommerce (`woocommerce-square`) is a WordPress plugin that lets a WooCommerce store take payments
through the merchant's own Square account and keeps the store and Square POS in sync. Payments: cards through
Square's Web Payments SDK, Apple Pay and Google Pay digital wallets, Cash App Pay, Square gift cards (buying and
redeeming), saved cards, and support for WooCommerce Subscriptions and Pre-Orders. Sync: products, variations,
categories, inventory and orders flow between WooCommerce and Square in the direction the merchant chooses (the
"system of record" setting), driven by Action Scheduler jobs that poll Square. This enrollment covers the plugin
code under `includes/`, `src/`, `templates/` and `woocommerce-square.php` on the `trunk` branch, including
`includes/Framework/`, the plugin's vendored copy of the SkyVerge payment gateway framework. Square's API, the Web
Payments SDK, the wallets, Cash App and the WooCommerce.com connect proxy are out of scope, but everything they
send to the plugin is untrusted input and the plugin's handling of it is in scope. There is no inbound webhook
endpoint: every piece of Square data arrives through API responses the plugin requests.

Untrusted input enters through:

- Shopper-facing `?wc-ajax=` actions: `square_credit_card_checkout_handler` (`includes/Gateway.php`), the digital
  wallet sheet (`square_digital_wallet_get_payment_request`, `_add_to_cart`, `_recalculate_totals`,
  `_process_checkout` in `includes/Gateway/Digital_Wallet.php`) and Cash App Pay
  (`square_cash_app_pay_get_payment_request`, `_set_continuation_session`, `square_cash_app_log_js_data` in
  `includes/Gateway/Cash_App_Pay_Gateway.php`). Each is guarded by a nonce; what matters is whether the cart,
  order and product the request names belong to the caller and whether the totals it sends are recomputed.
- `admin-ajax.php` actions open to anonymous callers (`wp_ajax_nopriv_`): `wc_square_credit_card_get_order_amount`
  and `wc_square_credit_card_should_charge_order` (`includes/Gateway.php`, which take an order id and key checked by
  `includes/Utilities/Order_Ajax_Authorization.php`), `wc_square_credit_card_log_js_data`, the gift card balance and
  removal actions (`includes/Gateway/Gift_Card.php`), and the framework's `sv_wc_apple_pay_*` actions
  (`includes/Framework/PaymentGateway/ApplePay/Payment_Gateway_Apple_Pay_Ajax.php`).
- The WooCommerce checkout, both classic and the Store API (`/wp-json/wc/store/v1/checkout` through
  `includes/Gateway/Blocks_Handler.php` and `includes/Gateway/Cash_App_Pay_Blocks_Handler.php`), the `order-pay`
  page (reached with an order key), the `order-received` page (`save_guest_details()` in
  `includes/Handlers/Order.php` writes POSTed billing fields to the order) and My Account payment methods. Through
  these the gateway receives Square payment tokens (card nonces), verification tokens, gift card tokens, wallet
  type and saved token ids (`includes/Gateway/Payment_Form.php`, `includes/Gateway.php`,
  `includes/Framework/PaymentGateway/Payment_Gateway_Direct.php`,
  `includes/Framework/PaymentGateway/PaymentTokens/`).
- The connect return. Square OAuth runs through WooCommerce.com's proxy
  (`https://api.woocommerce.com/integrations/login/square`), which redirects back to
  `wp-admin/admin.php?action=wc_square_connected` with `square_access_token` and `square_refresh_token` in the
  query string, handled by `handle_connected()` in `includes/Handlers/Connection.php` behind `manage_woocommerce`
  and a nonce. Tokens are stored encrypted in options by `includes/Settings.php` with
  `includes/Utilities/Encryption_Utility.php`; a scheduled job renews them through the proxy.
- Responses from the Square API: catalog, inventory, customers, locations and orders through `includes/API.php`,
  payments, refunds, cards and gift cards through `includes/Gateway/API.php`. The plugin writes them into products,
  variations, categories, stock, orders and order notes, the `{$wpdb->prefix}woocommerce_square_customers` table
  (`includes/Gateway/Customer_Helper.php`) and the sync records it renders in wp-admin (`includes/Sync/Records.php`).
  Names, SKUs and customer details in those responses can originate from Square POS staff or from Square's own
  customers, so treat them as untrusted when they reach HTML, SQL or order state.
- Sync jobs run by Action Scheduler with no logged-in user (`includes/Handlers/Background_Job.php`,
  `includes/Handlers/Sync.php`, `includes/Sync/`, order polling in `includes/Sync/Order_Polling.php` and
  `includes/Sync/Order_Importer.php`): their arguments are stored in the database and their results change product,
  stock and order data.
- The merchant-facing REST API `/wp-json/wc/v3/wc_square/*` (`includes/Admin/Rest/`: general settings including the
  sandbox application id and token, payment, Cash App and gift card settings; `includes/AJAX.php`: product import
  and onboarding state), the `manage_woocommerce`-gated `admin-ajax` sync and product actions (`includes/AJAX.php`,
  `includes/Settings.php`), the framework's token editor and capture actions
  (`includes/Framework/PaymentGateway/Admin/`), and the read-only WordPress Abilities in
  `includes/Internal/Abilities/`.
- The WordPress admin screens the plugin adds: the settings and onboarding React apps (`src/new-user-experience/`),
  the sync page (`includes/Admin/Sync_Page.php`), product quick edit, bulk edit and CSV import and export fields
  (`includes/Handlers/Products.php`), and capture and refund on the order screen.

### Actors

| Actor | How they get there | Trust |
|-------|--------------------|-------|
| Anonymous shopper | none needed; guest checkout is on by default | Untrusted. High band |
| Customer | self-registered at checkout or My Account (merchant-enabled; enabled in this image) | Untrusted. High band |
| Shop manager | admin-created; holds `manage_woocommerce`, not `install_plugins`, `edit_plugins` or `unfiltered_html` | Partly trusted. Low band |
| Administrator | admin-created | Fully trusted, including code execution. Not rated, except the PCI and secrets rules below |
| Square (API responses, connect return) | access token obtained through the connect proxy | Trusted party, untrusted payload. Data a third party can place in a Square account (item names, customer names, notes) that reaches wp-admin unescaped or changes order state is in scope |

## Components that matter most / least

Most important:

- Order state transitions: anything that marks an order paid, captured, refunded or completed must correspond to
  a successful Square payment for that order and that amount, on the merchant's account. `includes/Gateway.php`,
  `includes/Gateway/API.php`, `includes/Gateway/Cash_App_Pay_Gateway.php`, `includes/Gateway/Digital_Wallet.php`,
  `includes/Framework/PaymentGateway/Payment_Gateway_Direct.php`,
  `includes/Framework/PaymentGateway/Payment_Gateway.php`, and the gift card plus card split in
  `includes/Gateway/Gift_Card.php` and `includes/Gateway.php` (the amount charged to the card must be the order
  total minus what the gift card really covered).
- Order binding: an order id and key that let one shopper read totals for, pay for, or change the billing details
  of another shopper's order (`includes/Utilities/Order_Ajax_Authorization.php`, `save_guest_details()` in
  `includes/Handlers/Order.php`, the pay-for-order paths in `includes/Gateway.php`).
- Saved cards and Square customers (`includes/Framework/PaymentGateway/PaymentTokens/`,
  `includes/Gateway/Card_Handler.php`, `get_token_by_id()` in `includes/Gateway.php`,
  `includes/Gateway/Customer_Helper.php`): using, listing or deleting another user's token; mapping a shopper to
  another person's Square customer record by email.
- Gift cards (`includes/Gateway/Gift_Card.php`, `includes/Handlers/Order.php`, `includes/Handlers/Products.php`,
  `includes/Emails/WC_Square_Gift_Card_Sent.php`): applying, checking or draining a gift card the shopper does not
  hold, buying a gift card for less than its value, a recipient email the shopper did not type.
- Secrets: the Square access and refresh tokens (`wc_square_access_tokens`, `wc_square_refresh_tokens`, encrypted)
  and the sandbox token in settings. Any path that exposes them to a lower-privileged user, writes them to the
  debug log (`debug_mode` logs requests and responses through `includes/Framework/Plugin.php`), or lets a
  non-administrator change them. Card data never touches the plugin by design (the Web Payments SDK tokenizes in
  the browser); any path that logs, stores or echoes a full PAN or CVV is a PCI boundary.
- Authorization on `includes/Admin/Rest/` and `includes/AJAX.php`: a `permission_callback` that checks a global
  capability where per-object ownership is needed, or that lets a lower-privileged caller start a sync, import the
  catalog or change product data.
- Sync correctness as a security property: Square data overwriting prices, stock or product visibility the merchant
  did not intend (`includes/Handlers/Product.php`, `includes/Handlers/Category.php`, `includes/Sync/`), and stored
  action arguments executed later.
- Digital wallet and Cash App checkout: product id, quantity, attributes, address and shipping data from the wallet
  sheet, and totals recalculation before the charge.
- Output escaping in wp-admin screens that render Square data (sync records, order notes, customer and location
  names) and in the storefront forms.

Out of scope: `vendor/` (Composer packages, including the Square SDK), `node_modules/`, `build/` (built output;
patch `src/` instead), `tests/`, `bin/`, `docker/`, `docs/`, `.github/`, `wordpress-org-assets/`, the Square Web
Payments SDK, Square's API and dashboard, Apple Pay, Google Pay, Cash App, and the WooCommerce.com connect proxy.
WooCommerce core and WordPress core findings belong to their own enrollments; report them only if this plugin's
use of them creates the bug.

## How to exercise it

- Run `wp-start` first. It starts MariaDB and Apache. The store is at `http://127.0.0.1/`, with pretty permalinks,
  Storefront, one simple product, and the checkout, cart, shop and My Account pages installed. `wp-stop` stops both.
- PHP errors, warnings and deprecations from Apache and the CLI go to `/var/log/php-error.log`; Apache's own logs are
  under `/var/log/apache2/`.
- Users: `admin` / `admin` (administrator), `shopmanager` / `shopmanager` (shop_manager), `customer` / `customer`
  (customer). Registration at checkout and on My Account is enabled. Guest checkout is enabled.
- `wp --path=/var/www/html ...` (WP-CLI) sets up content, options, users and orders. `wp --path=/var/www/html wc
  ...` drives the WooCommerce REST API. `wp --path=/var/www/html eval '...'` runs PHP in a loaded WordPress.
- The plugin is at `/var/www/html/wp-content/plugins/woocommerce-square`, a symlink to `/src`, so a patch to `/src`
  takes effect on the next request. Client changes need `npm run build:webpack` (offline: `node_modules` are
  already installed).
- No Square account is connected and the scan runs without network. The connection check reads the stored access
  token (`get_access_token()` in `includes/Settings.php`); storing one with `wc_square()->get_settings_handler()
  ->update_access_token('test')` from `wp eval`, or saving sandbox credentials through the settings REST route,
  makes the plugin build a `Square\SquareClient` (`includes/API.php`) whose calls fail. Reason about the request
  the plugin would send and the response it would accept, and mock the API the way the suite does:
  `tests/php/Unit/API/Scripted_API.php` and `tests/php/Unit/Sync/Fixtures/` subclass `WooCommerce\Square\API` with
  scripted responses. The gateways can be enabled without a connection (`wp wc payment_gateway update
  square_credit_card --enabled=1 --user=admin`) to reach the checkout and AJAX code paths.
- PHPUnit: `cd /src && vendor/bin/phpunit --configuration tests/php/phpunit.xml.dist --filter <TestName>`, with
  MariaDB running. Tests use the `square_tests` database, the WordPress copy in `/tmp/wordpress` and the WooCommerce
  copy at `/woocommerce`. The suite is small (about a hundred tests in `tests/php/Unit/`: connection refresh,
  catalog option sync, order total reconciliation with gift cards, inventory write policy, abilities); checkout,
  wallets and gift card redemption have no unit coverage. The Playwright suite in `tests/e2e/` needs a Square
  sandbox account and the network, so it cannot run in this image.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate administrator would: create users at their real roles, set real options, add
products and orders. Drive the attack as the claimed actor, through the normal interface. Do not mint a nonce as an
administrator, mark an order paid through WP-CLI, give the attacker a capability they are supposed to gain, or
script a Square API response without showing how a third party gets that data into the merchant's Square account.
Reading the database to observe the outcome is fine. For XSS, show the payload executes in a browser context in the
victim's role.

## How you rate severity

Two questions settle the band, in this order: (1) can the attacker act without a merchant-created account
(anonymous or self-registered customer is the high band; shop manager is the low band; administrator is not
rated), and (2) is the chain real and unconditional in a default configuration with this gateway enabled.

### Anonymous shopper, or a self-registered customer

| Finding | Severity |
|---|---|
| Order marked paid, captured or completed without a successful payment for that order and amount; paying less than the cart total (including through the gift card and card split); refund, capture or void of someone else's order | Critical |
| Using, charging, listing or deleting another user's saved card; applying or draining a gift card the shopper does not hold | Critical |
| Disclosure of the Square access or refresh token, the sandbox token, or any full PAN / CVV | Critical |
| Proven RCE, unchained, no preconditions | Critical |
| Changing another shopper's order (billing details, status, notes) through an order key, id or session the attacker does not hold | High |
| XSS or SQL injection, unchained, reaching a shop manager or administrator session, including through data placed in Square | High |
| Reading another customer's order, address, email, last4 or gift card balance through an order key, session or REST route | High |
| Starting a catalog, inventory or order sync, importing products, or changing product or settings data without `manage_woocommerce` | High |
| Anything else with real security impact (IDOR on non-public data, SSRF with a demonstrated read) | Medium |
| Blind SSRF, open redirect without a token leak, missing rate limiting | Low |
| No real security impact | Informative |

### Shop manager

| Finding | Severity |
|---|---|
| Reaching the access token, code execution, file writes, or `install_plugins` / `edit_plugins` / `unfiltered_html` | Medium to High |
| Stored XSS, SQL injection, IDOR | Low |
| Most other findings | Low |

### Rules by class

- **Validity comes before severity.** Name the actor, what they can already do through the normal interface, and
  the specific thing they gain. No gain means no finding, however real the code defect.
- **Sandbox mode:** a finding that works only with sandbox credentials or only in development mode is one band
  lower.
- **Square payloads:** a finding that needs Square itself to be malicious is out of scope. A finding that needs a
  third party to place data in the merchant's Square account (a POS item name, a customer record created at a Square
  checkout) is in scope and must show how that party gets there; it is rated as the actor who placed the data.
- **CSRF:** needs realistic cross-origin exploitation under default `SameSite` cookie behaviour. A missing nonce on
  an action only an administrator can reach, where the attacker gains nothing they could not get by asking, is not
  a vulnerability.
- **Deserialization:** needs a real gadget in installed code; name it.
- **Race conditions** (double capture, double gift card redemption, concurrent syncs) count only with a demonstrated
  outcome.
- **Logging:** full card data, CVV, access or refresh tokens written to `wc-logs` or the database is High regardless
  of actor, including through `debug_mode`.

## How reports and patches should look

- One-sentence claim: *<actor> can <action> against <target>, which they otherwise could not.*
- An explicit actor / already holds / gains line, the least privileged role that triggers the issue, whether it
  needs registration, sandbox mode, a specific payment method, a Square connection, or a non-default setting, and
  the severity from the tables above.
- Name the affected file and function, and give a self-contained reproducer: WP-CLI setup plus `curl` (for
  `wc-ajax` and `admin-ajax` actions, include where the nonce comes from), or a PHPUnit test under
  `tests/php/Unit/` that scripts the Square API the way the existing fixtures do.
- Write patches as `git diff` against `/src`. Follow the WooCommerce coding standards (`vendor/bin/phpcs` with
  `phpcs.xml.dist` checks them) and use core APIs (`esc_html()`, `esc_attr()`, `wp_kses()`, `$wpdb->prepare()`,
  `current_user_can()`, `wp_verify_nonce()`, `hash_equals()`). For a REST route, fix the `permission_callback`, not
  the callback. Check whether the same fix is needed in the classic checkout, Store API, `wc-ajax` and `admin-ajax`
  twins of the same operation, and in both `includes/Gateway.php` and `includes/Gateway/Cash_App_Pay_Gateway.php`.
  `includes/Framework/` is shared with other gateway plugins, so say when a patch touches it.

## Anything to leave alone

- Anything an administrator can already do, including running PHP, installing plugins and reading the stored
  tokens.
- Findings that need `WP_DEBUG` / `display_errors` on, a plugin not installed in this image (Subscriptions,
  Pre-Orders), a server misconfiguration, or an already-compromised host.
- The Web Payments SDK, Apple Pay, Google Pay and Cash App behaviour in the browser or on Square's servers, and the
  WooCommerce.com connect proxy.
- Behaviour of Square's API or dashboard, and findings that require Square to be malicious.
- The Apple Pay domain association file under `.well-known/` being public (it is meant to be).
- Shopper-supplied text reaching the debug log through the `log_js_data` actions when debug mode is on (log noise,
  not a vulnerability, unless it carries secrets or card data).
- Version disclosure, order-number enumeration without data access, username enumeration, missing security
  headers, missing rate limiting on checkout or login, and clickjacking without security impact.
- Self-XSS, CSRF on login or logout, brute force, denial of service, phishing, social engineering.
- Vulnerabilities in Composer or npm `devDependencies`, unless practically exploitable remotely.
- Theoretical issues with no demonstrated, significant security impact.
