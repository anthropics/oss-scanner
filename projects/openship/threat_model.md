# Openship threat model

## Project and entry points

Openship is an Apache-2.0 deployment control plane with a Hono API, Next.js
dashboard, Electron desktop app, CLI, SDK, managed Cloud integration, and an
OpenResty routing edge. It deploys application code and manages infrastructure,
credentials, environment variables, domains, backups, and Actions jobs.

Treat HTTP and WebSocket requests, OAuth clients, scoped API tokens, webhooks,
repository contents, Compose definitions, archives, imported configuration,
container output, remote endpoints, and DNS responses as untrusted inputs.
Possession of a resource identifier does not establish permission to use it.

## Deployment modes and boundaries

- **Managed Cloud:** organizations are separate tenants. Authentication to one
  organization must not grant access to another organization's projects,
  workloads, credentials, billing, backups, or management operations. Tenant
  code must not gain access to the Cloud control-plane host or its credentials.
- **Cloud management of customer servers:** the hosted control plane may manage
  a server using credentials supplied by its authorized customer. That must not
  grant access to provider-owned hosts or another tenant's servers. Check which
  management features exist at the scanned revision rather than assuming that
  every self-hosted operation is enabled in Cloud.
- **Self-hosted and desktop:** an operator can intentionally administer their
  own machine and connected servers, including privileged shell access. This is
  not blanket trust for every account, workspace member, token, remote caller,
  or imported record. Examine local-host ownership, credential restrictions,
  role checks, and the explicitly configured native SDK execution policy.
- **Workload execution:** executing an authorized user's build commands is an
  intended feature. Distinguish Docker, bare-host, Cloud, and cluster runtimes.
  Bare execution is not a container sandbox. An untrusted request must not
  select a more privileged execution context or another tenant's resources.

Trace authority from the authenticated caller through the shared engine and
adapters, including background jobs and saved operations. A frontend restriction
is not an authorization boundary. Retained and imported identifiers need the
same checks as newly submitted identifiers. Check revocation and lifecycle races
as well as request-time checks.

## Review priorities

- `apps/api/src/`: authentication, authorization middleware, route registration,
  WebSocket upgrades, OAuth/MCP, webhooks, and proxying between control planes.
- `packages/platform/src/`: shared operations and authorization, resource and
  runtime resolution, deployment orchestration, imports, jobs, secrets, SSH,
  backups, billing, and Cloud management.
- `packages/adapters/src/`: Docker/bare/Cloud/cluster execution, transport and
  filesystem boundaries, archive handling, outbound connections, and the edge.
- `packages/db/src/`: organization scoping, ownership relations, transactions,
  dump/import validation, and concurrent state transitions.
- `packages/actions-runner/`: workflow input, process/container isolation,
  credentials, artifacts, cancellation, and job callbacks.
- `apps/dashboard/`, `apps/desktop/`, `apps/cli/`, and `packages/sdk/`: browser
  sessions, proxy routes, Electron IPC/navigation, local API exposure, and
  credential handling across clients. Shared policy lives in the engine; do
  not stop analysis at a client wrapper.
- `packages/adapters/src/infra/lua/` and `apps/edge/`: hostname and route ownership,
  access rules, management endpoints, traversal, redirects, and TLS handling.
- `apps/email/`: mail integration and webmail are in scope for source review;
  their standalone applications have separate dependency/build requirements.

## Build and offline testing

The complete public checkout is at `/src`. The image installs the locked Bun
workspace dependencies, Node 22, Bun 1.3.14, Go 1.26.9, OpenSSL, OpenSSH, and Lua.
It builds the Actions runners and the normal API/dashboard build. Development
dependencies, Go modules, migrations, fixtures, and build outputs remain in the
image. The API bundle is in `apps/api/dist/`, the dashboard in
`apps/dashboard/.next/`, and runner binaries in `packages/actions-runner/dist/`.

Run focused tests offline using the project's normal wrappers:

```sh
cd /src
bun run --cwd apps/api test test/lib/active-deployment-ownership.test.ts --maxWorkers=2
bun run --cwd apps/api test test/modules/cloud-ingest-isolation.test.ts --maxWorkers=2
bun run --cwd packages/adapters test --maxWorkers=2
bun run --cwd apps/dashboard test --maxWorkers=2
bun run --cwd packages/actions-runner test
```

`bun run test` runs the normal workspace suites, excluding the separate email
app. API/database integration fixtures use disposable PGlite databases and
synthetic identities. Many transport tests mock SSH, Docker, or provider
responses; distinguish those from an actual runtime reproduction. See
`apps/api/test/helpers/`, `apps/api/test/modules/jobs/_harness.ts`, the Vitest
configuration, and `CONTRIBUTING.md` for harness conventions. Do not set real
provider credentials or assume fixture authentication shortcuts exist in
production.

The separate `apps/api/test/e2e/` suite needs Docker and its test images; this
image does not provide a nested Docker daemon or preload those images. Electron
packaging/native desktop execution, standalone email builds, and a running
OpenResty edge are not prepared by this image. Their sources remain available;
state any additional setup required by a reproducer. No production database,
customer application, provider API, or external account should be contacted.

## Reports and severity

Read `/src/SECURITY.md` at the scanned revision, including its distinction
between current policy and historical audit notes. Send findings privately to
the enrollment's security contact, not public issues or pull requests.

Prioritize demonstrated authentication bypass, cross-tenant access, credential
disclosure, privilege escalation, unauthorized host execution, and destructive
operations on another principal's resources. State the hosting mode, attacker
permissions, configuration, exact revision, reachable entry point, and boundary
crossed. Include a minimal reproducer and a regression test when possible.
Do not infer a production compromise from a code finding, or treat legitimate
operator administration as a vulnerability without a separate trust violation.
