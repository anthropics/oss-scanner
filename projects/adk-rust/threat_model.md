# Threat model: adk-rust

adk-rust is a Rust workspace of 43 publishable crates for building LLM agents:
tool calling, multi-provider model clients, graph workflows, an HTTP/A2A server,
MCP integration, sandboxed code execution, sessions and memory. Applications
built on it run on servers that accept requests from the network and act on
output from a model, so the framework's job is to keep the operator's
configured policies in force no matter what the model, a remote agent, a tool
server or a client sends. `AGENTS.md` describes the crates and conventions;
`STABILITY.md` gives each crate's tier; `SECURITY.md` is the reporting policy.

## Where untrusted input enters

- **Network clients** of an application built on `adk-server`, `adk-awp`,
  `adk-acp` (server feature) or `adk-payments`: HTTP bodies and headers, A2A
  JSON-RPC, SSE and WebSocket streams (`adk-realtime`), webhooks.
- **Model output**: text, tool-call names and JSON arguments, structured
  outputs, and code in CodeAct agents. Treat all of it as attacker-controlled:
  a document, web page or tool result can carry injected instructions.
- **MCP servers** (`adk-tool/src/mcp/`): tool lists and JSON schemas, tool
  results, resources, elicitation and sampling requests, over stdio or
  Streamable HTTP. A remote MCP server is an untrusted peer.
- **Tool results and retrieved content**: RAG documents, memory search hits,
  browser pages (`adk-browser`), RSS feeds and HTTP responses fetched by action
  nodes.
- **Peer agents**: remote A2A agents and ACP agents the application connects
  to as tools.
- **Operator configuration**: YAML agent configs, `SKILL.md` files
  (`adk-skill`), `WorkflowSchema` documents and action-node definitions
  (`adk-action`). The operator is trusted, but a configuration loaded from a
  repository or marketplace is not; parsing must not panic or escape its
  declared scope.
- **Stored state**: sessions, memory and artifacts shared by many users of
  one deployment. Isolation between sessions, users and projects is a
  security property.

## Components that matter most

| Area | Code | What must hold |
|------|------|----------------|
| Public HTTP surface | `adk-server/src/{rest,a2a,agent_engine,background,webhooks,yaml_agent}/`, `adk-server/src/auth_bridge.rs`, `adk-awp/src/`, `adk-acp/src/`, `adk-payments/src/server/` | Requests are authenticated and authorised before they reach an agent, a run store or a cron job; rate limits (`adk-awp/src/rate_limit.rs`, `adk-server/src/a2a/rate_limit.rs`) and webhook HMAC verification hold; malformed input is rejected without a panic |
| Authentication and authorisation | `adk-auth/src/{middleware,access_control,permission,role,scope}.rs`, `adk-auth/src/sso/`, `adk-auth/src/secrets/`, `adk-server/src/a2a/bearer_auth.rs`, `adk-payments/src/auth/` | JWT, OIDC and OAuth2 validation (issuer, audience, expiry, algorithm, signature); RBAC and `ProtectedTool` decisions cannot be bypassed by a model-chosen tool name or argument shape |
| Model-controlled execution | `adk-agent/src/` (tool dispatch, `ToolConfirmationPolicy`, callbacks), `adk-tool/src/` (`FunctionTool` argument handling), `adk-graph/src/action/{http,file,code,rss,notification}.rs`, `adk-devtools/src/workspace.rs` and `adk-devtools/src/tools/` | A configured control is applied on every path: confirmation before a gated tool runs, `HttpActionPolicy` host and scheme rules (no SSRF to internal addresses), file nodes and dev tools confined to their allowed roots, no shell injection through `adk-devtools/src/tools/bash.rs` |
| Code execution and sandboxes | `adk-sandbox/src/{process,child_io,wasm}.rs`, `adk-sandbox/src/sandbox/{macos,linux,seccomp}.rs`, `adk-sandbox/src/workspace/`, `adk-code/src/{host_process,container,embedded_js,wasm_guest,rust_sandbox}.rs`, `adk-code/src/embedded_python/`, `adk-codeact-monty/` | Sandboxed code reaches nothing the profile does not grant (filesystem, network, environment, process tree); resource limits hold; output handling does not deadlock or overflow |
| Input from external servers | `adk-tool/src/mcp/{toolset,schema_limits,elicitation,http,auth,manager}.rs`, `adk-acp/src/`, provider response parsing in `adk-model/src/`, `adk-gemini/src/`, `adk-anthropic/src/` | Hostile schemas, results and stream frames cannot exhaust memory, hang the client or redirect credentials; MCP OAuth tokens go only to the server they were issued for |
| Secrets and data at rest | `adk-session` (`EncryptedSession`, backends), `adk-memory`, `adk-artifact`, `adk-auth/src/secrets/`, `adk-anthropic/src/base_url.rs`, provider clients | API keys and tokens never appear in logs, events, error messages or session state; encryption and key rotation are correct; plain-HTTP endpoints need the documented opt-in |

Lower priority: `adk-eval`, `adk-bench`, `adk-telemetry`, `adk-deploy`,
`adk-cli` (local launcher), `adk-studio` and `adk-ui` (separate repositories).
Every `unsafe` block in the workspace is in these files:
`adk-anthropic/src/managed_agents/client.rs`, `adk-audio/src/desktop/{capture,playback}.rs`,
`adk-bench/src/memory.rs`, `adk-devtools/src/tools/bash.rs`, `adk-enterprise/src/client.rs`,
`adk-graph/src/functional/typed_reducer.rs`, `adk-sandbox/src/child_io.rs`,
`adk-sandbox/src/sandbox/linux.rs`, `adk-server/src/agent_engine/entrypoint.rs`,
`adk-server/src/yaml_agent/interpolator.rs`, `adk-telemetry/src/gcp.rs`,
`adk-tool/src/mcp/toolset.rs`.

## How to exercise it

The image holds the checkout at `/src`, the pinned toolchain, every crate in
`Cargo.lock`, and a debug build of the default-feature workspace with all test
binaries in `target/debug`. Cargo is set offline (`CARGO_NET_OFFLINE=true`).

```bash
cd /src
cargo nextest run --workspace                      # the whole default-feature suite
cargo nextest run -p adk-server                    # one crate
cargo nextest run -p adk-tool --features mcp-sampling
```

- **Feature-gated modules**: `scripts/feature-coverage-pairs.txt` lists every
  `<package> <features>` pair the default build skips; each builds offline.
  `lancedb`, `surrealdb` and `adk-mistralrs` compile for a long time on two
  CPUs. The ONNX audio features (`whisper-onnx`, `kokoro`, …) download
  binaries at build time and do not build offline.
- **Driving agents without API keys**: `adk_model::mock::MockLlm`
  (`adk-model/src/mock.rs`) and `adk_managed::testing::ScriptedLlm` script
  model turns, including tool calls. The `adk-server/tests/` suites
  (`a2a_tests.rs`, `a2a_auth_boundary_tests.rs`, `background_auth_tests.rs`)
  start servers on loopback and are the template for request-level
  reproducers.
- **Tests that need the outside world** are `#[ignore]` with a reason
  (provider credentials, Redis, Postgres, Google Cloud). The image has no
  credentials; do not try to reach those services.
- The image build removes the `wild` linker sections from
  `.cargo/config.toml`; that modification is part of the build, not a finding.

## How we rate severity

| Severity | Examples |
|----------|----------|
| Critical | Sandbox escape: code run through `adk-sandbox`, `adk-code` or `adk-codeact-monty` reaches the host beyond the configured profile. Unauthenticated remote code execution. Authentication bypass in `adk-auth` or in the `adk-server`/`adk-awp` middleware. |
| High | A configured control is bypassed by model- or network-controlled input: `HttpActionPolicy` host/scheme rules (SSRF), file-node or `adk-devtools` root confinement, RBAC or `ProtectedTool`, `ToolConfirmationPolicy`. Cross-session or cross-user access to sessions, memory or artifacts. Secrets written to logs, events or error responses. Webhook or AP2 mandate signature verification that accepts a forged message. Plaintext recovery from `EncryptedSession`. |
| Medium | Panic, unbounded allocation or hang from input reachable over the network or from an MCP server. PII redaction in `adk-guardrail` that a plain encoding defeats. Missing rate limiting where the documentation promises it. |
| Low | Issues that need the operator's own configuration or filesystem to be malicious. Denial of service that needs an authenticated, privileged caller. Defects only in `examples/`. |

Prompt injection by itself (the model follows instructions planted in its
input) is model behaviour and is out of scope. It is in scope when the
framework fails to apply a control the operator configured against it.

## Anything to leave alone

- **Third-party crates**: report to the upstream project. In scope here only
  when adk-rust misuses the dependency. Known advisories in the dependency
  tree, with the accepted risk for each, are in
  `docs/security/DEPENDENCY-ADVISORIES.md` and `.cargo/audit.toml`.
- **`examples/`, `templates/`, `scripts/`, `xtask/`**: not shipped as
  libraries. Use them as reproducer scaffolding, not as findings.
- **`adk-sandbox` on Windows**: the AppContainer enforcer is unimplemented and
  reports itself unavailable (`adk-sandbox/src/sandbox/windows.rs`), as
  documented in `AGENTS.md`.
- **`adk-code` host-process backend without an OS sandbox feature** runs code
  with the host's privileges by design; the `sandbox-macos` and
  `sandbox-linux` features are the enforcers.
- **Experimental crates** (`adk-enterprise`, `adk-managed`,
  `adk-codeact-monty`) are in scope at lower priority.
- **Model behaviour**: hallucinated tool calls, refusals, and the quality of
  guardrail heuristics are not vulnerabilities.

## Reports and patches

- Send reports to `security@zavora.ai` or through
  [GitHub private vulnerability reporting](https://github.com/zavora-ai/adk-rust/security/advisories/new),
  never as a public issue. State the commit, the crate, the feature flags, the
  attacker's position (network client, MCP server, model output, operator) and
  the control that failed.
- A reproducer is best as a Rust test under the affected crate's `tests/`
  directory, runnable with `cargo nextest run -p <crate>`.
- A patch follows `AGENTS.md`: conventional-commit subject, `thiserror` for
  errors, `tracing` for logs, `cargo fmt`, `cargo clippy --workspace
  --all-targets -- -D warnings`, and a fragment under `changelog.d/` for a
  user-facing change. Stable crates (see `STABILITY.md`) take only additive
  public API changes in 2.x.
- One report per root cause, listing every affected entry point.
