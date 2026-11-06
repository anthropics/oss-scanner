# TanStack AI threat model

## Scope and trust boundaries

This enrollment covers https://github.com/TanStack/ai, with emphasis on substantive server execution. Relevant packages: `packages/ai`, `packages/ai-code-mode`, `packages/ai-mcp`, `packages/ai-persistence`, `packages/ai-isolate-node`, `packages/ai-isolate-quickjs`, `packages/ai-sandbox`, `packages/ai-skills`.

Untrusted inputs: user messages, provider streams, model-generated tool names and arguments, tool results, uploaded or fetched content, MCP responses, persisted conversation data and generated code.

Priority boundaries: Tool dispatch and validation, approval and execution state, provider protocol conversion, stream parsing, cancellation and resource cleanup, persistence isolation, MCP integration, skills file handling, sandbox/isolate bridges and code-mode capabilities. Include provider adapters and their shared openai-base code.

Model output and tool output are untrusted. Prompt injection alone is not proof of a library vulnerability: demonstrate a violated library capability or approval contract. Application-defined tools, credentials and authorization policy are trusted configuration. Local-process execution is not assumed to promise isolation equivalent to a VM; judge each driver by its documented guarantees. Never contact real model providers or use real API keys.

## Build and offline exercises

The Dockerfile uses the upstream `.nvmrc`, exact pnpm version and frozen lockfile. Source, dependencies, tests and built output remain under `/src`; package output is in `dist/` or `build/` according to each package configuration. It builds the listed packages and their declared dependency graph. Other repository source remains available for inspection.

From `/src`, rerun. For an offline verification, set `NX_SKIP_NX_CACHE=true` first so Nx executes the tests instead of returning results cached during image setup:

```sh
pnpm exec nx run-many --target=build --projects=@tanstack/ai,@tanstack/ai-code-mode,@tanstack/ai-mcp,@tanstack/ai-persistence,@tanstack/ai-isolate-node,@tanstack/ai-isolate-quickjs,@tanstack/ai-sandbox,@tanstack/ai-skills --parallel=2 --skipRemoteCache
pnpm exec nx run-many --target=test:lib --projects=@tanstack/ai,@tanstack/ai-code-mode,@tanstack/ai-mcp,@tanstack/ai-persistence,@tanstack/ai-isolate-node,@tanstack/ai-isolate-quickjs,@tanstack/ai-sandbox,@tanstack/ai-skills --parallel=2 --skipRemoteCache
```

Use existing package tests and local, synthetic fixtures. Do not use real credentials, customer data, external production services or deployment commands. Live cloud/provider tests, browser E2E suites, Docker-backed sandbox tests and platform-specific integrations are not claimed to run in this image. Any extra test runtime or fixture needed offline must be fetched during the online image build first.

## Severity and evidence

These are proposed triage guidelines for maintainer review. Critical requires demonstrated attacker-controlled arbitrary server execution or similarly broad compromise across a real trust boundary. High includes demonstrated unauthorized sensitive-data access, cross-tenant disclosure, stored/script-context XSS, or bypass of an explicitly enabled execution/authorization safeguard. Medium includes remotely triggerable bounded denial of service or narrower integrity/confidentiality loss. State authentication, deployment configuration, attacker capabilities, affected versions and exploit limits; do not rate hypothetical reachability as proven impact.

Report a minimal offline reproducer using public APIs or normal request entry points, expected versus observed behavior, root cause and a focused patch with a regression test. Group reports sharing one root cause and distinguish dependencies' bugs from defects in this repository. Ordinary typing, styling and performance defects without a security effect are lower priority. Examples are test harnesses, not a promise that every example is production hardened.

Send findings only through the configured private report channel. Do not place exploit details or confidential reports in public issues, enrollment files or PRs. This threat model describes intended boundaries and contains no vulnerability findings.

For Node isolate tests, retain `NODE_OPTIONS=--no-node-snapshot`. Native dependencies are built under the upstream install policy. The selected unit suites use mocks/local fixtures; remote provider and sandbox-driver integrations need separate offline fixtures.
