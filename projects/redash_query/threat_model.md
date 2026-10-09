# Threat model: redash_query

## What this project does and where untrusted input enters
redash_query is an unofficial Ruby CLI and library (`RedashQuery::Client`) for the Redash API. It runs saved
queries and polls their jobs, creates and archives queries, and prints results as JSON or CSV to stdout or to a file.
It is often called from scripts and automation. It uses only stdlib `net/http`.

Trust boundaries:
- **Redash HTTP responses are untrusted.** A malicious or compromised Redash server, or anything that can tamper with
  the response, controls job IDs, `query_result_id`, job error strings, datasource names, and result bodies. Some of
  these values are interpolated into later request paths or printed to the terminal.
- **The API key (`REDASH_API_KEY`) is the main asset.** It must only ever be sent to the host in `REDASH_BASE_URL`, over
  HTTPS (HTTP is allowed only for localhost), and must never appear in error messages, stderr, stdout, or output files.
- **CLI arguments and `--params` JSON** come from the operator. In automation they may come from upstream data, so
  input that escapes the intended request (path or parameter injection) is in scope.
- **`REDASH_BASE_URL`** is operator configuration. It is validated (scheme, no embedded credentials), and bypassing that
  validation is in scope.

## Components that matter most / least
- Most: `lib/redash_query/client.rb` (URL construction, auth header, job polling, response handling).
- Next: `lib/redash_query/cli.rb` (argument validation, output-file writing with `O_EXCL`/`0600`, terminal output).
- Least: `exe/redash_query` (a thin wrapper) and `test/`.

## How to exercise it
- `bundle exec rake test` runs the Minitest suite. All HTTP is stubbed with WebMock.
- Reproduce findings with WebMock stubs or a local stub server on `localhost`. Never contact a real Redash instance, and
  never use a real API key.

## How you rate severity
- **Critical**: the API key is sent to a host other than the one configured, or sent in cleartext to a non-local host.
- **High**: the API key leaks into errors, logs, stdout/stderr, or files. A server response causes requests to
  unintended API paths or methods (for example, path injection through job or result IDs). A file is written outside
  the path the operator specified, or an existing file is overwritten without `--force`.
- **Medium**: a malicious server causes unbounded polling, unbounded memory use, or a hang despite `--timeout`.
  Server-controlled strings inject terminal escape sequences. An output file is created with permissions broader
  than `0600`.
- **Low**: missing input validation with no demonstrated security impact.

## Anything to leave alone
- The operator choosing an `--output` or `--file` path they can already write or read is intended behavior, not path
  traversal.
- Redash server-side vulnerabilities, and SQL that the operator deliberately runs against their own datasource.
- Purely theoretical issues without a reproducer. Reports should include the file and line, prerequisites, a minimal
  reproducer (preferably a failing Minitest/WebMock test), and a proposed patch.
