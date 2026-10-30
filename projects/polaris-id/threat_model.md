# Polaris threat model

## What Polaris is

Polaris is a pre-pilot identity-token system: an authority issues a credential signed with ML-DSA-65, a
holder presents it, and anyone can check it offline against published keys or online through the
relying-party API. Report defects against the guarantees below.

## Where untrusted input enters, most important first

1. **The OpenID4VP verifier, `packages/polaris-oid4vp`.** Wallet responses (`direct_post.jwt`, a JWE),
   SD-JWT VC credentials and their key-binding JWTs, `x5c` chains, DCQL queries, status lists. The
   wallet, the issuer and the network are hostile. Any acceptance the specification requires it to
   refuse matters.
2. **The offline verifiers, `packages/polaris-verify`, `sdk/python`, `sdk/typescript`.** Credentials,
   packs, trust anchors, holder bindings, agent grants and zero-knowledge proofs, all read from files an
   attacker controls. `polaris-verify` refuses to run until the caller names its cryptography
   (`--pqc-provider` or `--dev-placeholder`); a way around that refusal is in scope.
3. **The web application, `polaris_web/`.** The relying-party API (`/api/v1`), the operator console,
   sign-in and WebAuthn, OpenID4VCI issuance, federation, the Atlas aggregates, sessions, CSRF and the
   Content-Security-Policy (`script-src 'self'`). Every outbound fetch is an SSRF candidate.
4. **The database boundary, `polaris_sql/`.** The schema, triggers, procedures and grants are the
   security boundary against a compromised application: the application connects as `polaris_app`,
   and a write that role can make around a rule procedure is a finding.
5. **Signing and custody, `polaris_web/pqc_signing.py`, `custody.py`.** Issuance requires two ML-DSA
   implementations to agree. A signature that verifies under an issuer's key without custody having
   signed it is the most serious finding there is.
6. **The ZK prover, `polaris_zk/`, and its independent Python witness, `polaris_zk/witness2/`.** A
   forged inclusion proof that either verifier accepts.
7. **Everything else SECURITY.md lists:** `polaris_checks/`, `scripts/`, the container images, compose
   files, Helm chart and Linux installer, the migration framework, the conformance suite,
   `polaris_card/`.

## Adversaries (docs/RED-TEAM-SCOPE.md)

- **TA-1, external criminal:** authentication bypass, exfiltration of `IdentityToken` or `Individual`
  rows, insertion of tokens.
- **TA-2, coerced insider** with a live operator or admin credential: an action against an identity
  record that leaves no row in `TokenLifecycleEvent`, `VerificationEvent`, `AuditAccessLog` or
  `AuthAuditLog`. The design is built around this actor.
- **TA-3, state-level:** one token whose signature verifies without custody having signed it, or
  persistence the logs do not show.
- Also: a compromised application role, a hostile relying party, a malicious wallet or issuer.

## The guarantees that matter most

The constitutional constraints in MISSION.md: C1, `VerificationEvent` and `TokenLifecycleEvent` are
append-only, with UPDATE and DELETE rejected by trigger; C2, `ZERO_KNOWLEDGE` events have
`token_id IS NULL`; C3, at most one `ACTIVE` token per `Individual`; C6, the disclosure level is enforced
server-side and a client cannot upgrade it; C10, identity attestation never carries spending authority.
A bypass of any of these, or of the engineering constraints C4, C5, C7, C8 and C9, is in scope. A measurable
timing difference in the duress-code comparison is in scope.

## How to exercise it

The image's shell has no network. Start the services first, then run what you need:

```
polaris-oss-start                                   # PostgreSQL 16 on :5432, Redis on :6399
python3 -m polaris_checks.run                       # the invariant checks; no database
python3 -m pytest polaris_checks/test_checks.py -q  # each check fails on its broken fixture
./scripts/polaris-test.sh quick                     # the database-backed product suites (or: app, a class)
cd polaris_zk && cargo test --release               # the prover
python3 scripts/polaris-ship.py run                 # the whole local gate (long)
```

The signer defaults to a labelled placeholder (`POLARIS_PQC_PROFILE=placeholder`); real ML-DSA-65 runs
with `POLARIS_USE_REAL_PQC=1`, and liboqs is installed. The image trusts local database connections and
carries the public demo accounts: both are test-harness setup, not findings.

## How we rate severity (SECURITY.md)

- **Critical:** breaks C1 to C10 in a deployable configuration.
- **High:** authentication bypass, data exposure, denial of service against the live stack.
- **Medium:** a leak that does not violate C2, an insecure default, weakened cryptography.
- **Low:** a defence-in-depth gap, a documentation error that could mislead a deployment.

## Out of scope

- The seed accounts and notional data (their passwords are public by design).
- **The placeholder signing default.** In scope: the guard that keeps it out of production failing.
- Payments and transactions (excluded by C10); volumetric denial of service; physical security;
  social engineering; misconfiguration of your own deployment.
- Vulnerabilities in dependencies: report them upstream. A Polaris path that makes one reachable is in
  scope.
- `lab/` (research and interoperability harnesses, some of them third-party code) and `docs/paper/`.
- What docs/PRODUCTION-READINESS.md states as outside the current scope is not a finding, unless the
  statement itself is false or incomplete.

## How we would like reports

One root cause per report. A reproducer as a failing test in the suite the code already has (a
`polaris_web/` test class, a package's test file, a conformance case) is most useful. A patch should be
minimal and come with a test that fails without it. Name the constraint or the specification section
the behaviour breaks.
