# Minimal Router

Minimal Router is an MIT-licensed Alpine Linux router appliance with a Go
management plane and React/TypeScript dashboard. It is currently beta, intended
for controlled pilots, with no production-readiness or widespread-adoption claim.
Its firewall and management boundaries protect devices behind the router.

Read SECURITY.md, ARCHITECTURE.md, docs/GOLDEN-IMAGE.md and the repository's
AGENTS.md for the current design and limitations. The public repository is the
entire audit scope; no private deployment inventory or credentials are needed.

## Boundaries and priorities

- WAN peers are untrusted; LAN clients are not automatically administrators.
  Check default-deny policy generation, interface binding, IPv6 fail-closed
  behavior and ways management services could become reachable from WAN.
- Audit API authentication, sessions, CSRF, authorization, first-run setup,
  recovery, request parsing and dashboard rendering of untrusted data.
- routerd is an unprivileged, potentially compromisable management process.
  router-applyd is the privileged helper, accepting only typed, bounded,
  allowlisted operations over a protected local Unix socket. Look for privilege
  escalation, command/configuration injection, path traversal and socket access
  failures across that boundary.
- Configuration changes must remain recoverable. Examine validation, durable
  intent/result journals, snapshots, confirmation, rollback, boot reconciliation,
  and fail-closed handling of ambiguous results or storage exhaustion.
- Firmware and restore inputs are adversarial. Check signature and architecture
  verification, anti-downgrade rules, archive extraction, runtime compatibility,
  A/B activation and rollback. Never remove a check to make a reproducer work.
- Credentials, private keys, session material and backups must not leak through
  APIs, logs, diagnostics, exports, filesystem permissions or MCP responses.
  MCP is read-only unless an operator explicitly enables administrator mode.
- Golden installation and firstboot are in scope for source review: image
  verification, disk-selection safeguards, unique device identity and credentials.

Pre-existing root, kernel, hypervisor or physical compromise is outside the
intended protection model; escalation from routerd to root is in scope. A hostile
authenticated administrator must be distinguished from an unauthenticated peer.
Document required network position, enabled optional features and privileges.

## Audit environment

The checkout is /src, Go binaries are /src/bin, dashboard output is /src/web/dist.
Go modules, pnpm dependencies and Playwright Chromium/WebKit are fetched during
the image build. With the network disabled, run:

    GOPROXY=off GOSUMDB=off go test -race ./...
    GOPROXY=off GOSUMDB=off go vet ./...
    pnpm --dir web test
    pnpm --dir web lint
    pnpm --dir web test:e2e

This Debian analysis image is not an installed Alpine appliance. OpenRC service
integration, real packet forwarding, firstboot and Golden ISO E2E need a separate
disposable Alpine/QEMU environment. Do not equate container tests with those
checks or real-lab validation. Do not run the installer against the audit host.

## Reports

Provide the commit, affected paths, attacker prerequisites, violated boundary,
impact and a minimal reproducible test using synthetic state. Distinguish code
inspection from a demonstrated exploit and identify environmental limitations.
Include a minimal fix with a regression test, preserving privilege separation,
default deny, signed updates and rollback. Deduplicate reports by root cause.

Prioritize unauthenticated code execution, meaningful authentication bypass,
privilege escalation, firmware verification bypass, secret disclosure, and
remotely triggerable loss of firewall enforcement. Do not infer critical severity
from a crash alone; describe reachability, persistence and recovery requirements.
