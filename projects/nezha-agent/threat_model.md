# Nezha Monitoring Agent: security review priorities

## Scope and relationship to the Dashboard

Source scope is `https://github.com/nezhahq/agent#main` only. This is the host-side component of Nezha Monitoring. The Dashboard repository is separately enrolled as `projects/nezha` (PR #108); its enrolment explicitly excludes Agent source. Review the Agent's side of its protocol and execution boundaries without treating the Dashboard, web frontends, third-party dependencies or other repositories as additional scan targets. The image preserves source at `/src`, the executable at `/src/build/nezha-agent`, the Go toolchain and module cache.

Do not install or start the Agent as a persistent service on the auditing host. Do not connect it to real Dashboard/Agent deployments, production services or third-party hosts. Use temporary local files, loopback servers, subprocess fixtures and simulated protocol peers. Ordinary tests run with `go test -mod=readonly -count=1 ./...`. The image sets `CI=true`, matching upstream GitHub Actions: `cmd/agent/main_test.go` deliberately does not execute `TestLookupIP`'s live Google DNS probes when CI is set. This image therefore does not verify public-DNS reachability; no source/tests have been removed or changed. The separate cross-repository `agentcompat` stress suite is also outside this image's ordinary test contract.

## Assets, authority and trust boundaries

- Host command execution, interactive terminal sessions, file listing/reading/writing/deletion/transfers, NAT forwarding and network probes run with the Agent process's OS privileges. A deployment may run it with elevated privileges; report the actual privileges required for an impact.
- Agent UUID and client secret, Dashboard endpoint and TLS verification settings, persisted configuration, executable/update integrity, telemetry and monitoring availability are security-relevant assets.
- Dashboard-issued gRPC tasks, streamed terminal/file/NAT data, task identifiers, sizes and cancellation events cross a network-to-host boundary. Validate framing and resource bounds, and keep task/session ownership isolated across reconnects and configuration reloads.
- File paths, symlinks, reparse points, special files and concurrent renames cross filesystem boundaries. Consider traversal, time-of-check/time-of-use, atomic replacement and cleanup semantics where a handler promises confinement or integrity.
- Configuration changes, credential rotation, Dashboard transfer and self-update must preserve the intended authenticated authority and transport requirements. Check that local feature-disable controls cannot be bypassed through alternate handlers or stale configuration snapshots.

## Priorities and limits on claims

1. Unauthenticated or wrongly authenticated control-channel access; secret disclosure or incorrect server identity/transport verification; unsafe credential rotation or control-plane transfer.
2. Bypasses of configured command/file/NAT restrictions, cross-task or stale-session ownership errors, unintended subprocess survival and unauthorized resource access.
3. Execution, terminal and file-operation paths that exceed their documented authority, especially when the Agent has elevated OS privileges.
4. Unsafe update provenance, executable replacement, persisted configuration permissions and secret-bearing errors/logs.
5. Crafted protocol input or repeated connection/task churn causing crashes, unbounded memory/goroutines/file descriptors, persistent loss of monitoring, or data corruption.

Remote command execution, broad file access and NAT can be intended functionality for a properly authorized Dashboard when the relevant features are enabled. An administrator issuing an explicitly permitted command is not by itself a vulnerability. A compromised fully trusted Dashboard also does not automatically demonstrate a new Agent vulnerability. Identify the missing authentication, violated local policy, unexpected authority escalation, isolation promise or other concrete boundary failure. Do not assume that merely opening an outbound gRPC connection exposes an unauthenticated public server on every Agent.

For each finding provide the affected commit/version, attacker capabilities and prerequisites, exact trust-boundary violation, safe local reproduction, host impact and a minimal patch/regression test where feasible. Distinguish release behaviour from current `main`, Linux from Windows/macOS-specific behaviour, and actual vulnerabilities from intentional compatibility behaviour or already-fixed public advisories. Deduplicate against the Agent's public GitHub Security Advisories. All security reports go privately to the project's primary contact in `project.yaml`, which is also listed in its `SECURITY.md`.
