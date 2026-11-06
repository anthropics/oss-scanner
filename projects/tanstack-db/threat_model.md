# TanStack DB threat model

## Scope and trust boundaries

This enrollment covers https://github.com/TanStack/db, with emphasis on substantive server execution. Relevant packages: `packages/db-ivm`, `packages/db`, `packages/db-sqlite-persistence-core`, `packages/node-db-sqlite-persistence`, `packages/cloudflare-durable-objects-db-sqlite-persistence`.

Untrusted inputs: collection records and keys, query values, synchronized data, persisted JSON and metadata, replayed mutations and schema identifiers when an application derives them from external input.

Priority boundaries: Node SQLite and Cloudflare Durable Objects SQLite persistence, shared SQL compilation and parameterization, transaction ownership and rollback, collection/database namespace isolation, persisted metadata decoding and synchronization boundaries. Include shared DB/query code reachable from these server adapters.

This library is not a standalone authenticated database service. Applications own tenant-to-database mapping, backend authorization and trusted schema/configuration. File paths, raw SQL and custom mutation callbacks supplied by trusted application code are not automatically hostile inputs. Show a realistic route from attacker-controlled record/query values to the claimed effect.

## Build and offline exercises

The Dockerfile uses the upstream `.nvmrc`, exact pnpm version and frozen lockfile. Source, dependencies, tests and built output remain under `/src`; package output is in `dist/` or `build/` according to each package configuration. It builds the listed packages and their declared dependency graph. Other repository source remains available for inspection.

From `/src`, rerun. For an offline verification, set `NX_SKIP_NX_CACHE=true` first so Nx executes the tests instead of returning results cached during image setup:

```sh
pnpm --filter @tanstack/node-db-sqlite-persistence... --filter @tanstack/cloudflare-durable-objects-db-sqlite-persistence... run build
pnpm --filter @tanstack/db-sqlite-persistence-core --filter @tanstack/node-db-sqlite-persistence --filter @tanstack/cloudflare-durable-objects-db-sqlite-persistence run test
```

Use existing package tests and local, synthetic fixtures. Do not use real credentials, customer data, external production services or deployment commands. Live cloud/provider tests, browser E2E suites, Docker-backed sandbox tests and platform-specific integrations are not claimed to run in this image. Any extra test runtime or fixture needed offline must be fetched during the online image build first.

## Severity and evidence

These are proposed triage guidelines for maintainer review. Critical requires demonstrated attacker-controlled arbitrary server execution or similarly broad compromise across a real trust boundary. High includes demonstrated unauthorized sensitive-data access, cross-tenant disclosure, stored/script-context XSS, or bypass of an explicitly enabled execution/authorization safeguard. Medium includes remotely triggerable bounded denial of service or narrower integrity/confidentiality loss. State authentication, deployment configuration, attacker capabilities, affected versions and exploit limits; do not rate hypothetical reachability as proven impact.

Report a minimal offline reproducer using public APIs or normal request entry points, expected versus observed behavior, root cause and a focused patch with a regression test. Group reports sharing one root cause and distinguish dependencies' bugs from defects in this repository. Ordinary typing, styling and performance defects without a security effect are lower priority. Examples are test harnesses, not a promise that every example is production hardened.

Send findings only through the configured private report channel. Do not place exploit details or confidential reports in public issues, enrollment files or PRs. This threat model describes intended boundaries and contains no vulnerability findings.

The image includes the `sqlite3` CLI required by the real CLI persistence contract tests.
