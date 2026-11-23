# How we would like reports written

## Layout and length
- One root cause per report. If several call sites share one root cause, list them in one report.
- At most one page before the reproducer, in this order: Summary, Attacker position, Impact, Reproduction, Root cause,
  Suggested fix.
- Title: the component and the effect, for example "Parquet reader: heap buffer overflow on a crafted dictionary page".

## What every report should state
- The attacker position from the threat model: unauthenticated client, restricted user (list the exact grants and
  settings needed), data in a file or a bucket, or a malicious server for `clickhouse-client`.
- Whether it works in the default configuration; otherwise, the non-default settings it needs.
- The commit the reproducer was run against (`/opt/clickhouse/COMMIT`) and the build: release, debug or ASan.
- A self-contained reproducer: SQL queries for `clickhouse local` or `clickhouse client`, or a short shell or Python
  script that crafts the input. Prefer a reproducer that a ClickHouse developer can paste into a terminal.
- The sanitizer output or the stack trace, trimmed to the relevant frames.
- What happens in the release build: an exception that fails only the query, a crash of the server, or memory
  corruption that goes unnoticed.

## Style
- Plain, factual language. Do not speculate about exploitability beyond what was demonstrated; say "not demonstrated"
  where it applies.
- Write names of SQL functions, settings, formats, classes and C++ functions in inline code, and functions as `f`
  rather than `f()`.
- Say "exception" for a `LOGICAL_ERROR`, not "crash": in release builds it does not take the server down.
- Dates in the YYYY-MM-DD format.
