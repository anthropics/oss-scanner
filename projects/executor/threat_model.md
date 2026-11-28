# Executor

## Scope and architecture

Scan the public `v2` branch of UsefulSoftwareCo/executor. It contains the
Executor SDK, app framework, MCP server, local/desktop product, self-hosted
server, and Cloudflare-hosted implementation. The public default branch is an
older product; do not substitute it for v2.

Executor connects AI agents to applications and third-party services. It stores
credentials, brokers OAuth, executes authored application code in workerd, and
exposes authorized operations over HTTP and MCP. A flaw at these boundaries
can expose connected accounts or allow unintended actions on their behalf.

Prioritize packages/sdk, packages/apps, packages/mcp, packages/app-templates,
packages/catalog, apps/local/server, apps/hosted/server, apps/hosted/self-host,
and apps/hosted/cloud, including their browser authentication flows.

## Adversarial inputs and security properties

Treat unauthenticated HTTP requests, authenticated users from another owner or
organization, MCP clients, imported repositories/packages, authored app source,
remote MCP/OpenAPI/GraphQL descriptions and responses, OAuth discovery/client
metadata, redirect URIs, webhook payloads, and browser content as potentially
hostile. Distinguish public metadata from credentials and privileged host APIs.

Investigate authentication and tenant isolation, object-level authorization,
credential selection and disclosure, OAuth state/PKCE/token binding and redirect
validation, refresh races, approval bypass or replay, unauthorized writes after
cancellation, sandbox/host boundary escapes, SSRF, path traversal, archive and
Git input handling, browser session security, and injection through imported
schemas or source. Trace an issue to a reachable product entry point.

Authored app code intentionally executes inside its sandbox and can perform
operations using credentials explicitly selected for that app/profile. Merely
running authored code or making an authorized external request is not a sandbox
escape. Show how an attacker exceeds that authority. Local filesystem access by
someone already controlling the host OS is not by itself a remote vulnerability.
Differentiate local single-user assumptions from hosted multi-user boundaries.

Do not contact production services or real users, use real credentials, or
attempt external exploitation. Use synthetic identities and local emulators.
Cloud infrastructure deployment, third-party outages, and marketing content
without a demonstrated security boundary are outside the executable test setup.
Cloud source remains in scope for analysis; validate with a local reproducer.

## Build and offline reproduction

The checkout is /src. Node 24.18.0, Bun 1.4.2, dependencies, Chromium, ffmpeg,
built dashboards, app framework, Motel collector, test runtime, app tarball,
and packaged self-host runtime are prepared during image build.

Start with `bun run e2e:pglite` for a small in-process database check.
Before running browser scenarios, run:

```sh
mkdir -p /root/.cache
ln -s /opt/playwright /root/.cache/ms-playwright
```

The suite deliberately filters child-process environment variables, including
PLAYWRIGHT_BROWSERS_PATH. This points Playwright's default root cache at the
already installed Chromium without a download. Run the symlink setup once in a
fresh image. The local OAuth callback-fragment scenario passed offline after
this setup. WebKit is not installed; WebKit-specific scenarios need that browser
added during the online build.

See e2e/README.md and e2e/test-plan.ts for product scenarios. Local/self-host
scenarios can be selected with `bun run e2e --target local --workers 1
--test-name '<scenario title>'` (or `--target self-host`). Some scenarios fetch
new app dependencies, exercise remote services, or need additional infrastructure;
these are not guaranteed offline merely because the source is present. Adapt
reproducers to installed dependencies and loopback emulators and explicitly
report any remaining setup limitation. Cloud E2E requires extra infrastructure
and is not claimed to run in this container. Do not invoke production deployment
scripts or commands that load service credentials.

## Findings and severity

Provide the affected revision, entry point, attacker prerequisites, minimal
self-contained local reproducer, expected and actual behavior, concrete security
impact, and a focused candidate patch with a regression test when possible.
Deduplicate paths that share a root cause. Clearly distinguish confirmed impact
from conjecture and identify which local/self-host/cloud variants are affected.

Critical: demonstrated unauthenticated host code execution, broad cross-tenant
credential compromise, or comparable systemic compromise.
High: demonstrated tenant-boundary bypass, theft of another user's credentials,
sandbox escape, or unauthorized sensitive actions beyond granted permissions.
Medium: bounded confidentiality/integrity impact or significant denial of service
with clear prerequisites. Low: limited hardening issues without substantial
exploit impact. Rate by demonstrated reachability and impact, not a bug class
alone; intentional app capabilities are not vulnerabilities by themselves.
