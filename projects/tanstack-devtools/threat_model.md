# TanStack Devtools threat model

## Scope and trust boundaries

This enrollment covers https://github.com/TanStack/devtools, with emphasis on substantive server execution. Relevant packages: `packages/event-bus`, `packages/devtools-bundler-core`, `packages/devtools-vite`, `packages/devtools-rspack`.

Untrusted inputs: HTTP, SSE and WebSocket traffic to development endpoints; browser-originated events; source path/editor parameters; package and plugin requests.

Priority boundaries: Node event-bus server, dev-server middleware and runtime bridges, origin/host and loopback assumptions, event routing, source-file/editor operations, package-manager subprocess construction and production removal of development instrumentation.

The normal deployment is a developer workstation with a local development server. Evaluate a malicious web page reaching localhost separately from a deliberately public server. Trusted project files, bundler plugins and explicit maintainer shell commands already execute with developer privileges. Do not assume a development endpoint is a production service; state exposure and required configuration.

## Build and offline exercises

The Dockerfile uses the upstream `.nvmrc`, exact pnpm version and frozen lockfile. Source, dependencies, tests and built output remain under `/src`; package output is in `dist/` or `build/` according to each package configuration. It builds the listed packages and their declared dependency graph. Other repository source remains available for inspection.

From `/src`, rerun. For an offline verification, set `NX_SKIP_NX_CACHE=true` first so Nx executes the tests instead of returning results cached during image setup:

```sh
pnpm exec nx run-many --target=build --projects=@tanstack/devtools-event-bus,@tanstack/devtools-bundler-core,@tanstack/devtools-vite,@tanstack/devtools-rspack --parallel=2 --skipRemoteCache
pnpm exec nx run-many --target=test:lib --projects=@tanstack/devtools-event-bus,@tanstack/devtools-bundler-core,@tanstack/devtools-vite,@tanstack/devtools-rspack --parallel=2 --skipRemoteCache
```

Use existing package tests and local, synthetic fixtures. Do not use real credentials, customer data, external production services or deployment commands. Live cloud/provider tests, browser E2E suites, Docker-backed sandbox tests and platform-specific integrations are not claimed to run in this image. Any extra test runtime or fixture needed offline must be fetched during the online image build first.

## Severity and evidence

These are proposed triage guidelines for maintainer review. Critical requires demonstrated attacker-controlled arbitrary server execution or similarly broad compromise across a real trust boundary. High includes demonstrated unauthorized sensitive-data access, cross-tenant disclosure, stored/script-context XSS, or bypass of an explicitly enabled execution/authorization safeguard. Medium includes remotely triggerable bounded denial of service or narrower integrity/confidentiality loss. State authentication, deployment configuration, attacker capabilities, affected versions and exploit limits; do not rate hypothetical reachability as proven impact.

Report a minimal offline reproducer using public APIs or normal request entry points, expected versus observed behavior, root cause and a focused patch with a regression test. Group reports sharing one root cause and distinguish dependencies' bugs from defects in this repository. Ordinary typing, styling and performance defects without a security effect are lower priority. Examples are test harnesses, not a promise that every example is production hardened.

Send findings only through the configured private report channel. Do not place exploit details or confidential reports in public issues, enrollment files or PRs. This threat model describes intended boundaries and contains no vulnerability findings.
