# Infisical threat model for scanner reports

Infisical is a multi-tenant platform for secrets, certificates (PKI), encryption keys (KMS and KMIP), privileged access (PAM) and agent credentials. Organizations hold projects, and projects hold environments, folders and secrets. Users and machine identities authenticate to the API and are authorized per organization, project, folder and resource. Infisical Cloud and self-hosted instances run the same code, with some behavior switched on the deployment type. Our published security model is in `docs/internals/security.mdx`.

## Scope

Scan these parts of the repository:

- `backend/`: the Node.js API (Fastify, Knex on Postgres, Redis and BullMQ). Routes are under `backend/src/server/routes/` and `backend/src/ee/routes/`.
- `backend/src/ee/`: enterprise features, under their own license.
- `backend-go/`: a Go port of part of the API. For a finding here, say whether the Node implementation of the same route has it too.
- `frontend/`: the React web app.
- `wasm/ironrdp-decoder/`: Rust source for the RDP session replay decoder, which the web app runs as WebAssembly to parse recorded sessions.
- `helm-charts/`, `docker-compose.prod.yml`, `cloudformation/` and `docker-swarm/`, for insecure defaults they ship.

Leave out `docs/` and the test suites and fixtures. Infisical Cloud infrastructure is not in this repository.

## Where untrusted input enters

- Routes reachable without a session: login and signup, account recovery, SSO callbacks (SAML, OIDC, LDAP), machine identity login methods, viewing shared secrets, and inbound webhooks such as the secret scanning app.
- Certificate enrollment (EST, SCEP, ACME) and KMIP, which authenticate through their own protocols. Findings here count when our implementation departs from the RFC or from the enrollment method the customer configured.
- Authenticated routes, called by any role from org admin down to project viewer, and by machine identities with narrow grants. Most findings that matter are a lower-privileged caller reaching something their grant denies.
- Machine identity auth that trusts an external issuer: AWS, GCP, Azure, Kubernetes, OIDC, JWT, SPIFFE, TLS certificate, LDAP, Alibaba Cloud and OCI. The customer chooses which issuers to trust. Look for flaws in how we verify the assertion (audience, issuer, bound claims, signature, the metadata fetch).
- Server-side requests to customer-supplied destinations: app connections, secret syncs, dynamic secrets, secret rotation, webhooks, audit log streams, identity auth metadata fetches, and gateways and relays into private networks. Outbound URLs go through the SSRF guard in `backend/src/lib/validator/validate-url.ts`. The guard is off in development mode and for requests sent through a gateway, whose purpose is to reach the customer's private network. Judge SSRF with production settings and without a gateway.
- The browser, where secret names, values, comments, tags and other user-supplied text render in other users' dashboards.

## Components that matter most

- Authentication: `backend/src/server/plugins/auth/`, `backend/src/services/auth/`, the identity auth services under `backend/src/services/identity-*`, and SSO under `backend/src/ee/services/{saml-config,oidc,ldap-config}/`.
- Authorization: `backend/src/ee/services/permission/` and `backend/src/lib/casl/`. Permissions apply at four scopes: organization, project, folder (additional privileges scoped to one folder) and resource (per-resource membership for PAM, signers and applications). Grants carry conditions on environment, secret path, tags and time. PAM and Agent Vault projects offer only the built-in Admin and Member roles, and Certificate Manager projects have no custom roles.
- Privilege changes: each organization runs one of two privilege systems, chosen by `shouldUseNewPrivilegeSystem` on the organization (on by default). On the new system, assigning a role or granting a privilege needs the explicit permission for that action, and an actor who holds it may grant access beyond their own. On the legacy system, `validatePermissionBoundary` in `backend/src/lib/casl/boundary.ts` also requires the actor to hold everything they grant. State which system a finding needs.
- Tenant isolation: every query that takes an org, project, environment or folder ID from the request must be scoped to the caller. Reaching into another organization is the most serious class of bug for us.
- Encryption: `backend/src/lib/crypto/`, `backend/src/services/kms/`, `backend/src/ee/services/{hsm,external-kms}/`. An operator root key (or HSM) protects an internal KMS root key, which protects per-organization and per-project data keys. Data is encrypted with AES-256-GCM.
- Secret read and write paths: `backend/src/services/secret-v2-bridge/`, secret imports and references, folder grants (`backend/src/services/project-folder-grant/`), approval policies (`backend/src/ee/services/secret-approval-request/`) and secret sharing (`backend/src/services/secret-sharing/`).
- Agent Vault (`backend/src/ee/services/agent-vault*/` and `backend/src/ee/services/agent-proxy-ca/`): AI agents call services through a proxy that attaches stored credentials, and the agent never sees those credentials.
- Stored third-party credentials: app connections, dynamic secrets, secret rotation, PAM accounts, CA private keys and KMS keys. PAM sessions are recorded.

## How to exercise it

Every dependency is installed and the code is built. Postgres and Redis are installed but stopped, so start them first with `infisical-test-services`.

- Backend e2e tests: `cd /src/backend && npm run test:e2e -- e2e-test/routes/v1/<name>.spec.ts`. The harness boots the whole API in process, runs migrations, seeds a user, org, project and machine identity (`backend/src/db/seed-data.ts`), and exposes `testServer.inject(...)` for requests. The specs under `backend/e2e-test/routes/` make good starting points for a reproducer. Database, Redis and key settings come from `/src/.env.test`, and each run drops and recreates the schema of that database, which in this image is a throwaway.
- The harness sets `ALLOW_INTERNAL_IP_CONNECTIONS=true`. Real deployments default to off, so judge SSRF findings with it off.
- Backend unit tests: `cd /src/backend && npm run test:unit -- <pattern>`.
- Go: `cd /src/backend-go && go test ./internal/...`. The integration tests under `tests/` need Docker and can't run here.
- Frontend: `cd /src/frontend && npm test`.

## How we rate severity

- Critical: reading or changing secrets, keys, certificates or stored credentials across organizations; making the server use credentials it holds for the instance or for one organization on behalf of another; authentication bypass to any user or machine identity; unauthenticated access to secret values; remote code execution on the server; recovering plaintext or data keys without the root key; SSRF that yields cloud credentials or key material.
- High: an authenticated caller reading secret values, credentials or private keys their grant denies, or raising their own privileges, within one organization; reading another organization's data that holds no secret values; a privilege change that the organization's privilege system should refuse; bypassing an approval policy under hard enforcement, or as someone the policy does not list as a bypasser; SSRF that reaches internal services, cloud metadata or a key-management endpoint; SQL injection; stored XSS that runs in another user's session.
- Medium: reading metadata the caller's grant denies within their own organization (secret names, member lists, configuration); SSRF that can only tell whether internal hosts or ports exist; actions that skip audit logging or PAM session recording; CSRF on a cookie-authenticated route that changes state.
- Low: a minor authorization or information gap that stays within what the caller could already reach, or a hardening gap with a concrete, demonstrated impact.

Rate a finding by what it reaches, including any pivot. SQL injection that yields secret values or key material, or writes data that grants access, is Critical. Say which role or identity the attacker holds, which settings or plan features the path needs, and whether it applies to Infisical Cloud, self-hosted instances, or both.

## Anything to leave alone

Our security model and product documentation describe the behavior on the left as intended. The right-hand column says what would make it a finding.

| Intended behavior | Report it when |
|---|---|
| Org and project admins, and the operator of a self-hosted instance, are trusted with what their role allows. | A lower role can do the same thing. |
| A built-in role can do what its default permissions allow. | The caller exceeds what their role grants. |
| A valid token acts with its owner's access. | The token acts beyond its grant or outside its organization. |
| Opening a PAM session, issuing a certificate and encrypting with a KMS key each need their own permission. Reading the credential, private key or key material needs a separate one. | A path returns the credential, private key or key material without that read permission. |
| Cross-project secret references and imports backed by a project folder grant need no permission in the source project, once the organization turns on cross-project sharing. | The reference or import reaches a folder that was never granted, or crosses into another organization. |
| A shared secret link with no restrictions opens for anyone holding it until it expires. | The link can be guessed, or it still opens after its expiry or view limit. |
| An external issuer the customer trusts for machine identity auth can authenticate the identities it vouches for. | Our verification of the issuer's assertion is flawed. |
| Under soft enforcement, a permitted bypasser can merge their own change request without approval, and approvers are notified. With no bypassers set, anyone can. | Someone outside the bypass list bypasses, a bypass works under hard enforcement, or someone bypasses another person's request. |
| A self-hosted operator can choose less safe settings, such as allowing connections to internal IP addresses. | A default setting is insecure. |

Also leave these alone:

- Denial of service, resource exhaustion and missing rate limits.
- Missing security headers or cookie flags, self-XSS, and clickjacking on pages with no sensitive action, unless the report shows a concrete impact.
- Actions confined to the caller's own account or session that expose no secrets, reach no other organization and gain no privilege.
- Example values in `.env.example` and the other `.env.*.example` files.
- Attackers with direct access to the database, disk or process memory, physical access, and social engineering. An attacker who can read the storage backend can tell which secrets exist without reading their values.
- A vulnerable dependency, unless the report shows a working exploit through Infisical code.

## How reports and patches should look

Give the route or function, the attacker's role, the configuration needed, a reproducer (an e2e spec is ideal), the observed result, and a proposed patch where possible. Mark which parts you demonstrated and which come from reading the source. Patches should fix the check where it is enforced. Many routes exist in several API versions (`v1` to `v4`), so say whether the other versions of the route, and its sibling routes, have the same gap.
