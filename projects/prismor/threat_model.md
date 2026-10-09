# Threat model

## What this project does and where untrusted input enters

Prismor guards AI coding agents (Claude Code, Codex, Cursor, Copilot CLI and others) at runtime. The agent calls a Prismor hook before and after each tool call. Prismor checks the call against a YAML policy, masks secrets, and returns allow, warn or deny. The project also ships an MCP gateway, an LLM proxy, and SDK adapters for agent frameworks.

Treat these inputs as attacker-controlled:

- Hook payloads on stdin: tool names, shell commands, file paths, file contents, URLs and tool results. A prompt-injected agent writes these.
- MCP tool definitions and tool results passing through `prismor mcp-gateway`.
- LLM requests and responses passing through `prismor proxy`, including streamed responses.
- Files in the agent's workspace: dotenv files, agent config files, skill files.
- Policy bundles and advisories pulled from a remote control plane. Prismor verifies their signatures, and a bypass of that check is in scope.

The local user who installed Prismor and owns `PRISMOR_HOME` is trusted.

## Components that matter most / least

Most important:

- Hook dispatch and the policy engine in `prismor/runtime/`: any input that turns a deny into an allow.
- The cloaking layer: any path where a registered secret reaches the agent, a log or telemetry unmasked.
- Signature checks on remote policy, advisories and device enrollment.
- The MCP gateway and LLM proxy: policy bypass or secret leakage through either.

Less important but in scope: the local dashboard, the other `prismor` CLI subcommands, and the adapters in `adapters/`.

Out of scope: `research/`, `examples/`, `grafana/`, and `tests/`.

## How to exercise it

- The image has an editable install. `prismor --help` lists the CLI.
- `python -m pytest tests -q -p no:randomly` runs the suite. One test errors at teardown on main (a leaked monkeypatch); the rest pass.
- `scripts/run_security_tests.sh` runs the security regression set.
- To drive a hook by hand, pipe a Claude Code style JSON payload into the hook dispatcher. Set a fresh `PRISMOR_HOME` first so earlier state doesn't leak in.

## How you rate severity

- Critical: with the default policy and no user interaction, an agent runs a command or reads a file that a deny rule should block; a registered secret reaches the agent or telemetry in clear text; or someone forges a signed policy bundle.
- High: the same bypasses, but only under a non-default configuration or on one specific agent host.
- Medium: a crash or hang in the hook path that makes the agent fail open; XSS in the local dashboard.
- Low: denial of service that fails closed, log injection, and anything that needs the local user's help.

## Anything to leave alone

- In observe mode, rules warn instead of block. That's intended.
- Prismor can't constrain an agent with no hook installed. Skip reports of the form "an unhooked agent can do X".
