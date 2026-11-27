# How we would like reports written

## Layout
- Sections, in this order: Summary, Impact, Attacker position, Affected code, Reproduction, Root cause, Suggested fix.
- Summary: two or three sentences on what an attacker can do and through which entry point.
- Keep each report to one or two pages.

## What every report should state
- The entry point: HTTP method and route (for example `PUT /databases/*/indexes`), TCP operation, or client API.
- The attacker position: unauthenticated client, or an authenticated certificate with which clearance
  (`ClusterAdmin`, `Operator`, `ValidUser`) and which database access (`Admin`, `ReadWrite`, `Read`); another cluster node;
  or someone supplying a file to import or restore.
- Secured or unsecured mode, and any non-default configuration key needed.
- The file and method where the faulty code lives, and the commit the finding was made against.
- A reproduction a maintainer can run: preferably an xUnit test using `RavenTestBase` or `ClusterTestBase` from
  `test/Tests.Infrastructure`, otherwise exact HTTP requests with expected and observed results.
- Whether the reproduction was run in the scanner environment and what it printed, or that it is untested.

## Style
- One root cause per report. List every entry point that reaches it in the same report.
- Plain, factual language. Say clearly when impact is inferred rather than shown.
- Trim stack traces to frames inside `Raven.*`, `Sparrow`, `Voron` and `Corax`.
