# Threat model: crowdsec-blocklist-import

Python daemon (also shipped as a Docker image and Homebrew formula) that imports ~32 public
IP threat feeds (~120k IPs) into CrowdSec via its Local API (LAPI), keeping firewall
blocklists current. Runs unattended on home servers and gateways.

## Untrusted input
- Remote threat-feed content fetched over HTTP(S): feed parsing, CSV/JSON handling,
  decompression, and memory use are the primary attack surface (a malicious or compromised
  feed server controls these bytes).
- Environment variables and .env configuration.
- CrowdSec LAPI responses.

## In scope
- Parsing of untrusted feed data (injection, crashes, memory exhaustion).
- Credential handling: the LAPI key and any secrets must not leak into logs, metrics,
  or error output.
- Log injection via attacker-controlled feed content.
- Denial of service via crafted or oversized feeds.
- Any path handling for cached feeds or state files.

## Out of scope
- CrowdSec itself and the upstream feed providers' infrastructure.

## Severity guidance
- Remote code execution or auth bypass against LAPI: critical.
- Secret/credential exposure: high.
- Crash or resource exhaustion from a crafted feed: medium to high.
- Incorrect blocklist entries without security impact: low.

## Report format
Minimal reproducer plus a small candidate patch; one issue per report, deduplicated by
root cause.
