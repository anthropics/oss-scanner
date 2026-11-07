# Marionette threat model

Prepared from public `marionettejs/marionette` master at
`909890031209404fd8a375447abf51cc3a35ebfe` on 2026-10-20. This is proposed scan
guidance for maintainer review, not an independently established security policy.
The enrollment follows `master`; recheck these facts when that branch changes.

## Project and scope

Marionette v5 is an MIT-licensed JavaScript UI library with TypeScript source,
explicit View/Region/Application ownership, lifecycle management, events and
configurable rendering, DOM, data and state providers. This repository also owns
`@mnjs/utils`, `@mnjs/radio`, `@mnjs/data` and `@mnjs/adapters`. Audit their
first-party implementations together: `src/`, `packages/*/src/` and the emitted
ESM, CommonJS and UMD artifacts. Runtime dependencies and adapters are boundaries
to inspect, not authorization to scan independent upstream repositories.

Prioritize template/data-to-DOM flows, DOM attributes and event delegation,
model/collection identity and serialization, property assignment and inherited
keys, provider integration, and lifecycle/cancellation that can expose stale or
wrong-owner data. Review executable packaging/development tools when a concrete
untrusted input can cross a filesystem, process or served-content boundary.
Docs and examples help establish intended behavior; prioritize shipped code.

## Attacker influence and trusted inputs

Applications may pass remotely supplied strings, JSON-shaped records, model
attributes, collection identities and event payloads through this library.
Trace such data through native and optional data providers, serialization,
template context, DOM insertion, event handling and observer cleanup. Show how
an attacker can actually influence the input in a supported consumer workflow.

Templates, renderer/provider functions, callbacks, classes, selectors and
application configuration are developer-supplied code/configuration. They are
not an execution sandbox for hostile plugins, arbitrary JavaScript objects with
attacker-defined getters or proxies, or untrusted template programs. The core
does not supply a network server, authentication, tenant authorization, API
transport or persistence. Those controls belong to consuming applications.

The native DOM provider assigns template output to `innerHTML`; attribute values
go through `setAttribute`. The documented contract requires applications to
escape untrusted text or use a renderer with safe text interpolation, sanitize
deliberate raw HTML, and enforce allowed URL schemes. A reproduction that puts
raw attacker HTML into a developer-authored HTML template only demonstrates this
documented application responsibility. Do investigate a library/adapter defect
that breaks a renderer's documented text boundary or crosses its owned DOM root.
Consider Lit, morphdom and jQuery adapter behavior separately; do not assume
identical escaping or DOM ownership semantics.

For assignment/lookup issues, demonstrate a public path from data keys or IDs to
unintended prototype mutation, inherited-property interpretation or another
concrete security effect. Do not infer prototype pollution solely from seeing
an assignment or from arbitrary hostile code already running in the same realm.

Events and Radio channels coordinate code in one JavaScript realm; channel names
are not access controls. Application readiness supports cooperative abort and
suppression of stale completions. Retained/restarted views and listener teardown
matter when a supported lifecycle can expose previous data or handlers. A leak,
crash or stale render needs demonstrated security consequences before assigning
high severity. Synchronous callback failures are documented to abort an operation;
do not presume transactional rollback or attempt-all cleanup after a throw.

## Reproduction environment

The Dockerfile uses the checked-in source toolchain: Node 24.19.0, npm 11.17.0,
the npm v3 lockfile, TypeScript/Rollup, Vitest/JSDOM, and Playwright 1.64.0.
It installs Chromium headless shell, Firefox and WebKit plus their Linux libraries
during the network-enabled build. The browser development-kit test installs its
own pinned consumer tooling; an online Chromium run warms the npm cache before
the full browser suite runs offline with `npm_config_offline=true`.
`/src` contains the source, `node_modules`,
generated `dist`/`.package` outputs and package builds; browsers are under
`/opt/playwright-browsers`.

The Dockerfile attempts the following with BuildKit networking disabled:

```sh
npm run check:release-profile
npm run check:browser-profile
npm run prepare
npm run test:source
npm test
npm_config_offline=true npm run test:browser
```

`prepare` invokes the full package build, declarations, type-consumer checks,
packaged docs and distribution validation. Unit tests exercise native data and
DOM behavior. Browser tests use locally packed first-party artifacts and a
loopback-only fixture HTTP server; they need no external site. Useful focused
commands are `npm test -- --project=node`, `npm test -- --project=dom`, and
`npm run test:browser -- --project=chromium` (run browser tests via npm).

Build with the public source checkout as context, then independently rerun in an
offline container (no host mounts, credentials or Docker socket):

```sh
docker build --progress=plain -t marionette-oss-scanner \
  -f /path/to/oss-scanner/projects/marionette/Dockerfile /path/to/public-marionette
docker run --rm --init --network=none --shm-size=1g marionette-oss-scanner \
  bash -lc 'npm run prepare && npm run test:source && npm test && npm_config_offline=true npm run test:browser'
```

The development browsers run in an isolated audit container; this environment
does not establish a production browser sandbox guarantee. Beyond the browser
development-kit case, the full installed-consumer fixture inventory, full
documentation checks, mutation/performance suites and agent
benchmark environment setup may require additional dependencies/caches and have
not been certified offline by this draft. Do not assume every repository script
is offline-ready. No model calls, deployment or publishing are needed for this
runtime audit.

## Severity and reporting preferences

Proposed severity should follow demonstrated impact and prerequisites. Cross-user
or cross-origin script execution or unauthorized data disclosure in a supported
integration can justify high severity. Reserve critical for demonstrated broad
compromise with a realistic attack path, not a generic UI bug. Availability-only
issues depend on realistic attacker-controlled work amplification and affected
scope; normal application exceptions and configuration mistakes are ordinary
bugs. Explain application preconditions rather than treating all consumers as
vulnerable. Maintainers make the final severity determination.

Provide the exact commit/package version, affected public API/provider, attacker
input and violated contract, minimal isolated reproduction, observed impact and
prerequisites, and a focused regression test. Demonstrate against first-party
code using synthetic data; never probe real consumer deployments. Include a
small candidate patch where useful. Deduplicate by root cause and violated
boundary, listing other affected APIs/providers under that report.

Current `SECURITY.md` requests private reports through
https://github.com/marionettejs/marionette/security/advisories/new and does not
publish a report email or promise a response deadline/backports. Preserve that
private reporting expectation. The maintainer has confirmed
`marionettejs@gmail.com` as the public enrollment report mailbox.
Do not place vulnerability details, credentials or private application data in
public issues, logs or proposed enrollment comments.
