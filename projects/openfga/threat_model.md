# Threat model: OpenFGA

## What this project does and where untrusted input enters

OpenFGA is a relationship-based access control (ReBAC) authorization server inspired by Google Zanzibar. Applications store an authorization model (types, relations, and rewrites such as union, intersection, exclusion, tuple-to-userset, and CEL conditions) and relationship tuples in a store, then ask OpenFGA authorization questions: `Check`, `BatchCheck`, `ListObjects`, `StreamedListObjects`, `ListUsers`, and `Expand`. Applications enforce access on the answers. **A wrong answer is an authorization bypass in every application that relies on it.** The project's stated priorities are, in order, correctness, reliability, and performance.

The server is `cmd/openfga` (`openfga run`). It serves gRPC on `:8081` (with server reflection), the HTTP/JSON gateway on `:8080`, and, when enabled, the playground on `:3000`. Data lives in one datastore: memory, PostgreSQL, MySQL, or SQLite (`pkg/storage/`).

Treat the following as attacker-controlled:

- **Every API request body and parameter** reaching `pkg/server/` over gRPC or HTTP: store IDs, model IDs, tuple keys (`object`, `relation`, `user`, including usersets `type:id#relation` and wildcards `type:*`), contextual tuples, condition names and `context` maps, continuation tokens, page sizes, and consistency preferences.
- **Authorization models** submitted with `WriteAuthorizationModel`. In many deployments the client that writes models is the same tenant that writes tuples, so a hostile model is in scope. Models are validated by `pkg/typesystem/` and `github.com/openfga/language`.
- **CEL condition expressions and their parameters** (`internal/condition/`), evaluated during checks with the request and stored context.
- **Continuation tokens** returned to clients and sent back (`pkg/encoder/`, `pkg/encrypter/`). They must not let a caller read another store's data or inject datastore queries.
- **Credentials**: the `Authorization` header with a preshared key or an OIDC bearer token (`internal/authn/`), and the claims inside the token.
- **The timing and shape of requests**: deep or wide model graphs, cycles, many concurrent requests, and requests that cancel mid-flight.

Trusted: the operator, the command-line flags, environment variables and config file, the datastore itself and its credentials, the OIDC issuer the operator configures, and the host.

### Authentication and tenancy

- `--authn-method none` (the default) has no authentication; anyone who can reach the port is a full client. This is documented and not a finding.
- `--authn-method preshared` accepts any of a set of static keys. Every key holder can call every API on every store.
- `--authn-method oidc` validates JWTs against the configured issuer and audience (`internal/authn/oidc/`). Both are required; issuer, audience, signature, expiry, and algorithm checks must hold.
- The experimental access-control feature (`--experimentals enable-access-control` with `--access-control-enabled`, `internal/authz/`) authorizes each API call per store and per module using an OpenFGA store. It narrows what an OIDC client can do; it is the only mechanism that separates tenants that share one server.

A **store** is the unit of isolation. Data, models, assertions, and changes from one store must never be readable or writable through a request for another store, including through caches, continuation tokens, `ReadChanges`, or the shared iterator.

## Components that matter most / least

Most important, in this order:

1. **Query resolution correctness**: `internal/graph/` (the `LocalChecker` and the resolver chain built in `internal/graph/builder.go`), `internal/check/`, the weighted-graph check, `internal/listobjects/` (including the ListObjects pipeline in `internal/listobjects/pipeline/`, which is **on by default**), `pkg/server/commands/reverseexpand/`, `pkg/server/commands/listusers/`, and `internal/planner/`. Exclusion (`but not`), intersection (`and`), public wildcards (`type:*`), tuple-to-userset (`from`), conditions, contextual tuples, and error handling inside these operators are where past bugs lived.
2. **Caching**: the check query cache, check and ListObjects iterator caches, shared iterator, cache controller (`internal/cachecontroller/`), and the cache-key functions in `pkg/storage/keys.go`. Two different requests must never share a key, and a cache must not serve results across stores, models, or invalidations.
3. **Authentication and API authorization**: `internal/authn/`, `internal/middleware/authn/`, `internal/authz/`, and the store ID middleware in `pkg/middleware/storeid/`.
4. **Datastores**: `pkg/storage/sqlcommon/`, `pkg/storage/postgres/`, `pkg/storage/mysql/`, `pkg/storage/sqlite/`, `pkg/storage/memory/`. Watch for SQL injection, collation or case-folding differences between engines, ordering and pagination errors, and tuple filters that return rows they should not.
5. **Model and tuple validation**: `pkg/typesystem/`, `internal/validation/`, `pkg/tuple/`. A tuple that passes validation but resolves differently from how it was validated, or a model the validator accepts but the resolver misinterprets, is in scope.
6. **CEL conditions**: `internal/condition/`, including the cost limit (`--max-condition-evaluation-cost`, default 100) and context size limit.
7. **The HTTP gateway and middleware**: `pkg/gateway/`, `pkg/middleware/`, and the HTTP/gRPC wiring in `cmd/run/`.

Experimental features are enabled with `--experimentals` (`pkg/server/config/config.go`). OpenFGA's security policy does not assign CVEs for experimental features but still wants reports. Report them, and say in the report that the feature is experimental. Exception: `pipeline_list_objects` is enabled by default and must be treated as stable.

Out of scope: `internal/mocks/`, test files and fixtures, `pkg/testfixtures/`, `pkg/testutils/`, `docs/`, `plans/`, `scripts/`, `telemetry/`, `.github/`, and the Helm chart, SDKs, CLI, and language repositories (they have their own repositories). A flaw wholly inside a dependency (`google/cel-go`, `grpc-go`, `grpc-gateway`, `pgx`, the MySQL or SQLite drivers) belongs upstream; report it here only when OpenFGA's use makes it reachable, and show the path.

## How to exercise it

The image has only loopback networking. The source is in `/src`, every module is in the Go module cache, `GOTOOLCHAIN=local`, `GOPROXY=off`, and `GOSUMDB=off` are set, and all tests are compiled with and without `-race`.

- **Server**: `/usr/local/bin/openfga` is built from `/src`. Start it with the memory datastore: `openfga run --playground-enabled=false`. Add `--authn-method preshared --authn-preshared-keys KEY` for authentication.
- **SQLite**: a migrated database is at `/var/lib/openfga/openfga.db`: `openfga run --datastore-engine sqlite --datastore-uri 'file:/var/lib/openfga/openfga.db'`.
- **PostgreSQL**: a migrated local cluster is installed. Run `service postgresql start`, then `openfga run --datastore-engine postgres --datastore-uri 'postgres://postgres:password@127.0.0.1:5432/openfga?sslmode=disable'`. Use `psql -h 127.0.0.1 -U postgres openfga` to inspect rows.
- **MySQL** is not installed. MySQL-specific findings can be argued from `pkg/storage/mysql/` and the migrations in `assets/migrations/mysql/`, but cannot be run here.
- **Clients**: `fga` (OpenFGA CLI) is installed: `fga store create`, `fga model write --file model.fga`, `fga tuple write`, `fga query check`, and `fga model test --tests tests.fga.yaml` (which runs Check, ListObjects, and ListUsers assertions against a built-in server with no network). Use `fga model transform` to convert DSL to JSON. `curl` and `jq` reach the HTTP API on `:8080`; `grpcurl -plaintext localhost:8081 list` reaches gRPC (reflection is enabled).
- **Tests**: `make test` and `make test-unit` run `go generate`, which installs `mockgen` and needs the network; run `go test` directly instead. Mocks are checked in. A correctness reproducer is usually best written as a new YAML case in `assets/tests/consolidated_1_1_tests.yaml` or `assets/tests/abac_tests.yaml`, run by `go test -run 'Memory|SQLite' ./tests/...`, or as a Go test next to the code it exercises.
- **Docker-backed tests**: the PostgreSQL and MySQL fixtures in `pkg/testfixtures/storage/` start containers through the Docker API, which does not exist here. `TestMatrixPostgres`, `TestCheckMySQL`, and similar tests, the Docker client tests in `pkg/testutils`, and every test in `pkg/storage/postgres`, `pkg/storage/mysql`, `pkg/storage/migrate`, `cmd/migrate`, and `cmd/validatemodels`, fail here; that is not a finding. The build log shows which tests passed. Matrix tests under heavy load can occasionally fail with `Request Cancelled` (the default 3s deadline); rerun before treating that as a result.
- `go test -race` is supported and recommended for anything touching caches, the resolver chain, the ListObjects pipeline, or concurrency helpers in `internal/concurrency/` and `internal/containers/`.

## How you rate severity

The trust boundary is between a client of the API and the data and decisions of the server. State the configuration the reproducer needs (datastore engine, authn method, experimental flags, non-default cache or limit settings); a finding against the defaults weighs more than one that needs a non-default setting.

- **Critical**: an unauthenticated caller bypassing preshared-key or OIDC authentication; reading or writing another store's tuples, models, or changes; SQL injection; remote code execution; or a Check/ListObjects/ListUsers result that grants access it should not for a simple, common model with default settings.
- **High**: an incorrect authorization decision (a false `allowed: true`, or an object or user returned that should not be) for a realistic model, reachable with default settings or a widely used stable option. Cache-key collisions or cache poisoning that leak decisions between requests. Bypass of the access-control feature's per-store or per-module checks.
- **Medium**: an incorrect decision that needs an unusual model combination or non-default stable option. A denial of service from one cheap request that defeats the documented limits (`--resolve-node-limit`, `--resolve-node-breadth-limit`, list deadlines and max results, `--max-condition-evaluation-cost`, request timeout, max model size and types), such as unbounded memory, a goroutine leak, or a panic that crashes the process. An incorrect decision in an experimental feature. Leaking secrets (preshared keys, datastore credentials, tokens) into responses or logs.
- **Low**: a false denial (`allowed: false` when access should be granted) with no other effect. A panic confined to one request that is recovered. Resource use that stays within configured limits but is higher than expected.

## How to report

- Include the full authorization model in DSL, the tuples, the request, the actual result, and the expected result, with an explanation from the model's semantics of why the expected result is right.
- Give a reproducer that runs in this image: preferably a YAML test case or a Go test, otherwise the exact `fga`, `curl`, or `grpcurl` commands with the `openfga run` command line.
- Say which APIs are affected (Check, BatchCheck, ListObjects, StreamedListObjects, ListUsers) and whether the bug depends on the datastore engine.
- Propose a minimal patch against `main` with a regression test. Keep unrelated refactoring out of it.
- Report one root cause once, listing every API and path it affects.

## Anything to leave alone

- `--authn-method none` exposing every API, and the absence of rate limiting or TLS by default; these are operator choices.
- Every preshared key, and every OIDC client without access control enabled, can act on every store; this is by design.
- The playground (`:3000`, off by default, `--playground-enabled`) is a development tool not intended for production exposure. Report it only if it exposes secrets or bypasses authentication on the API ports.
- Expensive models or large tuple sets that stay within the configured limits and deadlines are performance work, not vulnerabilities.
- Differences between results under `HIGHER_CONSISTENCY` and `MINIMIZE_LATENCY` caused by documented cache TTLs are expected staleness, not a bypass.
- `Expand` returns one level of the tree by design; clients are expected to expand further themselves.
