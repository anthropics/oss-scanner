# Threat model: hydra-stack

## What this project does and where untrusted input enters
hydra-stack is a self-evolving skill and memory system for coding agents (Claude Code, Codex, MCP clients).
It started as luna-stack. The security-relevant code is the engine in `memory/`:

- `hydra_graph.py`: SQLite knowledge-graph memory. Has a CLI (`argparse` subcommands) and a stdio JSON-RPC MCP server (`mcp_main`).
- `rag_worker.py`: optional embedding worker, run as a subprocess.
- `setup.py`: installer/doctor. Writes config, hooks and MCP entries into the user's agent configuration.

Untrusted input enters through:
1. Text the agent emits after reading attacker-controlled content (prompt injection), which then gets promoted into memory.
2. MCP tool-call arguments over stdin, from a possibly prompt-injected agent.
3. Third-party skill text read by `absorb`.
4. Obsidian vault notes read by `vault-import`, and graphify output read by `graphify-import`.
5. Direct tampering with `graph.db` / `mem.db` by another local process.

`memory/POISONING.md` documents the intended controls: trust lanes, the `screen()` insert filter, quarantine,
context sanitisation, burst caps, the HMAC audit/integrity chain, rollback, and protected nodes.

## Components that matter most / least
- Most: anything that lets untrusted text reach injected SessionStart context (`build_context`, `recent`, `sanitize_for_context`)
  without being quarantined; bypasses of `screen()`; trust-lane escalation (e.g. `untrusted`/`agent` text landing in the `user` lane);
  forging or silently breaking the integrity chain (`_audit`, `verify_integrity`); bypassing `protected` nodes;
  SQL injection; path traversal in vault/graphify import or export; command injection in subprocess calls;
  `setup.py` writing outside its intended config paths or with unsafe permissions (e.g. `graph.key` not 0600).
- Also in scope: the MCP JSON-RPC parser in `mcp_main` (malformed input causing crashes or wrong-tool execution).
- Least / out of scope: `shelf/` and the skill directories are prompt/markdown content, not executable code.
  Report them only if a file there executes code or is loaded by the engine in an unsafe way.

## How to exercise it
- `cd /src/memory && python3 -I test_hydra_graph.py` runs the full suite (stdlib only; temp HOME, DBs and vault per test).
- `python3 hydra_graph.py --help` lists the CLI. `python3 hydra_graph.py mcp` (see `main`) runs the stdio MCP server.
  Set `HOME` to a temp directory first.

## How you rate severity
- Critical: untrusted text becomes injected agent context with no quarantine, in a way that enables command execution
  or persistent instruction override; code execution from crafted vault, graphify or MCP input.
- High: bypassing `screen()` for a whole category of patterns; trust-lane escalation; forging the integrity chain undetected;
  rollback/protected-node bypass; path traversal writing files.
- Medium: one pattern evasion with limited impact; DoS from crafted input (crash, unbounded growth); info disclosure of local paths.
- Low: hardening gaps with no demonstrated path to the above.
- Per POISONING.md, false but innocuous facts passing the screen are by design and not a vulnerability.

## Anything to leave alone
- hydra-mem (`hydra_mem.py`) is not in this repository; do not report its absence.
- The intentional `git rev-parse` subprocess and the user-configured RAG worker subprocess are expected.
  Report them only if their arguments are attacker-influenced.
