# Threat model: WooCommerce core

## What this project does and where untrusted input enters

WooCommerce is an open-source ecommerce plugin for WordPress: a product catalog, cart, checkout, orders, customer
accounts, coupons, shipping, taxes, downloadable products, a REST API, a Store API for the block-based checkout,
webhooks, an importer and exporter, reports and analytics, and the wp-admin screens for all of it. This enrollment
covers the plugin under `plugins/woocommerce/` on `trunk`: `includes/`, `src/`, `templates/`, `client/` (built
into `assets/`), and the WooCommerce-maintained packages under `packages/` and `plugins/woocommerce/packages/`
(Action Scheduler, Blueprint, email editor). Everything else in the monorepo is tooling and out of scope.

Untrusted input enters through:

- Front-end requests from anonymous shoppers: shop, product and category pages (query vars, search, ordering,
  filters), add to cart, cart, checkout (`includes/class-wc-checkout.php`, `includes/class-wc-form-handler.php`),
  the `order-pay` and `order-received` pages reached with an order key, product reviews (comments), the
  downloadable-file endpoint (`includes/class-wc-download-handler.php`), shortcodes
  (`includes/shortcodes/`), widgets, and the session handler (`includes/class-wc-session-handler.php`).
- `?wc-ajax=` actions (`includes/class-wc-ajax.php`), many registered without a login (`nopriv`): refreshed
  fragments, apply and remove coupon, update shipping method, update order review, add to cart, checkout.
- The Store API, `/wp-json/wc/store/v1/*` (`src/StoreApi/`): cart, checkout, products, orders, anonymous by
  design with Cart-Token and nonce handling.
- The REST API, `/wp-json/wc/v3/*` and `/wp-json/wc-analytics/*` and `/wp-json/wc-admin/*`
  (`includes/rest-api/`, `src/Admin/API/`, `src/Internal/RestApi/`), authenticated by cookie + nonce, by
  consumer key/secret (`includes/class-wc-rest-authentication.php`, read or read/write keys bound to a user), or
  by application passwords.
- The `?wc-api=` endpoint (`woocommerce_api_{endpoint}` action), through which payment gateways receive callbacks
  and legacy integrations post data.
- My Account forms: registration, login, lost password, edit address, edit account, payment methods.
- Content from lower-privileged users that is later rendered to shop managers or administrators: order notes,
  checkout fields, billing and shipping addresses, product reviews, customer names, order attribution data.
- Files: product CSV import (`includes/import/`), tax rate import, product images and downloadable files, the
  Blueprint importer (`packages/php/blueprint/`), uploaded media handled through WordPress.
- Data fetched from remote servers: geolocation databases, the WooCommerce.com marketplace and update API,
  webhooks delivery responses, oEmbed through WordPress.
- The Abilities and MCP surfaces (`src/Abilities/`, `src/Internal/Abilities/`, `src/Internal/MCP/`), reached by
  agents through REST with a user's credentials.

### Actors

| Actor | How they get there | Trust |
|-------|--------------------|-------|
| Anonymous shopper | none needed; guest checkout is on by default | Untrusted. High band |
| Customer | self-registered at checkout or My Account (merchant-enabled; enabled in this image) | Untrusted. High band |
| Subscriber, Contributor, Author | WordPress roles, as in WordPress core's threat model | Untrusted beyond their capabilities. Subscriber high band if self-registration is on; Contributor and Author low band |
| REST API key with read permission | created by a shop manager or administrator and handed to an integration | Untrusted for writes. A read key reaching a write is a boundary |
| Shop manager | admin-created; holds `manage_woocommerce`, `edit_users`-class capabilities over customers, `edit_theme_options`; not `install_plugins`, `edit_plugins`, `edit_themes` or `unfiltered_html` | Partly trusted. Low band. Reaching any of those four capabilities, code execution or file writes crosses a boundary |
| Editor (single site) | admin-created | Trusted with raw HTML (`unfiltered_html`); not rated for XSS |
| Administrator | admin-created | Fully trusted, including code execution. Not rated, except the PCI rule below |
| Payment gateway / webhook consumer | `?wc-api=` callback, webhook delivery | Trusted party, untrusted payload |

Self-registration: say in every report whether the finding needs it. Guest checkout creates no account, but an
order key gives a guest access to one order; the order key is the boundary.

## Components that matter most / least

Most important:

- Capability and ownership checks: `current_user_can()` with WooCommerce capabilities, REST `permission_callback`s,
  Store API route permissions, and order and customer ownership checks (order key, customer id, session). A
  common real defect is a permission callback that checks a global capability instead of per-object ownership;
  compare against a sibling route that does it correctly.
- Secondary read paths: the same order or customer data is reachable through the REST API, the Store API,
  `wc-ajax`, My Account, the `order-received` page, webhooks and reports. A check enforced on one path is often
  missing on its twins.
- Money: anything that changes the amount a shopper pays, lets an order be marked paid or completed without
  payment, applies a coupon the shopper should not get, changes stock without a sale, or lets a shopper read or
  act on another shopper's order. `includes/class-wc-cart.php`, `includes/class-wc-checkout.php`,
  `includes/class-wc-order.php`, `src/StoreApi/Routes/V1/Checkout.php`, `includes/class-wc-coupon.php`,
  `includes/class-wc-discounts.php`.
- Downloadable products: the download handler, permission records, and file path handling (local paths, remote
  URLs, path traversal).
- Output escaping and `kses` in templates (`templates/`), admin list tables and meta boxes, emails
  (`includes/emails/`), and anything that renders customer-provided strings to a shop manager or administrator.
- SQL built through `$wpdb`, the HPOS data stores (`src/Internal/DataStores/Orders/`), analytics queries
  (`src/Admin/API/Reports/`), and anything that accepts `orderby`, `order` or filters from a request.
- File handling: product CSV importer (server path traversal, remote file fetch), tax rate importer, downloadable
  file uploads, the Blueprint importer, the logger (`src/Internal/Admin/Logging/`, file names and paths).
- Authentication: REST consumer key/secret handling, API key generation and storage, session cookies, the
  customer-login and lost-password flows, email verification on order pages.
- `unserialize()` of anything a lower-privileged user can influence; `maybe_unserialize()` on meta.
- Webhooks (`includes/class-wc-webhook.php`): delivery URL (SSRF to internal hosts), payload scope, secret handling.

Out of scope: third-party libraries vendored into the plugin (`plugins/woocommerce/vendor/`,
`plugins/woocommerce/lib/`, `includes/libraries/`, `node_modules/`), except where the way WooCommerce uses them
creates the vulnerability. `plugins/woocommerce/tests/`, `plugins/woocommerce-beta-tester/`, `tools/`, `.github/`,
`docs/`, `packages/js/` tooling and the monorepo build are out of scope unless they introduce a vulnerability
into the built plugin that stores run. WordPress core findings belong to the WordPress enrollment; report them
only if WooCommerce's use of core creates the bug.

## How to exercise it

- Run `wp-start` first. It starts MariaDB and Apache. The store is at `http://127.0.0.1/`, with pretty permalinks,
  Storefront, a simple product, a downloadable product, cash-on-delivery enabled as a payment method, and the
  shop, cart, checkout and My Account pages installed. `wp-stop` stops both.
- PHP errors, warnings and deprecations from Apache and the CLI go to `/var/log/php-error.log`; Apache's own logs are
  under `/var/log/apache2/`.
- Users (password equals username): `admin` (administrator), `shopmanager` (shop_manager), `customer` (customer),
  `editor`, `author`, `contributor`, `subscriber`. Registration at checkout and on My Account is enabled. Guest
  checkout is enabled.
- `wp --path=/var/www/html ...` (WP-CLI) sets up content, options, users and roles. `wp --path=/var/www/html wc
  ...` drives the WooCommerce REST API as a given `--user`. `wp --path=/var/www/html eval '...'` runs PHP in a
  loaded WordPress. `wp --path=/var/www/html wc tool run ...` runs the Status > Tools actions.
- The plugin Apache serves is `/var/www/html/wp-content/plugins/woocommerce`, a symlink to
  `/src/plugins/woocommerce`, so a patch to `/src` takes effect on the next request. JavaScript changes need
  `pnpm --filter='@woocommerce/plugin-woocommerce' build` (offline: `node_modules` are already installed).
- PHPUnit: `cd /src/plugins/woocommerce && sh ./client/blocks/bin/copy-blocks-json.sh && vendor/bin/phpunit -c
  ./phpunit.xml --filter <TestName>`, with MariaDB running. Tests use the `woocommerce_tests` database and the
  WordPress copy in `/tmp/wordpress`, configured as the maintainers' wp-env test environment is (`WP_DEBUG` off,
  `WP_TESTS_DOMAIN` localhost). Legacy tests live in `tests/legacy/unit-tests/`, newer ones in `tests/php/`. The
  full suite is about 17,700 tests and takes about 7 minutes on two CPUs. Offline, about 47 fail and 49 skip. The
  failures are tests that call WooCommerce.com or wordpress.org (`themes_api()`, the WooCommerce.com helper, the
  remote logger) and tests whose fixtures differ from the maintainers' wp-env setup: the payments settings lists
  (this image enables cash on delivery and serves the plugin through a symlink, so gateway counts and asset URLs
  differ), the legacy Select2 usage tracker, log file names and block template fixtures. The PayPal Buttons and
  multisite tests skip. A failure outside those groups is worth a look.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate administrator would: create users at their real roles, set real options, add
products and orders. Drive the attack as the claimed actor, through the normal interface. Do not mint a nonce as an
administrator, flip an option through the database, give the attacker a capability they are supposed to gain,
create an API key with more permission than the scenario claims, or drive the action from an administrator's
session. Reading the database to observe the outcome is fine. For XSS, show the payload executes in a browser
context in the victim's role, not only that it appears in the HTML.

## How you rate severity

Two questions settle the band, in this order: (1) can the attacker act without a merchant-created account
(anonymous or self-registered customer is the high band; contributor, author, shop manager and a read-only API key
are the low band; editor and administrator are not rated), and (2) is the chain real and unconditional on a
default configuration.

### Anonymous shopper, or a self-registered customer

| Finding | Severity |
|---|---|
| Proven RCE, unchained, no preconditions | Critical |
| Order marked paid or completed without payment, or paying less than the cart total through a flaw in totals, coupons, taxes or shipping (not through a merchant's misconfiguration) | Critical |
| XSS or SQL injection, unchained, reaching a shop manager or administrator session | High |
| Reading or changing another customer's order, address, email, phone or downloads through an order key, order id, session, Store API or REST route | High |
| Downloading a paid file without a valid permission, or reading arbitrary server files through the download handler or importer | High |
| Account takeover through the login, registration, lost-password or email-verification flows | High |
| SSRF with a demonstrated read of an internal host (webhooks, importer, remote file fetch) | High |
| Anything else with real security impact (stock manipulation, coupon abuse beyond the coupon's own rules, IDOR on non-public data) | Medium |
| Blind SSRF, open redirect without a token leak, missing rate limiting | Low |
| No real security impact | Informative |

### Contributor, Author, Shop manager, or a read-only API key

| Finding | Severity |
|---|---|
| Reaching `install_plugins`, `edit_plugins`, `edit_themes`, `unfiltered_html`, code execution or file writes | Medium to High |
| A read-only API key performing any write | Medium |
| Stored XSS, SQL injection, IDOR | Low |
| Most other findings | Low |

### Rules by class

- **Validity comes before severity.** Name the actor, what they can already do through the normal interface, and
  the specific capability or data they gain. No gain means no finding, however real the code defect.
- **Secondary paths:** a fix on the primary path does not count as fixed until the Store API, REST, `wc-ajax` and
  My Account twins are checked.
- **Deserialization:** needs a real gadget in installed code; name it. Phar deserialization through file-stat
  functions is dead on PHP 8+.
- **CSRF:** needs realistic cross-origin exploitation under default `SameSite` cookie behaviour. A missing nonce on
  an action only an administrator can reach, where the attacker gains nothing they could not get by asking, is not
  a vulnerability.
- **Coupons and pricing:** a shopper using a coupon exactly as the merchant configured it is not a finding; a
  shopper bypassing the coupon's own restrictions (usage limit, product or user restriction, expiry) is.
- **Race conditions** (double coupon use, oversold stock) count only with a demonstrated outcome.
- **PCI:** WooCommerce core never handles full card data; any path that logs or stores a full PAN or CVV passed
  through a gateway integration point is High regardless of actor.
- **Open redirects** are Informative unless they leak a token or chain into a proven exploit.

## How reports and patches should look

- One-sentence claim: *<actor> can <action> against <target>, which they otherwise could not.*
- An explicit actor / already holds / gains line, the least privileged role that triggers the issue, whether it
  needs self-registration, HPOS on or off, a block or classic checkout, or any non-default setting, and the
  severity from the tables above.
- Name the affected file and function, and give a self-contained reproducer: WP-CLI setup plus `curl`, or a PHPUnit
  test under `tests/php/`.
- Write patches as `git diff` against `/src`. Follow WordPress coding standards (`vendor/bin/phpcs` in
  `plugins/woocommerce` checks them) and use core APIs (`esc_html()`, `esc_attr()`, `wp_kses_post()`,
  `$wpdb->prepare()`, `current_user_can()`, `wp_verify_nonce()`, `wc_clean()`, `rest_ensure_response()`). For a
  REST or Store API route, fix the permission callback, not the callback. Add a changelog entry the way
  `plugins/woocommerce/changelog/` does when the fix is ready for a pull request.

## Anything to leave alone

- Anything an administrator or editor can already do, including running PHP, editing files, installing plugins,
  and raw HTML in content.
- XSS by an editor or administrator; self-XSS; CSRF on login or logout.
- Findings that need `WP_DEBUG` / `display_errors` on, a plugin or theme not bundled in this image, a server
  misconfiguration, or an already-compromised host.
- Intentionally public data: product catalog, prices, stock status, reviews, store address and the public
  `/wp-json/wc/store/v1` responses.
- Order-number and username enumeration, version disclosure, missing security headers, missing rate limiting on
  checkout, login or coupon entry, and clickjacking without security impact.
- Brute force, denial of service, memory exhaustion from large catalogs, phishing, text injection, social
  engineering.
- Behaviour of payment gateways, shipping carriers and other extensions (they have their own enrollments or
  programs) beyond WooCommerce's handling of what they send.
- Vulnerabilities in Composer or npm `devDependencies`, unless practically exploitable remotely.
- Theoretical issues with no demonstrated, significant security impact.
