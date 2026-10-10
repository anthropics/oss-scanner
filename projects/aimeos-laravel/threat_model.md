# Aimeos Laravel

## Scope and trust boundaries

Aimeos Laravel integrates the Aimeos commerce engine into Laravel applications.
It exposes storefront, basket, checkout, account and supplier pages, JSON:API,
administration and GraphQL endpoints, an optional MCP bridge, and console jobs.
Focus on the integration in `src/`, routes, configuration and views. Dependencies
under `vendor/aimeos/` provide the underlying commerce behavior; trace through
them when needed to demonstrate a vulnerability reachable from this integration.

Untrusted inputs include public requests, product and basket identifiers,
checkout and account data, uploaded files, API and MCP arguments, site and locale
selectors, and payment-provider callbacks. Distinguish anonymous shoppers,
authenticated customers, site administrators and operators with deployment or
configuration access. Check that resource ownership, action permissions and
site boundaries hold across all entry points.

Prioritize cross-site or cross-customer access, unauthorized administration,
order or price manipulation, payment-state changes, injection, unsafe uploads,
path traversal, SSRF, stored XSS and disclosure of customer data or credentials.
For callbacks, show whether authenticity and order association can be bypassed.
For MCP tools, inspect both route access and downstream tool authorization.

## Exercising the project

The checkout and Composer development dependencies are at `/src`. The image uses
PHP 8.5, Laravel 13, PHPUnit 12 and the optional `laravel/mcp` SDK, matching the
PHP 8.5 CI dependency selection. MariaDB supplies the MySQL protocol required by
the tests; upstream CI uses MySQL 8, so this does not cover engine-specific behavior.
There is no separate frontend build in this integration repository.

Run the full suite offline as root:

```sh
scanner-test
```

This starts the local database service and runs PHPUnit without coverage. The
suite's first setup test installs the schema and unittest fixtures. The database
uses the repository's test defaults: `127.0.0.1`, database `laravel`, username and
password `aimeos`. These are isolated test credentials, not deployment defaults.
Database processes must be restarted after image creation; the helper handles
that without requiring an entrypoint or external services.

For a focused reproducer, initialize fixtures first if necessary:

```sh
scanner-test --filter SetupCommandTest
scanner-test --filter SomeTestName
```

The Docker build runs the suite but preserves the image if it fails. Inspect
the test output before relying on its fixtures. The build removes its test
database and stops MariaDB before saving the image, so the first offline suite
starts with fresh fixtures. External payment, mail, search
and AI services are not provisioned; use mocks for offline reproduction.

## Interpreting findings

`tests/AimeosTestAbstract.php` deliberately disables several authorization and
access-control settings. This is test scaffolding, not evidence that production
routes are unprotected. Reproduce authorization findings with the relevant
middleware and configuration enabled, and state any deployment prerequisites.

Include the entry point, required role and configuration, minimal reproducer,
demonstrated impact and a focused regression test or patch. Rate severity by
reachable impact and prerequisites, especially exposure of customer data,
cross-site access, administrative compromise and financial manipulation.
Distinguish explicitly granted administrator capabilities from privilege
escalation. Dependency reports should demonstrate reachability through Aimeos
Laravel rather than only cite a dependency version.
