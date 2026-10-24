# Threat model

## What this project does and where untrusted input enters

Issuerd is an Identity and Access Management (IAM) server implementing
OIDC/OAuth2, API-compatible with Keycloak. It issues and validates security
tokens for humans and machines, so its entire network surface is security
critical and all input it receives is untrusted:

- Public protocol endpoints (Axum HTTP, `crates/issuerd-server` +
  `crates/issuerd-protocol`): authorization, token, userinfo, introspection,
  revocation, discovery, JWKS; PKCE, PAR/JAR/JARM/RAR, DPoP, CIBA (poll mode),
  RFC 8693 token exchange, dynamic client registration, and all four logout
  profiles. Parsing is pure functions on attacker-controlled request
  parameters; sessions and cookies ride through these flows.
- Admin REST API (`crates/issuerd-admin-api`) and the embedded admin/account
  SPA (`webclientsrc/`): realm-role authorization, CSRF, cross-realm isolation
  (a token issued by one realm must never administer another, except the
  `master` realm by design).
- JWT/JWS/JWK validation and signing-key custody (`crates/issuerd-token`;
  optional AES-256-GCM envelope encryption of signing keys at rest).
- Storage: PostgreSQL (sqlx, compile-time-checked queries), Redis cache, JSON
  file backend; JSON/YAML deserialization of provisioning and config.
- Federation (`crates/issuerd-federation`): LDAP/Kerberos binds to configured
  directories, identity brokering callbacks (`/broker/{alias}/endpoint`),
  SPNEGO. Outbound HTTP fetches (external JWKS, broker IdPs) are SSRF-guarded
  (https-only, publicly routable IPs, no redirects, capped bodies).

## Components that matter most / least

Most: everything under `crates/` and `src/` — protocol parsing/validation,
token signing and verification, session and cookie handling, admin
authorization, redirect-URI matching, storage queries. The embedded SPA
(`webclientsrc/src/`) matters for XSS/CSRF in an admin context.

Less but in scope: the CLI plumbing, metrics/health endpoints, themes.

Out of scope: `docs/`, `tests/` (harnesses and fixtures, including intentional
test credentials), `examples/` (lab/demo configs with well-known demo
passwords), `scripts/`, `lints/`, `rig/` research notes. Docker-dependent
integration stacks (Samba/OpenLDAP/Keycloak parity, cluster, OIDF conformance)
cannot run in the sandbox. SAML and UMA are not implemented — do not report
their absence. Third-party dependencies are out of scope unless there is a
demonstrated exploit path through Issuerd's usage.

## How to exercise it

The image leaves the workspace fully built at `/src` (toolchain: Rust 1.95,
Node from the base image):

- `cargo test --workspace --lib` — unit suite, fast, no I/O.
- `cargo test --test integration` — in-process end-to-end suite against the
  default target; needs no Docker (Keycloak/cluster/federation variants skip
  gracefully when their containers are absent).
- `target/debug/issuerd` — the daemon binary: `issuerd example` writes a
  starter config, `issuerd daemon -c issuerd.toml` serves HTTP on :8080 with
  the in-memory backend (see `examples/` for realm/client provisioning YAML),
  `issuerd openapi -o openapi.json` exports the API surface.
- `cd webclientsrc && npm run test` — Vitest suite for the SPA.

## How you rate severity

- **Critical**: unauthenticated RCE; forgery of tokens or bypass of JWT/JWS
  signature or DPoP proof validation; authentication bypass; cross-realm data
  access or Admin API actions without the required realm role; compromise of
  signing keys.
- **High**: privilege escalation within a realm; redirect-URI/PKCE/session/
  cookie/CSRF validation failures; SQL or LDAP injection; disclosure of tokens,
  client secrets, passwords, or key material (including via logs or error
  responses); stored XSS.
- **Medium**: unauthenticated input-driven resource exhaustion with bounded
  impact; reflected XSS requiring significant victim interaction; rate-limit or
  brute-force counter bypass.
- **Low**: panics or crashes on malformed input with no security impact;
  information disclosure of non-sensitive versions/configuration.

## Anything to leave alone

- Test-only fixture credentials under `tests/` and the well-known lab/demo
  values in `examples/` (e.g. `admin/admin`, `alice/changeme`) — intentional.
- `#![forbid(unsafe_code)]` is set workspace-wide; do not report the absence
  of memory-corruption classes that this already rules out in first-party code.
- Non-security hardening suggestions (performance, style, dependency-version
  churn) and purely theoretical findings without a plausible attack path.
- The log-hygiene/secret-redaction policy is enforced by dedicated dylint
  lints in CI; only report log leaks of actual secrets that those miss.
