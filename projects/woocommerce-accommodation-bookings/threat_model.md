# WooCommerce Accommodation Bookings

## Enrollment status

This is a preparation draft. Its public-source build and isolated unit environment do not provide a usable booking store. Keep the enrollment draft until the real Bookings dependency can be acquired by the scanner without private credentials and the integration suite passes with Bookings and Product Add-Ons. Do not substitute stubbed classes for that readiness requirement.

## Scope and trust boundaries

This WooCommerce Bookings add-on implements accommodation products, nights/date ranges, availability/rates, cart/order handling and optional Product Add-Ons integration. The public target is `/src`. Anonymous shoppers and customer accounts can supply booking dates, quantities, resources and cart data; administrators/shop managers configure products and availability. Those boundaries must prevent unauthorized booking/order access, unauthorized settings changes, unsafe rendering and attacker-controlled price/availability bypasses with meaningful impact.

Review `includes/class-wc-product-accommodation-booking.php`, `class-wc-accommodation-booking-cart-manager.php`, `class-wc-accommodation-booking-order-manager.php`, `class-wc-accommodation-booking-date-picker.php`, `includes/admin/`, `includes/integrations/` and browser assets under `src/`. Booking Core, WooCommerce and Product Add-Ons are dependencies; distinguish their behavior from the target plugin's own transformations, hooks and authorization assumptions.

## Available environment and limits

The image installs public Composer/npm dependencies, builds browser assets and translations, and retains PHPUnit. Run `scanner-test` offline for the WP_Mock suite and isolated changelog-formatter tests. These validate public code in isolation and do not exercise a real booking checkout, REST API, database, dependency versions or permissions.

The documented integration bootstrap requires actual WooCommerce Bookings and Product Add-Ons source. The repository's supported installation flow uses authenticated private release downloads. No credentials, private source, fabricated dependency implementation or production data are included. Integration and E2E claims must wait for an authorized, reproducible dependency solution.
