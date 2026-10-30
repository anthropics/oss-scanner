# Threat model

This file adapts Jaeger's existing security documents for the scanner. It does
not add rules those documents do not already state. Links are to
`main` of [jaegertracing/jaeger](https://github.com/jaegertracing/jaeger).

- [Threat model](https://github.com/jaegertracing/jaeger/blob/main/docs/security/threat-model.md) (trust boundaries B1–B4, threats T1–T6)
- [SECURITY.md](https://github.com/jaegertracing/jaeger/blob/main/SECURITY.md) (reporting, dependency policy, automated scanners)
- [Security architecture](https://github.com/jaegertracing/jaeger/blob/main/docs/security/architecture.md)
- [Assurance case](https://github.com/jaegertracing/jaeger/blob/main/docs/security/assurance-case.md)
- [CNCF self-assessment](https://github.com/jaegertracing/jaeger/blob/main/docs/security/self-assessment.md)
- [Security review 2026](https://github.com/jaegertracing/jaeger/blob/main/docs/security/security-review-2026.md)

The browser UI is a separate repository, [jaegertracing/jaeger-ui](https://github.com/jaegertracing/jaeger-ui), enrolled separately. Its `SECURITY.md` defers here.

## What this project does and where untrusted input enters

Jaeger is a CNCF graduated distributed tracing system. It collects spans from instrumented applications, stores them, and serves them through the Query API and the embedded UI. That scope is the project overview in the self-assessment and the overview in the threat model.

Untrusted input crosses the four trust boundaries in the threat model:

| Boundary | Description | Documented controls |
| --- | --- | --- |
| B1: SDK → Collector | External applications sending spans | TLS/mTLS, rate limiting, schema validation |
| B2: Collector → Storage | Internal service to database | TLS, authentication, authorized credentials |
| B3: Storage → Query | Database to internal service | TLS, authentication, read-only access |
| B4: Query → Users | Internal service to end users | TLS, bearer tokens, RBAC |

The 2026 security review restates the same edges: instrumented applications submit untrusted telemetry; the collector or ingester writes to storage; Query reads it back; users reach it through the Query API and browser UI. That review places browser environments, OpenTelemetry SDKs, identity providers, Kubernetes, and the internals of external storage outside this repository's boundary. Jaeger still has obligations where it accepts data from or connects to those systems. Rendering in the browser is boundary B4 as implemented by jaeger-ui.

Documented entry points, from the security architecture:

- OTLP over gRPC and HTTP, and Protobuf. These are the primary ingestion formats. Inbound spans are validated against their schemas.
- Size limits on gRPC messages and HTTP ingestion requests.
- Storage queries (Elasticsearch, Cassandra, and the other backends) built with parameterized queries or the backend client libraries.

Threat actors named in the threat model: a malicious or compromised application sending traces, an external attacker with network access, a malicious insider with legitimate access, and a network man-in-the-middle.

## Components that matter most / least

Most, because the threat model and assurance case put the security controls on them:

- Collector ingestion (B1): sampling, rate limiting, schema and size checks.
- Storage clients (B2 and B3): TLS, credentials, and query construction. The assurance case notes the collector writes and Query reads.
- Query API authentication and authorization (B4): bearer tokens, OAuth2, RBAC, as the operator configured them.

The assurance case lists these weakness classes as ones the project mitigates: injection (CWE-89, CWE-79) via structured protobuf/OTLP and parameterized storage queries; broken authentication (CWE-287); sensitive data exposure (CWE-200); broken access control (CWE-284); cross-site scripting (CWE-79), mitigated by "UI built with React (auto-escaping), CSP headers"; insecure deserialization (CWE-502); and SSRF (CWE-918), with the note that the backend does not fetch user-controlled URLs.

Less, or outside this repository:

- `idl/` and `jaeger-ui/` are git submodules. Unit tests in CI do not check them out. `make build-binaries` does, because the all-in-one binary embeds the built UI. Without those assets, `cmd/jaeger` serves a placeholder page (`cmd/jaeger/internal/extension/jaegerquery/internal/ui/assets.go`). Defects in UI rendering belong to the jaeger-ui enrolment.
- Examples under `examples/` (HotROD and similar) are demonstration programs.
- The storage engines themselves, SDKs, and cluster infrastructure are out of the boundary drawn by the 2026 review, except for Jaeger's own client and configuration code.

## Threats already enumerated

Impact and likelihood below are copied from the threat model. They are properties of those scenarios, not a general scale for other bugs.

- **T1 Denial of service via span flooding.** A malicious or misconfigured application sends excessive spans. Actor: malicious application. Impact: High (can overwhelm collector and storage). Likelihood: Medium. Mitigations: collector rate limiting, adaptive sampling, per-service resource quotas, Kafka buffering.
- **T2 Sensitive data exposure in traces.** Spans may contain PII or credentials. Actors: external attacker, malicious insider. Impact: High (data breach). Likelihood: Medium. Mitigations: TLS, Query RBAC, retention policies, guidance on what not to trace.
- **T3 Man-in-the-middle.** Unencrypted trace traffic is intercepted. Actor: man-in-the-middle. Impact: High. Likelihood: Low when TLS is used. Mitigations: TLS/mTLS, certificate verification on by default, optional pinning.
- **T4 Unauthorized access to trace data.** Someone reaches the Query UI or API without authorization. Actors: external attacker, malicious insider. Impact: Medium (information disclosure). Likelihood: Medium. Mitigations: bearer tokens, OAuth2, RBAC, audit logging.
- **T5 Storage backend compromise.** Direct access to the database. Actor: external attacker. Impact: High (full data access). Likelihood: Low. Mitigations: storage authentication, network isolation, encrypted connections, storage access controls.
- **T6 Supply chain.** A compromised dependency is introduced into the build. Actor: external attacker. Impact: Critical (code execution). Likelihood: Low. Mitigations: Dependabot, DCO, GPG-signed releases, SBOM generation, pinned dependencies with checksums.

Operator and instrumenter recommendations in the threat model: TLS with verification left on (`insecure` not set), mTLS for collector ingestion, bearer tokens or OAuth2, RBAC, audit logging, network segmentation, and never putting credentials or PII into spans.

Architecture defaults that match those recommendations: when TLS is enabled, certificate verification is on; `insecure: true` or `insecure_skip_verify: true` is an explicit opt-out. Minimum TLS in production is 1.2, and 1.3 is recommended. TLS 1.0 and 1.1 are documented as deprecated and must not be enabled in production. The assurance case notes that TLS itself is opt-in so non-production setups stay simple, and that production deployments must enable TLS, preferably mTLS, on external and inter-service connections. Credentials are not hardcoded; they come from the environment, flags, or files.

## How to exercise it

CI unit tests are `make test-ci` in `.github/workflows/ci-unit-tests.yml` (that target is `build-examples` and `cover`, with the race detector and `gotestsum`). The image also runs a narrower command that does not need those extra tools:

```
go test -count=1 -short -timeout 20m ./...
```

CI builds binaries with `make build-binaries` (`.github/workflows/ci-build-binaries.yml`), which needs the submodules. The image builds `./cmd/jaeger` and `./...`. The resulting binary is `/usr/local/bin/jaeger`. `jaeger version` and the placeholder UI path are enough to see that the build is the real one.

Static analysis already used by the project, from the self-assessment: `golangci-lint`, `gosec`, and Dependabot. `make govulncheck` is the documented way to check whether a Go dependency CVE is reachable.

## How you rate severity

The source documents do not define a general severity scale for vulnerability reports. They do not say, for example, that every crash is high, or how a post-authentication bug compares with an unauthenticated one. Do not invent a scale to fill that gap.

What they do say, and only this:

- Threats T1–T6 carry the Impact and Likelihood values quoted above.
- `SECURITY.md` dependency policy: CVEs in Jaeger code are patched in the newest releases. CVEs in dependencies are patched for supported versions when the CVE is applicable and the project's dependency-scanning automation rates it high or critical. Dependabot runs daily.
- `SECURITY.md` "Automated Security Scanners": raw scanner output is not accepted. Report only a finding that is actually applicable to Jaeger, with an explanation of why. Verify a Go dependency CVE with [govulncheck](https://pkg.go.dev/golang.org/x/vuln/cmd/govulncheck) against the source, not a binary. If that vulnerable path is not reachable from Jaeger, it is not actionable. Check whether Dependabot already tracks it, then use the reporting process in `SECURITY.md`.
- The assurance case names CWE mitigations and does not assign those CWEs a severity.
- Supported versions are the latest minor release only (`SECURITY.md`).

## Anything to leave alone

- Generic scanner output, especially Go module CVEs that govulncheck shows are not reachable, and anything Dependabot already tracks (`SECURITY.md`).
- "TLS is off unless configured." That is the documented non-production default. A finding is in scope when Jaeger skips verification, or speaks without TLS, despite the operator leaving the documented secure settings in place.
- TLS 1.0 and 1.1 remaining selectable. The architecture doc already says they must not be enabled in production and that the minimum there is TLS 1.2.
- Storage engines, SDKs, identity providers, Kubernetes, and browser engines, except for bugs in Jaeger's own clients, configuration, or the code that embeds the UI (security review 2026). UI rendering bugs belong in the jaeger-ui enrolment.
- Trace data that contains a secret because the instrumented application recorded one. The threat model tells developers not to do that. A defect is in scope when Jaeger itself copies a credential or token into a span.

## Reports

Report through `SECURITY.md`: a GitHub Security Advisory on jaegertracing/jaeger, or an encrypted message to the maintainers. The public key id in that file is `C043A4D2B3F2AC31`. This enrolment sends scanner mail to `cncf-jaeger-maintainers@lists.cncf.io`, the maintainers' list named in `MAINTAINERS.md`. There is no `auto_ccs` list.
