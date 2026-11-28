# Threat model

## What Probo is

An open-source GRC platform, run as multi-tenant SaaS (us.probo.com, eu.probo.com) and self-hosted. In scope:

- **`probod`**: the multi-tenant Go server (PostgreSQL, S3, remote headless Chrome) and the React apps it embeds: the
  console and employee portal (app origin) and the public compliance portal (own listener, customer domains).
- **`probo-agent`**: the device agent installed on customers' employee machines, running as root/SYSTEM. **As critical
  as the server**: a bug here compromises customers' machines, not just their Probo data.
- **Clients**: `prb` CLI, the cookie-banner SDK that runs on customers' websites (`packages/cookie-banner*`).

What matters most: **tenant isolation** and **integrity of the machines running the agent**.

## Actors

- **Anonymous**: compliance portal, cookie-banner API, sign-up/sign-in/reset/magic link, SAML/OIDC callbacks, public
  files, agent enrollment. Sign-up is open on SaaS, so **anyone can be OWNER of their own organization**; that must
  give nothing in any other.
- **Portal visitors**: anyone who signs in to a portal; may sign an NDA and request restricted items.
- **Members** by role (`pkg/coredata/member_role.go`): `OWNER`, `ADMIN`, `EMPLOYEE`, `VIEWER`, `AUDITOR`,
  `COMPLIANCE_PORTAL_MANAGER`, `COMPLIANCE_PORTAL_ACCESS_MANAGER`. Policies: `pkg/probo/policies.go`,
  `pkg/iam/iam_policies.go`, and each service's `policies.go`. ADMIN is denied some IAM actions (org deletion, member
  removal, SAML/SCIM config, granting OWNER).
- **Credentials**: sessions (assumed per organization), personal API keys and OAuth2 tokens (act across all the
  identity's organizations), SCIM tokens, device keys.
- **Trusted**: the operator (config, encryption key, database, storage, Chrome, `proboctl`, `probod-bootstrap`).

## Server: where to look

- **Authorization in console GraphQL and MCP** (`pkg/server/api/console/v1`, `pkg/server/api/mcp/v1`). Every resolver
  must do `scope, err := r.authorize(ctx, id, action)` and use *that* scope (`contrib/claude/authorization.md`). Bugs
  look like: no or wrong authorize call, a scope rebuilt from a client ID (`coredata.NewScopeFromObjectID`) or
  `NewNoScope()` on a tenant path, secondary IDs in an input (foreign keys, linked objects) not checked to be in the
  same organization, MCP tools diverging from their GraphQL twin. IDs (`pkg/gid`) embed the tenant and are
  client-supplied.
- **Authentication** (`pkg/server/api/connect/v1`, `pkg/iam`): password reset, magic links, invitations, sessions and
  organization assumption, SAML, OIDC, SCIM, the OAuth2 server (device flow, client metadata documents), API keys, and
  the token packages (`pkg/securecookie`, `pkg/securetoken`, `pkg/statelesstoken`).
- **Compliance portal** (`pkg/server/api/complianceportal/v1`, `pkg/complianceportal`): resolved by host name; items
  must belong to *the visited portal* and be `PUBLIC`, or `RESTRICTED` with a granted access and a signed NDA. Also
  e-signature (`pkg/esign`), access and rights requests, portal OAuth sign-in, custom domains (`pkg/certmanager`).
- **Cookie banner API** (`pkg/server/api/cookiebanner/v1`): unauthenticated, called from customers' websites.
- **Files** (`pkg/server/api/files/v1`, `pkg/filemanager`, `pkg/filevalidation`): any way to serve active content
  (HTML, SVG, JS) from the app or portal origin.
- **Rendering**: ProseMirror, Markdown and Mermaid in `packages/ui` and `packages/prosemirror`, emails. Stored XSS
  that runs in another organization's session, for portal visitors, or on customers' websites.
- **SSRF from requests `probod` makes** (webhooks, connectors, OAuth client metadata, agent fetch tools): they must use
  `httpclient.WithSSRFProtection()` or `netcheck` (`contrib/claude/httpclient.md`). Connector credentials must not be
  sent to another origin.
- **Integrations**: Slack, Linear, connector OAuth/install flows, identity federation for customers' clouds
  (`pkg/identityfederation`); a flow must bind to the organization and identity that started it.
- **LLM agents** (`pkg/agent`, `pkg/vetting`, `pkg/probot`, `pkg/cookiebanner`): vendor pages, uploads, banner reports
  and Slack messages reach prompts. Prompt injection leading to cross-tenant access or unauthorized writes is in scope.

## Device agent: where to look

Code: `cmd/probo-agent` (CLI, macOS PKG/Swift app/XPC helper, Windows MSI, `install.sh`) and `pkg/deviceagent`. Runs as
a launchd daemon (macOS), LocalSystem service (Windows), systemd/rc.d (Linux/FreeBSD), with a per-user tray and a
`probo://enroll` URL handler. It only polls the server, runs an allowlist of commands for posture checks, and
self-updates from GitHub releases verified with Sigstore, SHA-256 and (macOS) code signing.

- **Local privilege escalation** to root/SYSTEM: the XPC helper and its client check, URL handler, installers and
  uninstallers (including files read from shared locations), service definitions, state/run directories, races,
  temporary files, PATH or DLL lookups in privileged code.
- **Command injection**: any value reaching a shell, PowerShell or `sudo -u`.
- **Update integrity**: installing anything not built by Probo's release workflow, downgrades, extraction, races.
- **Hostile server, network or link**: must not run code on the device, read beyond posture data, or silently enroll
  it into an organization its user or admin did not choose.
- **Secrets**: the device key and enrollment tokens must not leak to other local users.

Swift and Windows-only code is not compiled in the image; review it as source.

## Severity

- **Critical**: unauthenticated cross-tenant access, auth bypass or account takeover, RCE on `probod`, SSRF from
  `probod` to metadata or credentials, RCE on a device through the agent, LPE to root/SYSTEM through the agent,
  bypass of update verification.
- **High**: authenticated cross-tenant read or write, privilege escalation within an organization, portal leaking
  restricted or other organizations' items, cross-organization or portal or cookie-banner stored XSS, SQL injection,
  readable SSRF, prompt injection with cross-tenant or unauthorized writes, silent device enrollment, device key leak.
- **Medium**: same-organization stored XSS, blind SSRF, open redirect, login CSRF, CSRF, spoofing e-signature
  evidence, NDA bypass.
- **Low**: user enumeration, missing hardening headers.

## Out of scope

- Denial of service and missing rate limiting.
- SSRF from requests the headless Chrome makes (agent browser, PDF rendering): isolated at the infrastructure level.
- Attacks needing the victim organization's OWNER or the operator, unless they cross a tenant or reach the host.
- Operator configuration choices, `proboctl`, `probod-bootstrap`, `compose*.yaml`, `contrib/`, `e2e/`, `examples/`,
  dev-only files.
- Intentionally global catalogs (common third parties, tracker patterns).
- Generated code under `pkg/server/api/*` (report the `.graphql` or spec source instead).
- `pkg/automerge`: a library not yet wired into the server (Medium at most).
- Dependency CVEs without a reachable path.

## How to exercise it

- Binaries are in `/src/bin`; tests are compiled. There is no PostgreSQL, S3 or Chrome in the image, so `probod` and
  `e2e/` cannot run, and DB tests skip themselves.
- Pure unit tests are good bases for reproducers: `pkg/iam/...`, `pkg/saferedirect`, `pkg/prosemirror`,
  `pkg/filevalidation`, `pkg/server/...` handlers, `pkg/deviceagent/...`.
- `SECURITY_NOTES.md` lists past advisories; most are authorization bugs of the kind described above.

Reports should name the handler, resolver, tool or agent function, the attacker's starting actor, a reproducer (Go
test, HTTP/GraphQL requests, or local commands), and a minimal patch.
