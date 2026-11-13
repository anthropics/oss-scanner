# Threat model

## What this project does and where untrusted input enters
Eneru is a Python daemon that watches UPS units through NUT (Network UPS Tools) and, on power events, shuts down VMs, containers, remote servers over SSH, and the local host. It usually runs as root (or in a container with a host-loopback delegate), so a bug can end in an unwanted host shutdown or code running as root.

Untrusted or semi-trusted input enters through:
- **NUT data**: `upsc`/`upscmd` output and variable values from a NUT server, which may be a remote or compromised device (for example a UPS's own network card). Values flow into logs, notifications, the stats DB, the dashboard, and shutdown decisions.
- **The HTTP API and browser dashboard** (`src/eneru/api.py`, `src/eneru/web/`): read-only status, plus authenticated write routes (config editor, self-test, NUT commands). Covers authentication (bcrypt), sessions, CSRF, and XSS in rendered telemetry.
- **MQTT** (`src/eneru/mqtt.py`): broker messages.
- **Configuration YAML**: written by an admin, but the config editor lets authenticated users change it. Values reach shell commands, SSH invocations (`remote_health.py`, `shutdown/remote.py`), and file paths.
- **Remote hosts over SSH**: output from shutdown and probe commands.

## Components that matter most / least
- Most: shutdown orchestration (`src/eneru/shutdown/`, `monitor.py`), command and SSH construction, the API auth and write routes, config validation (`config.py`).
- Less: notification formatting (Apprise), docs, `tools/`, `tests/e2e/` (CI harness only, out of scope).

## How to exercise it
- `python -m eneru validate --config examples/config-reference.yaml` covers every feature flag.
- `python -m eneru run --dry-run --config examples/config-reference.yaml` runs the daemon without real shutdowns.
- `pytest -m unit` runs the unit suite. NUT, SSH, and Docker are mocked.

## How you rate severity
- Critical: unauthenticated command execution, unauthenticated shutdown trigger, or auth bypass on the write API.
- High: command or shell injection from NUT data or authenticated config edits that escapes the intended command; path traversal; leaking secrets (passwords, SSH keys, API tokens) to unauthenticated users; a crash or logic bug that stops a needed shutdown during a real power event.
- Medium: stored XSS in the dashboard, CSRF on write routes, an unwanted shutdown triggered by malformed but authenticated input.
- Low: DoS of the dashboard or API that leaves monitoring and shutdown working.

## Anything to leave alone
- Commands an admin deliberately configures (custom shutdown or probe commands) run by design; only report escaping or injection beyond what the admin wrote.
- Running as root is intended for local-host orchestration.
