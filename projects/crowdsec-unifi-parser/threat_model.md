# Threat model: crowdsec-unifi-parser

CrowdSec parsers, scenarios, and iptables LOG rules that turn UniFi Dream Machine
firewall logs into clean, parseable CrowdSec events, plus a Python deployment script
(deploy-log-rules.py) that configures logging on the UDM/UDR.

## Untrusted input
- Kernel firewall log lines, which reflect network traffic controlled by remote
  attackers (packet contents can influence log fields).
- YAML parser/scenario configuration.
- Command-line and environment input to the deploy script.

## In scope
- Parser and grok-pattern correctness, including ReDoS or pathological backtracking on
  adversarial log lines.
- deploy-log-rules.py: it writes configuration on a gateway device; injection or unsafe
  file handling matters.
- Scenario logic errors that would let hostile traffic evade detection or cause false
  bans of legitimate users.

## Out of scope
- The CrowdSec engine and UniFi OS themselves.

## Severity guidance
- Evasion that silently disables detection of attacks: high.
- Regex denial of service against the log pipeline: medium to high.
- Deploy-script injection or unsafe writes: high.
- False positives/negatives without security impact: low.

## Report format
Minimal reproducer plus a small candidate patch; one issue per report, deduplicated by
root cause.
