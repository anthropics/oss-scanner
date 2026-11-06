# Threat model: micronaut-data

## What this project does and where untrusted input enters

Micronaut Data is a database access toolkit for the Micronaut Framework. Repository interfaces are analysed at
compile time and implemented without reflection or runtime proxies; queries are generated at build time (JPQL,
SQL, MongoDB pipelines, Cosmos SQL). It is a library: an application declares repositories and calls them from
its own code. Modules:

- `data-model`, `data-processor`, `data-runtime`, `data-tx`, `data-connection`: the query model and AST,
  the compile-time processor, runtime query building and pagination, transaction and connection management.
- `data-jdbc`, `data-connection-jdbc`, `data-tx-jdbc`: SQL generation (dialects for H2, MySQL, PostgreSQL,
  Oracle, SQL Server, ...), parameter binding, result mapping, JSON/vector column support.
- `data-hibernate-jpa`, `data-hibernate-reactive`, `data-jpa`, `data-tx-hibernate`: JPA/Hibernate integration.
- `data-r2dbc`, `data-mongodb`, `data-azure-cosmos`, `data-document-*`: reactive SQL, MongoDB and Cosmos DB.
- `data-spring*`: Spring Data compatibility.

Untrusted input reaches the library through the values an application passes to repository methods, which in
a web application usually come straight from HTTP requests:

- **Parameters bound into queries**: strings, collections, enums, JSON values; these must always be sent as
  bind parameters, never concatenated into the query text.
- **Dynamic parts of a query chosen by the caller**: `Sort` / `Sort.Order` property names and direction,
  `Pageable` page size and offset, `@Where` / `@Query` templates with placeholders, criteria and
  specification objects, dynamic `LIKE` patterns, `IN` list expansion and `ORDER BY` generation.
- **Query-method names** parsed at compile time (trusted, developer code).
- **Database responses** being mapped into entities.

Trusted input: application source code, repository interfaces, annotations (`@Query`, `@Where`, `@MappedEntity`),
`application.yml` and the environment. Bugs that need a malicious developer or configuration are out of scope.

## Components that matter most / least

Most important: query generation in `data-model` / `data-processor` (`SqlQueryBuilder`, the JPQL, MongoDB and
Cosmos builders, identifier and sort-property escaping and validation), `data-runtime` (pagination and sorting
at runtime, dynamic sort handling, cursor pagination), `data-jdbc` and `data-r2dbc` (parameter binding,
batching, result mapping), `data-hibernate-jpa`, `data-mongodb` (operator/pipeline construction),
`data-azure-cosmos`.

Still in scope but less exposed: `data-tx*`, `data-connection*`, `data-spring*`, `data-document-*`.

Out of scope: `test-suite-*`, `doc-examples`, `benchmarks`, `jakarta-data-tck`, `buildSrc` and build logic,
documentation (`src/main/docs`), and vulnerabilities in dependencies such as Hibernate, JDBC drivers or the
MongoDB driver. Report those upstream, unless Micronaut Data's use of the dependency is what makes them
exploitable.

## How to exercise it

- The image compiled every module and its tests and cached every dependency. The scan has no network, so
  Gradle is forced offline by `/root/.gradle/init.d/oss-scanner-offline.gradle`; passing `--offline` as well
  is fine. Always pass `-Dtestcontainers=false` so that tests needing Docker are skipped.
- Run a module's tests with `./gradlew --offline -Dtestcontainers=false :micronaut-data-model:test` (Gradle
  project names carry the `micronaut-` prefix: `:micronaut-data-processor:test`, `:micronaut-data-jdbc:test`,
  ...), a single class with `--tests 'io.micronaut.data.model.query.builder.SomeSpec'`. Tests are Spock
  (Groovy) and JUnit 5. Query builder tests need no database; `data-jdbc` and `data-hibernate-jpa` tests use
  in-memory H2 and run offline. Tests that need a database container (PostgreSQL, MySQL, Oracle, MongoDB, ...)
  cannot run in the scanner and should be skipped, not reported.
- The scan machine is small (2 CPUs, 8 GB): run one module at a time; `--max-workers=2` helps.
- Tests may start an embedded server on $HOSTNAME; the image sets `HOSTNAME=localhost` because the container's
  own hostname does not resolve without a network.

## How you rate severity

- **Critical**: SQL, JPQL, MongoDB or Cosmos query injection reachable with default configuration through a
  value, sort property, page parameter or pattern that an application would plausibly take from an HTTP
  request; cross-tenant or cross-schema data access caused by the library (multitenancy discriminator or
  schema selection ignored or bypassable).
- **High**: injection that needs a documented but non-default feature (for example a dynamic `@Query`
  template or a particular dialect); `@Where` / soft-delete filters that are silently dropped for some
  operation; transaction or connection leakage across requests; credentials or query parameters leaked in
  logs or exceptions.
- **Medium**: denial of service from a small input (unbounded page size or `IN` list expansion without a
  limit, pathological `LIKE` pattern handling, resource leaks); incorrect escaping that only breaks
  queries; weaknesses needing an unusual configuration.
- **Low / informational**: issues that need a malicious developer or configuration, a non-public API, or
  local access; hardening suggestions.

Default configuration matters: an issue reachable with the defaults rates one level higher than the same
issue that needs the developer to opt in.

## Reports and patches

- Patches should target the default branch (the current development line), use Java 25, keep binary
  compatibility of public API (add, deprecate; do not change signatures), and follow the surrounding code
  style. Mark internal API `@Internal`.
- Please include a failing Spock or JUnit 5 test next to the existing tests of the module, showing the
  generated query (or the executed statement) and the exact input that reproduces the issue.

## Anything to leave alone

- Credentials and connection strings in test fixtures are intentional non-secret fixtures.
- Findings that amount to "a dependency has a CVE": Dependabot and Renovate cover that.
- Behaviour of the database or its driver itself, and of Micronaut core: report those to the respective
  projects (micronaut-core is enrolled separately).
