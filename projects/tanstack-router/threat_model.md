# TanStack Router and Start threat model

## Scope and trust boundaries

This enrollment covers https://github.com/TanStack/router, with emphasis on substantive server execution. Relevant packages: `packages/start-server-core`, `packages/start-client-core`, `packages/router-core`, `packages/start-plugin-core`, `packages/router-ssr-query-core`.

Untrusted inputs: HTTP request methods, URLs, query strings, headers, cookies, FormData and serialized server-function arguments; SSR loader data and streamed values.

Priority boundaries: Server-function dispatch and middleware ordering; trusted server context versus client-supplied context; request-local state and SSR isolation; redirect and response construction; HTML/script escaping; serialization and stream framing; build transforms that keep server implementations and secrets out of browser bundles. Include React, Solid and Vue Start server adapters.

Applications provide authentication, authorization and input schemas. A server function is a remotely callable endpoint, not an authorization boundary merely because its identifier is obscure. Trusted build configuration and application source are not attacker-controlled by default.

## Build and offline exercises

The Dockerfile uses the upstream `.nvmrc`, exact pnpm version and frozen lockfile. Source, dependencies, tests and built output remain under `/src`; package output is in `dist/` or `build/` according to each package configuration. It builds the listed packages and their declared dependency graph. Other repository source remains available for inspection.

From `/src`, rerun. For an offline verification, set `NX_SKIP_NX_CACHE=true` first so Nx executes the tests instead of returning results cached during image setup:

```sh
pnpm exec nx run-many --target=build --projects=@tanstack/start-server-core,@tanstack/start-client-core,@tanstack/router-core,@tanstack/start-plugin-core,@tanstack/router-ssr-query-core --parallel=2 --skipRemoteCache
pnpm exec nx run-many --target=test:unit --projects=@tanstack/start-server-core,@tanstack/start-client-core,@tanstack/router-core,@tanstack/start-plugin-core,@tanstack/router-ssr-query-core --parallel=2 --skipRemoteCache
```

Use existing package tests and local, synthetic fixtures. Do not use real credentials, customer data, external production services or deployment commands. Live cloud/provider tests, browser E2E suites, Docker-backed sandbox tests and platform-specific integrations are not claimed to run in this image. Any extra test runtime or fixture needed offline must be fetched during the online image build first.

## Severity and evidence

These are proposed triage guidelines for maintainer review. Critical requires demonstrated attacker-controlled arbitrary server execution or similarly broad compromise across a real trust boundary. High includes demonstrated unauthorized sensitive-data access, cross-tenant disclosure, stored/script-context XSS, or bypass of an explicitly enabled execution/authorization safeguard. Medium includes remotely triggerable bounded denial of service or narrower integrity/confidentiality loss. State authentication, deployment configuration, attacker capabilities, affected versions and exploit limits; do not rate hypothetical reachability as proven impact.

Report a minimal offline reproducer using public APIs or normal request entry points, expected versus observed behavior, root cause and a focused patch with a regression test. Group reports sharing one root cause and distinguish dependencies' bugs from defects in this repository. Ordinary typing, styling and performance defects without a security effect are lower priority. Examples are test harnesses, not a promise that every example is production hardened.

Send findings only through the configured private report channel. Do not place exploit details or confidential reports in public issues, enrollment files or PRs. This threat model describes intended boundaries and contains no vulnerability findings.

The image sets Node's process-local `--dns-result-order=ipv4first` so the Vite test server and fetch agree on localhost resolution in Linux containers. No system DNS or network settings are changed.
