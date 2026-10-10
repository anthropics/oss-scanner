# Proto UI security review context

## Scope and maturity

Proto UI is an MIT-licensed, framework-independent component interaction protocol
and toolchain. Shared runtime and semantic modules are projected through host
Adapters, including React, Vue and Web Components. The CLI initializes consumer
workspaces and generates configuration, styles and component facades.

This enrollment targets the public `main` branch. Published stable 0.2.0 and
current source are different audit targets: do not infer that a source-only
feature ships in 0.2.0. The current source also contains a private
restricted-TypeScript compiler with differential conformance tooling; it is not
a published compiler profile or a general zero-runtime delivery guarantee.
Many spec entities remain draft. Lifecycle status must be preserved in findings.

## Inputs, trust boundaries and priorities

1. Review CLI parsing, path handling, generated JavaScript/CSS/declarations,
   file replacement and recovery, and package-manager invocation. Exercise
   malformed configuration, names, tokens, paths, existing files and symlinks
   in disposable fixtures. Separate attacker-controlled data from a developer's
   explicit, trusted choice of executable project code or output destination.
2. Review shared runtime/modules and host Adapters where application data,
   text, attributes, URLs, styles or events reach browser operations. Identify
   the actual caller-controlled input and the exact DOM/code sink. Distinguish
   host differences from a security property shared across Adapters.
3. Review the private compiler's restricted-source parsing, validation and
   output generation as source-only tooling. Establish reachability before
   claiming code injection or a bypass; do not assume arbitrary application
   JavaScript is promised to execute safely in a security sandbox.
4. Review generated style handling and Web Component boundaries in their
   documented scope. Shadow DOM is not an application security sandbox.
   Generated style receipts detect stale/accidental edits and are not
   cryptographic authentication of adversarial CSS. Trusted same-source
   artifacts must not be silently recast as untrusted input support.

A malicious dependency or already-authorized arbitrary developer code is not by
itself evidence of a Proto UI vulnerability. Focus on violations introduced by
Proto UI across a demonstrable trust boundary. Accessibility or visual parity
bugs are not automatically security vulnerabilities; explain the concrete
security consequence if one exists.

## Useful source and tests

- `packages/cli/`: initialization, configuration, filesystem and style tooling.
- `packages/runtime/`, `packages/modules/`, `packages/adapters/`: shared behavior
  and host-specific effects.
- `packages/compiler/`: private compiler and differential tests.
- `packages/prototypes/`: reusable component protocols.
- `spec/`: versioned contracts, lifecycle and test links; an applicable spec
  entity takes precedence over explanatory prose.
- `vitest.config.ts`, `scripts/test/run-runtime-tests.mjs` and
  `scripts/test/runtime-test-plan.mjs`: test configuration and browser inventory.
- `apps/www/`: local documentation/demo fixtures and browser regressions.

The image uses Node.js 24, pnpm 10.32.1 and preinstalled Chromium. From `/src`:

```sh
corepack pnpm@10.32.1 check:types
corepack pnpm@10.32.1 test:types
corepack pnpm@10.32.1 test:release
corepack pnpm@10.32.1 test:runtime
# Full repository aggregate (includes documentation and governance checks):
corepack pnpm@10.32.1 test
```

For a focused regression, pass an existing test-file filter to
`corepack pnpm@10.32.1 test:runtime -- <path>`; inspect whether that browser test
starts its own local server. The unfiltered runtime runner manages a shared
loopback-only development server for its registered development browser matrix.
Production-only browser suites have separate owners recorded in
`scripts/test/runtime-test-plan.mjs`; the runtime command alone is not proof of
full production-browser coverage.

All dependencies and tools must be present before offline scanning begins.
Use local fixtures only. No credentials, user files, external-service access,
publishing, deployment or live-site exploitation is needed. Native GPUI work
and non-browser platforms are outside this initial Node/Chromium build recipe;
report unsupported setup rather than claiming those paths were tested.

## Findings and severity

For each finding, provide the audited commit, affected file/line, attacker
capability, reachable input-to-effect chain, minimal offline reproducer,
expected versus observed behavior, and a regression test where practical.
State whether the affected path is published, source-only, experimental or
otherwise restricted, and identify duplicates sharing the same root cause.

Prioritize demonstrated unauthorized script execution, unintended filesystem
writes, command injection, confidential-data exposure and meaningful denial of
service. Severity should follow demonstrated reachability, privilege, impact
and realistic attacker control. Do not label speculative execution paths as
critical, or a developer intentionally running trusted code as remote execution.
A proposed minimal patch is useful but must be reviewed and tested; passing a
reproducer alone is not a security guarantee.
