# Kontext threat model

## What Kontext protects

Kontext evaluates local policy before supported AI-agent tool calls run. It
supports Claude Code, Claude Cowork, and Codex. It records decisions and
outcomes in a local SQLite authorization ledger. Managed installations fetch
configuration and export redacted records to the Kontext backend.

The security goal is to enforce configured policy at supported synchronous
hooks and preserve accurate, redacted evidence of those decisions. A bypass
can let an agent run a command or access data that the configured policy denies.

## Inputs and components to examine

Treat agent tool names, arguments, command strings, paths, hook metadata, and
transcript contents as untrusted. Repository files and agent configuration
discovered on disk may also contain attacker-controlled content.

Focus on:

- Hook parsing and normalization, including differences between the action
  evaluated by policy and the action the agent executes.
- Cedar policy evaluation, agent identity resolution, approval handling, and
  managed configuration validation.
- Local daemon APIs and Unix sockets, including access controls, request
  validation, and filesystem permissions.
- Credential storage and redaction before local persistence or managed export.
- Authorization ledger integrity, receipt verification, and attribution of
  events to the correct agent, session, and action.
- File discovery and configuration updates, including symlinks, path traversal,
  unintended reads, and writes outside the intended location.

State what access an attacker needs. Distinguish remote content that influences
an agent from direct local access as the same OS user, a different user, or root.
Use test fixtures and local mock services for managed backend interactions.

## Intended limits

Read README.md and docs/coverage.md for current enforcement behavior. Observe
mode records decisions without blocking. Enforcement only applies at supported
hooks. Kontext is not a kernel sandbox and does not prevent root or the machine
owner from removing the installation.

The documented behavior allows tool calls when policy evaluation fails, policy
is unavailable, or identity cannot be resolved. If the hook cannot obtain a
decision, the agent's own permission settings apply. These defaults alone are
not findings. A practical way for untrusted input to trigger those conditions
and evade an otherwise applicable policy is worth investigating.

The embedded risk and step-safety models are advisory. Misclassification alone
is not an enforcement bypass.

The hosted dashboard, backend implementation, other repositories, and live
third-party services are outside this submission. Vulnerabilities in this
repository's clients remain in scope.

## Build and tests

The checkout is in /src and the built CLI is /src/bin/kontext. The image keeps
the Go toolchain, downloaded modules, and build cache so tests can run offline.
Run tests as the provided regular user because permission tests rely on writes
to read-only directories failing, which does not happen as root:

```sh
runuser -u kontext-test -- go test ./...
runuser -u kontext-test -- go test -race ./...
runuser -u kontext-test -- go vet ./...
```

Use focused package tests for reproductions. Existing tests include mock
services and filesystem fixtures. The Linux image can exercise the portable
runtime, policy evaluator, parsers, and ledger. macOS Keychain, launchd, and
installation behavior require macOS for runtime validation. Report that
limitation when a finding depends on those components.

## Useful reports

Include the affected commit, required configuration, attacker-controlled input,
expected policy decision, actual result, and a minimal reproducer. Explain the
security consequence separately from the code defect. Include a regression
test and a small patch when possible.

Rate severity by demonstrated impact and attacker access. Give priority to
policy or approval bypasses, credential disclosure, and unintended code
execution. Distinguish a crash from a crash that enables an action that should
have been denied. Do not label a finding critical without showing the impact
that supports that rating.
