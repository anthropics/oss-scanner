# How we would like reports written

## Layout and length
- Keep each report short enough to read in a few minutes: aim for one to two pages.
- Use these sections, in this order: Summary, Impact, Affected component and versions, Attacker position, Reproduction,
  Root cause, Suggested fix.
- Summary: two or three sentences saying what an attacker can do and through which entry point.

## What every report should state
- The module and class where the faulty code lives (for example `server`, `com.arcadedb.server.http.handler.PostCommandHandler`)
  and the public entry point that reaches it: the HTTP endpoint (`/api/v1/...`), the wire protocol (Postgres, Redis,
  MongoDB, Bolt, gRPC, Gremlin, GraphQL, MCP) or the embedded Java API.
- The attacker's starting position: unauthenticated network client, authenticated user with which roles or type
  permissions, another node in the HA cluster, or someone supplying a file to import.
- The configuration needed, especially any non-default server setting (`arcadedb.*` properties, plugins enabled, HA mode).
- The commit of `main` the finding was made against.
- A reproduction that a maintainer can run as is: preferably a JUnit 5 test that uses the existing fixtures
  (`BaseGraphServerTest` or `StaticBaseServerTest` for server tests, `TestHelper` for engine tests), otherwise exact
  `curl` commands or wire-protocol client code with the expected and the observed result.
- Whether the reproduction was actually run in the scanner environment and what it printed, or whether it is untested.

## Style
- One root cause per report. If the same bug is reachable from several entry points, list them all in one report.
- Start the title with the module name in brackets, for example `[postgresw] Type ACL bypass via extended query protocol`.
- Plain, factual language. No speculation beyond what the reproduction shows; say clearly when impact is inferred.
- Use code blocks for code, requests and stack traces; trim stack traces to the frames inside `com.arcadedb`.
- Do not use the em dash character; use a normal dash, a comma, or rephrase.
