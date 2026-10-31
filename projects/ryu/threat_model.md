# Threat model

The canonical policy is `.github/SECURITY.md` in the repository. This file summarizes it for the
scanner.

## What this project does and where untrusted input enters
- Ryu is a self-hosted node that runs LLM-driven agents. They execute code, run shell commands,
  spawn subprocesses and make network calls on the operator's behalf. `ryu-core` (`apps/core`)
  is the node; `ryu-gateway` (`apps/gateway`) is the model/tool gateway it manages.
- **The agent is untrusted.** Treat everything an LLM produces (tool calls, tool arguments, code
  submitted to code mode, URLs it asks to fetch, text it writes into outputs) as adversarial
  input. The operator and the Core process are trusted.
- Other untrusted input: HTTP requests that reach Core or Gateway from off-box (remote or mesh
  bind), webhook and channel ingress, responses from model providers and MCP servers, and
  plugin and app manifests fetched from a marketplace before signature checks.

## Components that matter most / least
Most important (real containment boundaries):
- The deny-by-default code-exec sandbox: QuickJS on Wasmtime in `crates/core/tool-exec/`
  (`js_backend.rs`) and the WASI sandbox in `crates/core/sandbox/src/wasmtime.rs`. Any escape
  to network, filesystem, env or host memory.
- Remote and mesh auth: `enforce_remote_auth` in `apps/core/src/server/`, token checks, and
  any path that serves requests off-box without a valid token or fails open.
- Per-agent tool allowlists (`allowed_tools`): calling a tool the agent was not granted.
- The SSRF / egress guard (`crates/core/egress/`, `apps/core/src/local_egress/`): reaching
  loopback, private, link-local or cloud-metadata targets.
- Env-scrub and credential handling (`crates/gateway/credentials/`, `crates/core/vault/`,
  `apps/core/src/vault/`, `apps/core/src/plugin_secrets/`): secrets leaking to an agent,
  subprocess or log.
- Plugin manifest verification and the generic extension proxy
  (`apps/core/src/plugin_manifest/`, `apps/core/src/sidecar/ext_proxy.rs`).
- Other process-boundary sandbox backends in `crates/core/sandbox/src/` (docker, local,
  os_isolation, ssh and others).

In scope, lower priority:
- DLP / output redaction and the gateway firewall (`crates/gateway/firewall/`,
  `crates/gateway/screening/`) only when a real secret leaks through an output path that should
  redact it.

Out of scope:
- `apps/desktop`, `apps/island`, `apps/fumadocs` and the commercial `packages/*` UI layer
  (source-available, not part of this enrollment; see `LICENSING.md`).
- `vendor/` (third-party code) and `generated/` (generated files).

## How to exercise it
- `cargo test --manifest-path apps/core/Cargo.toml --features sandbox-wasmtime` and
  `cargo test --manifest-path apps/gateway/Cargo.toml`; test binaries are prebuilt in the image.
- Run with `RYU_PROFILE=dev RYU_KEYCHAIN=off RYU_DIR=/tmp/<dir>` so tests use an isolated data
  directory and never touch an OS keychain.
- Binaries are in `/src/target/debug/` (`ryu-core`, `ryu-gateway`).

## How you rate severity
- Critical: sandbox escape to host code execution, or unauthenticated remote access to Core or
  Gateway when bound off-box.
- High: tool-allowlist bypass, SSRF guard bypass reaching metadata or private targets,
  credential exfiltration through env-scrub, plugin signature bypass.
- Medium: DLP/redaction bypass leaking a real secret; memory-safety bugs without a demonstrated
  boundary crossing; DoS reachable from an unauthenticated off-box request.
- Low: DoS that needs an authenticated or local caller.

## Anything to leave alone
- Heuristic bypasses of the command scanner. It is accident prevention, not a boundary.
- Prompt injection without a chained boundary violation.
- Malicious third-party skills or plugins the operator chose to install.
- Social-engineering the operator into approving an action.
