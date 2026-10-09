# Threat model

## What this project does and where untrusted input enters
- `iliaal/smtp-validate-email` is a single-class pure-PHP library (`src/SMTPValidateEmail.php`) that checks whether mailboxes exist. For each domain in the supplied addresses it looks up MX records (`getmxrr()`), connects to each MX host on `connect_port` (default 25) and then the bare domain as a last resort, and runs `EHLO`/`HELO`, optional `STARTTLS`, `MAIL FROM`, an optional catch-all probe, `RCPT TO` per user, `RSET`, and `QUIT`. It never sends `DATA`.
- Untrusted input, attacker-controlled in typical deployments (sign-up forms, list cleaning):
  1. Email addresses passed to the constructor, `set_emails()`, or `validate()`. They are filtered with `FILTER_VALIDATE_EMAIL`, then split on the last `@` by `parse_email()`, and the local part and domain are placed into `RCPT TO:<...>`.
  2. DNS answers for those domains: whoever owns the domain picks the MX targets, so they can point at any IP, including loopback, RFC 1918, or link-local addresses.
  3. Everything the remote SMTP server sends: greeting, multi-line EHLO capabilities, reply codes and text, TLS handshake, timing, and connection close. Treat the server as malicious.
- Semi-trusted: the sender passed to `set_sender()` (validated against CR/LF/NUL, `<`, `>`, `\`, and whitespace, then used in `EHLO <domain>` and `MAIL FROM:<...>`). Applications usually hard-code it.
- Trusted configuration: public properties (`connect_port`, `ssl_verify_peer`, `catchall_test`, `catchall_is_valid`, `no_comm_is_valid`, `no_conn_is_valid`, `greylisted_considered_valid`, `noop`, `debug`) and the timeouts.
- Outputs: the `validate()`/`get_results()` array, which includes `<address>_error_msg` strings taken from server replies, and `get_log()`, which holds raw protocol text. Escaping these for HTML, SQL, or logs is the caller's job. `debug()` applies `htmlspecialchars()` only when echoing outside the CLI.

## Components that matter most / least
- Most:
  - Command construction and the CRLF guard: `send()` rejects `\r`, `\n`, and `\0`; `set_sender()`; `set_emails()`/`parse_email()`; `rcpt()`; `mail()`; `ehlo()`.
  - Connection target selection: `validate()` MX ordering plus the bare-domain fallback, and `connect()` building `"$host:$connect_port"` for `stream_socket_client()`. There is no private-address or loopback filter today. Address-literal domains (`user@[1.2.3.4]`) and hosts that resolve to internal addresses are relevant.
  - Response parsing: `recv()` accumulates `fgets()` chunks of up to 4096 bytes until a newline, with no total length cap; `expect()` loops over `NNN-` continuation lines, does the `STARTTLS` capability scan, calls `sscanf()` for the code, and runs the error-message regex over the full accumulated output.
  - Timeouts: `stream_set_timeout()` applies per read, not per command, so a server that sends a byte at a time may stall a validation past the documented command timeouts. The number of MX hosts tried is unbounded, and each gets `connect_timeout` (10 s).
  - TLS: `startTLS()` and the `ssl` stream context. `ssl_verify_peer` defaults to `FALSE` on purpose, and STARTTLS is opportunistic (used only when advertised).
  - Result integrity: a malicious or MITM server making an address read as valid when it isn't, or results from one domain bleeding into another in a multi-domain batch.
- Least: `demo.php`, the `tests/` harness.

## How to exercise it
- The scanner runs offline: there is no DNS and no route to real MX hosts, so live SMTP validation can't run. Exercise the library against local fakes instead:
  - `tests/TestableValidator.php` replaces the socket layer: queue server lines with `queueResponse()`, inspect `$sentCommands`, inject connect failures with `$failConnectHosts`, and set MX answers with `$mxQueryResults`. Most unit tests in `tests/Unit/` use it.
  - `tests/E2E/LocalSmtpValidator.php` overrides `mx_query()` to return `127.0.0.1`. `tests/E2E/SmtpValidationTest.php` starts `tests/fixtures/smtp_test_server.py` (aiosmtpd 1.4.6, installed in the image) on `127.0.0.1:${E2E_SMTP_PORT:-2525}`.
  - For hostile-server behaviour, write a small raw TCP server (Python or PHP) on 127.0.0.1, subclass the validator to return it from `mx_query()`, and set `connect_port`.
- Commands: `vendor/bin/phpunit` (unit suite) and `vendor/bin/phpunit --group e2e` (local SMTP).

## How you rate severity
- High: SMTP command injection (an extra command or line on the wire) or SSRF-style connection to an attacker-chosen internal host or port, reachable from an attacker-supplied email address or the DNS of an attacker-owned domain, with default settings. The missing private-address filter is one finding: report it once with demonstrated impact, not once per call site. Also high: certificate or hostname verification that is skipped, or a STARTTLS downgrade that goes unnoticed, while `ssl_verify_peer` is `true`.
- Medium: ReDoS, unbounded memory, or a hang beyond the configured timeouts triggered by one crafted address or one malicious server response; a crafted response that aborts the whole batch, not just its own domain.
- Low or out of scope: anything that needs attacker control of configuration (`connect_port`, `set_sender()` input, timeouts, flags); MITM or STARTTLS stripping while `ssl_verify_peer` is `false` (the documented default); unescaped server text in `_error_msg` or `get_log()` reaching an HTML, SQL, or log sink (the caller's job).

## Anything to leave alone
- Don't report that SMTP verification is unreliable (catch-all, greylisting, or servers that accept every `RCPT`); that is a known limitation of the technique.
- Don't report failing network lookups or connections inside the offline scanner itself.
- `getmxrr()` being unavailable on Windows is handled by `SMTP_Validate_Email_Exception_No_MX_Support` and is not a bug.
