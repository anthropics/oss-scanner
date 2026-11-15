# Threat model

## What this project does and where untrusted input enters

Netmiko is a Python library for connecting to network devices and interacting with their command-line
interfaces over SSH, Telnet, and serial connections. Applications provide connection details and
commands; devices return prompts, command output, and other network data.

Netmiko assumes callers connect to devices they are authorized to manage and that those devices are
generally trusted. Device responses may be malformed or unexpected. A compromised device is outside
the primary threat model. Report issues involving device responses only when they cause a demonstrable
security issue on the application using Netmiko or its host, not merely unexpected output.

Netmiko is a library for trusted automation code. Assume the caller supplies authorized targets,
credentials, and commands. It is the responsibility of higher level applications to validate inputs
or do other input checking (if they are making Netmiko available to untrusted or less trusted users).

## Components that matter most

In scope: connection setup and authentication; SSH host-key handling; channel reads and writes;
credential handling and session-log redaction; command/output processing; and all platform-specific
drivers.

Netmiko intentionally sends caller-provided commands to devices and returns device output. That
behavior alone is not a vulnerability. Findings should identify a concrete security impact beyond the
caller’s intended use of the library.

## How to exercise it

Use the existing unit tests and fixtures where applicable; coverage varies across transports and
platform drivers. Do not require real devices or credentials. In the scanner image, run:

```bash
uv run --frozen pytest -q tests/unit \
  -k 'not test_use_ssh_file and not test_use_ssh_file_proxyjump and not test_connecthandler_auth_failure and not ttp and not genie'
```

This excludes two SSH proxy tests that require the `ssh` executable, an authentication test that
requires a local SSH server, and optional TTP and Genie/PyATS parser tests. Other integration tests
may require configured network devices and credentials and are not expected to run in the scanner.

## How you rate severity

Assess vulnerabilities in Netmiko itself, not unsafe use by the application calling it. Callers are
responsible for choosing authorized targets, credentials, and commands, and for validating inputs when
exposing Netmiko through another application. Sending a caller-provided command to the configured
device is intended behavior, not a vulnerability by itself.

For each finding, explain the attacker’s capabilities, the required connection type and configuration,
and a process for reproducing the issue.

High severity requires a credible, demonstrated impact on the network device or on the system running
Netmiko. Do not assign high severity to speculative scenarios or consequences that depend solely on
callers providing bad or malicious input.

A compromised device is outside the primary threat model. If a finding depends on one, state that
prerequisite and demonstrate an impact beyond Netmiko returning unexpected output.

## Anything to keep in mind

SSH host-key checking is configurable and is not enabled by default for compatibility; Telnet is an
available, unencrypted transport still used in the network world.

When reporting concerns about these behaviors, state the relevant configuration and concrete impact.
Session logs may contain sensitive network device data, including configurations, so consider whether
a finding is an implementation flaw or a consequence of the caller's logging configuration.

