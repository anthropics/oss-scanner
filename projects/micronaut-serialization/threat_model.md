# Threat model: micronaut-serialization

## What this project does and where untrusted input enters

Micronaut Serialization (Serde) is a reflection-free serialization and deserialization library for the
Micronaut Framework. Type metadata is produced at compile time by an annotation processor (`@Serdeable`,
`@Introspected`) and a pluggable set of codecs reads and writes data. It is the JSON binding layer of many
Micronaut applications, so request and response bodies pass through it. Modules:

- `serde-api`, `serde-support`, `serde-processor`: the API, the shared runtime (deserializers, serializers,
  type resolution, polymorphism, `@JsonTypeInfo` handling, introspection lookup) and the compile-time processor.
- `serde-jackson`: JSON via Jackson's streaming parser; `serde-jsonp` / `serde-jsonp-impl`, `serde-jsonb`:
  JSON-P and JSON-B; `serde-jackson-cbor`, `serde-yaml`, `serde-bson`, `serde-protobuf`, `serde-properties`,
  `serde-toon`, `serde-stax-xml`, `serde-woodstox-xml`, `serde-oracle-jdbc-json`: other formats.

Untrusted input reaches the library at runtime as **serialized data of attacker-controlled shape**: HTTP
request bodies, messages from queues and caches, files, and documents returned by remote services. The
interesting questions are what an attacker can make the deserializer do:

- **Type selection**: polymorphic deserialization (`@JsonTypeInfo`, `@Serdeable.Deserializable` subtypes,
  type ids, `@JsonSubTypes`, default typing) must only instantiate types the developer allowed. Instantiating
  an arbitrary class named in the payload is a critical flaw.
- **Resource exhaustion**: deeply nested documents, very large strings, numbers or arrays, duplicate keys,
  billion-laughs style XML/YAML aliases, and unbounded buffering.
- **Property binding**: `@JsonIgnore`, `@JsonProperty(access=...)`, `@JsonIncludeProperties`, creators and
  `@Serdeable.Deserializable(...)` rules being ignored so that read-only, ignored or internal fields can be set
  (mass assignment), or secrets are written out on serialization.
- **XML and YAML specifics**: external entity (XXE) and DTD processing, YAML tags and anchors/aliases.
- **Numeric and string handling**: overflow and precision loss converting numbers, malformed Unicode,
  differences from Jackson that let one parser see a different document than another (parser differentials).

Trusted input: application source code, annotations on beans, `application.yml` and the environment. Bugs
that need a malicious developer or configuration are out of scope.

## Components that matter most / least

Most important: `serde-support` (deserializers, polymorphic and type-id resolution, property binding,
limits), `serde-jackson` (JSON parser integration), `serde-stax-xml` / `serde-woodstox-xml` (XML parsing),
`serde-yaml`, `serde-bson`, `serde-jackson-cbor`, `serde-protobuf`, `serde-api`.

Still in scope but less exposed: `serde-jsonp*`, `serde-jsonb`, `serde-properties`, `serde-toon`,
`serde-oracle-jdbc-json`, `serde-processor` (compile-time).

Out of scope: `test-suite-*`, `*-tck*` modules and `tests`, `doc-examples`, `benchmarks`, `buildSrc` and
build logic, documentation (`src/main/docs`), and vulnerabilities in dependencies such as Jackson, Woodstox
or SnakeYAML. Report those upstream, unless Micronaut Serialization's use of the dependency is what makes
them exploitable.

## How to exercise it

- The image compiled every module and its tests and cached every dependency. The scan has no network, so
  Gradle is forced offline by `/root/.gradle/init.d/oss-scanner-offline.gradle`; passing `--offline` as well
  is fine.
- Run a module's tests with `./gradlew --offline :micronaut-serde-jackson:test` (Gradle project names carry
  the `micronaut-` prefix: `:micronaut-serde-support:test`, `:micronaut-serde-api:test`, ...), a single class
  with `--tests 'io.micronaut.serde.SomeSpec'`. Tests are Spock (Groovy) and JUnit 5. The `serde-tck` and
  `serde-jackson-tck` modules hold the compatibility kits that the format modules run.
- The quickest reproducer is a JUnit or Spock test that builds an `ApplicationContext`, obtains an
  `ObjectMapper` and calls `readValue` on the hostile document for a `@Serdeable` type.
- Tests that need Docker cannot run in the scanner and should be skipped, not reported.
- The scan machine is small (2 CPUs, 8 GB): run one module at a time; `--max-workers=2` helps.

## How you rate severity

- **Critical**: remote code execution or arbitrary class instantiation through deserialization (type ids or
  polymorphic handling that go beyond the types the developer declared); XXE with file disclosure or SSRF in
  the XML modules with default settings.
- **High**: mass assignment (ignored, read-only or non-declared properties being bound from input);
  serialization of properties that were excluded (for example `@JsonIgnore`d secrets); parser differentials
  that bypass validation done on another parser's view of the same document; XML/YAML entity or alias
  expansion that exhausts memory with a small payload.
- **Medium**: denial of service from a small input (stack overflow from deep nesting, quadratic behaviour,
  unbounded allocation from a declared length) with default settings; weaknesses needing a non-default but
  documented configuration.
- **Low / informational**: issues that need a malicious developer or configuration, local access, or a
  non-public API; hardening suggestions.

Default configuration matters: an issue reachable with the defaults rates one level higher than the same
issue that needs the developer to opt in.

## Reports and patches

- Patches should target the default branch (the current development line), use Java 25, keep binary
  compatibility of public API (add, deprecate; do not change signatures), and follow the surrounding code
  style. Mark internal API `@Internal`.
- Please include a failing Spock or JUnit 5 test next to the existing tests of the module, with the exact
  document that reproduces the issue and the bean type it is deserialized into.

## Anything to leave alone

- Credentials and keys in test fixtures are intentional non-secret fixtures.
- Findings that amount to "a dependency has a CVE": Dependabot and Renovate cover that.
- Behaviour of Jackson, Woodstox or other parsers themselves, and of Micronaut core: report those to the
  respective projects (micronaut-core is enrolled separately).
