# TanStack Form threat model

## Scope and trust boundaries

This enrollment covers https://github.com/TanStack/form, with emphasis on substantive server execution. Relevant packages: `packages/form-core`, `packages/react-form`, `packages/react-form-nextjs`, `packages/react-form-remix`, `packages/react-form-start`.

Untrusted inputs: multipart/FormData keys and values, repeated and nested field names, uploaded-file metadata, request headers, serialized validation state and cookies.

Priority boundaries: Server validation adapters for Start, Next.js and Remix; FormData decoding and object construction; validator invocation and error propagation; server-to-client state serialization; Start cookie and redirect handling; shared core paths used by these adapters.

A form library does not supply application authentication, CSRF protection for every hosting framework, business authorization or safe database writes. User input must still be validated by application schemas. Demonstrate bypass of configured validation or a library-owned unsafe transformation, rather than absence of an application validator.

## Build and offline exercises

The Dockerfile uses the upstream `.nvmrc`, exact pnpm version and frozen lockfile. Source, dependencies, tests and built output remain under `/src`; package output is in `dist/` or `build/` according to each package configuration. It builds the listed packages and their declared dependency graph. Other repository source remains available for inspection.

From `/src`, rerun. For an offline verification, set `NX_SKIP_NX_CACHE=true` first so Nx executes the tests instead of returning results cached during image setup:

```sh
pnpm exec nx run-many --target=build --projects=@tanstack/form-core,@tanstack/react-form,@tanstack/react-form-nextjs,@tanstack/react-form-remix,@tanstack/react-form-start --parallel=2 --skipRemoteCache
pnpm exec nx run-many --target=test:lib --projects=@tanstack/form-core,@tanstack/react-form,@tanstack/react-form-nextjs,@tanstack/react-form-remix,@tanstack/react-form-start --parallel=2 --skipRemoteCache
```

Use existing package tests and local, synthetic fixtures. Do not use real credentials, customer data, external production services or deployment commands. Live cloud/provider tests, browser E2E suites, Docker-backed sandbox tests and platform-specific integrations are not claimed to run in this image. Any extra test runtime or fixture needed offline must be fetched during the online image build first.

## Severity and evidence

These are proposed triage guidelines for maintainer review. Critical requires demonstrated attacker-controlled arbitrary server execution or similarly broad compromise across a real trust boundary. High includes demonstrated unauthorized sensitive-data access, cross-tenant disclosure, stored/script-context XSS, or bypass of an explicitly enabled execution/authorization safeguard. Medium includes remotely triggerable bounded denial of service or narrower integrity/confidentiality loss. State authentication, deployment configuration, attacker capabilities, affected versions and exploit limits; do not rate hypothetical reachability as proven impact.

Report a minimal offline reproducer using public APIs or normal request entry points, expected versus observed behavior, root cause and a focused patch with a regression test. Group reports sharing one root cause and distinguish dependencies' bugs from defects in this repository. Ordinary typing, styling and performance defects without a security effect are lower priority. Examples are test harnesses, not a promise that every example is production hardened.

Send findings only through the configured private report channel. Do not place exploit details or confidential reports in public issues, enrollment files or PRs. This threat model describes intended boundaries and contains no vulnerability findings.
