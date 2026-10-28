# TanStack Query threat model

## Scope and trust boundaries

This enrollment covers https://github.com/TanStack/query, with emphasis on substantive server execution. Relevant packages: `packages/query-core`, `packages/react-query`, `packages/react-query-next-experimental`.

Untrusted inputs: server-fetched query data, dehydrated cache state, serialized error/data values, streaming hydration entries and cache keys derived from requests.

Priority boundaries: Next.js experimental streaming hydration, HTML/script-context escaping in HydrationStreamProvider and htmlescape, shared dehydration/hydration semantics, request-scoped cache ownership and server rendering paths. Framework adapters are relevant when they carry these values into generated HTML.

Query does not authenticate application fetches or make a deliberately shared cross-user QueryClient safe. Applications must use appropriate per-request ownership and choose which data to dehydrate. Distinguish library-created cross-request leakage from application cache reuse; demonstrate exploitable output from library-owned serialization rather than arbitrary application HTML injection.

## Build and offline exercises

The Dockerfile uses the upstream `.nvmrc`, exact pnpm version and frozen lockfile. Source, dependencies, tests and built output remain under `/src`; package output is in `dist/` or `build/` according to each package configuration. It builds the listed packages and their declared dependency graph. Other repository source remains available for inspection.

From `/src`, rerun. For an offline verification, set `NX_SKIP_NX_CACHE=true` first so Nx executes the tests instead of returning results cached during image setup:

```sh
pnpm exec nx run-many --target=build --projects=@tanstack/query-core,@tanstack/react-query,@tanstack/react-query-next-experimental --parallel=2 --skipRemoteCache
pnpm exec nx run-many --target=test:lib --projects=@tanstack/query-core,@tanstack/react-query,@tanstack/react-query-next-experimental --parallel=2 --skipRemoteCache
```

Use existing package tests and local, synthetic fixtures. Do not use real credentials, customer data, external production services or deployment commands. Live cloud/provider tests, browser E2E suites, Docker-backed sandbox tests and platform-specific integrations are not claimed to run in this image. Any extra test runtime or fixture needed offline must be fetched during the online image build first.

## Severity and evidence

These are proposed triage guidelines for maintainer review. Critical requires demonstrated attacker-controlled arbitrary server execution or similarly broad compromise across a real trust boundary. High includes demonstrated unauthorized sensitive-data access, cross-tenant disclosure, stored/script-context XSS, or bypass of an explicitly enabled execution/authorization safeguard. Medium includes remotely triggerable bounded denial of service or narrower integrity/confidentiality loss. State authentication, deployment configuration, attacker capabilities, affected versions and exploit limits; do not rate hypothetical reachability as proven impact.

Report a minimal offline reproducer using public APIs or normal request entry points, expected versus observed behavior, root cause and a focused patch with a regression test. Group reports sharing one root cause and distinguish dependencies' bugs from defects in this repository. Ordinary typing, styling and performance defects without a security effect are lower priority. Examples are test harnesses, not a promise that every example is production hardened.

Send findings only through the configured private report channel. Do not place exploit details or confidential reports in public issues, enrollment files or PRs. This threat model describes intended boundaries and contains no vulnerability findings.

The experimental Next.js streaming package has no `test:lib` target at the inspected revision. The unit command exercises Query core and React Query; it does not establish streaming integration coverage. Build checks are not a substitute for a browser-backed streaming regression test.
