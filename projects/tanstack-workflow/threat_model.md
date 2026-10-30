# TanStack Workflow threat model

## Scope and trust boundaries

This enrollment covers https://github.com/TanStack/workflow, with emphasis on substantive server execution. Relevant packages: `packages/workflow-core`, `packages/workflow-runtime`, `packages/workflow-vercel`, `packages/workflow-netlify`, `packages/workflow-cloudflare`, `packages/workflow-railway`, `packages/workflow-store-drizzle-postgres`, `packages/workflow-store-cloudflare-d1`.

Untrusted inputs: HTTP scheduler requests and headers, external events, workflow inputs, persisted run/event data and timer/schedule identifiers.

Priority boundaries: Scheduler handler authorization when configured, durable runtime execution and replay, leases and ownership, idempotency, concurrent dispatch and event delivery, run namespace separation, SQL parameter binding and persistence state integrity. Inspect platform handlers and both Postgres/Drizzle and Cloudflare D1 stores.

Workflow definitions and application callbacks are trusted executable code. Applications own public ingress authentication, tenant routing and database credentials. Do not call an intentionally unauthenticated handler configuration a bypass; prove violation of an enabled policy. Reliability defects require a concrete attacker-controlled security impact to be security findings.

## Build and offline exercises

The Dockerfile uses the upstream `.nvmrc`, exact pnpm version and frozen lockfile. Source, dependencies, tests and built output remain under `/src`; package output is in `dist/` or `build/` according to each package configuration. It builds the listed packages and their declared dependency graph. Other repository source remains available for inspection.

From `/src`, rerun. For an offline verification, set `NX_SKIP_NX_CACHE=true` first so Nx executes the tests instead of returning results cached during image setup:

```sh
pnpm exec nx run-many --target=build --projects=@tanstack/workflow-core,@tanstack/workflow-runtime,@tanstack/workflow-vercel,@tanstack/workflow-netlify,@tanstack/workflow-cloudflare,@tanstack/workflow-railway,@tanstack/workflow-store-drizzle-postgres,@tanstack/workflow-store-cloudflare-d1 --parallel=2 --skipRemoteCache
pnpm exec nx run-many --target=test:lib --projects=@tanstack/workflow-core,@tanstack/workflow-runtime,@tanstack/workflow-vercel,@tanstack/workflow-netlify,@tanstack/workflow-cloudflare,@tanstack/workflow-railway,@tanstack/workflow-store-drizzle-postgres,@tanstack/workflow-store-cloudflare-d1 --parallel=2 --skipRemoteCache
```

Use existing package tests and local, synthetic fixtures. Do not use real credentials, customer data, external production services or deployment commands. Live cloud/provider tests, browser E2E suites, Docker-backed sandbox tests and platform-specific integrations are not claimed to run in this image. Any extra test runtime or fixture needed offline must be fetched during the online image build first.

## Severity and evidence

These are proposed triage guidelines for maintainer review. Critical requires demonstrated attacker-controlled arbitrary server execution or similarly broad compromise across a real trust boundary. High includes demonstrated unauthorized sensitive-data access, cross-tenant disclosure, stored/script-context XSS, or bypass of an explicitly enabled execution/authorization safeguard. Medium includes remotely triggerable bounded denial of service or narrower integrity/confidentiality loss. State authentication, deployment configuration, attacker capabilities, affected versions and exploit limits; do not rate hypothetical reachability as proven impact.

Report a minimal offline reproducer using public APIs or normal request entry points, expected versus observed behavior, root cause and a focused patch with a regression test. Group reports sharing one root cause and distinguish dependencies' bugs from defects in this repository. Ordinary typing, styling and performance defects without a security effect are lower priority. Examples are test harnesses, not a promise that every example is production hardened.

Send findings only through the configured private report channel. Do not place exploit details or confidential reports in public issues, enrollment files or PRs. This threat model describes intended boundaries and contains no vulnerability findings.

The selected store and platform unit suites use local fixtures/mocks; they do not prove production Postgres or cloud deployment behavior. Provision a local database during image setup before adding database-backed integration tests. This is a newer project; security relevance does not establish service eligibility.
