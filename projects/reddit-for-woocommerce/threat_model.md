# Reddit for WooCommerce

## Scope and trust boundaries

This WooCommerce extension connects a merchant's store to Reddit advertising through WooCommerce Connect Server (WCS). The target is the public PHP/JavaScript plugin under `/src`, including REST controllers, connection state, product exports, and storefront conversion tracking. WordPress, WooCommerce, Jetpack, WCS and the advertising service are dependencies; report a dependency issue only when a concrete exploit in this plugin demonstrates its impact.

Treat anonymous shoppers, customer accounts, product/order fields, HTTP parameters and remote responses as untrusted. Administrators and shop managers may configure the integration. Their credentials do not make a lower-privileged user's ability to reach those operations acceptable. The supplied administrator is a reproduction aid, not the assumed attacker.

Relevant boundaries include REST permission checks versus route handlers; customer-controlled product/cart/order data versus HTML, CSV and event payloads; local options and credentials versus REST responses/logs; and remote response data versus local persistence or rendering. Review authorization, CSRF, stored/reflected XSS, credential disclosure, unintended filesystem access, and attacker-influenced outbound requests where the code provides a reachable path.

## Source map

- `includes/API/Site/Controllers/`: connection, account, campaign, onboarding and settings REST routes under `/wc/rfw/`.
- `includes/API/AdPartner/` and `includes/Connection/`: requests through WCS and connection credentials.
- `includes/Admin/Export/` and `includes/CsvExporter/`: catalog/export data and output files.
- `includes/Tracking/`: browser pixels, server-side conversion payloads and consent handling.
- `js/src/`: merchant UI and browser-side data handling.

## Environment and checks

The image builds the plugin with development dependencies retained, installs released WordPress and WooCommerce, and activates the plugin. Source is `/src`; the disposable WordPress site is `/var/www/html`, served at `http://127.0.0.1` after `wp-start`. `wp-stop` shuts down Apache and MariaDB. Database and WordPress credentials are synthetic test data.

Accounts: `admin` / `admin` (administrator), `shopmanager` / `shopmanager` (shop manager), `customer` / `customer` (customer). These accounts exist only inside the scanner image. `wp --path=/var/www/html --user=admin ...` can seed local fixtures. The separately installed WordPress test database is `scanner_tests`.

Run `scanner-test` after the image build. It requires successful plugin loading, denies anonymous/customer settings writes, permits a shop manager to read settings, loads the storefront, and runs the complete PHP test suite, followed by the JavaScript unit suite. Run it with the container network disabled; dependency installation and asset compilation happen during the network-enabled build.

## Limits

No live WCS, Jetpack or advertising account credentials are included. OAuth/account linking, real ad creation, live catalog delivery and external event acceptance cannot be validated offline. Local request construction and response handling remain available to inspect and reproduce with explicit fixtures. Do not send requests to production services or treat mocked responses as proof that external services enforce a boundary.

Missing paid-service access and intentionally synthetic local credentials are not vulnerabilities. Reports should identify the attacker role, reachable plugin path, reproducible local steps and demonstrated impact.
