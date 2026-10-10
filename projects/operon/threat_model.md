# Threat model for Operon

## What this project does and where untrusted input enters
Operon is a native cockpit and supervisor for AI coding agents (such as Claude Code, Codex CLI, and Antigravity CLI). It launches agent processes, manages tmux sessions, monitors running workloads, and ingests execution transcripts.

Untrusted or semi-trusted input enters through four main surfaces:
1. **Agent terminal streams & tmux output**: Text, escape sequences, and status updates emitted by running agent processes.
2. **Agent transcripts**: JSON and JSONL event logs produced by agent CLI runs or read from disk.
3. **Local configuration & project manifests**: User- or repo-supplied configuration files (`config.toml`, `.operon/`, workspace settings).
4. **Subprocess argument and environment handling**: Parameters passed to CLI executables, git commands, and tmux.

## Components that matter most / least
- **Critical scope**:
  - `src/exec.rs`: Process execution, argument escaping, and environment boundary handling.
  - `src/tmux.rs` & `src/tmux/hooks.rs`: Construction of tmux commands, socket handling, and config file editing.
  - `src/transcript.rs`: JSON/JSONL transcript parsing, log file resolution, and deserialization routines.
  - `src/config.rs` & storage (`rusqlite`): Database schema migrations, deserialization, and path resolution.
- **Out of scope**:
  - Pure UI styling and layout logic inside `src/ui/` (fonts, widget paddings, colors).
  - Physical access attacks or scenarios where an attacker already possesses full shell access as the local user.
  - Missing X11/Wayland display errors when running headlessly in CI or container environments.

## How to exercise it
- Run the full test suite with `cargo test --locked`.
- Specific unit tests for transcript ingestion, config parsing, and command generation can be targeted directly with `cargo test --locked <module_name>`.

## Severity rating
- **Critical**: Unintended command execution outside the designated agent process; path traversal allowing arbitrary file read/write outside the workspace/cache roots; exfiltration of API keys or environment secrets.
- **High**: Panics or hangs triggered by maliciously crafted transcripts, unescaped tmux command injection, or memory corruption in dependencies.
- **Medium**: Unbounded memory growth or CPU hangs when parsing large or malformed log streams (DoS).
- **Low**: Clean panics on clearly invalid internal state that do not cross security boundaries.

## Anything to leave alone
- Do not report display/renderer initialization errors that occur purely because no X11/Wayland display server is running.
- Do not report attacks that assume an untrusted local user already has full write permissions to the user's home directory.
