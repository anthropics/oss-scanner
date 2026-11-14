# Customs Fees for WooCommerce

## Scope and trust boundaries

This plugin calculates customs/import fees for a WooCommerce cart from merchant-configured rules and product origin/HS-code metadata. Target `/src`, especially rule administration and import/export, cart fee calculations, order metadata, and frontend/admin output.

Anonymous shoppers and customer accounts are untrusted. Shipping destinations, cart quantities, request parameters and imported rule contents must not grant access to merchant configuration or other customers' data. Administrators and shop managers may manage rules; possession of those capabilities is not the baseline attacker. Evaluate capability/nonce checks, stored/reflected XSS, unsafe imports, unauthorized option or product metadata writes, unintended data export, and fee manipulation across cart/order boundaries. A pricing discrepancy is a security finding only with a demonstrated attacker-controlled path and meaningful impact.

## Source map

- `includes/class-cfwc-templates.php`: live preset-management AJAX handlers; verify both nonce and `manage_woocommerce` checks. `includes/admin/` contains merchant screens and other AJAX handlers. The separate `class-cfwc-ajax.php` class is not currently instantiated by the loader; do not mistake its methods for reachable routes.
- `includes/class-cfwc-settings.php`, `class-cfwc-export-import.php`: rule normalization and persistence.
- `includes/class-cfwc-calculator.php`, `class-cfwc-rule-matcher.php`: matching, compounding, caches and fee amounts.
- `includes/class-cfwc-loader.php`, `class-cfwc-display.php`, `class-cfwc-emails.php`: cart/order integration and presentation.
- `includes/class-cfwc-products*.php`, `assets/`: product data and browser UI.

## Environment and checks

The image contains public source, built assets, released WordPress/WooCommerce, MariaDB, Apache and the complete WooCommerce legacy PHPUnit bootstrap. `/src` is the plugin; `/var/www/html` is a disposable store. `wp-start` serves `http://127.0.0.1`; `wp-stop` stops it.

Synthetic accounts are `admin`/`admin`, `shopmanager`/`shopmanager`, and `customer`/`customer`. The WP-CLI command uses `--path=/var/www/html --user=admin` for fixture setup. Runtime data and the separate `scanner_tests` database contain no production information.

Run `scanner-test` with the container network disabled. It exercises a real WooCommerce cart against a configured customs rule, checks real AJAX denial for anonymous/customer requests and invalid nonces, verifies a shop manager can apply and persist a preset, checks the storefront, then invokes the entire PHP suite directly with `--fail-on-empty-test-suite`. The repository's `composer test` wrapper suppresses failures, so it is deliberately not the validation entrypoint.

No external customs service is needed for local rule calculation. WooCommerce is a dependency; findings must demonstrate impact through this plugin. Report the attacker role, reachable path, reproduction and concrete effect. Synthetic credentials and a privileged fixture-setup account are not vulnerabilities.
