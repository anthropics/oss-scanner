# Threat model

## What this project does and where untrusted input enters

pgjdbc is the PostgreSQL JDBC driver. It is a pure Java client library that speaks the
PostgreSQL frontend/backend protocol, and it runs inside the application that loads it.

Untrusted input reaches the driver in four places:

- Applications bind parameter values with `setString`, `setObject`, arrays, `PGobject` and
  similar methods. In most applications an attacker controls these values. The most important
  class of bug is anything that lets a bound value change the meaning of the SQL sent to the
  server. Examples are SQL injection through parameter inlining, simple query mode, escape
  processing, `standard_conforming_strings=off`, or the quoting of array and composite literals.
- The driver parses the SQL text it is given for placeholders, escapes, comments, dollar quotes
  and statement boundaries. The SQL itself is trusted. A parser mistake that makes a bound value
  or a quoted literal be read as SQL is in scope.
- The driver reads bytes from the network. Anyone on the path can supply them before TLS is
  established, and at any time when TLS is off or the server is not verified. A malicious or
  compromised server is also in scope. Findings here include infinite loops, hangs and crashes
  in the client, and anything that leaks client secrets such as passwords or keys to a server
  that was not meant to receive them. Memory use driven by the server is a finding only in the
  cases described after the severity list below.
- Connection URLs and properties are usually trusted configuration, but some applications let
  users supply parts of them. Some properties load classes, for example `socketFactory`,
  `sslfactory`, `sslhostnameverifier` and `authenticationPluginClassName`. They are documented
  to instantiate arbitrary classes, so reporting that alone is not a finding.

## Components that matter most / least

- The packages that matter most are `org.postgresql.core`, `org.postgresql.jdbc`,
  `org.postgresql.ssl` and the authentication code. The core package holds the protocol code,
  including `Parser`, `QueryExecutorImpl`, `PGStream` and the `v3` package. The jdbc package
  handles statements and parameters, `PgResultSet` conversions, and array and type encoding.
  The ssl package sets up TLS and verifies host names. Authentication lives in
  `org.postgresql.core.v3.ConnectionFactoryImpl` and the SCRAM and GSS code.
- The `copy`, `largeobject`, `replication`, `xa`, `jdbcurlresolver` and `util` packages are
  also in scope.
- The `osgi`, `ds` and `translation` packages matter less. The `ds` package wires up
  DataSources, and `translation` holds generated message bundles.
- The `benchmarks/` directory, the test modules (`pgjdbc-*-test` and `testkit`),
  `build-logic*/`, `docs/` and `packaging/` are out of scope.

## How to exercise it

- Build the driver with `./gradlew --offline $PGJDBC_GRADLE_FLAGS :postgresql:jar`.
- The image provides `pgjdbc-test-db`, which starts a local PostgreSQL server on
  localhost:5432 in the background. It runs the scripts in `docker/postgres-server/scripts`,
  the same ones CI uses, so the server has SSL, SCRAM and prepared transactions enabled and has
  the users and databases the tests expect. The server log is `/var/log/pgjdbc-test-db.log`.
- Run tests with `./gradlew --offline $PGJDBC_GRADLE_FLAGS :postgresql:test --tests <class>`.
  The tests live under `pgjdbc/src/test/java`. Good starting points are
  `org.postgresql.core.ParserTest` and the `org.postgresql.test.jdbc2` package. Tests that need
  GSS, replicas or other servers are not set up in this image.
- To test against a hostile server, the easiest reproducer is usually a small Java or Python
  program that listens on a socket and writes crafted protocol messages.

## How you rate severity

- Critical findings include SQL injection through bound parameters under default settings.
  They also include bypassing TLS host name or certificate verification when the user asked for
  `sslmode=verify-full`, and remote code execution from data sent by the server.
- High findings include SQL injection that needs a non-default but documented setting. They also
  include sending a password or other credential in clear text, or to an unintended host, when
  the settings say the driver should not. Denial of service before authentication completes is
  high when it takes down the whole application rather than just the one connection. Examples
  are a JVM-wide out of memory error, or a hang that holds a shared lock.
- Medium findings include other denial of service caused by a malicious server or network
  attacker, such as a hang, an unbounded loop or excessive memory use. Rate such a finding high
  instead when the context makes the impact comparable to the pre-authentication case above.
  Information leaks between connections or statements are also medium.
- Low findings are issues that need control over trusted configuration or application code.

Large allocations driven by the server are normal. A server can legitimately send a 1 GiB
value, and the driver has to allocate memory for it. A server asking the client to allocate a
lot of memory is not a finding on its own. Report it only when the allocation is far out of
proportion to the data the server actually sends, or when it happens before authentication.

## Anything to leave alone

- Do not report that a connection property naming a class loads that class. That is by design.
- The `sslmode` values `prefer`, `allow` and `require` do not verify the server identity. That
  is documented behavior.
- Do not report deserialization in `PGobject` subclasses supplied by the application.
- Proposed patches must not change the public API, because it is a compatibility promise.
