# Logos web threat model

## Project and trust boundaries

This monorepo contains the public Logos website, a public form intake API,
the Payload CMS admin, a CRM app, browser demos, and shared packages.
The website is statically exported, while the API and CMS have server-side
request handlers. Content submitted through the CMS is published through
GitHub pull requests.

The scan image builds the API, CMS, CRM, demos, and shared packages and
type-checks the website. A full website static export requires external media
API credentials that are not supplied to the scanner. Website source and unit
tests remain available for analysis.

Prioritise first-party code in `apps/api`, `apps/cms`, `apps/logos-crm`,
`apps/logos-demos`, `apps/web`, and the shared packages they use. The most
important boundaries are public form input reaching Notion or n8n,
authentication and authorisation in the CMS and CRM, the CMS-to-GitHub content
workflow, read-only demo proxy routes, and untrusted content rendered in the
public site or admin.

## Offline verification

From `/src`, run:

```sh
pnpm turbo run test --filter=api --filter=cms --filter=web --filter=@repo/content --filter=logos-demos
```

These tests run without network access. The scanner image does not contain
production credentials or services.

## How to assess findings

Treat unauthorised content publication, admin account compromise, exposure of
server-side tokens, and a demonstrated route from untrusted input to code
execution as high or critical according to impact. Stored cross-site scripting,
server-side request forgery, and bypasses of form validation or abuse controls
are also important when they have a realistic exploit path. Explain the
attacker's entry point, affected code path, impact, and a minimal reproducer.
Review proposed patches against the repository's existing tests and content
workflow contracts.

Report vulnerabilities in this repository's own code. Do not report a
dependency advisory as a source-code finding. Use test values only; the
scanner environment has no production credentials or live services.
