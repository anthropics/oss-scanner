# Seclume threat model

## What it is
Seclume is a set of Java clients (JDBC drivers for PostgreSQL, MySQL/MariaDB, SQL Server and Oracle; Kafka, RabbitMQ,
Redis, mail, HTTPS, SSH, LDAP and cloud clients) built so that credentials never become heap objects. Secrets are read
into locked native memory, used for the login and wiped afterwards.

## Security goals (what counts as a vulnerability)
- A credential (password, token, API or signing key, TLS traffic secret) is left on the Java heap, in a String or
  byte[], or can be found in a heap dump taken after use. Highest severity: this is the library's purpose.
- A secret is not wiped on a failure path: exception, Error, interruption, timeout, rejected login, dropped
  connection, failed TLS handshake.
- A secret is written to logs, exception messages, toString output, metrics, diagnostics or reports.
- Session isolation breaks: state, credentials or in-flight data leak between pooled connections or borrowers.
- Wire-protocol or cryptography flaws: authentication bypass, downgrade, accepting what the primitive must refuse
  (altered tags, off-curve points), memory-safety issues in the native-memory handling.
- Settings that accept a secret as a plain value (`password=`, `secret=`, `value=`) instead of refusing it.

## Where untrusted input enters
Server responses on every wire protocol (handshakes, authentication, TLS), secret-provider responses (Vault, cloud
secret stores, metadata servers), connection URLs and configuration, and data returned by the servers.

## Out of scope
- Anything that needs an attacker who already controls the JVM process, its debugger or native memory.
- Secrets supplied by the application itself as Strings before reaching seclume.
- Test code, benchmarks and demos under `demo/` and the `seclume-bench` and `seclume-tls-anvil` modules, unless they
  affect released artifacts.

## Severity
- Critical: a secret recoverable from a heap dump of a normal login, or authentication bypass.
- High: a secret retained or logged on a failure path, cross-session leakage, or a cryptographic flaw with a
  demonstrated impact.
- Medium: hardening gaps without a demonstrated path to a secret.
- Low: robustness issues (crashes, hangs) from malformed server input with no secret exposure.

## Reports
Include a reproducer using synthetic credentials and a proposed patch with a regression test. Do not include real
credentials. Do not copy anything from the private `seclume-tcp-core` repository into patches.
