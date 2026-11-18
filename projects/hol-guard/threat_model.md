# HOL Guard threat model

## Purpose and trust boundary

HOL Guard is an Apache-2.0, local-first security layer for AI agents, tool calls, plugins, skills, MCP servers, and package installs. The repository contains a Python CLI and plugin scanner under `src/codex_plugin_scanner/`, plus a Rust native runtime in `rust/crates/`. Guard evaluates actions and configuration, applies local policy, requests approval or blocks risky actions, and records evidence. Optional Guard Cloud connectivity is not necessary for local protection.

The protected boundary is **the developer's machine, credentials, workspaces, and agent tools**. Agent output, repository contents, installed plugins and skills, command strings, MCP tool arguments and results, dependency metadata, package archives, and remote responses should be treated as untrusted, even if they originate from a familiar tool.

## Highest-value attack surfaces

1. **Command interception and enforcement.** Review parsing and normalization of shell commands, pipelines, redirections, quoting, encodings, shell wrappers, environment assignments, PATH overrides, and alternate interpreter or execution paths. Focus on discrepancies between what Guard classifies and what the operating system executes. Relevant code includes `rust/crates/guard-command/`, `rust/crates/guard-hook-core/`, `rust/crates/guard-runtime/`, and adapter code under `src/codex_plugin_scanner/guard/`.
2. **Approval and policy state.** Review default-deny and failure behavior, hash-based reapproval, decision persistence, extension trust boundaries, rule ordering, policy scope, and any way to reuse or forge an approval for a different command or artifact. A command paused for review is meant to offer both one-time and persistent approval; the authorization must remain bound to the approved operation.
3. **MCP, plugin, and agent integrations.** Audit tool-call mediation, hook registration, local MCP proxy transport, configuration parsing, plugin and skill installation, and any bypass that silently removes protection or promotes untrusted metadata into privileged commands.
4. **Secrets and local files.** Look for symlink races, path traversal, unsafe temporary files, archive extraction, insecure filesystem permissions, untrusted workspace traversal, and exposure of tokens or private data in logs, receipts, terminal output, telemetry, or optional cloud sync. Relevant code includes `rust/crates/guard-secure-fs/`, `rust/crates/guard-archive/`, and secret scanning code.
5. **Dependency and update integrity.** Inspect source validation, remote advisory and rules ingestion, artifact provenance, package-manager shims, update/install flows, cache fallback, and any mechanism that lets attacker-controlled dependency data disable or evade inspection. Do not assume external package contents are safe.
6. **Plugin scanner.** Treat scanned package manifests, README files, scripts, MCP declarations, and archives as hostile input. Merely scanning a project should not execute that project's code or interpret a package-authored instruction as a privileged directive.

## Severity guidance

- **Critical:** reliable arbitrary code execution or secret exfiltration through Guard's own trusted execution context; a systemic remotely exploitable bypass of enforcement that causes dangerous operations to execute without review; an unauthenticated compromise of protected cloud or local secrets.
- **High:** a reproducible bypass of an intended block or approval check for a realistic dangerous action; forged or cross-scoped approvals; exploitable filesystem escape, malicious package execution during inspection, or disclosure of sensitive credentials outside the intended local boundary.
- **Medium:** attacker-triggered denial of protection or persistent degradation, localized non-secret file overwrite, policy confusion that requires strong preconditions, or sensitive metadata leakage with meaningful impact.
- **Low / informational:** bounded crashes without persistent effect, misleading diagnostics without an enforcement impact, or hardening suggestions without a demonstrated trust-boundary violation.

Assess exploitability in the actual hook or installation context; a theoretical string match mismatch is not automatically a bypass. Include the precise command, tool payload, config, fixture, or test that reproduces a finding and the affected commit. Prefer minimal patches and regression tests.

## How to exercise the code offline

- Rust source and compiled binary: `rust/crates/` and `/usr/local/bin/hol-guard-runtime`.
- Python package: `/src/.venv/bin/python` with an editable `codex_plugin_scanner` installation; `hol-guard` and `plugin-scanner` are on `PATH`.
- Rust tests can be run with `cargo test --offline --locked --manifest-path rust/Cargo.toml -p guard-command -p guard-scanner`. Other crates can be selected similarly.
- The root `tests/` directory is excluded by the project's current `.dockerignore` when this Dockerfile is built against the project checkout. The image still contains Python source, Rust crate tests, dependency caches, and CLI entry points. Do not claim that absent Python tests have passed.
- Never run agent hooks against a real user's files or credentials during a proof of concept. Use temporary workspaces, synthetic secrets and local fixtures. Offline scans cannot rely on live Guard Cloud, package registries, GitHub APIs, or external agent services.

## Reporting scope

Security consequences of code in this repository are in scope, including vulnerabilities reachable through optional features. A dependency vulnerability is relevant if HOL Guard exposes or worsens it. Pure detection-quality disagreements, unsupported platform integrations, marketing copy, and hypothetical issues without a trust-boundary impact are not security reports by themselves. Report sensitive findings privately to `security@hol.org`, rather than opening public issues.
