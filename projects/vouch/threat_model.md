# Threat model

## What this project does and where untrusted input enters
Vouch is hardware-backed authentication: a user proves presence with a FIDO2 security key (touch + PIN) and the
server issues short-lived credentials (SSH certificates, AWS credentials via OIDC, Kubernetes, Git and others).
It is an OAuth 2.0 / OpenID Connect provider (FAPI 2.0 Security Profile, DPoP, HTTP Message Signatures).

Untrusted input enters at:
- `vouch-server` HTTP endpoints: WebAuthn registration/authentication (attestation objects, COSE keys, client data),
  OAuth/OIDC endpoints (authorize, token, PAR, introspection, revocation, DPoP proofs), SCIM provisioning, and the
  web UI / admin pages.
- Signed HTTP requests verified by `vouch-httpsig` (RFC 9421).
- Policy documents evaluated by the server's policy engine.
- Responses from the server and local IPC traffic handled by `vouch-cli` and `vouch-agent` on user machines.

## Components that matter most / least
In scope, highest priority first (see SECURITY.md):
- `crates/vouch-server/` — credential issuance, authentication and authorization, session and token handling, tenant
  isolation.
- `crates/vouch-httpsig/` — HTTP message signature parsing and verification.
- `crates/vouch-common/` — shared protocol and crypto helpers.
- `crates/vouch-agent/` and `crates/vouch-cli/` — local credential agent and CLI.

Lower priority / out of scope: `crates/vouch-tests/` (test harness), `fuzz/`, `docs/`, `charts/`, `packaging/`,
`scripts/`, and third-party dependencies (unless vouch uses them incorrectly).

## How to exercise it
- `cargo test --workspace --all-features` runs the unit and integration tests (already built in the image).
- `fuzz/fuzz_targets/` shows the parsers we consider attack surface (attestation objects, BER, COSE keys, policy
  evaluation, HTTP signatures).

## How you rate severity
- Critical: issuing credentials without a valid FIDO2 human-presence proof, authentication bypass, cross-tenant
  access, forging or replaying tokens/certificates, or remote code execution.
- High: privilege escalation within a tenant, bypass of DPoP / sender-constraining, signature verification flaws,
  leaking secrets or long-lived key material.
- Medium: stored XSS or CSRF in the web UI that needs user interaction, information disclosure without credentials,
  timing side channels on secret comparison.
- Low: denial of service (including panics, which our lints aim to forbid), issues needing local root on the user's
  machine.

## Anything to leave alone
- Vulnerabilities that require an already-compromised server host or administrator account.
- Lint-style findings (unwrap/expect/indexing) in test-only code.
