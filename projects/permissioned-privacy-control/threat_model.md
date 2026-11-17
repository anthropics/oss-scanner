# Open Privacy Suite threat model

Open Privacy Suite (this repository, Permissioned Privacy Control) is a JSON-RPC gateway that sits in front of the
nodes of a shared EVM chain. Several organizations transact on one chain, and the gateway decides, per caller, which
JSON-RPC methods they may call, which contracts they may call or read, and which transactions, receipts and events
they may see. The chain itself is not encrypted: privacy exists only at this access layer, so a flaw in it exposes one
organization's business to another.

Project security policy: `SECURITY.md`. Plain-language trust model: `site/src/app/docs/what-it-does/page.mdx`.
Enforcement details: `site/src/app/docs/security/page.mdx` and its sub-pages (`view-as-user`, `strict-read-profile`,
`audit-integrity`), `site/src/app/docs/rbac/page.mdx`, `site/src/app/docs/disclosure/page.mdx`. Where this file and
those pages disagree, the pages describe the intended behavior.

## Components and where untrusted input enters

The server is one Go binary, `cmd/server`. Most of the code is under `internal/`.

- **JSON-RPC proxy** (`internal/proxy`, `internal/rbac`, `internal/tracer`, `internal/nodehttp`,
  `internal/server/jsonrpc_processor.go` and the other RPC handlers in `internal/server`): every JSON-RPC request
  body, parameter, header and path segment (including `org_id`) is attacker-controlled. Requests are checked against
  the caller's method allowlist, contract grants, function and parameter constraints, organization and KYC status,
  then forwarded to the upstream node. Responses (transactions, receipts, logs, traces) are filtered per caller.
- **Explorer data API** (`internal/explorer`, `internal/server/explorer_*.go`): block-explorer endpoints that redact
  or drop transactions, logs and counts per viewer.
- **Authentication** (`internal/auth`, `internal/server/auth*.go`, `internal/server/oauth.go`,
  `internal/server/eth_link.go`): Privado ID zero-knowledge proof login (the wallet's response is attacker-controlled),
  Microsoft Entra ID (Azure AD) login with tenant pinning, the gateway's own OAuth 2.0 authorization server
  (`/oauth/authorize`, `/oauth/token`, callbacks), JWT access and refresh tokens (HS256), and linking Ethereum
  addresses to an identity by EIP-191 signature or by recovering the sender of an `eth_sendRawTransaction`.
- **Admin API** (`internal/server/admin_*.go`): organizations, groups, memberships, contract grants, compliance
  settings and audit logs.
- **Impersonation and dry-run** (`internal/server/impersonation.go`, `internal/server/admin_dry_run*.go`,
  `internal/viewscope`): an organization admin can see the chain as one of their members, read-only.
- **Cross-organization authorization oracle** (`internal/server/admin_policy_check.go`): evaluates access for
  allowlisted organizations (`CROSS_ORG_AUTHORIZATION_ORACLE_ORG_IDS`) with its own credential
  (`CROSS_ORG_AUTHORIZATION_ORACLE_TOKEN`). It is a cross-tenant trust boundary.
- **Sharing** (`internal/disclosure`, `internal/server/disclosure*.go`, `internal/rbac/visibleto_unlock.go`,
  `internal/server/explorer_visibleto_unlock_resolver.go`, `internal/server/admin_shared_infra.go`): disclosure grants
  (consented, scoped, expiring), `visibleTo` sharing on transactions, and shared-infrastructure contracts that a super
  admin marks as visible to everyone.
- **Compliance** (`internal/compliance`): sanctions and travel-rule checks on transfers.
- **Audit log** (`internal/audit`): append-only, hash-chained access and admin logs with a scheduled integrity
  verifier and optional signed checkpoints.
- **Signed transaction approvals** (`internal/nodeapproval`): the gateway signs an approval for a transaction it has
  authorized, and enforcing block producers include only approved transactions. The producer-side Besu and Reth
  integrations live in a separate repository (gateway-fm/ops-node-integrations) and are out of scope here.
- **Admin UI** (`frontend/`, React and TypeScript): renders organization, group and user names, DIDs, contract data,
  event data and logs. Much of this is user- or chain-supplied.
- **MCP server** (`mcp/`, a separate Go module): a client of the admin API for operators' tooling. Lower priority.

## Attackers to consider

- Unauthenticated network clients. On JSON-RPC they may call only the claim-free chain metadata methods
  (`eth_blockNumber`, `eth_chainId` and similar); every other JSON-RPC method requires authentication. The explorer
  data API serves anonymous, redacted views to callers on the private network by design.
- Authenticated users with limited group permissions. This is the main attacker: a member of organization A who tries
  to read or act outside their groups' method allowlist, contract grants or parameter constraints, or to reach
  organization B at all.
- Organization admins (tier 2), read-only organization admins, and contract admins (tier 3) who try to act outside
  their organization or tier: a read-only admin making changes, an org admin conferring org-admin status, or anyone
  writing through the impersonation surface.
- Holders of the operator token (`OPERATOR_API_TOKEN`). It may create and delete organizations and mint their first
  org admins, by design. Reading or changing a tenant organization's members, regular groups, contracts, grants or
  audit logs with it is a finding.
- Holders of the cross-organization oracle token. Evaluation for an organization outside the allowlist, or the oracle
  accepting admin, operator or user credentials, is a finding.
- Anyone who authors chain data: calldata, event logs, revert data and token metadata are attacker-written even though
  the upstream node that returns them is trusted.
- Identity inputs: Privado wallet responses, Azure AD tokens (including tokens from other tenants), OAuth requests, and
  signatures offered for address linking.

## Security invariants

A way to break any of these is in scope.

1. **Fail closed.** A missing or invalid token, a missing database row, a query error, or tracing being unavailable
   leads to denial, never to access.
2. **Cross-organization isolation.** A user of organization A cannot read or call organization B's contracts, see its
   transactions, logs or events, or learn that they exist, except through the documented sharing mechanisms (contract
   grants, disclosure grants, `visibleTo`, shared-infrastructure contracts). This includes indirect access, such as
   calling through an intermediary contract or running creation code in `eth_call` without `to`.
3. **Personal wallets.** A user's linked personal addresses and their history are visible only to that user and to
   recipients of a disclosure grant the user approved. Documented exceptions: under `PRIVACY_READ_PROFILE=standard`
   an org admin using View as user or dry-run sees the member's own activity in the named organization, and
   `ORG_ADMIN_VIEW_USER_TXS=true` shows org admins user-to-user rows with counterparties redacted. Anything beyond
   these is a finding.
4. **Access and visibility agree.** For any viewer and address, the JSON-RPC access layer (`rbac.AccessController`,
   claim handling) and the explorer visibility layer (`GetBatchVisibility`, `GetBatchEventAccess`) give the same
   answer. A surface that shows what another refuses is a finding.
5. **Memberships and admin status come only from server-side state** written through the admin API or the configured
   Azure AD tenant mapping. Data a client supplies at login or on a request must not add memberships, claims or admin
   status.
6. **Escalation prevention.** Org-admin status can be conferred, removed or reshaped only with the full admin token or
   the operator token. A tier-2 org admin may manage read-only admins only, and contract admins cannot use the admin
   API.
7. **Impersonation is read-only** and stays within the named organization. Under `PRIVACY_READ_PROFILE=strict`, View
   as user and dry-run reads are refused.
8. **Disclosure grants** reveal exactly what was approved, to the named grantee, until expiry or revocation. Each
   successful read writes an audit event; a failed audit write does not block the read (documented).
9. **Method allowlist.** Only methods the proxy supports and the caller's groups list by exact name reach the node.
   Batch requests and unsupported methods are never forwarded.
10. **Opaque errors.** Raw database or internal error text never reaches a client.
11. **Tamper-evident audit.** A change to past audit entries made through the API or the application's own database
    role (append-only on audit tables) that the integrity verifier does not detect is a finding.
12. **Network boundary.** `X-Forwarded-For` is honored only from 127.0.0.1, ::1, 10.0.0.0/8, 172.16.0.0/12,
    192.168.0.0/16, 100.64.0.0/10 and `TRUSTED_PROXIES`, by design; localhost-only endpoints accept those private
    ranges by TCP peer address. Spoofing a client address from outside them is a finding. Outbound requests built from
    user input must not reach internal networks.

## Trusted, or out of scope

- The operator who runs the gateway and anyone with the full admin token, the database owner role or other database
  write access beyond the application role, or control of configuration and environment variables. They are fully
  trusted; the product does not hide data from its operator. Tail truncation of the audit log is detected only when
  `AUDIT_CHECKPOINT_KEY` is set (documented).
- The upstream node and direct access to it. Deployments must make every node of the chain reachable only through the
  gateway (documented). Findings that need direct node access are out of scope.
- Documented behavior: authenticated users see chain metadata such as block numbers and timestamps; grants and
  disclosures reveal what they say they reveal.
- Development-only code and switches. Code compiled only with the `mockauth` build tag (`internal/server/auth_dev.go`,
  `internal/server/auth_dev_admin.go`, `internal/server/dev_test_identities.go`, `internal/server/token_ttl_dev.go`),
  which includes mock login (`ALLOW_MOCK_LOGIN`, `/oauth/session/:id/mock-complete`) and demo auto-authentication
  (`DEMO_AUTO_AUTH_DELAY`); and runtime switches that are on only when `ENVIRONMENT` is not `production` (it defaults
  to `development`): `MOCK_SIGNATURES` and `/auth/verify`. Report these only if reachable in a build without
  `-tags mockauth` running with `ENVIRONMENT=production`. `internal/server/auth_dev_admin_prod.go` is part of production builds and is in scope.
- The demo, quickstart, development and test stacks and their seeded identities and tokens, which are public on
  purpose: `demo/`, `demos/`, `poc/`, `contracts/` (demo contracts), `e2e/`, `docker-compose.yml`,
  `docker-compose.quickstart.yml`, `docker-compose.scale.yml`, the `*demo*`, `*e2e*` and `*.dev*` compose files, and
  the quickstart, demo, seed and test scripts in `scripts/`. Production manifests (`docker-compose.prod.yml`,
  `docker-compose.privacy.yml`, `deployments/`) and production scripts such as `scripts/init-audit-db.sh` are in scope.
- The docs site `site/`, except as the description of intended behavior.
- Third-party services (Privado ID issuers and wallets, Microsoft Entra ID, upstream RPC providers). How this code
  verifies what they return is in scope.
- Dependency vulnerabilities reported only from a version number, without a path through this code.

## How to exercise it

- Run `ops-start-postgres` first. It starts the local PostgreSQL 15 server. `TEST_DATABASE_URL` and
  `E2E_DATABASE_URL` already point the tests at it. Run packages with `-p 1` because they share the database:
  `go test ./internal/rbac/... -p 1 -run TestName`.
- Prefer reproducers written as Go tests next to the affected code. `internal/server/server_test.go`,
  `internal/server/auth_test.go` and `internal/server/explorer_api_test.go` show how to build a test server with
  organizations, groups, users and tokens.
- Real Privado proof verification needs the iden3 state RPC and an IPFS gateway, which are unreachable here. Use test
  doubles such as `internal/auth/mock_privado.go` (used only by tests).
- The server is built at `/usr/local/bin/privacy-proxy` without `-tags mockauth`. Run it with
  `ENVIRONMENT=production` to match a deployment. Running it end to end needs an upstream Ethereum node, which the
  image does not have; `config.example.toml` lists the configuration.
- Baseline test runs are logged in `/var/log/ops-go-tests.log` and `/var/log/ops-frontend-tests.log`. These need
  Docker and fail here, which is expected and not a finding: `internal/redis`, the store tests in `internal/explorer`
  (`store_test.go`, `store_keyset_test.go`, `store_tx_data_batch_test.go`), the Redis-backed preflight-limit tests in
  `internal/server`, and everything under `e2e/`. `TestMigrateAuditOnly_NonOwnerWithPrimaryKey_StillMigrates` in
  `internal/db` also fails here: it drops a cluster-wide role that an earlier test left objects under, which works only
  when each test has its own server.
- Admin UI: `cd frontend && npm run test:run`.

## How we rate severity

- **Critical:** breaking cross-organization isolation (invariant 2); gaining org-admin or super-admin rights, or
  another identity, from an unauthenticated or regular-user position; authentication bypass, such as an unverified
  proof, claim or JWT being accepted; reading tenant data with the operator token; the oracle evaluating for an
  organization outside its allowlist.
- **High:** another user's personal wallet history becoming visible beyond the documented exceptions (invariant 3); a
  method allowlist, contract grant or parameter constraint bypass within the caller's own organization; a read-only
  admin making changes; any write through impersonation; access under a disclosure grant beyond its scope, grantee or
  expiry; disclosure of signing keys or tokens; SSRF to internal networks; stored XSS in the admin UI from user- or
  chain-supplied data; an audit change the verifier misses; an enforcing producer including a transaction without a
  matching, unexpired approval.
- **Medium:** leaks of existence, counts, volumes or other metadata that the viewer may not see; internal error text
  in responses; rate-limit bypass; denial of service by an unauthenticated client.
- **Low:** denial of service that needs an authenticated account; a banned user keeping access until their current
  access token expires (up to 5 minutes); hardening issues without a demonstrated impact.
- Anything that requires the full admin token, database write access beyond the application role, or control of
  configuration is not a vulnerability.
