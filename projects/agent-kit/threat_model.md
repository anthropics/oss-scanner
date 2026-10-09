# agent-kit threat model

## Scope

Scan the TypeScript packages in this repository, especially `core`, `sandbox`,
`sessions`, `curator`, `ai`, and `node`. Treat examples as supporting context.
The project is a reusable library. Authentication and deployment policy belong
to the host application unless this repository implements or documents them.

## Assets and trust boundaries

- Tenant isolation: one tenant's volume, transcripts, audit records, memory,
  skills, and pending writes must not be reachable by another tenant.
- Secrets and credentials that may appear in user or model supplied content.
- The approval boundary for writes to memory, skills, and tenant files.
- The sandbox boundary around shell commands, filesystem paths, and network
  egress.

Treat user content, imported files, agent instructions, transcripts, tool
arguments, model output, and persisted memory or skills as untrusted. A model
response does not become trusted merely because it came from a configured
provider.

## Areas to prioritize

- Cross-tenant reads or writes, including mistakes in volume binding, cache
  keys, transcript stores, and Postgres storage scoping.
- Path traversal, symlink escapes, unsafe archive or file handling, and writes
  that cross the tenant volume boundary.
- Shell command construction, command allowlists, destructive-operation guards,
  secret scrubbing, and network egress restrictions.
- Prompt injection or secret exfiltration that bypasses threat scanning or
  reaches memory, skills, tool execution, or the system prompt.
- Any path that applies a memory, skill, or filesystem write without the
  configured approval gate.
- Concurrency or lifecycle bugs that expose one tenant's state to another.

## Report guidance

Report exploitable security issues with the affected public API, attacker
control, violated boundary, and a minimal local reproducer. Distinguish a
reachable vulnerability from a defense-in-depth concern. Do not contact or
test third-party systems; demonstrations should run against local fixtures.
