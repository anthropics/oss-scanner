# OpenClaw scanner guidance

## Authoritative policy

Read `/src/SECURITY.md` at the scanned revision. It is authoritative for trust
boundaries, exclusions, endpoint-specific authorization, and report requirements.

OpenClaw is local-first agent infrastructure for trusted operators. It connects
a Gateway, agent runtimes, tools, a browser-based Control UI, messaging plugins,
and companion applications. Untrusted inputs include incoming messages and
attachments, HTTP and WebSocket requests, webhook payloads, web content, model
outputs, and downloaded files or archives.

## Boundaries and priorities

Prioritize reachable production paths that let untrusted input cross an actual
authentication, pairing, sender authorization, tool-policy, execution-approval,
configured sandbox, filesystem, or credential boundary. Investigate Gateway
request handling, channel ingress, tool execution, browser automation, file and
archive handling, and secret handling. Follow shared implementations into
`packages/` and plugin implementations into `extensions/`; do not limit analysis
to `src/`.

Key policy distinctions:

- Shared-secret Gateway callers are trusted operators; session routing does
  not provide hostile-user isolation.
- Installed plugins, operator configuration, process environments, and host
  state are trusted. Intentional execution capabilities need a separate bypass.
- Prompt injection alone is excluded. Context visibility and trigger
  authorization are different contracts.
- State the executor and sandbox configuration. Node Code Mode's VM is not an
  isolation boundary; QuickJS and OS sandboxes have distinct contracts.
- Dependency and resource-exhaustion claims need demonstrated OpenClaw impact.
  Test-only and maintainer-only surfaces are not production entry points.

Apply the full policy, rather than extending these summaries into new exclusions.

## Build and offline testing

The Dockerfile retains the complete checkout at `/src`, installs development
dependencies with the repository's pinned pnpm and frozen lockfile, and runs
`pnpm build`. Node, Bun, native compilation tools, and Playwright Chromium remain
in the image. Chromium is cached at `/opt/playwright` before networking is
disabled. The generated CLI and Control UI are available under `dist/`.

Use the repository's test wrappers, which select the appropriate test projects.
For example:

```sh
cd /src
pnpm test packages/net-policy/src/ip.test.ts --maxWorkers=1
pnpm test src/gateway/auth-surface-resolution.test.ts --maxWorkers=1
```

Consult `docs/help/testing/suites.md` and `package.json` for current commands.
Run full workspace compilation during the online build stage and use focused
source tests during offline analysis. Preserve original failure output and
distinguish an environment or fixture problem from a product defect.

Use synthetic data and local fixtures that run without real provider credentials,
channel accounts, or external services. Native macOS, iOS, and Android application
sources are also available for review.

For CLI reproduction, use `pnpm openclaw ...` and an isolated temporary state
directory/profile. Do not assume the scanner's root shell or its container
privileges describe a normal OpenClaw deployment.

## Reports and severity

Include the commit, affected code, prerequisites, attacker control, boundary
crossed, reproduction, observed impact, and proposed fix. Verify release claims
against the released artifact. Explain policy applicability and base severity
on demonstrated impact. Prefer focused patches with boundary-level regressions.

Send findings through this enrollment's private email delivery to
`josh@openclaw.org`. Do not publish vulnerability details in public issues or
pull requests.
