# home-assistant-garmin_connect threat model

## What it is
A Home Assistant custom integration (`custom_components/garmin_connect`) that logs in to Garmin Connect
via the `ha-garmin` library, stores tokens in the HA config entry, polls health/activity data into
sensors, and exposes services (e.g. uploading activities/workouts, setting body composition) plus a
calendar and diagnostics.

## Trust boundaries / untrusted input
- **Config flow / options flow input** (username, password, MFA code) entered by an HA user.
- **Service calls** — can be triggered by any HA user/automation, including via the HA REST/WebSocket API; parameters (file paths, IDs, payloads) are untrusted.
- **Data from Garmin servers** rendered into sensor states/attributes, calendar events and frontend (`www/`) assets.
- **Diagnostics downloads** shared publicly by users in bug reports.

## What matters most
- Credentials or tokens leaking into logs, entity attributes, diagnostics output or exceptions (diagnostics must redact).
- Service calls that read/write arbitrary files on the HA host (path traversal outside allowed dirs, ignoring `allowlist_external_dirs`).
- Stored XSS via Garmin-supplied strings reaching the HA frontend / bundled `www` cards.
- Non-admin users invoking services that should require admin.

## Out of scope
- Vulnerabilities in Home Assistant core itself or in Garmin's servers.
- Attacks requiring HA admin access (admins are fully trusted in HA's model).

## Severity guidance
- Critical: unauthenticated remote code execution or credential theft.
- High: authenticated non-admin user reads arbitrary files / obtains Garmin tokens; credentials in diagnostics.
- Medium: stored XSS in frontend from Garmin data; token leakage to local logs.
- Low: DoS from malformed responses, hardening.
