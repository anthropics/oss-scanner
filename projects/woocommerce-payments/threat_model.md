# Threat model: WooPayments

## What this project does and where untrusted input enters

WooPayments (`woocommerce-payments`) is a WordPress plugin that adds a hosted payment gateway to WooCommerce. The
plugin on the merchant's site collects checkout data, creates and confirms payment intents through the WooPayments
server (a private Automattic service reached over Jetpack Connection, which proxies Stripe), stores payment tokens,
handles refunds, disputes, deposits, multi-currency, fraud protection, express checkouts (Apple Pay, Google Pay,
WooPay) and in-person payments. This enrollment covers the plugin code under `includes/`, `src/` and `client/` on
the `develop` branch. The WooPayments server, WooPay and Stripe are out of scope, but every byte they send to the
plugin is untrusted input and the plugin's handling of it is in scope.

Untrusted input enters through:

- Shopper-facing endpoints reachable without a login: the WooCommerce checkout and cart (classic shortcode and the
  Checkout block via the Store API, `/wp-json/wc/store/v1/*`), the `?wc-ajax=` and `admin-ajax.php` `nopriv`
  actions registered in `includes/class-wc-payment-gateway-wcpay.php`, `includes/express-checkout/`,
  `includes/class-wc-payments-woopay-button-handler.php` and `includes/class-woopay-tracker.php`, the
  `order-pay` and `order-received` pages (reached with an order key), My Account payment methods, and the
  multi-currency switcher.
- Server-to-plugin calls: `POST /wp-json/wc/v3/payments/webhook` (reached through Jetpack-signed requests from the
  WooPayments server; `includes/class-wc-payments-webhook-processing-service.php` interprets the payload) and
  `/wp-json/payments/woopay/session` (authenticated by a signature or an attestation, see
  `includes/admin/class-wc-rest-woopay-session-controller.php`). Treat the payload of both as attacker-controlled
  once past authentication: what can a forged or replayed event make the plugin do?
- Responses from the WooPayments server (`includes/wc-payment-api/`): intents, charges, disputes, account data.
  The plugin renders parts of them in wp-admin.
- The merchant-facing REST API under `/wp-json/wc/v3/payments/*` (controllers in `includes/admin/`), which by default
  requires `manage_woocommerce`, and the in-person-payments routes used by the mobile apps (terminal locations,
  readers, connection tokens), which authenticate as a store user.
- The WordPress admin screens the plugin adds (settings, transactions, disputes, deposits, fraud rules), reached by
  shop managers and administrators.

### Actors

| Actor | How they get there | Trust |
|-------|--------------------|-------|
| Anonymous shopper | none needed; guest checkout is on by default | Untrusted. High band |
| Customer | self-registered at checkout or My Account (merchant-enabled; enabled in this image) | Untrusted. High band |
| Shop manager | admin-created; holds `manage_woocommerce`, not `install_plugins`, `edit_plugins` or `unfiltered_html` | Partly trusted. Low band |
| Administrator | admin-created | Fully trusted, including code execution. Not rated, except the PCI and secrets rules below |
| WooPayments server / WooPay | authenticated by Jetpack signature, blog-token signature or attestation | Trusted party, untrusted payload. A forged, replayed or cross-site payload that is accepted is High band |
| Mobile app (in-person payments) | application password of a store user | Same trust as that user |

## Components that matter most / least

Most important:

- Payment state transitions: anything that marks an order paid, captured, refunded or completed must correspond to
  a real successful intent for that order and that amount. `includes/class-wc-payments-order-service.php`,
  `includes/class-wc-payment-gateway-wcpay.php`, `includes/class-wc-payments-webhook-processing-service.php`,
  `includes/class-wc-payments-checkout.php`.
- Order and intent binding: an intent id, order key or session that lets one shopper act on, pay for, or read
  another shopper's order. Compare every `order_id` / `payment_intent` pair taken from the request with what the
  server returns.
- Saved payment methods and tokens (`includes/class-wc-payments-token-service.php`, `includes/payment-methods/`):
  using, listing or deleting another user's token.
- Secrets: Jetpack blog tokens, WooPayments account data, anything the plugin writes to logs
  (`includes/class-logger.php`). Card data never touches the plugin by design (Stripe.js tokenizes in the
  browser); any path that logs, stores or echoes a full PAN, CVV, or a raw card payload is a PCI boundary.
- Authorization on REST controllers in `includes/admin/`: a route whose `permission_callback` checks a global
  capability where per-object ownership is needed, or routes that forward requests to the server with the
  merchant's credentials on behalf of a lower-privileged caller.
- Webhook and WooPay request authentication: signature checks, replay, and the shape of accepted payloads.
- Express checkout and WooPay session handling (`includes/express-checkout/`, `includes/woopay/`,
  `includes/woopay-user/`): cart and address data from the wallet sheet, shipping and totals recalculation.
- Fraud protection rules (`includes/fraud-prevention/`): a shopper bypassing a rule the merchant turned on.
- Multi-currency (`includes/multi-currency/`): a shopper choosing a rate or amount the merchant did not set.
- Output escaping in wp-admin screens that render server data (transactions, disputes, customer names, metadata).

In scope although vendored: `vendor/woocommerce/subscriptions-core/`, which Automattic maintains
(https://github.com/Automattic/woocommerce-subscriptions-core) and which handles recurring billing, renewals and
subscription switching inside WooPayments.

Out of scope: the rest of `vendor/` (Composer packages such as the Jetpack libraries), `node_modules/`, `dist/`
(built output; patch `client/` instead), `tests/`, `bin/`, `docker/`, `dev/`, `.github/`, the WooPayments server,
WooPay, Stripe.js, Apple Pay and Google Pay. WooCommerce core and WordPress core findings belong to their own
enrollments; report them only if WooPayments' use of them creates the bug.

## How to exercise it

- Run `wp-start` first. It starts MariaDB and Apache. The store is at `http://127.0.0.1/`, with pretty permalinks,
  Storefront, one simple product, and the checkout, cart, shop and My Account pages installed. `wp-stop` stops both.
- PHP errors, warnings and deprecations from Apache and the CLI go to `/var/log/php-error.log`; Apache's own logs are
  under `/var/log/apache2/`.
- Users: `admin` / `admin` (administrator), `shopmanager` / `shopmanager` (shop_manager), `customer` / `customer`
  (customer). Registration at checkout and on My Account is enabled. Guest checkout is enabled.
- `wp --path=/var/www/html ...` (WP-CLI) sets up content, options, users and orders. `wp --path=/var/www/html wc
  ...` drives the WooCommerce REST API. `wp --path=/var/www/html eval '...'` runs PHP in a loaded WordPress.
- The plugin is at `/var/www/html/wp-content/plugins/woocommerce-payments`, a symlink to `/src`, so a patch to
  `/src` takes effect on the next request. Client changes need `pnpm run build:client` (offline: the
  `node_modules` are already installed).
- The site is not connected to the WooPayments server and the scan runs without network. `WP_ENVIRONMENT_TYPE` is
  `development`. Calls through `includes/wc-payment-api/` will fail; reason about the request the plugin would
  send and the response it would accept, and mock the API client in a PHPUnit test to drive the rest of the flow.
- PHPUnit: `cd /src && vendor/bin/phpunit --configuration phpunit.xml.dist --filter <TestName>`, with MariaDB
  running. Tests use the `wcpay_tests` database and the WordPress copy in `/tmp/wordpress`. The suite mocks the API
  client (`WC_Payments_API_Client`) extensively; look in `tests/unit/` for patterns.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate administrator would: create users at their real roles, set real options, add
products and orders. Drive the attack as the claimed actor, through the normal interface. Do not mint a nonce as an
administrator, mark an order paid through WP-CLI, give the attacker a capability they are supposed to gain, or
forge a webhook without showing how the signature check is bypassed. Reading the database to observe the outcome
is fine. For XSS, show the payload executes in a browser context in the victim's role, not only that it appears in
the HTML.

## How you rate severity

Two questions settle the band, in this order: (1) can the attacker act without a merchant-created account
(anonymous or self-registered customer is the high band; shop manager is the low band; administrator is not
rated), and (2) is the chain real and unconditional in a default configuration with WooPayments as the active
gateway.

### Anonymous shopper, or a self-registered customer

| Finding | Severity |
|---|---|
| Order marked paid, captured or completed without a successful payment for that order and amount; paying less than the cart total; refund, capture or void of someone else's order | Critical |
| Using, charging, listing or deleting another user's saved payment method | Critical |
| Disclosure of secrets: Jetpack tokens, account credentials, webhook or signing secrets, or any full PAN / CVV | Critical |
| Proven RCE, unchained, no preconditions | Critical |
| Accepted forged or replayed webhook or WooPay session payload that changes order, customer or settings state | High (Critical if it reaches the first row) |
| XSS or SQL injection, unchained, reaching a shop manager or administrator session | High |
| Reading another customer's order, address, email, last4 or dispute data through an order key, intent id, session or REST route | High |
| Bypassing a merchant-enabled fraud rule or multi-currency setting to change what is charged | High |
| Anything else with real security impact (IDOR on non-public data, SSRF with a demonstrated read) | Medium |
| Blind SSRF, open redirect without a token leak, missing rate limiting | Low |
| No real security impact | Informative |

### Shop manager

| Finding | Severity |
|---|---|
| Reaching secrets, code execution, file writes, or `install_plugins` / `edit_plugins` / `unfiltered_html` | Medium to High |
| Stored XSS, SQL injection, IDOR | Low |
| Most other findings | Low |

### Rules by class

- **Validity comes before severity.** Name the actor, what they can already do through the normal interface, and
  the specific thing they gain. No gain means no finding, however real the code defect.
- **Test mode:** a finding that works only in test mode or only with dev mode on is one band lower.
- **Server payloads:** a finding that needs the WooPayments server itself to be malicious is out of scope; a
  finding that needs a third party to reach the webhook or session route with a forged payload is in scope and
  must show how authentication is passed.
- **CSRF:** needs realistic cross-origin exploitation under default `SameSite` cookie behaviour. A missing nonce on
  an action only an administrator can reach, where the attacker gains nothing they could not get by asking, is not
  a vulnerability.
- **Deserialization:** needs a real gadget in installed code; name it.
- **Race conditions** (double refund, double capture) count only with a demonstrated outcome.
- **Logging:** full card data, CVV or secrets written to `wc-logs` or the database is High regardless of actor.

## How reports and patches should look

- One-sentence claim: *<actor> can <action> against <target>, which they otherwise could not.*
- An explicit actor / already holds / gains line, the least privileged role that triggers the issue, whether it
  needs registration, test mode, or a non-default setting, and the severity from the tables above.
- Name the affected file and function, and give a self-contained reproducer: WP-CLI setup plus `curl`, or a PHPUnit
  test under `tests/unit/` that mocks `WC_Payments_API_Client`.
- Write patches as `git diff` against `/src`. Follow WordPress coding standards (`vendor/bin/phpcs` checks them)
  and use core APIs (`esc_html()`, `esc_attr()`, `wp_kses()`, `$wpdb->prepare()`, `current_user_can()`,
  `wp_verify_nonce()`, `rest_ensure_response()`). For a REST route, fix the `permission_callback`, not the
  callback. Check whether the same fix is needed in the Store API, `wc-ajax` and REST twins of the same operation.

## Anything to leave alone

- Anything an administrator can already do, including running PHP and installing plugins.
- Findings that need `WP_DEBUG` / `display_errors` on, a plugin not installed in this image, a server
  misconfiguration, or an already-compromised host.
- Stripe.js, Apple Pay, Google Pay and WooPay behaviour in the browser or on their servers.
- Behaviour of the WooPayments server, WooPay or Stripe APIs, and findings that require them to be malicious.
- Version disclosure, order-number enumeration without data access, username enumeration, missing security
  headers, missing rate limiting on checkout or login, and clickjacking without security impact.
- Self-XSS, CSRF on login or logout, brute force, denial of service, phishing, social engineering.
- Vulnerabilities in Composer or npm `devDependencies`, unless practically exploitable remotely.
- Theoretical issues with no demonstrated, significant security impact.
