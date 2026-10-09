# Nautilo security audit

## Project and trust boundaries

Nautilo is an MIT-licensed, self-hosted, multi-user AI workspace. Humans and
their agents collaborate in Rooms, delegate durable Tasks, and work with
private or shared Memory, documents, and Artifacts. A server supplies the web
Workbench; Desktop and Mobile connect to that server. Agents can invoke tools
and, when authorized, request execution on connected devices.

Treat unauthenticated network clients, lower-privileged authenticated users,
uploaded files, imported documents, web pages, model output, tool results, and
external MCP/provider responses as potentially hostile. Authentication,
membership, capabilities, data/decryption authority, and user consent are
distinct checks. A tool description or model instruction grants no authority.

The operating-system administrator and deployment operator can control their
own installation. An ordinary user, model, document, or remote client must not
inherit that authority. A malicious user must not gain another user's data or
device access simply because both use the same Nautilo server.

## Priority areas

All externally reachable HTTP routes and WebSocket message handlers implemented
in this repository are in scope, including unauthenticated entry points and
authenticated endpoints accessible to ordinary users. Enumerate entry points
and report coverage gaps or additional reproduction requirements. Inclusion in
scope is not a claim that every endpoint has been exercised.

- **Server authentication and authorization:** HTTP and WebSocket routes,
  principal binding, invitations, Room membership, object ownership, and
  resource scope. Look for cross-user access and confused-deputy behavior.
  Start with `packages/server`, `packages/trust`, and `packages/db`.
- **Private and shared data:** namespace access, encryption admission,
  credentials, Memory, Artifacts, and document versions. Follow authority
  through retrieval, persistence, task execution, and result delivery. Check
  revocation and membership changes across queues, retries, and restarts.
  Relevant owners include `packages/runtime`, `packages/lattice-crypto`,
  `packages/lattice-bridge`, `packages/vault`, and server compositions.
- **Agent and tool execution:** untrusted inputs must not bypass tool policy,
  approvals, filesystem grants, or runtime scope. Trace the complete path from
  tool arguments to the actual executor in `packages/agent`,
  `packages/security`, and `packages/sandbox`.
- **Connected devices:** relay authentication, IPC sender validation, device
  and session binding, filesystem paths and symlinks, process execution,
  cancellation, and stale grants. Inspect `packages/relay`,
  `packages/desktop-filesystem-grants`, `packages/workstation-profiles`,
  `packages/computer-use-host-protocol`, `packages/computer-use-host`, and
  `apps/desktop/electron`. Keep Desktop, headless Relay, and native Host
  authority separate.
- **Untrusted content and outbound requests:** document and archive import,
  uploads, rendered HTML/Markdown/SVG, mini-app assets, path traversal, SSRF,
  command injection, and credential leakage through logs or model-visible
  content. Inspect server handlers, Workbench, document packages, connected
  website adapters, and MCP integration.

These are audit priorities, not assertions that any particular defect exists.
`README.ai`, `AGENTS.md`, and package manifests provide further source maps.

## Environment and reproduction

The complete public checkout and installed workspace dependencies are in
`/src`. The image uses the contributor Bun pin and Node 24. Server and agent
code run directly from TypeScript; built Workbench assets are in
`apps/workbench/dist`. Source-owned Office dependencies are prepared during
the build. No provider credentials or real user data are included.

### What the supplied Dockerfile delivers

| Capability | Delivered by this image |
| --- | --- |
| Public source, locked workspace dependencies, Bun and Node | Installed under `/src` and available offline |
| Workbench and source-owned Office build outputs | Built for inspection and the documented tests |
| Linux PTY binding and password-hashing dependency | Available for local execution/reproduction tests |
| Default process | A Bash shell; no Nautilo services start automatically |
| PostgreSQL, Logto, database migrations applied to a live instance | Not provisioned |
| Docker Engine/Compose infrastructure for a development stack | Not provisioned or exposed by this Dockerfile |
| Claimed owner, logged-in browser, configured Genie/model | Not provisioned |
| Model server, weights, deterministic provider fixture, or provider credentials | Not supplied |

The validated deliverable is an offline source/build/unit-test environment.
Installation, first login, and a first model response have not been validated
in this image. The optional procedure below describes additional setup, not
an already-running service or a one-command offline instance installer.

Run package scripts from `/src`, for example:

```sh
bun run --cwd packages/security test:unit
bun run --cwd packages/trust test:unit
bun run --cwd packages/desktop-filesystem-grants test:unit
bun run --cwd packages/relay test:unit
```

The scanner shell runs as root. The server unit suite includes tests that
expect writes to protected filesystem locations to fail; run it as the image's
unprivileged `node` user so Unix permission checks are meaningful:

```sh
runuser -u node -- bash -c 'git config --global --add safe.directory /src && cd /src && bun run --cwd packages/server test:unit'
```

Use package test runners rather than one repository-wide `bun test` command:
some tests require isolation because they replace modules. Prefer focused
synthetic regression tests that exercise the actual public route or authority
boundary, with an allowed control case and a denied adversarial case.

The audit runs offline. The image does not provision PostgreSQL, Logto, model
providers, hosted browser services, or a running Nautilo instance. Tests that
need them are integration tests and require separate disposable fixtures;
do not describe a mocked unit test as end-to-end exploit confirmation. Native
macOS/Windows behavior, signed installers, mobile devices, and OS permission
dialogs cannot be reproduced in this Linux container. Their source and
portable contracts remain in scope; state any platform-dependent evidence
that a maintainer needs to confirm.

Use synthetic identities, files, and secrets in a disposable test environment.
Do not probe existing public Nautilo deployments or reuse maintainer/user
accounts. Any optional provider connection must use an audit-operator-supplied
test account and the network access explicitly permitted for that environment.

## Optional running-instance and model testing

### Prerequisites and offline limits

This section is for agents whose audit operator provides an isolated runtime
environment with the necessary services. Anthropic's normal audit is offline;
these instructions do not change that isolation. Website links are background
references, and cannot be assumed reachable during a scan.

A full instance needs application PostgreSQL with the required extensions,
Logto and its PostgreSQL service, initialized configuration and database roles,
migrations, and the Nautilo server/Workbench. The normal source launcher uses
Docker infrastructure. It cannot run that stack in the supplied audit shell
without additional operator provisioning. Container images, service packages,
browser automation dependencies, and any local model weights must be made
available before network access is removed. Do not assume a Docker socket or
nested Docker support is present.

Use the same source revision as the finding. The public packaged-install
guides can select a stable release different from the audited checkout; record
the actual source commit or image digest if using that route. Missing services
or network access are reproduction limitations to report, not reasons to
bypass authentication, authorization, or device admission.

### Start a fresh instance when infrastructure is available

On the operator-provided development host, work from the audited checkout with
its pinned Bun/Node versions and dependencies. Inspect existing targets with
`bun run dev:list-instances`, select an unused name, and start the source stack:

```sh
bun run dev-stack --instance oss-audit
```

Keep the launcher running. Use its reported instance identity and browser URL.
The source setup command accepts a private deploy configuration and secrets
file; its implementation is `bin/nautilo-dev/src/commands/setup-instance.ts`
and the configuration schema belongs to `packages/deploy-config`.

Prepare those files outside the checkout with mode `0600`. A minimal
`audit-setup.toml` for the current schema is:

```toml
schemaVersion = 1

[admin]
handle = "audit-owner"
displayName = "Audit Owner"
password = { fromEnv = "NAUTILO_AUDIT_PASSWORD" }
pin = { fromEnv = "NAUTILO_AUDIT_PIN" }
```

Put the corresponding operator-chosen test password and separate approval PIN
in `audit-secrets.env`, using those variable names. Retain them for sign-in;
do not include their values in reports. Provider credentials can be added
later. Then, in a second shell:

```sh
bun run dev:setup --instance oss-audit \
  --config /path/to/private/audit-setup.toml \
  --secrets-file /path/to/private/audit-secrets.env
bun run dev:setup-status --instance oss-audit
```

Replace the placeholder paths with the operator-prepared files. For browser
claim testing, follow the normal claim URL/account-creation path instead of
pre-claiming through the setup command. Claim the instance once, keep the
recovery material private, and reuse the same instance after interruption.

Confirm `setupState: ready`, open the reported Workbench URL, and sign in as
the created owner. Server health alone does not prove working login. Use the
browser client for this Linux audit; native Desktop/Mobile installation is
separate qualification.

### Connect a model and verify the first response

For an allowed hosted provider, open **Server admin → API Keys**, save the
audit operator's test credential, validate it, and select a chat model served
by that provider. A stored or validated credential is not evidence that a
complete turn works. Hosted inference requires permitted outbound networking
and an account with access/credit; it cannot be exercised in the normal
network-disabled scan.

For an operator-provided local OpenAI-compatible model endpoint, the generic
gateway adapter uses `NAUTILO_GATEWAY_BASE_URL` and
`NAUTILO_GATEWAY_API_KEY` (with optional `NAUTILO_GATEWAY_LABEL`). Supply these
through the instance's private configuration and select an admitted gateway
model matching the endpoint's actual model ID. The key is required by the
adapter even for a test endpoint; it does not fall back to `OPENAI_API_KEY`.
See `packages/agent/src/providers/universal.ts` and
`packages/agent/src/chat/model-runtime-credentials.ts` for the configuration
and credential-resolution path. These adapter settings do not by themselves
register a model in the catalogue or satisfy model availability/admission.

Verify reachability from the actual server process: localhost refers to its
own network namespace. With networking disabled, an external host or sibling
container is not automatically reachable. A local model must run within the
permitted audit topology and fit its resource budget. No local-model setup or
end-to-end gateway connection is claimed by this enrollment's validation.

Send a short message and require a streamed response, completed turn, and a
persisted transcript after reopening the conversation. Sign out and back in
to verify the owner session. Add an ordinary second user and test private
conversation isolation, shared Room access, and denied cross-user requests.

An operator may instead supply a deterministic local provider fixture to
exercise streaming, error handling, and controlled tool-call responses. Label
that evidence as simulated provider behavior; it does not establish real
model inference or hosted-provider compatibility. No such fixture is bundled.
If no usable model route is available, state that first-response testing was
not performed and continue the source and focused tests that remain possible.

### Public user and operator references

- [Run Nautilo from source](https://nautilo.ai/docs/build/development/local-development): fresh-instance configuration and setup-file format.
- [Your first Nautilo](https://nautilo.ai/docs/operator/deploy/local): the Mac packaged-install journey through a first Genie conversation.
- [Deploy with Docker Compose](https://nautilo.ai/docs/operator/deploy/docker-compose): packaged infrastructure and claim options.
- [Create the first owner](https://nautilo.ai/docs/operator/first-owner): browser claim, sign-in, PIN, and recovery.
- [Add your API keys](https://nautilo.ai/docs/operator/provider-keys): provider setup and validation.
- [Your first hour](https://nautilo.ai/docs/use/first-hour): basic user workflows after joining a server.

The source, test commands, capability table, and setup outline above can be
read without visiting these links. If operators require a fully executable
offline instance, its service packaging, startup procedure, model route, and
login-to-response acceptance must be added and validated separately.

## Findings and severity

Assess severity from demonstrated reachability, attacker prerequisites,
affected users, and impact, rather than a dangerous-looking API alone.

- Critical candidates include unauthenticated arbitrary code execution on a
  server or connected device, or broad compromise of protected user data.
- High candidates include cross-user disclosure or modification of protected
  data, privilege escalation, credential theft, and execution beyond granted
  device/tool authority. Explain the required account, grant, and user action.
- Medium candidates include meaningful but bounded availability or integrity
  failures with constrained scope. Explain realistic resource requirements.
- Treat hardening suggestions without a demonstrated security boundary
  violation as such. Do not equate missing tests with an exploitable defect.

Prompt injection is relevant when it crosses an enforced security boundary,
leaks protected data, or causes an unauthorized effect. An authorized user
deliberately granting a tool access is not itself an authorization bypass;
check whether adversarial inputs can exceed that grant or misrepresent consent.
Dependency advisories should establish how the affected code is reached in
Nautilo. Deliberately vulnerable research fixtures under
`dev/evals/security-research` are test material, not production vulnerabilities.

For each finding, provide the source commit, affected files, attacker starting
authority, execution/data path, minimal reproducer, expected and observed
behavior, and impact. Distinguish verified execution from static hypotheses.
Include a focused regression test and a minimal patch when feasible, preserving
legitimate authorized behavior. Group variants by root cause and explain any
remaining paths the patch does not cover. Do not include real credentials or
personal data. Deliver reports privately through the configured contact.
