# Threat Model

## Project and trust boundaries

openHAB Core is the Java runtime and service layer of the openHAB home automation platform. Security-relevant input may arrive through network-facing services and APIs, persisted configuration and state, automation rules and scripts, installed extensions, or local files processed by core services. Treat data from remote clients, extensions, configuration files, and other user-controlled sources as untrusted unless the code enforces a clear boundary.

## Areas of interest

Prioritize vulnerabilities in authentication and authorization, REST and other network-facing interfaces, session handling, deserialization and parsing, path and file handling, persistence, and interactions between core services and extensions. Consider whether an issue can be reached by an unauthenticated or lower-privileged user and whether it can affect other users, the host, or connected devices.

Issues confined to openHAB add-ons or third-party dependencies should identify the affected component and be reported only when the vulnerable behavior is reachable through openHAB Core or materially affects its security boundary. Avoid reporting unsupported deployment assumptions as vulnerabilities.

## Build and tests

The image builds the repository using openHAB Core's Java 21 static-analysis CI command `./.github/scripts/maven-build install -B -T 1.25C -U -Dspotless.check.skip=true -Dmaven.test.skip=true -Dfeatures.verify.skip=true`, then runs the Linux sysfs discovery integration-test module. Other tests are skipped during the build. The test run caches its Maven dependencies while build networking is available, so it can also be rerun in the offline shell opened by `tools/check`. Focus analysis on the source code and tests in this checkout; the scan runs without network access after the image is built.

## Severity guidance

Prioritize remotely reachable authentication or authorization bypasses, arbitrary code execution, disclosure of sensitive data, and vulnerabilities that let an untrusted client control or disrupt the host or connected systems. Consider required privileges, user interaction, deployment defaults, and practical impact. Report denial of service and defense-in-depth weaknesses with severity proportionate to their reachability and impact.
