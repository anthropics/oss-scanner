# Threat model: micronaut-core

## What this project does and where untrusted input enters

Micronaut is a JVM framework for building microservices and serverless applications. `micronaut-core` is its
foundation: compile-time dependency injection and AOP (`inject`, `inject-java`, `inject-groovy`, `inject-kotlin`,
`core-processor`, `aop`), the application context and configuration (`context`), an HTTP server and client built on
Netty (`http`, `http-server`, `http-server-netty`, `http-netty`, `http-client`, `http-client-core`, `http-netty-http3`),
JDK-based HTTP client (`http-client-jdk`), routing (`router`), JSON binding with Jackson (`json-core`, `jackson-core`,
`jackson-databind`), WebSocket support (`websocket`), management endpoints (`management`), functions (`function*`),
retry/circuit breakers (`retry`), and context propagation.

Untrusted input reaches the framework at runtime through:

- **HTTP requests** served by the Netty server: request line and URI, headers, cookies, query and path parameters,
  bodies (JSON, form, multipart, streaming), HTTP/2 and HTTP/3 frames, WebSocket frames, and TLS. This is the main
  attack surface: applications built on Micronaut expose it directly to the Internet.
- **HTTP responses** received by the HTTP clients from remote servers (headers, bodies, redirects, chunked and
  compressed encodings), which an application may point at third-party services.
- **Request routing and binding**: the router matches URIs to controller methods and binds request data to method
  arguments; errors here become authorization bypasses in the application (for example reaching a route that a
  filter or security rule expected to be matched differently).
- **Static resource serving** (`StaticResourceResolver` and friends) resolves request paths to files on the
  classpath or file system.
- **Management endpoints** (`management`), when enabled, expose health, beans, loggers, environment and similar
  endpoints over HTTP.

Trusted input: application source code, annotations and configuration files (the compile-time processors read
trusted developer code), the environment and system properties, and anything a developer writes in a bean. Bugs
that need a malicious application developer or a malicious configuration file are out of scope.

## Components that matter most / least

Most important, in this order: `http-server-netty`, `http-netty`, `http-server`, `http`, `router`,
`json-core` / `jackson-*`, `websocket`, `http-client*`, `management`, `core` (URI parsing, path matching, conversion
and IO utilities used by the above), `context-propagation`, `function-web`.

Still in scope but less exposed: `context`, `inject*` runtime (bean lookup at runtime), `retry`, `discovery-core`,
`messaging`, `runtime`.

Out of scope: `test-suite-*` and `*-test` modules, `benchmarks`, `buildSrc` and build logic, `src/main/docs`,
`graal` (native-image configuration only), the experimental `*-python` modules, and vulnerabilities that live in a
dependency (Netty, Jackson, Reactor, ...). Report dependency issues upstream, unless Micronaut's use of the
dependency is what makes them exploitable.

## How to exercise it

- The image compiled every module and its tests and cached every dependency. The scan has no network, so Gradle
  is forced offline by `/root/.gradle/init.d/oss-scanner-offline.gradle`; passing `--offline` as well is fine.
- Run a module's tests with `./gradlew --offline :micronaut-http-server-netty:test` (Gradle project names carry the `micronaut-` prefix: `:micronaut-core:test`, `:micronaut-router:test`, ...), a single class with
  `./gradlew --offline :micronaut-http-server-netty:test --tests 'io.micronaut.http.server.netty.SomeSpec'`. Tests are
  Spock (Groovy) and JUnit 5; `http-server-tck` / `http-client-tck` hold the server and client compatibility kits.
- The quickest reproducer for an HTTP finding is a Spock or JUnit test that starts an `EmbeddedServer` with a
  small controller and sends raw bytes with a socket or a `HttpClient`; many such tests exist under
  `http-server-netty/src/test`.
- Tests that need Docker (Testcontainers) or a browser (Geb, only with `-Dgeb.env=...`) cannot run in the
  scanner and should be skipped, not reported.
- The scan machine is small (2 CPUs, 8 GB): run one module at a time; `--max-workers=2` helps.
- Tests start an embedded server on $HOSTNAME; the image sets `HOSTNAME=localhost` because the container's own
  hostname does not resolve without a network. If a test fails with "Temporary failure in name resolution",
  run it with `HOSTNAME=localhost` in the environment.

## How you rate severity

- **Critical**: remote code execution; a request that bypasses routing, filters or binding in a way that gives an
  unauthenticated client access to a route or data it should not reach (path normalisation or matching confusion,
  filter ordering/skipping, request smuggling across a trust boundary); deserialisation of untrusted data into
  arbitrary types.
- **High**: denial of service from a small or cheap request (decompression bombs, unbounded buffering, missing
  limits on multipart/headers/frames, regular-expression blow-up, resource leaks per request); path traversal or
  arbitrary file read in static resource serving; response splitting / header injection; SSRF or credential
  leakage through the HTTP client (for example forwarding authorization headers across hosts on redirect);
  bypass of TLS certificate validation.
- **Medium**: denial of service that needs sustained high volume; information disclosure (stack traces, bean or
  environment details) in default error handling; weaknesses that need a non-default but documented configuration.
- **Low / informational**: issues that need a malicious application developer, a malicious configuration, local
  access, or a non-public API; hardening suggestions.

Default configuration matters: an issue reachable with the defaults rates one level higher than the same issue
that needs the developer to opt in.

## Reports and patches

- Patches should target the default branch (the current `5.x.x` line), use Java 25, keep binary compatibility of
  public API (add, deprecate; do not change signatures), and follow the surrounding code style. Mark internal
  API `@Internal`.
- Please include a failing Spock or JUnit 5 test next to the existing tests of the module, and the exact request
  bytes or client code that reproduces the issue.

## Anything to leave alone

- Reflection and unsafe usage flagged by static rules in the build (`noReflection`, Error Prone): build policy,
  not vulnerabilities.
- Annotation processors and compile-time visitors handling malicious *source code*: compile time runs on trusted
  code.
- Findings that amount to "a dependency has a CVE": Dependabot and Renovate cover that.
- Netty-internal behaviour that Micronaut only configures; please report those to Netty.
