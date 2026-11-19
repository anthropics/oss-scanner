# Threat model: WooCommerce Stripe Payment Gateway

## What this project does and where untrusted input enters

The WooCommerce Stripe Payment Gateway (`woocommerce-gateway-stripe`) is a WordPress plugin that lets a WooCommerce
store take payments through the merchant's own Stripe account: cards and local payment methods through Stripe
Elements and Stripe Checkout, express checkouts (Apple Pay, Google Pay, Link), saved payment methods, refunds,
disputes, subscriptions and pre-orders support, Stripe Terminal for the mobile apps, an OAuth connection flow to
Stripe, and a product feed plus checkout session flow for Stripe's Agentic Commerce. This enrollment covers the
plugin code under `includes/`, `client/` and `assets/` on the `develop` branch. Stripe's API, Stripe.js and the
wallets are out of scope, but everything they send to the plugin is untrusted input and the plugin's handling of it
is in scope.

Untrusted input enters through:

- The Stripe webhook endpoint `?wc-api=wc_stripe` (`includes/class-wc-stripe-webhook-handler.php`). The request
  is authenticated by an HMAC-SHA256 signature over the signed payload with the stored webhook secret
  (`validate_request`). Once authenticated, the event body drives order state: payments, captures, refunds,
  disputes, reviews, setup intents. Treat the body as attacker-controlled when reasoning about what an accepted
  event can do, and the signature check, timestamp tolerance, and account-id binding
  (`event_belongs_to_connected_account`) as the boundary.
- Shopper-facing `?wc-ajax=wc_stripe_*` actions (`includes/class-wc-stripe-intent-controller.php`,
  `includes/payment-methods/class-wc-stripe-express-checkout-ajax-handler.php`, `includes/ajax-handlers/`), which
  create, update, confirm and verify payment and setup intents, update order status after a redirect, and build
  carts and shipping options for the wallet sheets. Each is guarded by a nonce; what matters is whether the order,
  intent and customer referenced in the request belong to the caller.
- The WooCommerce checkout, cart and Store API (`/wp-json/wc/store/v1/*`), the `order-pay` and `order-received`
  pages (reached with an order key), and My Account payment methods, through which the gateway receives payment
  method ids, intent ids and saved-token ids.
- Responses from the Stripe API (`includes/class-wc-stripe-api.php`): intents, charges, customers, payment
  methods, account data, which the plugin stores on orders and renders in wp-admin.
- The OAuth connection return (`includes/connect/`): state, account id and keys returned from Stripe Connect.
- The merchant-facing REST API `/wp-json/wc/v3/wc_stripe/*` (controllers in `includes/admin/`: settings, account,
  account keys, tokens, orders, locations, connection tokens, agentic commerce), which requires a capability, and
  the Abilities API registrations in `includes/abilities/`.
- Agentic Commerce (`includes/agentic-commerce/`): the product feed delivered to Stripe and the checkout sessions
  created from agent requests, including shipping and tax calculation, inventory and manual approval.
- The WordPress admin screens the plugin adds, reached by shop managers and administrators.

### Actors

| Actor | How they get there | Trust |
|-------|--------------------|-------|
| Anonymous shopper | none needed; guest checkout is on by default | Untrusted. High band |
| Customer | self-registered at checkout or My Account (merchant-enabled; enabled in this image) | Untrusted. High band |
| Shop manager | admin-created; holds `manage_woocommerce`, not `install_plugins`, `edit_plugins` or `unfiltered_html` | Partly trusted. Low band |
| Administrator | admin-created | Fully trusted, including code execution. Not rated, except the PCI and secrets rules below |
| Stripe (webhooks, API responses, OAuth return) | signature, API key, OAuth state | Trusted party, untrusted payload. A forged, replayed or cross-account payload that is accepted is High band |
| Agent / Stripe Agentic Commerce | Stripe-authenticated session | Untrusted. High band |

## Components that matter most / least

Most important:

- Order state transitions: anything that marks an order paid, captured, refunded or completed must correspond to
  a successful intent or charge for that order and that amount, on the merchant's account.
  `includes/class-wc-stripe-webhook-handler.php`, `includes/class-wc-stripe-order-handler.php`,
  `includes/class-wc-stripe-intent-controller.php`, `includes/class-wc-gateway-stripe.php`,
  `includes/abstracts/`, `includes/payment-methods/`.
- Order, intent and customer binding: an intent id, order key, customer id or token that lets one shopper act on,
  pay for, or read another shopper's order or saved payment method. Compare the ids in the request with the order
  and with what Stripe returns.
- Saved payment methods (`includes/payment-tokens/`, `includes/class-wc-stripe-customer.php`): using, listing or
  deleting another user's token; attaching a payment method to the wrong Stripe customer.
- Secrets: secret API keys and webhook secrets stored in options, connection tokens, OAuth state. Any path that
  exposes them to a lower-privileged user, writes them to logs (`includes/class-wc-stripe-logger.php`), or lets a
  non-administrator change them. Card data never touches the plugin by design (Stripe.js tokenizes in the
  browser); any path that logs, stores or echoes a full PAN or CVV is a PCI boundary.
- Webhook authentication: signature verification, timestamp tolerance, account-id binding, replay.
- Authorization on REST controllers in `includes/admin/`: a `permission_callback` that checks a global capability
  where per-object ownership is needed, or that forwards requests to Stripe with the merchant's key on behalf of a
  lower-privileged caller.
- Express checkout and checkout session handling: cart, address and shipping data from the wallet sheet or the
  agent, and totals recalculation.
- Agentic Commerce: product visibility and exclusion rules, inventory tracking, tax and shipping calculation, and
  manual approval; an agent buying a product the merchant excluded, or at a price the merchant did not set.
- Output escaping in wp-admin screens that render Stripe data (charges, customer names, dispute evidence, metadata).

Out of scope: `vendor/` (Composer packages), `node_modules/`, `build/` and `assets/js/*.min.js` (built output;
patch `client/` and `assets/js/*.js` instead), `tests/`, `bin/`, `docker/`, `.github/`, `phpstan-stubs/`,
Stripe.js, Stripe's API and dashboard, Apple Pay, Google Pay and Link. WooCommerce core and WordPress core findings
belong to their own enrollments; report them only if this plugin's use of them creates the bug.

## How to exercise it

- Run `wp-start` first. It starts MariaDB and Apache. The store is at `http://127.0.0.1/`, with pretty permalinks,
  Storefront, one simple product, and the checkout, cart, shop and My Account pages installed. `wp-stop` stops both.
- PHP errors, warnings and deprecations from Apache and the CLI go to `/var/log/php-error.log`; Apache's own logs are
  under `/var/log/apache2/`.
- Users: `admin` / `admin` (administrator), `shopmanager` / `shopmanager` (shop_manager), `customer` / `customer`
  (customer). Registration at checkout and on My Account is enabled. Guest checkout is enabled.
- `wp --path=/var/www/html ...` (WP-CLI) sets up content, options, users and orders. `wp --path=/var/www/html wc
  ...` drives the WooCommerce REST API. `wp --path=/var/www/html eval '...'` runs PHP in a loaded WordPress.
- The plugin is at `/var/www/html/wp-content/plugins/woocommerce-gateway-stripe`, a symlink to `/src`, so a patch
  to `/src` takes effect on the next request. Client changes need `npm run build:webpack` (offline:
  `node_modules` are already installed).
- No Stripe keys are configured and the scan runs without network. To exercise the gateway, set test keys through
  the settings (`wp option update woocommerce_stripe_settings ...` or the settings REST route) and expect calls
  through `includes/class-wc-stripe-api.php` to fail; reason about the request the plugin would send and the
  response it would accept, and mock `WC_Stripe_API` in a PHPUnit test to drive the rest of the flow. Webhook
  handling can be exercised end to end: compute a valid signature with a known secret and POST to
  `?wc-api=wc_stripe`.
- PHPUnit: `cd /src && vendor/bin/phpunit --configuration phpunit.xml.dist --filter <TestName>`, with MariaDB
  running. Tests use the `wc_stripe_tests` database and the WordPress copy in `/tmp/wordpress`. Look in
  `tests/phpunit/` for how the suite mocks the API and builds webhook requests. Run the suite one test class at a
  time (`--filter '^WC_Stripe_Helper_Test'`): the maintainers run it sharded with paratest
  (`bin/phpunit.sh`), and a single sequential run of all 4,600 tests shows a couple of dozen order-dependent
  errors that do not reproduce per class.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate administrator would: create users at their real roles, set real options, add
products and orders. Drive the attack as the claimed actor, through the normal interface. Do not mint a nonce as an
administrator, mark an order paid through WP-CLI, give the attacker a capability they are supposed to gain, or
forge a webhook without showing how the signature check is bypassed or the secret obtained. Reading the database to
observe the outcome is fine. For XSS, show the payload executes in a browser context in the victim's role.

## How you rate severity

Two questions settle the band, in this order: (1) can the attacker act without a merchant-created account
(anonymous or self-registered customer is the high band; shop manager is the low band; administrator is not
rated), and (2) is the chain real and unconditional in a default configuration with this gateway enabled.

### Anonymous shopper, or a self-registered customer

| Finding | Severity |
|---|---|
| Order marked paid, captured or completed without a successful payment for that order and amount; paying less than the cart total; refund, capture or void of someone else's order | Critical |
| Using, charging, listing or deleting another user's saved payment method | Critical |
| Disclosure of secret API keys, webhook secrets, OAuth tokens, or any full PAN / CVV | Critical |
| Proven RCE, unchained, no preconditions | Critical |
| Accepted forged, replayed or cross-account webhook that changes order, customer or settings state | High (Critical if it reaches the first row) |
| XSS or SQL injection, unchained, reaching a shop manager or administrator session | High |
| Reading another customer's order, address, email, last4 or dispute data through an order key, intent id, session or REST route | High |
| An agent (Agentic Commerce) buying an excluded product, at a wrong price, or bypassing manual approval | High |
| Anything else with real security impact (IDOR on non-public data, SSRF with a demonstrated read) | Medium |
| Blind SSRF, open redirect without a token leak, missing rate limiting | Low |
| No real security impact | Informative |

### Shop manager

| Finding | Severity |
|---|---|
| Reaching secret keys, code execution, file writes, or `install_plugins` / `edit_plugins` / `unfiltered_html` | Medium to High |
| Stored XSS, SQL injection, IDOR | Low |
| Most other findings | Low |

### Rules by class

- **Validity comes before severity.** Name the actor, what they can already do through the normal interface, and
  the specific thing they gain. No gain means no finding, however real the code defect.
- **Test mode:** a finding that works only with test keys or only in dev mode is one band lower.
- **Stripe payloads:** a finding that needs Stripe itself to be malicious is out of scope; a finding that needs a
  third party to reach the webhook endpoint with a forged payload is in scope and must show how the signature check
  is passed (missing secret, weak comparison, replay window, wrong account).
- **CSRF:** needs realistic cross-origin exploitation under default `SameSite` cookie behaviour. A missing nonce on
  an action only an administrator can reach, where the attacker gains nothing they could not get by asking, is not
  a vulnerability.
- **Deserialization:** needs a real gadget in installed code; name it.
- **Race conditions** (double refund, double capture, double webhook) count only with a demonstrated outcome.
- **Logging:** full card data, CVV, secret keys or webhook secrets written to `wc-logs` or the database is High
  regardless of actor.

## How reports and patches should look

- One-sentence claim: *<actor> can <action> against <target>, which they otherwise could not.*
- An explicit actor / already holds / gains line, the least privileged role that triggers the issue, whether it
  needs registration, test mode, a specific payment method, or a non-default setting, and the severity from the
  tables above.
- Name the affected file and function, and give a self-contained reproducer: WP-CLI setup plus `curl` (for
  webhooks, include how the signature was computed), or a PHPUnit test under `tests/phpunit/`.
- Write patches as `git diff` against `/src`. Follow WordPress coding standards (`vendor/bin/phpcs` checks them)
  and use core APIs (`esc_html()`, `esc_attr()`, `wp_kses()`, `$wpdb->prepare()`, `current_user_can()`,
  `wp_verify_nonce()`, `hash_equals()`). For a REST route, fix the `permission_callback`, not the callback. Check
  whether the same fix is needed in the Store API, `wc-ajax` and REST twins of the same operation.

## Anything to leave alone

- Anything an administrator can already do, including running PHP, installing plugins and reading the stored keys.
- Findings that need `WP_DEBUG` / `display_errors` on, a plugin not installed in this image, a server
  misconfiguration, or an already-compromised host.
- Stripe.js, Elements, Checkout, Link, Apple Pay and Google Pay behaviour in the browser or on Stripe's servers.
- Behaviour of Stripe's API, dashboard or webhooks delivery, and findings that require Stripe to be malicious.
- The Apple Pay domain association file being public (it is meant to be).
- Version disclosure, order-number enumeration without data access, username enumeration, missing security
  headers, missing rate limiting on checkout or login, and clickjacking without security impact.
- Self-XSS, CSRF on login or logout, brute force, denial of service, phishing, social engineering.
- Vulnerabilities in Composer or npm `devDependencies`, unless practically exploitable remotely.
- Theoretical issues with no demonstrated, significant security impact.
