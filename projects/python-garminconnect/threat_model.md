# python-garminconnect threat model

## What it is
A Python client library for the (unofficial) Garmin Connect web API. It logs in with a user's Garmin
credentials (including MFA), stores OAuth/session tokens on disk (default `~/.garminconnect`), and
exposes methods that fetch and upload health, activity, workout and device data.

## Trust boundaries / untrusted input
- **HTTP responses from Garmin servers** (JSON, FIT/GPX/TCX files, redirects, SSO HTML pages) — treat as untrusted.
- **Files passed in by the caller** for upload (FIT/GPX/TCX, workout definitions).
- **Token files on disk** — may be read from a shared or synced home folder.
- Caller-supplied arguments (dates, IDs, paths) that end up in URLs or file paths.

## What matters most
- Leakage of credentials, MFA codes, OAuth tokens or cookies (logs, exceptions, debug output, VCR cassettes, world-readable token files).
- Token files written with insecure permissions or to attacker-controlled paths.
- Path traversal when saving downloaded activities / files.
- URL/parameter injection that sends requests (with auth headers) to an unintended host.
- TLS verification being disabled or bypassed.

## Out of scope
- Garmin's own server-side vulnerabilities.
- Rate limiting / account lockout by Garmin.
- `demo.py` / `example.py` UX issues not involving credential handling.

## Severity guidance
- Critical: remote attacker obtains credentials or tokens without local access.
- High: token/credential exposure via logs, files or misdirected requests; path traversal writing outside the target dir.
- Medium: insecure file permissions on token storage; information leak of non-credential personal data.
- Low: DoS from malformed server responses, hardening issues.
