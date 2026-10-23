# Threat model: crowdsec-unifi-bouncer

Installs and persists the official CrowdSec firewall bouncer on UniFi Dream Machines
(UDM, UDM SE, UDR), with automatic recovery from firmware updates. Shell installer and
boot-restore scripts run as root on network gateways; a Go sidecar (sidecar/) provides a
small proxy and metrics endpoint.

## Untrusted input
- CrowdSec LAPI decisions, which drive ipset/iptables changes.
- YAML configuration files (bouncer and sidecar).
- The UniFi OS environment itself (firmware updates wipe and re-trigger install paths).

## In scope
- Command injection in shell scripts wherever config or environment values reach
  iptables, ipset, or systemctl.
- Privilege escalation: scripts run as root on a gateway.
- Go sidecar: authentication, request parsing, and what it exposes on the network.
- Boot-restore and persistence logic that could be abused to survive reboots maliciously.

## Out of scope
- The upstream CrowdSec bouncer binary and UniFi OS itself.

## Severity guidance
- Remote command execution as root: critical.
- Firewall bypass or injection of arbitrary firewall rules: high.
- Unauthenticated access to sidecar functionality: high.
- Local denial of service: medium.

## Report format
Minimal reproducer plus a small candidate patch; one issue per report, deduplicated by
root cause.
