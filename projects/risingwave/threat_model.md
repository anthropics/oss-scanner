# RisingWave security review scope

## Project and trust boundaries

RisingWave is an Apache-2.0, PostgreSQL-compatible streaming database. The public
repository contains the SQL frontend, batch and streaming execution, meta service,
storage, connectors, and supporting libraries. Review the checked-out public
revision and record its commit ID in each report.

Prioritize the following attacker-controlled input and boundaries:

- PostgreSQL wire-protocol frames, startup/authentication messages, SQL, prepared
  statement parameters, COPY input, and malformed or unusually nested values.
- Authentication, authorization, ownership, grants, catalog access, and separation
  between database users. Show the exact privileges needed by the attacker.
- Source records, schemas, connector configuration, file/object contents, and
  external service responses. Distinguish trusted connector administrators from
  ordinary SQL users and from parties that only control upstream data.
- Deserialization, length/allocation checks, unsafe Rust, JNI/FFI boundaries,
  expression/UDF execution, filesystem paths, credential handling, error messages,
  logs, and network destinations derived from untrusted data.
- Internal RPC and meta/storage messages. State whether exploitation requires
  access to an internal network, a trusted node, or administrator credentials;
  do not silently treat those interfaces as publicly accessible.

## Build and local reproduction

The checkout is at `/src`. The Dockerfile builds `target/ci-dev/risingwave` from
source using `rw-dynamic-link,all-connectors-lite,udf`. Rust registry/git caches
and build outputs are retained. `CARGO_NET_OFFLINE=true` applies after setup.
Dependency optimization is disabled for this audit build to reduce cold-build time;
line-table debug information, debug assertions and overflow checks are retained.
The audit defaults to two Cargo/CMake jobs. Keep the all-in-one package selected
when running these unit suites so Cargo reuses the binary's dependency features:


```sh
cargo test --locked --offline --profile ci-dev --lib \
  -p risingwave_cmd_all -p risingwave_sqlparser -p pgwire -p risingwave_connector_codec \
  --no-default-features \
  --features risingwave_cmd_all/rw-dynamic-link,risingwave_cmd_all/all-connectors-lite,risingwave_cmd_all/udf
```

Append `-- TEST_NAME` to filter for a focused test. Dropping the all-in-one
package can change dependency features and trigger a second compilation.

For SQL/protocol experiments, start a disposable in-memory instance inside the
isolated scanner environment (use only synthetic data):

```sh
ENABLE_TELEMETRY=false target/ci-dev/risingwave playground \
  > /tmp/risingwave-scanner.log 2>&1 &
PGPASSWORD='' psql -h 127.0.0.1 -p 4566 -U root -d dev -c 'SELECT 1;'
```

Wait for PostgreSQL readiness before connecting. The default root account here
is a local test convenience, not evidence of an authentication bypass. Configure
separate test users and relevant permissions when testing authorization.

Build coverage limitations: the optional heavy LanceDB sink, the frontend's
optional DataFusion feature, Java connector assemblies, the dashboard frontend, and external
service integration environments are not built/provisioned. Their public source
may still be inspected, but reports must distinguish source-only hypotheses from
reproduced findings. No private RisingWave Cloud services are available.
Connector dependencies can still compile DataFusion crates; this does not enable
the frontend's optional DataFusion feature or validate external integrations.

## Evidence and triage guidance (proposed for maintainer review)

For each finding, provide the exact commit, file/line, affected configuration,
attacker access and privileges, violated boundary, minimal synthetic reproducer,
observed versus expected result, and a proposed fix plus regression test where
possible. Deduplicate reports with the same underlying cause. If a dependency
appears responsible, identify a concrete vulnerable use in RisingWave and avoid
claiming a dependency advisory alone is a new RisingWave vulnerability.

Suggested severity depends on realistic impact and preconditions. Unauthenticated
code execution or broad unauthorized data access may be critical; demonstrated
privilege escalation, secret disclosure, or a reliable remotely triggered outage
may be high. Report lower-impact issues too, but distinguish a single-session
error from whole-service unavailability. Do not classify every parser panic,
resource-intensive authorized query, or administrator-controlled connector URL
as a critical issue without demonstrating the relevant boundary violation.

Do not exclude an issue merely because exploitation requires authentication:
low-privileged users and upstream data producers are meaningful adversaries.
Evaluate platform-specific and feature-specific behavior with explicit caveats.

## Data handling and disclosure

Use only the public checkout, public dependencies, and synthetic test fixtures.
Do not seek production access, customer datasets, internal endpoints, cloud
credentials, personal data, or private repositories. Do not contact real external
targets to demonstrate SSRF or exfiltration; use loopback/local test services.
Disable telemetry for reproductions and keep scanning offline.

Send reports through the configured verified security contact. Do not publish
unfixed findings, exploit details, or real credentials in public issues, PRs,
build logs, or the enrollment repository. Redact incidental secrets. These are
requested handling instructions, not additional contractual guarantees from
Anthropic; the service agreement governs retention, access, and disclosure.
