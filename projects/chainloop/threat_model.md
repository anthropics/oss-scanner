# Chainloop threat model

Chainloop is an open-source software supply chain control plane. It collects, stores, verifies, and
enforces policy on attestations (in-toto / SLSA provenance, SBOMs, signatures) across many teams and
organizations. A compromise of Chainloop lets an attacker forge the evidence that downstream systems
trust, so integrity and tenant isolation matter more than availability.

## Components and where untrusted input enters

The repository is one Go module with three deployable binaries plus shared packages under `pkg/`.

- **Control plane — `app/controlplane/`.** The main gRPC/Connect + HTTP API. It authenticates users
  (OIDC, `github.com/coreos/go-oidc`), issues and checks JWTs (`github.com/golang-jwt/jwt/v5`) and
  long-lived **API tokens**, and authorizes every call through **casbin RBAC**
  (`app/controlplane/pkg/authz`). Untrusted input: every API request field, workflow contracts,
  attestation envelopes submitted for storage/verification, policy references, OCI/artifact
  references, invitation and membership operations, and webhook/integration payloads. Persistence is
  through the **ent** ORM (`app/controlplane/pkg/data/ent`, generated code).
- **Artifact CAS — `app/artifact-cas/`.** A content-addressable storage proxy. Untrusted input: the
  bytestream upload/download gRPC API, caller-supplied digests and resource names, and the bytes
  themselves. It brokers access to backends (`pkg/blobmanager/` for S3, OCI, and Azure Blob) on behalf
  of tenants, so an authorization mistake here is a cross-tenant artifact read/write.
- **CLI — `app/cli/`.** Crafts and pushes attestations, signs with **sigstore/cosign**, and verifies.
  Untrusted input from the CLI's perspective: server responses, local contract and predicate files,
  and anything parsed during `attestation` and `policy` commands.
- **Shared libraries — `pkg/`.** Notable for an auditor:
  - `pkg/attestation/` — in-toto statement assembly and **sigstore** verification (cosign, fulcio,
    rekor, timestamp-authority). Signature/trust-root logic lives here.
  - `pkg/policies/`, `pkg/cache/policyevalbundle/` — policy evaluation with **OPA/rego**
    (`github.com/open-policy-agent/opa`). Policies come from users, so this is attacker-influenced
    code execution; look for sandbox escapes, resource exhaustion, and rego that reaches the network.
  - `pkg/netguard/` — the guard intended to stop requests to internal/link-local addresses. Treat a
    bypass here as an SSRF primitive, especially combined with `pkg/resourceloader/` (fetches
    user-named external resources) and OCI reference resolution.
  - `pkg/credentials/` — secret storage via HashiCorp Vault and cloud KMS. Any leak of these is high+.
  - `pkg/casclient/`, `pkg/blobmanager/` — storage access; watch for path/resource-name handling and
    tenant scoping.

Request bodies are validated with **protovalidate**; gaps between what validation enforces and what
the handlers assume are worth probing.

## Trust boundaries that matter most

1. **Tenant / organization isolation.** Chainloop is multi-tenant. Any path that lets one organization
   read or write another's attestations, workflows, CAS artifacts, policies, or memberships is the
   highest-value bug class. Endpoints that act on a caller-supplied identifier (an artifact digest, a
   workflow, project, or organization reference) should re-check that the caller owns the named
   resource rather than trusting the reference.
2. **AuthN/AuthZ.** OIDC/JWT verification, API-token scoping and revocation, and the casbin policy
   enforcement in `app/controlplane/pkg/authz`. Missing or incorrect authorization on an endpoint, or
   a token that keeps working past revocation/expiry, is an auth bypass.
3. **Attestation and signature integrity.** Accepting a forged, unsigned, replayed, or wrong-identity
   attestation as valid, or accepting a signature against an attacker-controlled trust root, defeats
   the product's purpose.
4. **Policy engine.** User-supplied rego/WASM policies are evaluated server-side. Code execution beyond
   the intended sandbox, SSRF from policy evaluation, or unbounded resource use are in scope.

## How to exercise it

**A live stack runs offline in this container.** Run `chainloop-start` (and `chainloop-stop` to tear
down). It boots everything on loopback with no network:

| Component | Address | Notes |
|---|---|---|
| Control plane | HTTP `127.0.0.1:8000`, gRPC `127.0.0.1:9000` | unauthenticated readiness at `GET /statusz` |
| Artifact CAS | HTTP `127.0.0.1:8001`, gRPC `127.0.0.1:9001` | unauthenticated readiness at `GET /statusz` |
| Dex (OIDC) | `127.0.0.1:5556/dex` | in-memory; static login `john@chainloop.local` / `password` |
| Vault | `127.0.0.1:8200` | dev mode, token `notasecret`, KV v2 at `secret/` |
| Postgres | `127.0.0.1:5432` | db `controlplane`, user `postgres`, trust auth; migrations already applied |

Server logs are under `/tmp/chainloop/*.log`. The database schema is baked into the image (atlas
migrations applied at build time). The CLI is on `PATH` as `chainloop`; point it at the local control
plane with `--insecure --control-plane 127.0.0.1:9000 --artifact-cas 127.0.0.1:9001`, and use the
**inline** CAS backend to avoid needing external object storage (`chainloop casbackend` ... `inline`).
This lets you drive real control-plane↔CAS flows, DB-backed authorization, tenant/organization
boundaries, attestation push/verify, and policy evaluation against a running system, and build
reproducers that actually execute.

- `go test ./...` runs the unit suite. The build sets `SKIP_INTEGRATION=true`, so the integration
  tests (which spin up Postgres/Vault via testcontainers and need a Docker daemon) call `t.Skip()`
  and are not run offline. The unit tests around auth, authz, attestation, policy, CAS, and
  credentials are the useful ones to read for intended behavior.
- The three binaries are also built to `/usr/local/bin/chainloop-controlplane`,
  `/usr/local/bin/chainloop-cas`, and `/usr/local/bin/chainloop`.

Note on the live stack's auth shortcuts: Vault dev mode and Dex's static passwords exist only to make
the stack runnable offline. Please do not report the dev credentials, the in-memory Dex storage,
`tls_disable` on the local Vault, or trust auth on the local Postgres as findings — they are scanner
scaffolding, not how Chainloop is deployed.

## How we rate severity

- **Critical:** cross-tenant data access or modification; authentication bypass; forging or validating
  a fraudulent attestation/signature; remote code execution (including policy-engine sandbox escape to
  the host); leak of stored signing keys or backend credentials.
- **High:** privilege escalation within a tenant (e.g. member → admin, scope escalation on an API
  token); SSRF reaching internal services or cloud metadata (netguard bypass); authorization gaps that
  expose another tenant's metadata without full data access; injection into the ent/SQL layer.
- **Medium:** information disclosure of non-secret internal detail; CSRF; most denial-of-service
  (unbounded policy evaluation, request amplification) unless it is trivially remote and unauthenticated,
  in which case rate it high.
- **Low / out of scope:** findings requiring control-plane admin credentials the attacker already has;
  issues only in generated code (ent, protobuf/Connect, wire) that reflect an upstream generator rather
  than Chainloop's own logic; and deployment manifests under `deployment/` used as examples. Please
  still mention these, but rate them accordingly.

Reproducers and proposed patches against the handler, middleware, authz, attestation, or policy code
are the most actionable. Where a finding depends on tenant scoping or token scope, please state the
exact caller identity and the resource owner in the reproduction so we can confirm the boundary crossed.
