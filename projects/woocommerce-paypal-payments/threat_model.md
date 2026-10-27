# Threat model: WooCommerce PayPal Payments

## What this project does and where untrusted input enters

WooCommerce PayPal Payments (`woocommerce-paypal-payments`, "PPCP" in the code) is a WordPress plugin that lets a
WooCommerce store take payments through the merchant's own PayPal account: PayPal, Venmo and Pay Later through the
PayPal JS SDK, advanced card processing through hosted card fields, Apple Pay, Google Pay and Fastlane (the `axo`
modules), local payment methods (iDEAL, Bancontact, BLIK, EPS, MyBank, Przelewy24, Trustly, Multibanco, OXXO, Pay
upon Invoice), saved payment methods, refunds, voids and captures, order tracking, PayPal Subscriptions and
WooCommerce Subscriptions support, an onboarding flow that connects the store to PayPal through Woo's partner
referral, and an agentic "store sync" API that exposes the cart and checkout to PayPal-authenticated agents. The
plugin is modular: `bootstrap.php` and `modules.php` boot one module per feature under `modules/<name>/`
(`services.php` wires the container, `src/` holds the PHP, `resources/` the JS and SCSS that webpack builds into
`assets/`). This enrollment covers `src/`, `api/`, `lib/common/`, `modules/*/src`, `modules/*/services.php`,
`modules/*/extensions.php` and `modules/*/resources` on the `dev/develop` branch. PayPal's API, the PayPal JS SDK,
Apple Pay, Google Pay and Fastlane are out of scope, but everything they send to the plugin is untrusted input and
the plugin's handling of it is in scope.

Untrusted input enters through:

- PayPal webhooks at `/wp-json/paypal/v1/incoming` (`modules/ppcp-webhooks/src/IncomingWebhookEndpoint.php`).
  There is no local signature check: `verify_request` forwards the five `PAYPAL-*` transmission headers and the
  body to PayPal's `verify-webhook-signature` API with the merchant's bearer token
  (`modules/ppcp-api-client/src/Endpoint/WebhookEndpoint.php`, `verify_current_request_for_webhook`) and accepts
  the event only on `verification_status: SUCCESS`. Two shortcuts matter: an event whose id matches the stored
  simulation state (`modules/ppcp-webhooks/src/Status/WebhookSimulation.php`, started by a shop manager through the
  `ppc-webhooks-simulate` action) is accepted without verification, and the `PAYPAL_WEBHOOK_REQUEST_VERIFICATION`
  constant can disable verification while the store is in sandbox mode (`modules/ppcp-webhooks/services.php`).
  Once accepted, the handlers in `modules/ppcp-webhooks/src/Handler/` drive order state from the body: captures
  completed, pending, refunded and reversed, checkout orders approved and completed, vault tokens deleted, billing
  plans and subscriptions. Treat the body as attacker-controlled when reasoning about what an accepted event can
  do, and the verification call, the simulation match and the constant as the boundary.
- Shopper-facing `?wc-ajax=ppc-*` actions, one class per action under `modules/*/src/Endpoint/` (the `ENDPOINT`
  constants), registered in each module's `*Module.php`: creating, approving and changing the PayPal order for the
  current cart (`modules/ppcp-order-endpoints/src/Endpoint/CreateOrderEndpoint.php`, `ApproveOrderEndpoint.php`,
  `ChangeCartEndpoint.php`, `UpdateShippingEndpoint.php`), cart simulation and script parameters
  (`modules/ppcp-button/src/Endpoint/`), the SDK v6 client token, cart quote and simulation
  (`modules/ppcp-sdk-v6/src/Endpoint/`), vaulting (`modules/ppcp-save-payment-methods/src/Endpoint/`,
  `modules/ppcp-vault-component/src/Endpoint/CreateVaultOrderEndpoint.php`), Google Pay payment data
  (`modules/ppcp-googlepay/src/Endpoint/UpdatePaymentDataEndpoint.php`), Fastlane logging and script attributes
  (`modules/ppcp-axo/src/Endpoint/`), the subscription payment method change
  (`modules/ppcp-wc-subscriptions/src/Endpoint/SubscriptionChangePaymentMethod.php`) and the return from PayPal
  (`modules/ppcp-wc-gateway/src/Endpoint/ReturnUrlEndpoint.php`, which reads the PayPal order id from `token`).
  Each reads a JSON body and checks a nonce through `modules/ppcp-order-endpoints/src/Endpoint/RequestData.php`;
  what matters is whether the PayPal order, WooCommerce order, session and customer referenced in the request
  belong to the caller (`ApproveOrderEndpoint` compares the PayPal order's `custom_id` with the WooCommerce session
  id, `CreateOrderEndpoint` checks `key_is_valid` plus `pay_for_order` on the pay-for-order page).
- The Apple Pay admin-ajax actions `ppcp_validate`, `ppcp_create_order`, `ppcp_update_shipping_contact` and
  `ppcp_update_shipping_method` (`modules/ppcp-applepay/src/Assets/ApplePayButton.php`,
  `ApplePayDataObjectHttp.php`), open to anonymous users through `wp_ajax_nopriv_` and guarded by the WooCommerce
  checkout nonce, and the domain association file served at `/.well-known/apple-developer-merchantid-domain-association`
  (`modules/ppcp-applepay/src/ApplepayModule.php`).
- The WooCommerce checkout, cart and Store API (`/wp-json/wc/store/v1/*`) and the checkout blocks
  (`modules/ppcp-blocks/`, `modules/ppcp-axo-block/`, the `AbstractPaymentMethodType` integrations in
  `modules/ppcp-local-alternative-payment-methods/src/`), the `order-pay` page (reached with an order key) and My
  Account payment methods, through which the gateways (`modules/ppcp-wc-gateway/src/Gateway/PayPalGateway.php`,
  `CreditCardGateway.php`, `CardButtonGateway.php`, `modules/ppcp-axo/src/Gateway/AxoGateway.php`,
  `modules/ppcp-local-alternative-payment-methods/src/PayUponInvoice/PayUponInvoiceGateway.php`) receive PayPal
  order ids, saved-token ids, the `ppcp_resume_nonce` and `ppcp_resume_wc_order` 3-D Secure resume parameters and
  `ppcp-resume-order`.
- The shipping callback PayPal calls during a wallet checkout, `/wp-json/paypal/v1/shipping-callback`
  (`modules/ppcp-wc-gateway/src/Endpoint/ShippingCallbackEndpoint.php`), authenticated only by a cart token and a
  PayPal order id that resolve to a stored cart transient (`modules/ppcp-button/src/Session/CartDataTransientStorage.php`).
- The agentic store-sync REST API `/wp-json/wc/v3/agentic/merchant-cart*`
  (`modules/ppcp-store-sync/src/Endpoint/`), off by default (`PCP_STORE_SYNC_ENABLED` in `modules.php`, on in the
  integration suite): a JWT in `Authorization: Bearer`, verified against PayPal's JWKS, issuer, scopes and the
  merchant id (`modules/ppcp-store-sync/src/Auth/JwtAuthService.php`); in sandbox mode `SandboxAuthService.php`
  skips the claim checks by design. Accepted requests build carts, apply coupons, pick shipping rates and create
  WooCommerce orders from the agent's data (`modules/ppcp-store-sync/src/CartValidation/`), and the ingestion jobs
  push product data to PayPal (`modules/ppcp-store-sync/src/Ingestion/`).
- Responses from the PayPal API (`modules/ppcp-api-client/src/Endpoint/`, all through `RequestTrait.php`):
  orders, captures, refunds, payment tokens, merchant status, partner referral and credential responses, which the
  plugin stores on orders, in options and in user meta, and renders in wp-admin.
- The onboarding and connection flow (`modules/ppcp-settings/src/Handler/ConnectionListener.php`,
  `modules/ppcp-settings/src/Service/OnboardingUrl.php`, `modules/ppcp-settings/src/Service/AuthenticationManager.php`,
  `modules/ppcp-api-client/src/Endpoint/LoginSeller.php`, `modules/ppcp-api-client/src/Endpoint/PartnerReferrals.php`):
  the return from PayPal on the settings page carries `merchantIdInPayPal`, `merchantId` and `ppcpToken`, a one-time
  token bound to the connecting user and to a PKCE-style seller nonce; the REST route
  `/wc/v3/wc_paypal/authenticate/oauth` exchanges `sharedId` and `authCode` for the client id and secret, and
  `/authenticate/direct` accepts a client id and secret typed by the merchant.
- The merchant-facing REST API `/wp-json/wc/v3/wc_paypal/*` (`modules/ppcp-settings/src/Endpoint/`,
  `modules/ppcp-settings/src/Extension/ExtensionRestEndpoint.php`: settings, payment methods, styling, Pay Later
  messaging, todos, webhooks, features, login link, onboarding, migrate to ACDC), which requires
  `manage_woocommerce` (`RestEndpoint::check_permission`); the Abilities API registrations in
  `modules/ppcp-abilities/src/` (same capability, with payer PII redacted by default in
  `modules/ppcp-abilities/src/Handler/GetPaypalOrderHandler.php`); and the shop-manager `wc-ajax` actions: void
  order (`modules/ppcp-wc-gateway/src/Endpoint/VoidOrderEndpoint.php`), tracking
  (`modules/ppcp-order-tracking/src/Endpoint/OrderTrackingEndpoint.php`), webhook resubscribe and simulation
  (`modules/ppcp-webhooks/src/Endpoint/`), the Pay Later configurator (`modules/ppcp-paylater-configurator/src/Endpoint/`).
- The WordPress admin screens the plugin adds (the settings app in `modules/ppcp-settings/resources/js`, order meta
  boxes, the tracking form, admin notices with the `ppc-mute-message` action in
  `modules/ppcp-admin-notices/src/Endpoint/MuteMessageEndpoint.php`), reached by shop managers and administrators,
  and the settings-page redirects that read `page`, `tab` and `section`
  (`modules/ppcp-settings/src/Service/GatewayRedirectService.php`).
- The public PHP API in `api/order-functions.php` (`ppcp_capture_order`, `ppcp_refund_order`, `ppcp_void_order`
  and friends), which other plugins call with their own authorization; a bug there is in scope, a caller's missing
  capability check is not.

### Actors

| Actor | How they get there | Trust |
|-------|--------------------|-------|
| Anonymous shopper | none needed; guest checkout is on by default | Untrusted. High band |
| Customer | self-registered at checkout or My Account (merchant-enabled; enabled in this image) | Untrusted. High band |
| Shop manager | admin-created; holds `manage_woocommerce`, not `install_plugins`, `edit_plugins` or `unfiltered_html` | Partly trusted. Low band |
| Administrator | admin-created | Fully trusted, including code execution. Not rated, except the PCI and secrets rules below |
| PayPal (webhooks, shipping callback, API responses, onboarding return) | remote verification call, cart token, bearer token, onboarding token | Trusted party, untrusted payload. A forged, replayed or cross-account payload that is accepted is High band |
| Agent (store sync) | PayPal-issued JWT | Untrusted. High band |

## Components that matter most / least

Most important:

- Order state transitions: anything that marks an order paid, captured, refunded, voided or completed must
  correspond to a successful PayPal capture or authorization for that order and that amount, on the merchant's
  account. `modules/ppcp-wc-gateway/src/Processor/OrderProcessor.php`,
  `modules/ppcp-wc-gateway/src/Processor/AuthorizedPaymentsProcessor.php`,
  `modules/ppcp-wc-gateway/src/Processor/RefundProcessor.php`, `modules/ppcp-wc-gateway/src/Gateway/`,
  `modules/ppcp-webhooks/src/Handler/`, `modules/ppcp-order-endpoints/src/`.
- Order, PayPal order and customer binding: a PayPal order id, order key, session id, cart token or saved token
  that lets one shopper act on, pay for, or read another shopper's order or payment method. Compare the ids in the
  request with the WooCommerce order, the session (`modules/ppcp-session/src/SessionHandler.php`,
  `modules/ppcp-order-endpoints/src/Helper/EarlyOrderHandler.php`) and what PayPal returns.
- Saved payment methods (`modules/ppcp-wc-payment-tokens/src/WcPaymentTokensModule.php`,
  `modules/ppcp-save-payment-methods/`, `modules/ppcp-vault-component/`, the `_ppcp_target_customer_id` user
  meta): using, listing or deleting another user's token; attaching a payment token to the wrong PayPal customer;
  changing the payment method of another user's subscription (`modules/ppcp-wc-subscriptions/`,
  `modules/ppcp-paypal-subscriptions/`).
- Secrets: the client id and secret, merchant id and webhook id in the `woocommerce-ppcp-settings` and
  `woocommerce-ppcp-data-*` options (`modules/ppcp-settings/src/Data/GeneralSettings.php`), the cached bearer
  token (`modules/ppcp-api-client/src/Authentication/PayPalBearer.php`), SDK client tokens, the onboarding token
  and seller nonce, and the reCAPTCHA secret keys (`modules/ppcp-fraud-protection/src/Recaptcha/Recaptcha.php`).
  Any path that exposes them to a lower-privileged user, writes them to logs (`modules/woocommerce-logging/`), or
  lets a non-administrator change them. Card data never touches the plugin by design (hosted card fields and the
  wallets tokenize in the browser); any path that logs, stores or echoes a full PAN or CVV is a PCI boundary
  (`modules/ppcp-card-fields/`, `modules/ppcp-wc-gateway/src/Gateway/CreditCardGateway.php`).
- Webhook acceptance: the remote verification call and how its failure is handled, the simulation shortcut, the
  constant, replay of an already-processed event, an event for another merchant's order.
- Authorization on the REST controllers and `wc-ajax` actions: a `manage_woocommerce` check where per-object
  ownership is needed, a shopper action that reaches a merchant-only operation, an onboarding or settings route
  that forwards requests to PayPal with the merchant's credentials on behalf of a lower-privileged caller.
- Wallet, callback and agent flows: cart, address, shipping and coupon data from the Apple Pay and Google Pay
  sheets, the SDK v6 cart quote (`modules/ppcp-sdk-v6/src/Endpoint/CartQuoteEndpoint.php`), the shipping callback,
  and the store-sync validators (price, inventory, coupon, currency, shipping in
  `modules/ppcp-store-sync/src/CartValidation/`): paying less than the cart total, a coupon the caller cannot
  have, stock bypass, an order created for another customer.
- Onboarding: the one-time token and seller nonce binding in `OnboardingUrl.php` and `ConnectionListener.php`,
  the stored OAuth details, and the redirects on the settings page.
- Output escaping in wp-admin screens and the storefront that render PayPal data (payer names, order notes,
  tracking numbers, Pay Later messaging configuration, product data echoed back from store sync).

Out of scope: `vendor/` (Composer packages), `node_modules/`, `assets/` (built output; patch `modules/*/resources/`
instead), `lib/packages/` (Mozart-prefixed copies of `inpsyde/modularity` and `psr/container`), `tests/`, `stubs/`,
`docs/`, `wordpress_org_assets/`, `.ddev/`, `.github/`, `.claude/`, the PayPal JS SDK, PayPal's API and dashboard,
Apple Pay, Google Pay, Fastlane and reCAPTCHA. WooCommerce core and WordPress core findings belong to their own
enrollments; report them only if this plugin's use of them creates the bug.

## How to exercise it

- Run `wp-start` first. It starts MariaDB and Apache. The store is at `http://127.0.0.1/`, with pretty permalinks,
  Storefront, one simple product, and the checkout, cart, shop and My Account pages installed. `wp-stop` stops both.
- PHP errors, warnings and deprecations from Apache and the CLI go to `/var/log/php-error.log`; Apache's own logs are
  under `/var/log/apache2/`. The plugin's own log goes through WooCommerce's logger (`wp wc` has no log command; read
  `/var/www/html/wp-content/uploads/wc-logs/`).
- Users: `admin` / `admin` (administrator), `shopmanager` / `shopmanager` (shop_manager), `customer` / `customer`
  (customer). Registration at checkout and on My Account is enabled. Guest checkout is enabled.
- `wp --path=/var/www/html ...` (WP-CLI) sets up content, options, users and orders. `wp --path=/var/www/html wc
  ...` drives the WooCommerce REST API. `wp --path=/var/www/html eval '...'` runs PHP in a loaded WordPress; the
  plugin's container is `WooCommerce\PayPalCommerce\PPCP::container()` once `plugins_loaded` has fired.
- The plugin is at `/var/www/html/wp-content/plugins/woocommerce-paypal-payments`, a symlink to `/src`, so a patch
  to `/src` takes effect on the next request. JS and SCSS changes under `modules/*/resources/` need `npm run build`
  (offline: `node_modules` are already installed).
- The store is not connected to PayPal and the scan runs without network. To exercise the gateways, connect with
  fake sandbox credentials through the settings REST route (`POST /wp-json/wc/v3/wc_paypal/authenticate/direct`
  with `clientId`, `clientSecret` and `useSandbox`) or by writing the `woocommerce-ppcp-settings` option, and expect
  every call through `modules/ppcp-api-client/src/Endpoint/RequestTrait.php` to fail; reason about the request the
  plugin would send and the response it would accept, and replace the `api.endpoint.order`, `api.endpoint.webhook`
  and sibling services through the container in a test (`tests/integration/PHPUnit/IntegrationMockedTestCase.php`,
  `bootstrapModule`, shows how) to drive the rest of the flow. Webhook handling cannot be verified end to end
  offline, because verification is a call to PayPal: show how the verification result is bypassed or misread, or
  drive `IncomingWebhookEndpoint::handle_request` with a mocked `WebhookEndpoint`.
- PHPUnit, unit suite: `cd /src && vendor/bin/phpunit --configuration phpunit.xml.dist --filter <TestName>`. It runs
  on Brain Monkey with the stubs in `tests/stubs/` and needs neither WordPress nor MariaDB. Tests live in
  `tests/PHPUnit/`, one directory per module.
- PHPUnit, integration suite: `cd /src && vendor/bin/phpunit --configuration tests/integration/phpunit.xml.dist
  --filter <TestName>`, with MariaDB running. It loads the WordPress copy in `/tmp/wordpress` (database
  `ppcp_tests`, plugin active, `PPCP_INTEGRATION_WP_DIR` in `/src/.env.integration`) and uses WooCommerce, the
  container and the real endpoints with the PayPal API services replaced. `tests/integration/PHPUnit/setup.php`
  seeds the tax options and `tests/integration/data/tax_rates.csv` the totals tests rely on; it ran during the
  build, rerun it if `PurchaseUnitTest` reports wrong totals. `tests/integration/PHPUnit/Traits/HandlesWcAjaxEndpoints.php`
  shows how to drive a `wc-ajax` endpoint from a test. The tests under `tests/integration/PHPUnit/PayPalSubscriptions/`
  need WooCommerce Subscriptions, which is not installed, and fail for that reason.
- JavaScript: `npm run test:unit-js` runs the Jest suites next to the sources in `modules/*/resources/js`.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate administrator would: create users at their real roles, set real options, add
products and orders. Drive the attack as the claimed actor, through the normal interface. Do not mint a nonce as an
administrator, mark an order paid through WP-CLI, give the attacker a capability they are supposed to gain, start a
webhook simulation as a shop manager to get an event accepted, or forge a webhook without showing how the
verification result is bypassed. Reading the database to observe the outcome is fine. For XSS, show the payload
executes in a browser context in the victim's role.

## How you rate severity

Two questions settle the band, in this order: (1) can the attacker act without a merchant-created account
(anonymous or self-registered customer is the high band; shop manager is the low band; administrator is not
rated), and (2) is the chain real and unconditional in a default configuration with this gateway enabled and
connected.

### Anonymous shopper, or a self-registered customer

| Finding | Severity |
|---|---|
| Order marked paid, captured or completed without a successful payment for that order and amount; paying less than the cart total; refund, capture or void of someone else's order | Critical |
| Using, charging, listing or deleting another user's saved payment method, or changing the payment method on another user's subscription | Critical |
| Disclosure of the client secret, bearer tokens, the onboarding token, webhook ids with the ability to use them, or any full PAN / CVV | Critical |
| Proven RCE, unchained, no preconditions | Critical |
| Accepted forged, replayed or cross-merchant webhook, shipping callback or store-sync request that changes order, customer or settings state | High (Critical if it reaches the first row) |
| XSS or SQL injection, unchained, reaching a shop manager or administrator session | High |
| Reading another customer's order, address, email, payer details or tracking data through an order key, PayPal order id, cart token, session or REST route | High |
| An agent (store sync) or wallet flow buying at a price the merchant did not set, with a coupon it cannot have, or past stock and shipping validation | High |
| Anything else with real security impact (IDOR on non-public data, SSRF with a demonstrated read) | Medium |
| Blind SSRF, open redirect without a token leak, missing rate limiting | Low |
| No real security impact | Informative |

### Shop manager

| Finding | Severity |
|---|---|
| Reaching the client secret or bearer token, code execution, file writes, or `install_plugins` / `edit_plugins` / `unfiltered_html` | Medium to High |
| Stored XSS, SQL injection, IDOR | Low |
| Most other findings | Low |

### Rules by class

- **Validity comes before severity.** Name the actor, what they can already do through the normal interface, and
  the specific thing they gain. No gain means no finding, however real the code defect.
- **Sandbox mode:** a finding that works only with sandbox credentials (including the store-sync
  `SandboxAuthService` shortcut), only with `PAYPAL_WEBHOOK_REQUEST_VERIFICATION` disabled, or only with a
  `PCP_*` feature flag changed from its default is one band lower.
- **PayPal payloads:** a finding that needs PayPal itself to be malicious is out of scope; a finding that needs a
  third party to reach the webhook endpoint, the shipping callback or the store-sync API with a forged payload is
  in scope and must show how the check is passed (simulation id, verification response misread, missing webhook
  id, guessable cart token, JWT claim not checked).
- **CSRF:** needs realistic cross-origin exploitation under default `SameSite` cookie behaviour. A missing nonce on
  an action only an administrator can reach, where the attacker gains nothing they could not get by asking, is not
  a vulnerability.
- **Deserialization:** needs a real gadget in installed code; name it.
- **Race conditions** (double refund, double capture, double webhook) count only with a demonstrated outcome.
- **Logging:** full card data, CVV, the client secret or bearer tokens written to `wc-logs` or the database is High
  regardless of actor.

## How reports and patches should look

- One-sentence claim: *<actor> can <action> against <target>, which they otherwise could not.*
- An explicit actor / already holds / gains line, the least privileged role that triggers the issue, whether it
  needs registration, sandbox mode, a connected store, a specific payment method or feature flag, or a non-default
  setting, and the severity from the tables above.
- Name the affected module, file and function, and give a self-contained reproducer: WP-CLI setup plus `curl` (for
  `wc-ajax` actions, include the JSON body and where the nonce came from), or a PHPUnit test under `tests/PHPUnit/`
  (Brain Monkey) or `tests/integration/PHPUnit/` (real WordPress).
- Write patches as `git diff` against `/src`. Follow the repository's coding standards (`vendor/bin/phpcs` with
  `phpcs.xml.dist`, `vendor/bin/phpstan` with `phpstan.neon`, PHP 7.4 syntax) and use core APIs (`esc_html()`,
  `esc_attr()`, `wp_kses()`, `$wpdb->prepare()`, `current_user_can()`, `wp_verify_nonce()`, `hash_equals()`). For a
  REST route, fix the `permission_callback`, not the callback; for a `wc-ajax` action, fix the check before the
  work. Check whether the same fix is needed in the classic checkout, the blocks checkout, the Apple Pay and
  Google Pay paths, and the SDK v6 twins of the same operation.

## Anything to leave alone

- Anything an administrator can already do, including running PHP, installing plugins and reading the stored
  credentials.
- Findings that need `WP_DEBUG` / `display_errors` on, a plugin not installed in this image, a server
  misconfiguration, or an already-compromised host.
- The PayPal JS SDK, hosted card fields, Fastlane, Apple Pay and Google Pay behaviour in the browser or on their
  servers.
- Behaviour of PayPal's API, dashboard or webhook delivery, and findings that require PayPal to be malicious.
- The partner client ids and merchant ids defined in `woocommerce-paypal-payments.php` (`CONNECT_WOO_CLIENT_ID`
  and siblings): they are public identifiers of Woo's partner integration, not secrets.
- The Apple Pay domain association file being public (it is meant to be).
- Version disclosure, order-number enumeration without data access, username enumeration, missing security
  headers, missing rate limiting on checkout or login, and clickjacking without security impact.
- Self-XSS, CSRF on login or logout, brute force, denial of service, phishing, social engineering.
- Vulnerabilities in Composer or npm `devDependencies`, unless practically exploitable remotely.
- Theoretical issues with no demonstrated, significant security impact.
