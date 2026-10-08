# Threat model

## What this project does and where untrusted input enters
mcp-unifi is a Python MCP server that drives a self-hosted UniFi OS gateway (Network, plus opt-in Protect and Access) through the gateway's local API key. Whoever can call its tools holds admin-equivalent control of the network: firewall rules, port forwards, VLANs, WLANs, client blocking, door access.

Untrusted input enters in three places:
- **MCP tool arguments** from the client, which is usually an LLM. Treat every argument as attacker-influenced (prompt injection reaching a tool call is the realistic path).
- **The Streamable HTTP transport** (`server.py`, `scoping.py`), where a bearer token from `MCP_UNIFI_AUTH_TOKENS` gates every request and the `client_id:token:module1|module2` form restricts a client to modules. Stdio is unauthenticated by design; the parent process owns that boundary.
- **Responses from the UniFi controller** (`clients/`), which can carry attacker-controlled strings such as client hostnames, SSIDs and device names.

## Components that matter most / least
Most important:
- HTTP bearer auth and per-module scoping (`server.py`, `scoping.py`, `config.py`).
- Secret redaction across logs, the audit log and every tool response (`redaction.py`, `modules/network/_common.py`, `audit.py`). The guarantee is that no API key, PSK, VPN key, RADIUS secret or Access credential ever leaves the server.
- The dry-run, preview-then-confirm token, and composite rollback paths (`modules/network/confirm.py`, `_pending.py`, `composites.py`): a destructive change must not apply without a matching confirmation.
- TLS verification and certificate pinning to the controller (`tls.py`, `cli/pin_cert.py`).
- Path and ID handling when building controller URLs (`clients/ids.py`, `clients/unifi.py`).

Less important: `cli/replay.py` (operator tool run on trusted logs), `telemetry.py`, `healthcheck.py`. Out of scope: `evals/`, `docs/`, `charts/`, `scripts/`.

## How to exercise it
`STUB_MODE=true` runs every tool against in-memory fake controllers, no network needed. `pytest` runs the suite; `tests/test_output_redaction.py` sweeps every tool for secret leaks. Start the HTTP server with `STUB_MODE=true MCP_UNIFI_AUTH_TOKENS=<token> python -m mcp_unifi.server` (port 3714).

## How you rate severity
- Critical: bypassing HTTP bearer auth or module scoping; a secret (controller API key, WLAN PSK, VPN or RADIUS key, Access credential) returned in a tool response, log or audit record.
- High: a destructive write that applies without its confirmation or ignores `dry_run`; tool arguments that redirect requests to a host other than the configured controller (SSRF) or traverse to unintended API paths; TLS verification or pinning bypass.
- Medium: rollback that leaves the controller in a partially applied state; audit-log injection or omission.
- Low: denial of service against the server process itself.

## Anything to leave alone
Stdio transport having no auth is intentional. `MCP_UNIFI_AUTH_REQUIRED=false` disabling auth is an explicit operator choice. Missing per-tool RBAC and rate limiting are documented non-goals in SECURITY.md.
