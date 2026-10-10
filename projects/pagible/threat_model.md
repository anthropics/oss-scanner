# Pagible CMS

## Scope and trust boundaries

Pagible is a Laravel CMS monorepo with a Vue administration UI, public page
rendering, GraphQL and JSON:API interfaces, MCP tools, AI integrations, and
optional packages such as imports, backups, billing, CDN purging and webhooks.
Review first-party code throughout the repository, including optional packages.

Untrusted inputs include public HTTP requests, API and tool arguments, uploaded
files and media, imported content, remote URLs, webhook payloads, and AI output.
Authenticated editors are not necessarily administrators. Check authorization
for the requested action and resource, including tenant/site separation, access
to unpublished content, and frontend page restrictions.

Prioritize authorization bypasses, cross-tenant access, unsafe file handling,
path traversal, SSRF, injection, stored XSS, secret disclosure, and webhook or
billing authenticity failures. Trace input through validation, persistence,
publication, rendering, background jobs and outbound requests. Treat AI output
as untrusted when it reaches tools or persisted content.

Distinguish capabilities explicitly granted to administrators (such as editing
trusted templates or configuring integrations) from escalation by less trusted
users. State the required role and configuration for every finding.

## Exercising the project

The checkout is at `/src`. Composer development dependencies, the admin and
webhook admin npm dependencies, built UI assets and Cypress are installed during
the online build. PHP tests use Orchestra Testbench with SQLite (`DB_DRIVER=sqlite`):

```sh
vendor/bin/phpunit
vendor/bin/phpunit --testsuite Core,Admin,GraphQL,JsonAPI,MCP,Webhooks
vendor/bin/phpstan analyze --no-progress
cd admin && npm run test:unit
```

The build runs PHPUnit but preserves the image if tests fail; inspect its output
and rerun relevant tests when investigating. Optional packages may have their own
Composer dependencies and test configurations beyond the root suite. Database
server variants, external AI/search/payment services and the root Playwright
coverage harness are not provisioned. Use existing fakes and mocks for offline
reproducers; do not rely on live credentials or network access.

## Reports and severity

Include the affected entry point, required privileges and configuration, a
minimal reproducer or regression test, demonstrated impact, and a focused patch
where possible. Assess severity using the reachable impact and prerequisites;
distinguish unauthenticated compromise from attacks requiring privileged access.
For resource exhaustion, demonstrate a practical amplification or availability
impact. For dependency findings, show how Pagible exposes the vulnerable behavior.
