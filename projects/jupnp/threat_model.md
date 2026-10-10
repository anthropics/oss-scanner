# jUPnP threat model

## Purpose and trust boundaries

jUPnP is a Java library for implementing and consuming UPnP and DLNA services. Its core functionality parses device and service descriptions, handles SOAP actions and GENA event subscriptions, and discovers devices over SSDP. Applications use it to communicate with devices on a local network; the library itself is not an Internet-facing service.

Treat network traffic from devices and control points as untrusted, including SSDP datagrams, HTTP device and service descriptions, SOAP requests and responses, and event-subscription traffic. Prioritize parsing and validation of those inputs, XML handling, request and response processing, device/service graph construction, and lifecycle or concurrency behavior reachable through normal library APIs. Consider the privileges and network access of the application embedding jUPnP when assessing impact; do not assume a local-network-only issue is remotely reachable from the Internet.

## Scope and priorities

- Focus on the Java library modules under `bundles/`, especially `org.jupnp` and `org.jupnp.support`, and on the public APIs used by applications to create control points, registries, devices and services.
- Assess malformed or adversarial protocol inputs for injection, unsafe XML processing, resource exhaustion, hangs, unexpected filesystem access, and incorrect authorization or trust decisions. Distinguish vulnerabilities from protocol interoperability problems and documented failure behavior.
- Include the command-line tool and OSGi integrations where their behavior creates a security impact beyond the embedding application's expected privileges.
- Example applications and test fixtures are useful for reproducers; an insecure example alone is not a vulnerability in the library.
- Attribute defects in Java, the JVM, Maven plugins, Jetty, or other dependencies to the relevant upstream project, while reporting unsafe or incorrect use by jUPnP when applicable.

## Build and offline test environment

The Docker image uses Eclipse Temurin JDK 17 and runs the upstream CI build command, `./mvnw -B -ntp -U clean verify`, which builds and tests the Maven reactor, including its unit and integration-test modules. Dependencies are downloaded during image creation; the subsequent scanner analysis runs offline. Preserve Maven's local dependency cache and build output in the image so builds and tests do not need Internet access during analysis.

To run the offline test suite in the scanner container, use:

```sh
./mvnw -o -B -ntp verify '-Dtest=*,!BinaryLightTest#testClient,!BinaryLightTest#testServer,!IncompatibilityTest#validateCallbackURILength,!RetrieveRemoteDescriptorsNullConfigTest#testDescribeWithNullConfiguration' -Dsurefire.failIfNoSpecifiedTests=false
```

The four excluded test methods require `ModelUtil.getFirstNetworkInterfaceHardwareAddress()` to find an active non-loopback interface with a hardware address. The scanner's network-isolated container has no such interface, so those methods error before exercising their intended behavior. The full test suite runs during the online image build; only those environment-dependent methods are excluded from the offline rerun. This limitation is specific to the scanner container and is not a project vulnerability.

The build runs in a Linux container and does not reproduce the upstream CI matrix across Java 11, 17, 21, 25 and 26, macOS, and Windows. UPnP discovery and device interaction also depend on local network behavior; any tests unavailable in the scanner container should be explicitly documented with the exact test and reason rather than treated as project vulnerabilities.

## Assessing findings

For each finding, identify the protocol or API entry point, attacker-controlled input, required network position and configuration, and a realistic impact on an application using jUPnP. Provide a minimal reproducer and regression test when possible. Treat crashes, hangs and resource exhaustion separately from code execution; do not infer remote exploitability solely from a parser or network-related code path. Include the affected version, build/test command and any environmental limitations, and record failed reproduction attempts or uncertainty.
