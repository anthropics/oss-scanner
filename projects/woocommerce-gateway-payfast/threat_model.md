# Threat model: WooCommerce Payfast Gateway

## What this project does and where untrusted input enters

WooCommerce Payfast Gateway (`woocommerce-gateway-payfast`) is a WordPress plugin that lets a WooCommerce store take
payments through the merchant's Payfast account, a South African processor. It is a redirect gateway: at checkout
the shopper is sent to Payfast with a signed form, pays there, and Payfast reports the result back to the store
with an Instant Transaction Notification (ITN). Only South African rand (ZAR) orders are accepted. The plugin also
charges WooCommerce Subscriptions renewals through Payfast's subscriptions API with a token stored on the
subscription, integrates with the Checkout block, and exports and erases personal data for the privacy tools. This
enrollment covers `woocommerce-gateway-payfast.php`, `gateway-payfast.php`, `includes/` and `src/blocks/` on the
`trunk` branch. Payfast's hosted payment page, sandbox and API are out of scope, but everything they send to the
plugin is untrusted input and the plugin's handling of it is in scope.

Untrusted input enters through:

- The ITN endpoint `?wc-api=WC_Gateway_PayFast` (`includes/class-wc-gateway-payfast.php`, `check_itn_response()`
  and `handle_itn_request()`): a POST with no WordPress authentication, answered with HTTP 200 whatever happens. The
  checks run in this order: (1) `validate_signature()`, an MD5 over the posted fields in the order they were posted
  plus the stored passphrase (`_generate_parameter_string()`), compared with `===`; (2) in live mode only,
  `is_valid_ip()`: `REMOTE_ADDR`, or the first address of an `X-Forwarded-For` header when one is present, whoever
  sent it, against Payfast's published ranges and the addresses its hostnames resolve to. Sandbox mode (the
  `testmode` setting, on by default and in this image) skips this step; (3) `validate_response_data()`: the fields
  are posted back to Payfast's validate URL and the answer must contain `VALID`; (4) `amounts_equal()` against the
  order total with a 0.01 tolerance, the order currency must be ZAR, and `custom_str1` must equal the order key,
  where a `renewal_order_id` inside the JSON `item_description` field moves the amount check to a renewal order
  while the key check stays on the order named by `custom_str3`; (5) an order already `completed` is not processed
  again. After that, `payment_status` decides: COMPLETE calls `payment_complete()`, stores `payfast_amount_fee` and
  `payfast_amount_net` from the body and writes `token` to the subscriptions of the order; FAILED, PENDING and
  CANCELLED change the order (and, for CANCELLED, the subscriptions). The `custom_str4=change_pay_method` branch
  stores a token on a subscription before the amount check runs. Treat the body as attacker-controlled when
  reasoning about what an accepted notification can do, and the passphrase signature plus Payfast's validation
  answer as the boundary: the IP check is off in sandbox mode and trusts `X-Forwarded-For`.
- The pay-for-order (receipt) page: `receipt_page()` and `generate_payfast_form()` read `$_GET['key']` (compared
  with `hash_equals()` to the order key, plus the `pay_for_order` capability) and `$_GET['change_pay_method']`, and
  print the auto-submitting form: merchant id, merchant key, billing name and email, amount, order id and key,
  return, cancel and notify URLs, and the MD5 signature computed with the passphrase. `process_payment()` reads
  `$_GET['change_payment_method']`. The `woocommerce_gateway_payfast_payment_data_to_send` filter lets other code
  change what is signed.
- The WooCommerce checkout, both the shortcode form and the Checkout block (`src/blocks/payment-method/`,
  `includes/class-wc-gateway-payfast-blocks-support.php`), the Store API, the order-received page built by
  `get_payfast_return_url()` and reached with the order key, and the cancel-order URL.
- Responses from Payfast's API (`api_request()`, `https://api.payfast.co.za/subscriptions/<token>/<command>`, signed
  with the passphrase; `validate_payfast_credentials()`, a ping made when the credentials change), which the plugin
  logs and turns into order notes and statuses.
- Data the plugin stored earlier from Payfast and acts on later: `_payfast_subscription_token`,
  `_payfast_renewal_flag` and the legacy `_payfast_pre_order_token` on orders and subscriptions, used by
  `scheduled_subscription_payment()` (the `woocommerce_scheduled_subscription_payment_payfast` hook, run by Action
  Scheduler), `cancel_subscription_listener()` and `maybe_cancel_subscription_token()`.
- The settings page (WooCommerce > Settings > Payments > Payfast, behind `manage_woocommerce`) and the WooCommerce
  REST route `/wp-json/wc/v3/payment_gateways/payfast`. The credentials and the sandbox switch need
  `manage_options` (`can_manage_credentials()`, `protect_credential_settings()`,
  `redact_rest_credential_settings()`, filter `woocommerce_gateway_payfast_credentials_capability`); the other
  settings need `manage_woocommerce` only.
- wp-admin screens that render Payfast data: the order totals box (`display_order_fee()`, `display_order_net()`
  print ITN-supplied meta), the admin notices, and the privacy exporter and eraser in
  `includes/class-wc-gateway-payfast-privacy.php`, run by an administrator.
- Logs and emails: in sandbox mode, or with logging on, `log()` writes every ITN body, the validate exchange and
  the API responses to the `payfast` WooCommerce log; on an ITN error in sandbox mode with debug emails on, an email
  with the remote address, `gethostbyaddr()` of it and the ITN values goes to the configured address.

### Actors

| Actor | How they get there | Trust |
|-------|--------------------|-------|
| Anonymous shopper | none needed; guest checkout is on by default, and the ITN endpoint and pay page need no login | Untrusted. High band |
| Customer | self-registered at checkout or My Account (merchant-enabled; enabled in this image) | Untrusted. High band |
| Shop manager | admin-created; holds `manage_woocommerce`, so every Payfast setting except the credentials and the sandbox switch, not `install_plugins`, `edit_plugins` or `unfiltered_html` | Partly trusted. Low band |
| Administrator | admin-created | Fully trusted, including code execution. Not rated, except the secrets rules below |
| Payfast (ITN, API responses) | passphrase signature, the validate call, source IP in live mode | Trusted party, untrusted payload. A forged, replayed or cross-order ITN that is accepted is High band |

## Components that matter most / least

Most important:

- Order state transitions: anything that marks an order paid or completed, or that fails, holds or cancels an
  order or a subscription, must correspond to a Payfast transaction for that order and that amount, on the
  merchant's account. `handle_itn_request()`, `handle_itn_payment_complete()`, `handle_itn_payment_failed()`,
  `handle_itn_payment_pending()`, `handle_itn_payment_cancelled()`.
- ITN authentication and binding: what the signature covers (posted order, empty values kept, the passphrase, the
  `===` comparison), replay (only a `completed` order stops a second COMPLETE; a pending, on-hold or failed order
  is processed again), the three ways an order is named (`custom_str3`, `custom_str1`, `renewal_order_id` in
  `item_description`), the validate call and what a `VALID` answer proves, the IP check with its
  `X-Forwarded-For` handling and its absence in sandbox mode, and the `change_pay_method` branch.
- Secrets: `merchant_id`, `merchant_key` and `pass_phrase` in the `woocommerce_payfast_settings` option. The
  passphrase signs every ITN and API call; any path that shows it to a shop manager (settings HTML, the REST
  route), writes it to the log or an email, or lets a non-administrator change it or the sandbox switch, matters.
  The merchant key is placed in the public redirect form by Payfast's protocol and is not a secret; the passphrase
  must never be. Card data never touches the plugin: the shopper pays on Payfast's page.
- Subscription tokens: a token stored from an ITN charges the shopper's Payfast account on every renewal
  (`submit_subscription_payment()`, `submit_ad_hoc_payment()`). Writing a token to the wrong subscription,
  cancelling or reusing someone else's token (`cancel_subscription_listener()`,
  `_is_subscription_token_used_by_another_active_subscription()`), or charging an amount that is not the
  renewal's.
- Authorization: the key and capability check in `generate_payfast_form()`, the credential and setting split in
  the settings and REST paths, and the privacy eraser.
- Outbound requests: `api_request()` builds the URL from the stored token, `validate_response_data()` posts the ITN
  body back to Payfast, and the credential ping; what a token or a filtered payload can do to those URLs and
  signatures.
- Output escaping in wp-admin for Payfast-supplied values: the fee and net totals, the sandbox notice that echoes
  the merchant id and key, admin notices, and the data handed to the Checkout block script.

Out of scope: `vendor/` (Composer dev tooling), `node_modules/`, `build/` (built output; patch `src/blocks/`
instead), `tests/`, `wordpress_org_assets/`, `.github/`, Payfast's payment page, sandbox and API, WooCommerce
Subscriptions and WooCommerce Pre-Orders (not installed in this image; their own code is Automattic's and reports
about it go through the same program, against those products). WooCommerce core and WordPress core findings belong
to their own enrollments; report them only if this plugin's use of them creates the bug.

## How to exercise it

- Run `wp-start` first. It starts MariaDB and Apache. The store is at `http://127.0.0.1/`, with pretty permalinks,
  Storefront, one simple product at R100, and the checkout, cart, shop and My Account pages installed. `wp-stop`
  stops both.
- PHP errors, warnings and deprecations from Apache and the CLI go to `/var/log/php-error.log`; Apache's own logs are
  under `/var/log/apache2/`; the plugin's own log is `wp-content/uploads/wc-logs/payfast-*.log` under
  `/var/www/html` (sandbox mode logs every ITN).
- Users: `admin` / `admin` (administrator), `shopmanager` / `shopmanager` (shop_manager), `customer` / `customer`
  (customer). Registration at checkout and on My Account is enabled. Guest checkout is enabled.
- `wp --path=/var/www/html ...` (WP-CLI) sets up content, options, users and orders. `wp --path=/var/www/html wc
  ...` drives the WooCommerce REST API. `wp --path=/var/www/html eval '...'` runs PHP in a loaded WordPress.
- The plugin is at `/var/www/html/wp-content/plugins/woocommerce-gateway-payfast`, a symlink to `/src`, so a patch
  to `/src` takes effect on the next request. Block changes need `npm run build:webpack` (offline: `node_modules`
  are already installed).
- The gateway is enabled, in sandbox mode, with placeholder credentials (merchant id `00000000`, merchant key
  `scanner-merchant-key`, passphrase `scanner-passphrase`); they are not a Payfast account. Payfast shows at
  checkout, and placing an order lands on the order-pay page, whose form auto-submits to
  `sandbox.payfast.co.za`, which is unreachable without network. Fetch that page with `curl` (as the customer, or
  as a guest with the order key) to see exactly what the plugin signs. Change the settings with `wp option update
  woocommerce_payfast_settings --format=json '{...}'`; saving credentials triggers `validate_payfast_credentials()`,
  which fails offline and may set `woocommerce_payfast_invalid_credentials`, so delete that option afterwards.
- ITN handling can be exercised end to end. POST form fields to `http://127.0.0.1/?wc-api=WC_Gateway_PayFast` with
  `signature` set to `md5()` of `key=urlencode(value)` pairs joined by `&`, in the order posted and without the
  `signature` field, followed by `&passphrase=urlencode(passphrase)` (`_generate_parameter_string($data, false,
  false)`). The handler then posts the fields to Payfast's validate URL, which fails offline: a must-use plugin that
  filters `pre_http_request` and returns `array( 'body' => 'VALID' )` for that URL, as
  `tests/e2e/test-plugins/payfast-webhook-faker/` does, drives the rest of the flow. Say in a report which of the
  checks the attacker passes and how. Set `testmode` to `no` to exercise `is_valid_ip()`; DNS lookups fail offline,
  the hardcoded ranges still apply, and `X-Forwarded-For` is honoured.
- WooCommerce Subscriptions is not installed. The `wcs_*` paths are guarded with `function_exists()`, so renewal,
  cancellation and token code is reachable only by reading it or by installing a copy you bring; renewals go through
  `api_request()`, which fails offline and marks the renewal order failed.
- There is no PHPUnit suite; `tests/` holds Playwright end-to-end tests that need a browser and a Payfast sandbox
  account. The checks that run offline are `vendor/bin/phpcs -p --standard=phpcs-compat.xml.dist
  '--ignore=*/vendor/*,*/node_modules/*,*/build/*,*/tests/*' .` (PHP 7.4 to 8.4 compatibility) and `npm run phpcs`
  (WooCommerce coding standards; it reports pre-existing warnings on `trunk`). For a reproducer, use WP-CLI plus
  `curl`, or a short PHP script run with `wp eval-file`.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate administrator would: create users at their real roles, set real options, add
products and orders. Drive the attack as the claimed actor, through the normal interface. Do not read the
passphrase out of the database to sign a notification unless the finding is that the passphrase leaks, do not
mark an order paid through WP-CLI, do not give the attacker a capability they are supposed to gain, and do not
mock the validate call silently: a finding that needs `validate_response_data()` stubbed is a finding about what a
validated notification can still do (wrong order, wrong amount, replay), and must say so. Reading the database to
observe the outcome is fine. For XSS, show the payload executes in a browser context in the victim's role.

## How you rate severity

Two questions settle the band, in this order: (1) can the attacker act without a merchant-created account
(anonymous or self-registered customer is the high band; shop manager is the low band; administrator is not
rated), and (2) is the chain real and unconditional in a default configuration with this gateway enabled.

### Anonymous shopper, or a self-registered customer

| Finding | Severity |
|---|---|
| Order marked paid or completed without a Payfast transaction for that order and amount; paying less than the order total; failing, holding or cancelling someone else's order or subscription through the ITN endpoint | Critical |
| Charging another shopper's Payfast subscription token, moving a token between subscriptions, or cancelling another shopper's subscription at Payfast | Critical |
| Disclosure of the passphrase or of the stored settings to a lower-privileged user | Critical |
| Proven RCE, unchained, no preconditions | Critical |
| Accepted forged, replayed or cross-order notification that changes order, subscription or settings state | High (Critical if it reaches the first row) |
| XSS or SQL injection, unchained, reaching a shop manager or administrator session | High |
| Reading another customer's order, name, email or address through the order key, the return URL, the receipt page or a REST route | High |
| Anything else with real security impact (IDOR on non-public data, SSRF with a demonstrated read, for example through the token in the API URL) | Medium |
| Blind SSRF, open redirect without a token leak, missing rate limiting | Low |
| No real security impact | Informative |

### Shop manager

| Finding | Severity |
|---|---|
| Reaching the passphrase or the sandbox switch, code execution, file writes, or `install_plugins` / `edit_plugins` / `unfiltered_html` | Medium to High |
| Stored XSS, SQL injection, IDOR | Low |
| Most other findings | Low |

### Rules by class

- **Validity comes before severity.** Name the actor, what they can already do through the normal interface, and
  the specific thing they gain. No gain means no finding, however real the code defect.
- **Sandbox mode:** a finding that works only in sandbox mode is one band lower; a live store runs with it off. The
  IP check being skipped in sandbox mode is by design and not a finding on its own.
- **Payfast payloads:** a finding that needs Payfast itself to be malicious is out of scope; a finding that needs a
  third party to reach the ITN endpoint with a forged payload is in scope and must show how both the signature and
  the validate call are passed (passphrase known, empty or leaked; a replayed real notification; a notification
  for one order accepted against another). The MD5 signature scheme is Payfast's protocol; a finding about it must
  show a practical forgery, not the choice of hash.
- **CSRF:** needs realistic cross-origin exploitation under default `SameSite` cookie behaviour. A missing nonce on
  an action only an administrator can reach, where the attacker gains nothing they could not get by asking, is not
  a vulnerability.
- **Deserialization:** needs a real gadget in installed code; name it.
- **Race conditions** (two notifications for one order, renewal and ITN crossing) count only with a demonstrated
  outcome.
- **Logging:** the passphrase or the settings option written to `wc-logs`, the database or an email is High
  regardless of actor. ITN bodies in the log in sandbox mode are expected.

## How reports and patches should look

- One-sentence claim: *<actor> can <action> against <target>, which they otherwise could not.*
- An explicit actor / already holds / gains line, the least privileged role that triggers the issue, whether it
  needs registration, sandbox mode, Subscriptions, or a non-default setting, and the severity from the tables
  above.
- Name the affected file and function, and give a self-contained reproducer: WP-CLI setup plus `curl` (for a
  notification, include the exact fields in order and how the signature was computed, and say whether the validate
  call was stubbed), or a PHP script for `wp eval-file`.
- Write patches as `git diff` against `/src`. Follow WordPress coding standards (`npm run phpcs` checks them) and
  use core APIs (`esc_html()`, `esc_attr()`, `wp_kses()`, `$wpdb->prepare()`, `current_user_can()`,
  `wp_verify_nonce()`, `hash_equals()`). Keep the ITN validation sequence intact and add to it rather than
  reordering it; the repository's `AGENTS.md` treats it as a contract with Payfast's servers. Check whether the same
  fix is needed on the shortcode checkout, the Checkout block and the REST twin of the same setting.

## Anything to leave alone

- Anything an administrator can already do, including running PHP, installing plugins and reading the stored
  settings.
- Findings that need `WP_DEBUG` / `display_errors` on, a plugin not installed in this image, a server
  misconfiguration, or an already-compromised host.
- Payfast's hosted payment page, sandbox and API behaviour, and findings that require Payfast to be malicious.
- The merchant key in the redirect form and the merchant id and key in the sandbox settings notice: Payfast's
  protocol puts them there, and they are not secrets. The passphrase is.
- Version disclosure, order-number enumeration without data access, username enumeration, missing security
  headers, missing rate limiting on checkout, login or the ITN endpoint, and clickjacking without security impact.
- Self-XSS, CSRF on login or logout, brute force, denial of service, phishing, social engineering.
- Vulnerabilities in Composer or npm `devDependencies`, unless practically exploitable remotely.
- Theoretical issues with no demonstrated, significant security impact.
