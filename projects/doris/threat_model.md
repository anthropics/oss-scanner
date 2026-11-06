# Apache Doris threat model

This enrollment scans `apache/doris`, branch `branch-4.2`. The scope and trust
assumptions below summarize the maintained Doris security contract:
https://github.com/apache/doris/blob/master/threat-model.md
and its companion policy:
https://github.com/apache/doris/blob/master/SECURITY.md.
Those documents live on master; do not assume master's configuration defaults or
implementation details also apply to 4.2. In particular, 4.2 defaults FE
`enable_all_http_auth` to **false**, whereas master defaults it to true. The
Dockerfile explicitly enables it in the packaged FE configuration for this audit.

Send findings privately to `kirs@apache.org`, copying `private@doris.apache.org`,
as configured in `project.yaml`. Do not disclose vulnerabilities in public GitHub
issues or enrollment PR comments. Doris' general disclosure process is at
https://doris.apache.org/community/security/.

## What the project does and where untrusted input enters

Doris is a distributed analytical SQL database. The Java Frontend (FE) handles
client authentication, SQL analysis, planning, authorization and cluster metadata.
The C++ Backend (BE) executes plans and manages storage. The storage-compute
separated deployment also includes a shared Cloud Meta Service and a Recycler.

The supported deployment is inside an operator-controlled private network, with
client-facing services separated from internal cluster services. Direct Internet
exposure and hostile access to the internal cluster network are outside the model.
An attacker need not have Internet access: an untrusted application or SQL user
inside the client network is still in scope.

In-scope attackers are:

- An unauthenticated client reaching FE MySQL (9030), FE HTTP (8030), FE Arrow
  Flight SQL (8070), or **BE Arrow Flight SQL (8050)**. BE Flight is a client
  service, not an internal RPC service.
- An authenticated SQL or HTTP user with limited privileges, trying to access
  another user's objects, credentials, sessions or data, exceed their grants,
  or execute code in a Doris process.
- A non-admin user granted catalog-creation privileges, within that privilege's
  documented capabilities. Establish the actual grant before claiming escalation.
- A legitimate cloud tenant attempting to access another tenant's metadata or
  data through the shared Meta Service's tenant-selection and authorization paths.

Client protocol bytes, credentials, session identifiers, SQL text, and HTTP request
parameters are untrusted. SQL statements are an intentional database interface;
show a privilege boundary violation or server escape rather than merely executing
SQL supplied by a client.

## Components that matter most / least

Prioritize these paths, following their callers and callees as necessary:

- `fe/fe-core/`: MySQL protocol handling, HTTP controllers, session identity,
  privilege checks, SQL analysis/planning and Arrow Flight SQL handling.
- `fe/fe-authentication/` and `fe/fe-authorization/`: authentication providers,
  access-control implementations and plugin boundaries used by FE.
- `fe/fe-common/`: shared configuration and security-sensitive utilities.
- `be/src/service/`, `be/src/runtime/`, and the Flight code they call: native
  client protocol processing, authentication and query-result ownership.
- `cloud/src/meta-service/` and `cloud/src/meta-store/`: correct tenant-scoped
  metadata access in the shared Meta Service. Do not confuse a trusted internal
  transport with permission to return one tenant's objects to another tenant.
- `ui/` and FE-served web content: browser attacks crossing users or privileges.
- Catalog, filesystem and Java-extension code where a restricted client's request
  can cross an actual privilege boundary; distinguish this from admin-loaded code.

Internal FE/BE RPC, edit-log replication, heartbeat, BRPC, BE HTTP (8040) and
broker traffic rely on network isolation and honest cluster peers. An exploit
requiring independent hostile access to those ports is outside the model. A
client-facing entry point that can drive an internal operation without the
required privilege is still worth investigating end to end.

Tests, sample applications, CI/development scripts, vendored reference code,
optional FE demo plugins, SDKs and separately maintained client extensions are not
the target. Third-party dependency CVEs alone are not Doris findings; demonstrate
a reachable, in-model exploit in the enrolled source.

## How to exercise it

The checkout is `/src`. The Dockerfile builds FE (including the UI and Java
extensions), BE and Cloud with the repository's `build.sh`. Native builds use ASan
and retain debug information; build trees and generated protocol bindings remain
available for incremental reproducers. The official toolchain is under
`/var/local/ldb-toolchain`; native dependencies are built from the 4.2 checkout's
definitions and installed under `/src/thirdparty/installed`. The master build
image's prebuilt libraries are not reused. Dependency build sources are removed
after installation to reduce image size.
Maven dependencies are retained under `/root/.m2`, with offline mode enabled after
setup; UI dependencies remain in `/src/ui/node_modules`.

- Small FE smoke test, also run during setup:
  `cd /src && bash ./run-fe-ut.sh --run org.apache.doris.mysql.MysqlPasswordTest`.
- Targeted FE tests: `bash ./run-fe-ut.sh --run <fully-qualified-test-class>`.
  Authentication and privilege tests are under
  `fe/fe-core/src/test/java/org/apache/doris/mysql/`.
- Incremental native build: `BUILD_TYPE=ASAN bash ./build.sh --be --cloud -j 1`.
  Build artifacts are in `be/build_ASAN/` and `cloud/build_ASAN/`.
- Packaged services are under `/src/output/fe/`, `/src/output/be/`, and
  `/src/cloud/output/`. Use their shipped startup scripts. A running FE and BE
  must be configured and registered together for SQL regression tests; the
  Dockerfile does not leave a cluster running. Use the repository's
  `run-regression-test.sh` for regression suites after that setup.

The scanning environment has no Internet access. External catalogs, object
stores, LDAP and FoundationDB are not provisioned by this image; use local test
fixtures or mocks rather than assuming a live external service. Native unit-test
binaries are not prebuilt; use `run-be-ut.sh` for tests when the audit resources
permit. Runtime services and tests must use local, non-conflicting ports.

**FE HTTP baseline:** keep the effective `enable_all_http_auth=true` throughout
security testing. Check the running value via `ADMIN SHOW FRONTEND CONFIG` or an
authenticated `/api/show_config` request; inspect both `fe.conf` and
`fe_custom.conf`, since the latter can override the former. The source default
being false on 4.2 is not a newly discovered bypass. FE `/metrics` and
`/api/health` are intentionally public. Some endpoints authenticate using a
cluster token instead of a user password; validate the relevant credential.
Authentication and object-level authorization are separate checks.

## Severity and report requirements

Use the maintained contract's distinction between security-critical violations
and correctness-only failures, and rate the demonstrated impact and prerequisites:

- Critical: demonstrated code execution or equivalent complete server compromise
  through an in-scope client interface without administrative privileges.
- High: authentication bypass, substantial RBAC bypass, credential theft,
  cross-tenant data access, or reachable native memory corruption with a credible
  security impact. A crash alone is not proof of arbitrary code execution.
- Medium / low: narrower unauthorized disclosures or browser attacks, according
  to the data, victim privileges and required interaction.

Every report should identify the exact 4.2 commit, deployment shape, entry point,
attacker role and initial grants, effective configuration, and the boundary crossed.
Include a minimal reproducer and observed results. Distinguish confirmed impact
from hypotheses; show the client-to-sink path for internal-service issues. Prefer
focused patches and negative tests showing a restricted or unauthenticated caller
being rejected while legitimate access remains functional.

## Explicit non-goals and intended capabilities

- Operators, `SUPER` / `ADMIN_PRIV` holders, cluster peers, admin-installed UDFs,
  plugins and JDBC drivers are trusted. Executing code that an administrator
  deliberately installs is not a privilege escalation.
- Admin-connected external catalogs and storage are trusted inputs. Findings
  requiring malicious data from a compromised external system are outside this
  model; do not generalize that trust to bytes from a client-facing protocol.
- Pathological authenticated SQL consuming resources, ordinary query failures,
  timing side channels, and Byzantine replication peers are not modeled attacks.
  Reachable memory corruption or an authentication defect is a different claim.
- TLS and login lockout are configurable and not universally enabled by default.
  Report a broken configured protection rather than its absence by default.
- Catalog connections intentionally make outbound requests. An administrator's
  chosen destination, or a URL accepted within catalog-creation privileges, is
  not by itself proof of SSRF privilege escalation; apply the maintained model's
  treatment of catalog URLs and operator responsibilities.
- BE HTTP 8040 is internal and has a different authentication default from the
  authenticated FE HTTP audit baseline. Do not expose it to untrusted clients to
  manufacture a vulnerability. Host, Kubernetes and hypervisor isolation are
  operator responsibilities; Meta Service tenant isolation remains in scope.
