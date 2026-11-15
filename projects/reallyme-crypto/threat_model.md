# ReallyMe Crypto threat model

ReallyMe Crypto provides cryptographic operations, key formats, and provider
bindings used by JOSE, COSE, and credential libraries. `SECURITY.md`,
`CONTRACT.md`, `PROVIDER_POLICY.md`, and `SECURITY_MEMORY_MODEL.md` describe
the supported behavior and security policy.

## Trust boundaries

Applications pass data from remote peers into public APIs as encoded keys,
signatures, ciphertexts, algorithm identifiers, and context bytes. Treat those
values and serialized operation requests as untrusted. Native callers also
supply pointers and lengths at the C ABI and JNI boundaries. Keys, plaintext,
and derived secrets are confidential for their documented lifetimes.

Review the repository's cryptographic composition, provider routing, input and
wire validation, key formats, and memory ownership across the native ABI and
WASM. Prioritize signature verification, key and suite binding, authenticated
plaintext release, and secret handling across language boundaries. Verification
and authenticated decryption must fail closed. Inputs need explicit bounds,
errors must be typed and redacted, and an unavailable provider must return an
error without selecting another implementation. Review platform adapters against
the same contracts. The image builds Linux Rust, the native C ABI, and the raw
Rust WASM module. Apple, Android, Kotlin, and browser SDK tests require separate
platform environments.

## Offline validation

Run the existing conformance suite from `/src`:

```sh
/opt/reallyme-crypto/bin/vectors_tests --test-threads=2
```

The C ABI library and raw WASM module are in `/opt/reallyme-crypto/lib`.
Cargo's locked dependencies are available offline for additional Rust tests.
Use public vectors and synthetic fixtures for validation.

## Severity and scope

- Critical: key recovery, unauthenticated code execution, or broad authentication
  compromise in a supported, ordinarily deployed configuration.
- High: practical forgery, verification bypass, unauthorized secret disclosure,
  or memory unsafety with significant impact in a supported configuration.
- Medium: remotely reachable denial of service, limited policy violations, or
  side channels with material deployment prerequisites.
- Low: demonstrated security impact under uncommon conditions.

Assess impact using the public entry point, features, provider, and deployment
assumptions. Identify whether the default configuration is affected or the
finding requires an optional provider, a non-default feature, or an unmet
caller obligation documented at the API boundary. Tie findings that rely on
test-only interfaces or synthetic keys to a supported production path before
assigning production impact.

Scope includes this repository's use of dependencies. Dependency internals,
downstream applications, production services, already compromised hosts and
toolchains, physical access, and hardening suggestions without a demonstrated
security impact fall outside the review.
