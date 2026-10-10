# RustFS threat model

## Project and attack surfaces

RustFS is an S3-compatible distributed object storage server written in Rust. It manages object bytes, versions, metadata, access policies, credentials, encryption keys, and cluster administration.

Treat request methods, paths, query parameters, headers, bodies, object names, multipart state, XML/JSON configuration, and client-supplied claims as untrusted. Attackers may be unauthenticated clients or authenticated users with limited permissions; a storage user is not automatically a cluster administrator.

Prioritize S3 operations (including signed/presigned requests, anonymous access, multipart uploads, versioning, copies, Object Lock, and S3 Select), IAM/STS/service accounts, administrative and console authentication, identity-provider integrations, and inter-node HTTP/gRPC requests. Also consider configured replication, remote-tier, notification, KMS, and alternate protocol integrations.

The image builds the server's default features, currently FTPS, WebDAV, and GCS support. SFTP, Swift, HTTP/3, and rio-v2 require explicit builds. Compilation does not imply that a listener or integration is enabled. Record the actual build features and runtime configuration for each finding.

## Components and trust boundaries

- `rustfs/src/auth.rs`, `rustfs/src/storage/access.rs`, and `rustfs/src/admin/`: credential validation, signature coverage, authorization actions, session claims, and administrative privilege boundaries.
- `crates/iam/`, `crates/policy/`, `crates/credentials/`, and `crates/signer/`: credential scope, policy conditions, deny semantics, and forged or caller-supplied identities.
- `crates/ecstore/`, `crates/filemeta/`, `crates/rio/`, and `rustfs/src/storage/`: filesystem path confinement, metadata parsing, integrity checks, version isolation, encryption, and persistent data integrity.
- `crates/ecstore/src/cluster/rpc/` and `rustfs/src/storage/rpc/`: peer authentication, request integrity, replay controls, and confinement of peer operations to intended storage resources.
- `crates/crypto/`, `crates/kms/`, `crates/trusted-proxies/`, `crates/protocols/`, `crates/replication/`, `crates/notify/`, and `crates/targets/`: secret exposure, forwarded identity, protocol authorization parity, outbound endpoint validation, and TLS checks.

A bucket policy may intentionally grant public access. Demonstrate access contrary to the configured policy. Compare versioned/unversioned actions, source/destination authorization for copies, and parent/session scopes for derived credentials.

State whether exploitation requires administrator access, a cluster secret, writable server configuration, or direct filesystem access. Do not silently grant those privileges to an ordinary client. Inter-node requests must still reject missing or invalid authentication. Validated identity, groups, and token claims must not be replaced by arbitrary request headers; forwarded identity depends on the configured trusted-proxy boundary.

## Offline environment and reproduction

Source, toolchain, Cargo dependencies, and build artifacts remain in the image at `/src`. The server is `/src/target/debug/rustfs`. The image also fetches the console assets during its online build. Generated protobuf/FlatBuffers code is already checked into the source repository.

The following focused library suites run during image construction and can be rerun without networking:

```bash
cd /src
cargo test --frozen -p rustfs-credentials -p rustfs-policy -p rustfs-signer --lib
```

For other tests, keep Cargo offline and use focused filters. Tests needing a server, Vault, an identity provider, notification receiver, or remote storage require local fixtures; external services are unavailable. Use localhost, temporary data directories, throwaway credentials, and bypass proxies explicitly for localhost.

For request-level findings, exercise the actual server rather than only a helper function. Consult `docs/testing/README.md`, `crates/e2e_test/README.md`, and `docs/testing/security-regressions.md`: the E2E harness requires a server build receipt through `scripts/e2e_binary.py`. The image does not prebuild every optional feature or every E2E target.

Review the known advisory regressions in `docs/testing/security-regressions.md`. Distinguish new exploit paths from already documented advisories or intentional compatibility behavior. The console frontend is maintained separately; focus this enrollment on this repository's server, its console routes, and its integration boundaries.

## Severity and report evidence

Assess confidentiality, integrity, and availability together with attacker privileges and deployment assumptions. Unauthenticated remote code execution, broad authorization bypass, or cluster credential/key compromise merits critical or high severity when the demonstrated impact supports it. Unauthorized object access, cross-user escalation, arbitrary filesystem access, and persistent data corruption generally merit high severity. For resource exhaustion, consider authentication, repeatability, amplification, recovery, and affected availability rather than assigning a fixed rating.

Include the source commit, exact features/configuration, attacker credentials and permissions, affected code location, a minimal offline reproducer, expected versus actual behavior, and observable impact. Use an authorized control where useful, and verify stored state for integrity findings. Prefer a small regression test and a minimal patch; deduplicate reports sharing the same root cause while listing all demonstrated affected entry points.

Follow `SECURITY.md`: report privately through GitHub Security Advisories or `security@rustfs.com`. Do not publish exploit details in public issues.
