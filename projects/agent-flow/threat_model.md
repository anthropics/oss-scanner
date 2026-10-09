# Threat model

## What this project does and where untrusted input enters
agent-flow (`@drix10/agent-flow` on npm) sits between autonomous coding agents (Claude Code, Pi, Codex, Gemini CLI,
OpenCode) and a git repository. Its core is a **guard**: a pre-tool hook that decides whether an agent's tool call
(file write, shell command, read, MCP call) is allowed, plus a pre-commit hook, a state machine for an
implement → review → QA pipeline, and a read-only MCP server. `SECURITY.md` in the repo lists every security claim
and the test that backs it; please read it first.

Treat the **agent as the attacker**. Untrusted input enters through:
- Hook input JSON on stdin (`bin/agent-flow.js`, `extensions/lib/guard.ts`): tool name, file paths, shell command
  text, MCP arguments — all chosen by a model that may be prompt-injected.
- Repository content the agent can write: `.agent-flow/` manifest files, `AGENTS.md`, branch names, git refs,
  symlinks, file names (`extensions/lib/manifest.ts`, `fsutil.ts`, `git.ts`).
- MCP tool arguments (`extensions/lib/mcp.ts`), CLI arguments, and diffs scanned for secrets (`risk.ts`).

## Components that matter most / least
- Most: `extensions/lib/guard.ts`, `denycmd.ts`, `fsutil.ts` (`resolveInside`), `git.ts`, `state.ts`, `audit.ts`,
  `mcp.ts`, `uninstall.ts`, `bin/agent-flow.js`. Note these are the `.ts` sources; `.js` beside them is build output.
- Least: `skills/`, `prompts/`, `docs/` (Markdown instructions), `templates/`, `scripts/`, `tests/`.

## How to exercise it
- `npm test` (node --test) runs everything against real git repos in temp dirs. `tests/redteam/corpus.json` holds
  blocked, allowed and documented-gap guard cases; `tests/guard.test.js` and `tests/hardening.test.js` show how to
  feed the guard a tool call.
- The CLI is linked as `agent-flow` (try `agent-flow --help`, `agent-flow guard`, `agent-flow mcp`).

## How you rate severity
- Critical: a bypass of an **Enforced** claim in SECURITY.md that lets a pipeline role write a protected path or
  trust file (`.agent-state.json`, `.agent-flow/audit.jsonl`, `.git/`), escape `AGENT_FLOW_WORKTREE` through file
  tools, or get arbitrary command execution from crafted repo content, hook input or MCP arguments.
- High: a read-only role (reviewer, QA) can write through file tools; the guard fails open (allows) on malformed
  or missing input where protection is configured; secret values get printed or written; the audit chain can be
  forged without detection against an anchored head.
- Medium: a bypass of a **Best-effort** shell check using plain shell syntax the guard claims to handle (a write
  verb, redirect, `cd`, `sh -c`, git flag abbreviation) that is not listed as a known gap.
- Low: denial of service of the CLI or hook (it hangs or crashes on input), unless it makes the guard allow a call.

## Anything to leave alone
- Gaps SECURITY.md already admits: anything run inside an interpreter (`python -c`, `node -e`, a script file) or
  behind a shell variable; recursive `grep -r` reaching an env file; harnesses listed as "Instructed only".
- A human bypassing hooks on purpose (`--no-verify`, `AGENT_FLOW_ALLOW_PROTECTED=1`, `AGENT_FLOW_ALLOW_SECRET_READ=1`).
- `.reference/` and `plan/` are untracked local folders, not part of the project.
