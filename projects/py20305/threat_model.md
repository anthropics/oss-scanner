# Threat model: py20305

## What this project does and where untrusted input enters

py20305 is a Python client for IEEE 2030.5 (Smart Energy Profile 2.0) and the CSIP and CSIP-AUS profiles. It runs on a gateway or inside a distributed energy resource (solar inverter, battery, EV charger), connects to a utility's IEEE 2030.5 server over mutual TLS, receives control events, and applies them to a device. A device-side connector (SunSpec Modbus) carries those controls to equipment.

Untrusted input enters at these points:

1. Responses from the IEEE 2030.5 server (`client/http.py`, `xml/serialization.py`, `models/`). XML from the server is untrusted: the server may be compromised, spoofed, or reached through a misconfigured TLS setup. The parser is `lxml` with `resolve_entities=False` and `no_network=True`, bound through `xsdata-pydantic`.
2. The notification listener (`subscription/notification_server.py`). It accepts inbound `POST /notify` from the server and can require a client certificate.
3. DNS-SD discovery (`client/dnssd/`). Multicast DNS responses from anyone on the local network are parsed in `wire.py` and turned into a server URL in `discover.py`.
4. TLS handling (`client/tls.py`, `client/connector.py`): certificate verification, hostname checking, cipher selection, and handling of private keys.
5. The optional management API (`api/`). It is unauthenticated and binds to loopback by default.
6. The device connector (`connectors/`). Modbus register values read from a device are lower trust than local configuration.
7. Configuration files (`config.py`). Written by the operator; lowest priority.

## Components that matter most / least

Most important, in order:

1. Event processing (`events/`): the state machine, supersession, randomization, timers, and dispatch. A defect that applies a control the server did not send, applies it to the wrong device or at the wrong time, or ignores a cancellation directly affects grid equipment.
2. TLS and identity (`client/tls.py`, `client/connector.py`, `security/identity.py`): any path where certificate or hostname verification is skipped when it was configured, or where private key material is logged, written, or exposed.
3. XML parsing of server responses: entity expansion, external entity resolution, parser resource exhaustion, and schema confusion that yields a model with values the server did not send.
4. The notification listener and DNS-SD parsing, which are reachable from the network without the client initiating the exchange.
5. The management API: injection, path traversal (for example in certificate swap), and cross-origin or DNS-rebinding access from a browser on the same host to the loopback API.
6. Telemetry and forwarders (`telemetry/`, `forwarders/`): lower priority, but leaking certificate material or credentials into published telemetry is in scope.

Out of scope: `models/` and `schemas/` are generated from the IEEE 2030.5 XSDs (report a parser behavior, not a generated class); `examples/`, `scripts/`, `tools/`, `docs/`, `tests/`.

## How to exercise it

- Run the suite: `pytest -q`. `tests/e2e` needs a live server in Docker and does not run offline.
- `tests/scenario/support.py` is a scriptable IEEE 2030.5 server over real mutual TLS. Its responses can be scripted, delayed, or served malformed, which makes it the best starting point for a reproducer. `tests/scenario/` also has a Modbus device and an MQTT broker.
- `scripts/make_test_config.py <dir>` writes a client configuration and a test certificate. `py20305 --config <dir>/client.yaml --check` validates a configuration.
- The management API can be tested in-process with `fastapi.testclient.TestClient` against an app from `py20305.api.app.create_app`.

## How you rate severity

- Critical: a network attacker without the server's private key causes a control to be applied to a device (TLS or hostname verification bypass when configured); remote code execution; disclosure of the client's private key.
- High: a control applied that the server did not send, applied to the wrong device, or a cancellation or supersession ignored; a single crafted response, notification, or mDNS packet that crashes or hangs the client, or causes unbounded memory growth; XML entity resolution or network access during parsing; reaching the loopback management API from a web page.
- Medium: denial of service that requires the authenticated server; DNS-SD answers that steer discovery to an attacker URL when TLS verification still holds; credential or certificate material in logs or telemetry.
- Low: incorrect handling of malformed but harmless input; issues that need operator-controlled configuration files.

## Known test failures in the scan image

Five tests fail in the offline scan image. None is a security finding:

- `tests/test_docker.py::TestNothingSecretIsBuildable` (3 cases) reads `/src/.dockerignore`, which the scanner removes before the build.
- `tests/test_subscription_integration.py::TestLifecycle::test_rediscovery_loop_is_bounded_under_persistent_pending` and `TestRediscoveryReconciliation::test_rediscovery_mixed_reconciliation` resolve `example.com` and need DNS.

## Anything to leave alone

- `check_hostname=False` and the notification listener's `off` client-certificate mode. Both are documented, explicit weakenings. A report that either reduces security when deliberately enabled is not a finding. A report that either is applied when not configured is a finding.
- The management API is unauthenticated by design and binds to loopback by default. Exposure after an operator binds it to a routable address is not a finding.
- Additional TLS cipher suites added through `additional_ciphers`. This is an operator opt-in for servers with RSA certificates.

## Report format

Include a minimal reproducer as a pytest test (using `tests/scenario/support.py` where possible), and a proposed patch with a regression test.
