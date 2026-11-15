# Threat model

## What this project does and where untrusted input enters
Shopware 6 is an open-source e-commerce platform (Symfony/PHP, MySQL/MariaDB). One installation serves
one or more sales channels (storefronts or headless clients) and is managed through an administration UI
backed by the Admin API. Untrusted input enters through:

- **Store API** (`/store-api/*`, `src/Core/**/SalesChannel/*Route.php`): used by the storefront and headless
  clients. Callers are anonymous visitors, guests and logged-in customers who send only a public sales-channel
  access key, plus optionally a context token. **This is the most exposed surface.** It accepts DAL criteria
  (filters, sorting, associations, aggregations, includes, `term`) from the request.
- **Storefront** (`src/Storefront`): server-rendered Twig pages, forms (login, registration, account, checkout,
  newsletter, contact, reviews) and the HTTP cache (`src/Storefront/Framework/Cache`,
  `src/Core/Framework/Adapter/Cache/Http`).
- **Admin API** (`/api/*`, `src/Core/Framework/Api`): used by administration users and integrations
  (OAuth client credentials). Every user or integration is limited by ACL roles (`src/Core/Framework/Api/Acl`)
  unless it has the `admin` flag. **An ACL-restricted user is untrusted beyond their granted privileges.**
  This covers the generic entity CRUD, `_action/sync`, cloning, search/aggregation, state machine transitions,
  import/export, media upload and URL import, and user/role/integration management.
- **Apps** (`src/Core/Framework/App`, `src/Core/Framework/Script`, `src/Core/System/CustomEntity`,
  `src/Core/Framework/Webhook`): an app installed from a zip or the store supplies a manifest, App Scripts
  (Twig run in a sandbox), custom entity definitions, templates and webhook endpoints. **An app is
  only trusted with the permissions it requests in its manifest.** Escaping the App Script sandbox, running
  SQL through custom entity definitions, or reading data beyond the requested permissions is a vulnerability.
- **Unauthenticated endpoints outside the Store API**: OAuth token, password recovery (admin and customer),
  SSO, `/api/_info/*`, document download for guests, newsletter confirmation, payment finalize/handle-payment
  callbacks.
- **Server-side fetches**: media URL import, external media links, app/webhook/payment/tax/checkout gateways
  and flow actions all go through `src/Core/Content/Media/File/FileUrlValidator.php` and similar guards
  (SSRF to internal addresses is in scope).
- **Templates edited by admin users**: mail templates, document templates, CMS and SEO URL templates are
  rendered in a Twig sandbox (`src/Core/Framework/Adapter/Twig/SecurityExtension.php` and the allow-listed
  functions/filters). A user who may edit templates must not be able to run arbitrary PHP.

## Components that matter most / least
- Most: `src/Core/Framework/DataAbstractionLayer` (criteria parsing, `Dbal` query building, aggregations,
  association/field visibility and read protection), Store API routes in `src/Core/Checkout` (cart, order,
  payment, customer/account, documents) and `src/Core/Content` (product, review, media, CMS),
  `src/Core/Framework/Api` (ACL, OAuth, sync, user/integration/role handling), the App system and App Script
  sandbox, Twig sandboxing, the HTTP cache (cache keys, cookies and private data in cached responses),
  password recovery and session handling.
- Less: `src/Administration` (Vue SPA; XSS there is in scope but needs an authenticated victim),
  `src/Elasticsearch` (not enabled in this image, `SHOPWARE_ES_ENABLED=0`), `src/Core/Framework/Demodata`.
- Out of scope: `src/Core/DevOps` (CI, static analysis and test tooling), `src/Core/Profiling`, everything
  under `tests/`, the `Test` folders shipped inside `src/`, `vendor/`, and bugs that live entirely in
  third-party dependencies (Symfony, Twig, Doctrine DBAL, etc.) unless Shopware code makes them reachable.

## How to exercise it
- The image has Shopware installed against a local MariaDB 12.3. Run `start-mariadb` first (root/root on
  127.0.0.1:3306). Databases: `shopware` (installed shop with `--basic-setup`, admin user `admin` / `shopware`)
  and `shopware_test` (used by PHPUnit). Configuration is in `/src/.env`.
- `bin/console` works offline. Start a web server with
  `php -S 127.0.0.1:8000 -t public public/index.php &`; the storefront is at `http://127.0.0.1:8000/`
  (the configured sales-channel domain, so use that exact host) and the Store API at `/store-api/*`
  with the `sw-access-key` header set to the storefront sales channel's `access_key` from the `sales_channel`
  table. The Admin API takes a token from `POST /api/oauth/token`.
- Tests: `vendor/bin/phpunit --testsuite unit` (no DB writes) and `vendor/bin/phpunit --testsuite integration`
  (uses `shopware_test`). The integration tests under `tests/integration/Core/Framework/Api` and
  `.../Checkout` show how to call the Admin API and Store API in-process (`AdminApiTestBehaviour`,
  `SalesChannelApiTestBehaviour`). A reproducer as a PHPUnit integration test is the preferred format.
- The image runs PHP 8.5. Some historical bugs only appeared on PHP < 8.4 with emulated PDO prepares; report
  such issues with the PHP versions they need, and do not dismiss them because they do not reproduce here.

## Anything to leave alone
- A user with the `admin` flag is fully trusted on on-premises installs: they can install plugins (arbitrary
  PHP). Do not report "admin can execute code" unless it bypasses a documented boundary (the Twig/App Script
  sandbox) or works with a narrower ACL privilege than `admin`.
- Plugins (`custom/plugins`, Symfony bundles) are fully trusted code. Apps are not (see above).
- The `sw-app-user-id` header is intended delegation, not impersonation. An integration (or app) that holds
  valid client credentials may send it to act on behalf of a user, for example an app working for the admin
  user who opened it. `ApiRequestContextResolver::resolveContextSource()` then limits the request to the
  intersection of the integration's and the user's permissions. For an app integration, the user must also
  hold `app.<name>` or `app.all`. For an admin integration, the request gets the user's own permissions, which
  are never more than it already has. Do not report "an integration can set `sw-app-user-id` to any user ID,
  including an admin's". Report it only if the effective permissions end up higher than the integration would
  have without the header, or if the header is honoured without valid integration credentials (e.g. on a
  user token, a Store API request or an unauthenticated route).
- Do not report missing security headers, verbose errors in `APP_ENV=dev`, the default `admin`/`shopware`
  credentials of this test image, or exposure of `.env` when the web root is misconfigured to the project root.
- Do not report findings that need direct database, filesystem or shell access, or a malicious reverse proxy
  that the operator configured as trusted.
- Business logic findings (prices, promotions, stock) are welcome when a customer can get goods or discounts
  they are not entitled to, but please show a concrete cart/order outcome.
- Reports should name the attacker's starting position (anonymous, customer, admin user with which ACL
  privileges, app with which permissions) and include a reproducer plus a patch against `src/`.
