# BrassClaw security scan scope

BrassClaw is a Rust personal AI assistant. It processes untrusted chat messages,
model output, MCP commands, external content and authored component definitions,
and can access files, processes, network services and secrets through host Tools.
Please assess the current source, not claims of completed migration in old docs.
`docs/implementation-status.md` identifies implemented boundaries, remaining work
and canonical implementation owners. `simplified_v3.md` is the authority target.

## Trust model and priorities

The instance-token operator administers the instance. An authenticated operator
intentionally configuring a provider or enabling a Tool is expected behavior.
There are no intended tenant/project/feature-role authorization boundaries.
External-service authentication, secret/network/sandbox enforcement, live Tool
allow/block policy and technical resource limits remain security boundaries.

Prioritize unauthenticated ingress and token validation; secret disclosure;
filesystem/symlink escapes; SSRF and network policy bypass; process sandbox
escapes; SQL injection; WebUI XSS/CSRF; and untrusted model/content escalation
into host Tool execution. Follow real callers through enabled feature paths.

For ordinary PostgreSQL/skills-db execution, inspect retained catalogue snapshots,
typed data versus executable code, exact component associations and approval,
immutable Tool implementations and alias identity, live policy before dispatch,
task/attempt isolation, cancellation, child results, retries and unresolved effects.
An assembly/execution failure must never replay as a Tier-2 fallback.
System seeds use verified installation bootstrap; post-installation authored
changes use Q1/behavior/human-Q2. A `source: system` label alone is not approval.
Monty is one supervised instance-wide service, not a per-chat execution fallback.

Relevant areas include `crates/brassclaw_reborn_webui_ingress`,
`crates/brassclaw_reborn_composition`, `crates/brassclaw_monty_host`,
`crates/brassclaw_skills`, `crates/brassclaw_runtime_policy`,
`crates/brassclaw_filesystem`, `crates/brassclaw_network`,
`crates/brassclaw_process_sandbox` and `crates/brassclaw_secrets`.

## Build and offline reproduction

The source is `/src`; binaries are `/src/target/debug/brassclaw` and
`/src/target/debug/monty_worker`. Default CLI features include PostgreSQL and
skills-db. Cargo dependencies are fetched online before offline auditing.
Embedded PostgreSQL/pgvector artifacts are compiled into the product at build
time. No production credentials or external model endpoint is supplied.

The scanner shell starts as root. PostgreSQL tests must use the `scanner` user,
for example `runuser -u scanner -- env HOME=/home/scanner cargo test --locked
--offline -p brassclaw_auth` from `/src`. This is an example entry point, not a
claim that tests passed or that it covers the complete product. Determine the
relevant package/features and real test prerequisites for each reproducer.
Use isolated local PostgreSQL and synthetic secrets. A skipped DB test, missing
model service or unavailable offline fixture is a coverage gap, not a pass.
Do not contact live installations or third-party services to reproduce issues.

## Report requirements

Email reports to the registered contact. Include report ID, exact scanned commit,
file/line, affected configuration, attacker prerequisites, complete data flow,
minimal isolated reproducer, observed versus intended behavior and a proposed
focused patch/regression test. Distinguish demonstrated vulnerabilities from
unverified hypotheses and already documented migration gaps. A documented gap
remains reportable if a reachable attack violates an intended boundary.

Rate remotely reachable unauthenticated code execution or broad secret theft
highest; demonstrate the actual boundary crossed and privileges required.
Authorized operator Tool usage alone is not an exploit. Do not claim multi-tenant
isolation requirements that the product does not promise. Dependency-only issues
should be distinguished from vulnerabilities in this project's own code.
