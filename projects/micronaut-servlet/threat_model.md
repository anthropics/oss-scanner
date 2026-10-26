# Threat model: micronaut-servlet

## What this project does and where untrusted input enters

Micronaut Servlet lets Micronaut HTTP applications run on servlet containers and other embedded servers
instead of Netty. It adapts the container's request and response objects to Micronaut's HTTP API and routing.
Modules:

- `servlet-core`, `servlet-api`, `servlet-engine`, `servlet-processor`: the shared adapter layer (request and
  response wrappers, body reading and writing, multipart, cookies, static resources, async handling).
- `servlet-websocket`: WebSocket support on top of the container.
- `http-server-jetty`, `http-server-tomcat`, `http-server-undertow`: embedded servlet containers.
- `http-server-jdk`: server based on the JDK's built-in `com.sun.net.httpserver`.
- `http-poja-common`, `http-poja-apache`, `http-poja-test`: plain-old-Java-application runtimes that parse HTTP
  from a stream (for example for AWS Lambda-style or inetd-style use).

Untrusted input reaches the library at runtime through **HTTP requests** received by the container: request
line and URI, headers, cookies, query and path parameters, bodies (JSON, form, multipart, streaming) and
WebSocket frames. The adapter layer decides how the container's view of a request becomes Micronaut's view,
so discrepancies are the interesting bugs: path normalisation and matching differences that let a request
reach (or miss) a route or filter, header and cookie parsing, multipart handling, request size limits,
`Content-Length` / chunked handling, and the HTTP parsing in the `http-poja-*` runtimes, which are
implemented in this repository rather than by a container.

Trusted input: application source code, annotations and configuration (`application.yml`, container
settings) and the environment. Bugs that need a malicious developer or configuration are out of scope.

## Components that matter most / least

Most important: `servlet-core` (request/response adaptation, body and multipart handling, path handling,
static resources), `http-poja-common` and `http-poja-apache` (hand-written HTTP parsing), `http-server-jdk`,
`servlet-websocket`.

Still in scope but less exposed: `http-server-jetty`, `http-server-tomcat`, `http-server-undertow` (mostly
container configuration), `servlet-engine`, `servlet-processor`.

Out of scope: `test-suite-*`, `test-sample-poja`, `benchmarks`, `buildSrc` and build logic, documentation
(`src/main/docs`), and vulnerabilities inside Jetty, Tomcat, Undertow or the JDK server themselves. Report
those upstream, unless Micronaut Servlet's use of the container is what makes them exploitable.

## How to exercise it

- The image compiled every module and its tests and cached every dependency. The scan has no network, so
  Gradle is forced offline by `/root/.gradle/init.d/oss-scanner-offline.gradle`; passing `--offline` as well
  is fine.
- Run a module's tests with `./gradlew --offline :micronaut-servlet-core:test` (Gradle project names carry
  the `micronaut-` prefix: `:micronaut-http-server-jetty:test`, `:micronaut-http-poja-common:test`, ...), a
  single class with `--tests 'io.micronaut.servlet.SomeSpec'`. Tests are Spock (Groovy) and JUnit 5. The
  `test-suite-http-server-tck-*` projects run Micronaut's HTTP server compatibility kit against each
  container and are the most direct way to reproduce a request-handling issue; otherwise start an
  `EmbeddedServer` with a small controller and send raw bytes with a socket or an `HttpClient`.
- Tests that need Docker or a browser cannot run in the scanner and should be skipped, not reported.
- The scan machine is small (2 CPUs, 8 GB): run one module at a time; `--max-workers=2` helps.
- Tests start an embedded server on $HOSTNAME; the image sets `HOSTNAME=localhost` because the container's
  own hostname does not resolve without a network. If a test fails with "Temporary failure in name
  resolution", run it with `HOSTNAME=localhost` in the environment.

## How you rate severity

- **Critical**: request smuggling or desynchronisation in the `http-poja-*` parsers; a path or URI handling
  discrepancy that lets an unauthenticated request reach a route or static resource that a filter or security
  rule expected to protect; path traversal out of the static-resource root; remote code execution.
- **High**: reading files outside the intended location; header or cookie injection (response splitting);
  multipart handling that writes to attacker-chosen paths or bypasses configured size limits; WebSocket
  origin or frame handling flaws that expose data across sessions.
- **Medium**: denial of service from a small request (unbounded buffering, missing body or header limits,
  resource leaks on aborted requests); information disclosure in error responses; weaknesses needing a
  non-default but documented configuration.
- **Low / informational**: issues that need a malicious developer or configuration, local access, or a
  non-public API; hardening suggestions.

Default configuration matters: an issue reachable with the defaults rates one level higher than the same
issue that needs the developer to opt in.

## Reports and patches

- Patches should target the default branch (the current development line), use Java 25, keep binary
  compatibility of public API (add, deprecate; do not change signatures), and follow the surrounding code
  style. Mark internal API `@Internal`.
- Please include a failing Spock or JUnit 5 test next to the existing tests of the module, with the exact
  request bytes that reproduce the issue and the container(s) affected.

## Anything to leave alone

- Credentials in test fixtures are intentional non-secret fixtures.
- Findings that amount to "a dependency has a CVE": Dependabot and Renovate cover that.
- Behaviour of the servlet container itself and of Micronaut core's HTTP layer: report those to the
  respective projects (micronaut-core is enrolled separately).
