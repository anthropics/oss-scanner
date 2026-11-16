# Threat model: Pydantic Logfire (Python SDK)

## What this project does and where untrusted input enters
Logfire is an observability SDK built on OpenTelemetry. It runs inside the user's application, records spans,
logs and metrics, and exports them over OTLP to the Logfire backend. This repository holds the SDK
(`logfire-sdk/logfire/`), its CLI (`logfire ...`) and the no-op shim `logfire-api/`. The backend is closed
source and is not in this repository.

The application, its code, its configuration and its environment variables are trusted. Untrusted input is:
- Data the instrumented application handles and the SDK records: HTTP headers, URLs, bodies, SQL statements,
  LLM messages, exception messages, and attribute values of any type and shape.
- Incoming trace context and baggage headers (`traceparent`, `baggage`).
- Requests from browsers to the OTLP forwarding endpoint (`logfire_proxy`, `forward_export_request`).
- Local HTTP requests to the `logfire gateway` proxy and its OAuth callback.

## Components that matter most
1. **OTLP forwarding**: `logfire-sdk/logfire/_internal/forwarding.py`. It forwards browser telemetry to
   Logfire with the server's write token. Of interest: a path that reaches anything other than `/v1/traces`,
   `/v1/logs` or `/v1/metrics`, client headers that replace or leak the `Authorization` header, and body
   size or queue limits that can be bypassed.
2. **Scrubbing**: `_internal/scrubbing.py`. Of interest: a value that the default patterns should redact
   (passwords, tokens, cookies, auth headers) but that reaches an exporter through another attribute, event,
   exception field or integration.
3. **Credentials**: `_internal/auth.py`, `_internal/config.py`, `_internal/client.py`,
   `_internal/exporters/otlp.py`, `query_client.py`. Of interest: a write, read or user token sent to a host
   other than the configured one (redirects, the token-to-region mapping), stored with loose file
   permissions, or written to logs and exceptions.
4. **Serialization and formatting**: `_internal/json_encoder.py`, `json_schema.py`, `formatter.py`,
   `json_formatter.py`, `db_statement_summary.py`, `stack_info.py`. Of interest: a recorded value that takes
   super-linear CPU time or unbounded memory, or that raises into the application. The SDK must never break
   the application it observes.
5. **Trace context**: `propagate.py`, `_internal/baggage.py`. Of interest: incoming context that is extracted
   when `distributed_tracing=False`, and baggage that becomes attributes without limits.
6. **CLI gateway**: `_internal/cli/gateway.py`, `gateway_auth.py`. A local proxy that adds credentials to
   requests. Of interest: requests accepted without the local token (another local user, a web page, DNS
   rebinding), OAuth callback flaws (state, PKCE), and headers forwarded in either direction that should not be.
7. **Managed variables**: `variables/` (remote configuration, template rendering in `_handlebars.py`,
   composition).

Also in scope, but less important: `_internal/integrations/`, `_internal/auto_trace/` (it rewrites trusted
code), `db_api.py`, `experimental/` and `logfire-api/`.

## How to exercise it
- `tests/` is a pytest suite. Run `pytest -n logical --dist=loadgroup` from `/src`. HTTP interactions are
  replayed from cassettes in `tests/cassettes/` and `tests/otel_integrations/cassettes/`.
- `test_celery.py`, `test_mysql.py` and `test_redis.py` in `tests/otel_integrations/` start containers and
  need a Docker daemon, which the image does not have. Pass `--ignore` for each of them: the sockets they
  leak otherwise fail unrelated tests with a `ResourceWarning`.
- The `exporter: TestExporter` fixture captures spans in memory; `exported_spans_as_dict()` shows what would
  be sent. `tests/test_forwarding.py`, `tests/test_secret_scrubbing.py` and `tests/test_json_args.py` are
  good starting points for PoCs.

## How we rate severity
- **Critical**: code execution from recorded data or from a network request; the forwarding endpoint or the
  gateway made to send its credentials to a host the attacker chooses.
- **High**: a token leaked to another host, to logs or to a file other users can read; the gateway used
  without its local token; a scrubbing bypass for the default patterns under the default configuration; a
  small recorded value or request that exhausts CPU or memory, or crashes the application, under the default
  configuration.
- **Medium**: the same issues when they need a non-default but documented option; incoming trace context
  honoured when `distributed_tracing=False`.
- **Low**: cost that grows linearly with the recorded data, and issues that need a malicious Logfire backend.

## Anything to leave alone
- The Logfire backend, and vulnerabilities in OpenTelemetry packages or in the instrumented libraries
  themselves, unless the SDK uses them in an unsafe way.
- Scrubbing is pattern-based by design: a secret under a name, or in a shape, that no default pattern
  matches is not a finding.
- The application recording a secret on purpose, a hostile environment or configuration file, and
  `logfire run` executing the script it is given.
- `logfire.testing`, `docs/`, `examples/`, `plans/`, `release/`, `scripts/` and `pyodide_test/`.
