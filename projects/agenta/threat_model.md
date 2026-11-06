# Agenta threat model

## Purpose and scope

Agenta is a self-hostable workspace for AI coworkers and automations. Users configure agents, run conversations, connect model providers and external tools, share work, and give agents files and code to execute. Agenta therefore processes untrusted content while holding credentials and authority that must not pass to that content.

Scan the public Agenta repository. Prioritize the MIT-licensed application code outside `ee/` directories, as described in the root `LICENSE`. Enterprise code under any `ee/` directory has a separate license and is not part of this enrollment. Third-party dependencies and vendor services are not independent scan targets. A defect in Agenta's use of a dependency is in scope.

Read the checked-out code rather than assuming this document proves a protection exists. The paths below are review starting points, not an exhaustive list. The repository changes frequently. Follow imports and current entrypoints if a path moves.

## Components and assets

- `api/oss/src/` contains the FastAPI application, authentication middleware, authorization, project resources, secrets, sessions, tools, gateways, triggers, channels, templates, and file mounts. PostgreSQL and Redis support these components.
- `services/runner/` is the TypeScript agent runner. It drives agent execution, tool permission checks, approval handling, callbacks, credential delivery, and local or remote execution environments.
- `sdks/python/` and `clients/python/` contain the Python SDK and client used by the API and services. `services/oss/` contains supporting execution services.
- `web/mobile/` is the current web application despite its name. `web/packages/` contains shared frontend and SDK code. `web/oss/` and `web/ee/` are retired desktop applications according to the root contributor guide; shared code still imported from them must be followed where applicable. The current build targets `@agenta/mobile`.

Protect project and organization data, conversation records, files, model and integration credentials, OAuth tokens, subscription logins, webhook secrets, and the host and other execution environments. Protect the integrity of tool approvals, agent configurations, connection selection, and scheduled or event-driven actions.

## Attackers and untrusted inputs

Consider an unauthenticated Internet client, a logged-in user without access to another resource, and a member whose role does not authorize the requested action. Also consider a malicious shared agent or template author, a hostile tool or model endpoint, an external message sender, and code executing inside an agent's permitted environment.

Treat the following as attacker-controlled unless a specific check establishes otherwise:

- HTTP request bodies, headers, route parameters, resource identifiers, cookies, stream reconnect parameters, and uploaded files.
- Channel messages and webhook payloads from Slack, Telegram, WhatsApp, embedded chat, and other adapters. Provider-supplied delivery identifiers and timestamps require validation appropriate to the adapter.
- Model output, tool names and arguments, tool results, Model Context Protocol (MCP) server metadata, and all URLs returned by an upstream. MCP is the protocol used to expose external tools to an agent.
- Imported agent packages, ZIP members, repository content, skills, manifests, configuration references, attachment names, mount-relative paths, and generated HTML, Markdown, SVG, and other previews.
- Files, relay requests, process output, and environment-visible material that sandbox code can change.

## Security boundaries to examine

### Authentication and resource access

Start at `api/oss/src/middlewares/auth.py`, `api/oss/src/core/access/`, `core/memberships/`, `core/sharing/`, and their FastAPI routes. Check project and organization scoping at both route and storage boundaries. An identifier, slug, stream cursor, session ID, or resource reference is not authorization.

Test reads and writes separately, including nested resources, shared agents and sessions, attachments, streaming responses, exports, and changes to membership or sharing after a token or cache entry is issued. A project membership must not silently grant every resource-specific capability.

Some callback and ingress routes are intentionally exempt from the ordinary authentication middleware. Follow the handler and its signature, shared-token, visitor-key, or OAuth-state checks before reporting an authentication bypass. Conversely, a public-route exemption must not grant access to unrelated routes through prefix matching or alternate URL forms.

### Credentials and the model/tool gateways

Review `api/oss/src/core/secrets/`, `apis/fastapi/vault/`, `core/gateways/`, and the SDK's connection resolution. Distinguish normal user responses from authorized internal runtime reads. Check nested credential fields, write-only values, subscription login attempts, refresh tokens, errors, telemetry, and logs.

The gateway data routes distinguish Agenta authentication from upstream provider authentication. Review `X-AG-Credentials`, token audiences, grants, expiration, and run claims. A gateway-scoped credential must not become a general API or vault credential. A model or tool must not select a different tenant, provider account, connection, or authority by putting routing fields in its arguments.

Review `api/oss/src/core/gateways/egress.py`, `core/webhooks/utils.py`, the SDK network helpers, and `services/runner/src/tools/ssrf-guard.ts`. Examine server-side request forgery (SSRF), including redirects, name resolution changes, IPv4 and IPv6 encodings, OAuth discovery and registration URLs, metadata services, and credential/header forwarding across destinations. A check at registration time alone does not prove safety at connection time.

Do not assume all outbound network policies share defaults. The gateway has its own secure-default configuration; webhook delivery has separate operator settings. State which settings a reproducer requires, and distinguish an explicit operator exception from a bypass of an enabled restriction.

### Tool permissions, approvals, and execution identity

Review the runner's `permission-plan.ts`, `tools/gateway-policy.ts`, `tools/relay.ts`, `tools/executable-tool-gate.ts`, `tools/execution-authorization.ts`, and `tools/commit-authorization.ts`, together with SDK permission compilation and API callbacks.

A tool that needs approval must not run before approval. A denial must remain a denial across execution engines and callback paths. An approval must authorize the actual arguments, resolved file content, resource, connection, session, and operation that execute. Examine replay, stale approvals, argument substitution, mutable files, concurrent runs, retry/resume, and reconnect paths.

Tool catalog descriptions and read-only hints are metadata, not a substitute for the execution-side policy. Model-generated arguments and a caller-supplied tool-call ID must not create authority. An agent must not widen its own effective permission by editing a local configuration copy or relay record.

The runner's HTTP server is an internal service with its own authentication contract. Review `services/runner/src/server.ts` and the API-to-runner clients. Do not assume the runner is intended to be exposed as an unauthenticated public endpoint.

### Files, imports, and execution environments

Review `api/oss/src/core/mounts/`, `core/sessions/attachments/`, `core/agent_templates/`, and the corresponding routes, SDK, runner workspace readers, materialization, and mount setup.

Check path traversal, absolute paths, mixed separators, symbolic links, race conditions, object-storage prefixes, scoped storage credentials, archive extraction, decompression limits, and resource ownership. Files and storage credentials must stay within the mount and authority granted to that execution. Imported configuration must not smuggle credentials or connection bindings from another project.

Distinguish local execution from an isolated remote sandbox. Agenta intentionally supports shell commands and user-authored code. Executing code in the caller's own authorized environment, reading files that were deliberately mounted there, or using credentials deliberately injected into that environment is not by itself a vulnerability. A useful finding demonstrates access beyond the granted environment, another user or project, a protected path, or a credential/capability that should have remained outside it.

Do not claim that a declared filesystem or network preference is enforced for every provider without checking the provider implementation and its documented limitations. Report a mismatch between an enforceable promised restriction and execution behavior with the relevant provider and configuration.

### Browser previews and generated applications

Review `web/packages/agenta-entities/src/drive/htmlApp/` and `web/packages/agenta-entity-ui/src/drive/htmlApp/`, plus Markdown, SVG, file download, and attachment renderers.

An HTML app may run scripts in a restricted iframe, but it must not gain the host application's origin, login state, or unrestricted file authority. Review message-source validation, transferred ports, navigation, granted path scopes, read/write grants, and grant revocation. Running a script inside its intended isolated frame is expected. Executing it with the host page's privileges or exceeding its file grant is not.

### Event-driven execution and callbacks

Review `core/triggers/`, `core/channels/`, `core/webhooks/`, and their routes and tasks. Check signature verification, replay handling, delivery deduplication, sender identity, project/resource binding, and permission checks when an event becomes an agent run. A valid provider signature does not necessarily authorize the sender to use every agent or connection.

## Offline build and tests

The enrollment Dockerfile uses the Agenta repository root as its build context and keeps the checkout at `/src`. It installs separate locked Python environments for `api`, `services`, and `sdks/python`; installs and builds the runner extension; and builds the current web application and its shared packages. It retains development dependencies and source files for investigation. PostgreSQL and Redis binaries are available for local experiments but are not automatically started or populated.

The image does not contain a deployed Agenta stack, real accounts, provider credentials, or production data. Use synthetic fixtures and mocked upstreams. Do not contact any public or private Agenta deployment, cloud metadata service, real customer, or external provider. A local mock can demonstrate an attack without contacting the actual target.

The commands below select existing tests that can run without external services. They are starting points, not a claim of complete security coverage. Run them inside the scanner's offline shell. Python commands use the installed virtual environment directly, so `uv` need not resolve anything after networking is disabled.

```bash
cd /src/api
.venv/bin/python -m pytest -o addopts='' -q \
  oss/tests/pytest/unit/agent_templates/test_archive.py \
  oss/tests/pytest/unit/mounts/test_mount_name.py \
  oss/tests/pytest/unit/mounts/test_storage_prefix.py \
  oss/tests/pytest/unit/gateways/test_gateways_blocked_address_ranges.py

cd /src/services/runner
pnpm exec vitest run --project unit \
  tests/unit/attachment-path-safety.test.ts \
  tests/unit/execution-authorization.test.ts \
  tests/unit/commit-authorization.test.ts \
  tests/unit/gateway-policy-intake.test.ts \
  tests/unit/permission-plan.test.ts \
  tests/unit/ssrf-guard-vectors.test.ts

cd /src/web/packages/agenta-entities
pnpm exec vitest run \
  tests/unit/htmlApp.scope.test.ts \
  tests/unit/htmlApp.scopeToken.test.ts \
  tests/unit/htmlApp.manifest.test.ts \
  tests/unit/htmlApp.grants.test.ts
```

Other useful suites are in `api/oss/tests/pytest/unit/{access,auth,sharing,secrets,gateways,managed_tools,sessions,triggers,channels,mounts,agent_templates}/`, `services/runner/tests/unit/`, and the shared frontend packages' `tests/unit/` directories. Some tests require running dependencies or intentionally mock enforcement. In particular, the API unit conftest stubs some resource checks by default; tests that need the real checks opt out. A passing mocked unit test does not demonstrate that the complete deployed path is safe.

Acceptance and integration tests can require PostgreSQL, Redis, authentication services, an initialized application, or external model APIs. Do not treat missing services or credentials as a vulnerability. If a reproduction needs supporting services, initialize them locally with test-only data and no Internet access. Keep test commands bounded for the scanner's CPU and memory limits.

## Severity guidance

Rate the demonstrated impact and required attacker authority, not the name of the bug class. State whether a finding works in a default supported configuration or requires an explicit operator change.

- Critical: Demonstrated unauthenticated compromise of the application host or equivalent broad control. A demonstrated sandbox escape or cross-tenant flaw with broad credential theft or arbitrary execution can also be critical. Do not infer critical severity from a suspicious primitive alone.
- High: Demonstrated unauthorized access to another user's or project's sensitive data or credentials; consequential privilege escalation; approval bypass that performs a protected external action; host-origin script execution that exposes authenticated data or capabilities; or SSRF with demonstrated sensitive read/write impact.
- Medium: A demonstrated security impact with narrower reach, material preconditions, or limited availability damage. For example, a bounded local resource-exhaustion flaw with a realistic untrusted input may be medium.
- Low: Limited security impact that does not establish meaningful access to protected data or actions. Keep informational hardening suggestions separate from vulnerabilities.

The enrollment requests email and GitHub private vulnerability reports at `high` and above. Do not inflate a finding to meet the delivery threshold. Keep the model-generated findings private; do not open public issues or publish exploit details.

## Report and patch guidance

For each finding, provide the affected revision and source locations, attacker role, preconditions and relevant configuration, the intended boundary, exact reproduction steps, expected and actual results, and demonstrated impact. State what was executed and what is inferred. Use synthetic identifiers, addresses, and secrets. Do not include real tokens or customer data.

Include a small deterministic reproducer or regression test that fails before the fix. For authorization findings, show a permitted control case and the forbidden case. Use real enforcement code wherever possible; identify every mocked dependency and never mock away the check under review.

Prefer a minimal patch at the shared enforcement boundary. Explain compatibility effects and run the targeted regression tests after the patch. Do not silently weaken authentication, permission checks, path guards, network policy, or secret redaction to make a test pass. Group findings with the same root cause and list all affected execution paths.

Do not report prompt injection alone, a dependency version alone, intentional execution of approved code, intentional access granted to an app, operator access to their own host, unsupported deployment changes, or missing external services as an Agenta vulnerability. A concrete application-boundary bypass caused by those inputs remains in scope.
