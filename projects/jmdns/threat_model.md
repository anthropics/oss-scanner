# Threat Model

## Project and trust boundaries

JmDNS is a Java implementation of multicast DNS (mDNS) for service discovery and service registration on local networks. It receives DNS messages from the local network, parses service and host records, and exposes discovered information to applications. Treat network packets and service data as untrusted, including data from devices on the same LAN.

## Areas of interest

Prioritize malformed or oversized DNS messages, record and name parsing, compression-pointer handling, resource exhaustion, unsafe assumptions about packet contents, and concurrency or lifecycle issues in discovery and registration. Assess whether malicious mDNS traffic can crash or hang applications, corrupt discovery state, expose data across interfaces, or cause unsafe service information to be consumed. Consider the local-network scope of mDNS when assessing reachability. Issues in consuming applications or unrelated third-party dependencies are out of scope unless JmDNS creates or materially amplifies the security impact.

## Build and tests

The Docker image uses Java 17 and runs `mvn -B test -Dtest='*,!JmDNSTest#testListMyServiceIPV6'`, matching the repository's Maven GitHub Actions build except for one test that needs unavailable IPv6 multicast support in this container. This ran 92 tests successfully. The scanner's final shell has networking disabled, so mDNS integration tests also cannot run there; the offline-compatible subset is `mvn -o -B test -Dtest='*,!JmDNSTest,!JmmDNSTest'`, which ran 67 tests successfully. The scan itself runs without network access after the image is built.

## Severity guidance

Prioritize remotely reachable parsing flaws that can cause code execution, memory corruption, sensitive data exposure, or reliable denial of service in applications using JmDNS. Account for the requirement that mDNS traffic generally originates on the same local network, as well as the application's use of the library and the attacker's ability to send multicast packets. Report lesser-impact robustness and defense-in-depth issues with severity proportionate to their practical reachability and impact.
