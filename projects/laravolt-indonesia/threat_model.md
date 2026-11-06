# Threat model: laravolt/indonesia

## What this project does and where untrusted input enters

`laravolt/indonesia` is a Laravel package that ships the administrative regions of Indonesia
(provinces, cities/regencies, districts, villages) as migrations, CSV-backed seeders, Eloquent models
and a facade/service (`src/IndonesiaService.php`). It also registers resource routes for an admin
editor (`routes/web.php` -> `src/Http/Controllers/{Provinsi,Kabupaten,Kecamatan,Kelurahan}Controller`)
whose prefix and middleware come from config (`laravolt.indonesia.route.*`).

Untrusted input reaches the package through:

- **HTTP requests to the editor routes** (index/search, show, store, update, destroy for each region
  type). Route middleware is configurable, so assume a deployment may expose them to authenticated
  but low-privilege users.
- **Search strings and IDs** that applications forward into `Indonesia::search($term)->all()`,
  `allProvinces()`, `paginate*()`, `find*($id, $with)` and the model `search` scopes. Apps commonly
  wire these to public "select province/city" dropdown endpoints, so treat them as fully untrusted.
- **The `$with` relation list** passed to `find*()`; apps sometimes forward it from the query string.

Trusted: configuration, the bundled CSV data and seeders, artisan commands run by operators.

## Components that matter most / least

- Most: `src/IndonesiaService.php` (search, relation loading, cache keys, `clearCache()`),
  `src/Models/*` (search scopes and relations), `src/Http/Controllers/*` (mass assignment, validation,
  authorization), `src/Tables/*` (listing/search rendering), views under `resources/`.
- Less: `src/Commands/*`, `src/Seeds/*` (operator-run, trusted input), `src/Permission.php`.
- Out of scope: `tests/`, the CSV data files themselves (data accuracy is not a security issue), and
  bugs that live entirely in Laravel or laravolt/suitable.

## Risks we care about

- SQL injection or query manipulation through search terms, IDs or the `$with` relation list.
- Mass assignment or missing validation/authorization in the editor controllers (e.g. modifying or
  deleting regions without the expected permission when the app uses the documented middleware).
- Stored XSS: region names edited through the controllers and rendered in tables/views.
- Cache poisoning or cross-request leakage through `getCacheKey()`; `clearCache()` flushing the whole
  application cache (`Cache::flush()`) when called from a reachable path.
- Resource exhaustion: unbounded `all()` / `allVillages()` / relation loading (`cities.districts.villages`)
  reachable from a single unauthenticated request.

## How to exercise it

- After the Docker build, run `vendor/bin/phpunit -c phpunit.xml`. `tests/TestCase.php` boots
  orchestra/testbench with an in-memory SQLite DB and loads `database/migrations`.
- Write reproducers as testbench tests (extend `Laravolt\Indonesia\Test\TestCase`).

## How you rate severity

- Critical: SQL injection or RCE reachable from an unauthenticated request in a default install.
- High: SQL injection reachable by an authenticated user; write/delete through the editor routes
  without the configured authorization; stored XSS that executes for administrators.
- Medium: resource exhaustion from a single request that ties up a worker; cache poisoning that serves
  wrong data to other users; reflected XSS.
- Low: issues that need the developer to forward clearly unsafe values (e.g. raw relation names from
  the request into `$with`) or to remove the documented middleware; information disclosure of public
  region data.

## Report and patch format

- Please include a testbench test or minimal script against `/src`, and a patch against `src/`.

## Anything to leave alone

- Do not report that region data is public or inaccurate; it is public reference data by design.
- Do not report "the app forgot to add auth middleware" when the package documents the
  `route.middleware` config; only report if the package's own default or code bypasses it.
- Do not report issues in dev dependencies (PHPUnit, testbench, php-coveralls).
