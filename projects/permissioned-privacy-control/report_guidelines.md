# How we would like reports written

## Layout and length
- Under one page, with these sections in this order: Summary, Attacker position, Reproduction, Impact, Suggested fix.
- One root cause per report.

## What every report should state
- The attacker's starting position: unauthenticated; a member of organization A with named groups and claims; an org
  admin or contract admin; or a holder of the operator token.
- The endpoint, JSON-RPC method or admin API route that reaches the faulty code, and the file and function at fault.
- Which invariant from `threat_model.md` is broken, and which organization's or user's data crosses which boundary.
- Whether the issue is reachable in a build without `-tags mockauth`, running with `ENVIRONMENT=production`.
- Any configuration it depends on, for example `PRIVACY_READ_PROFILE`, Azure AD, or signed approvals enabled.

## Style
- Plain text and short sentences. Start the title with the component, for example "rbac:", "explorer:", "auth:".
- Give the reproducer as a Go test where possible, runnable with `go test -p 1 -run <Name> ./internal/<package>/...`
  after `ops-start-postgres`.
