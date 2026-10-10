# Threat model

## What this project does and where untrusted input enters
Aeon is an autonomous agent framework that runs on GitHub Actions. An operator forks the repo, turns on skills (`skills/*/SKILL.md`) and schedules them in `aeon.yml`. Each run launches a coding-agent harness (Claude Code by default, via `harness-adapter/run-harness`) with the repo's secrets (model keys, `GH_TOKEN`/PAT, Telegram/Discord/Slack tokens, API keys). Hundreds of forks run it unattended, so a bug in canon reaches every fork.

Treat as untrusted:
- **Inbound chat messages** (`.github/workflows/messages.yml`, `apps/webhook/src/worker.js`): Telegram, Discord and Slack messages, slash commands, button callbacks and replies. Only the owner (`TELEGRAM_CHAT_ID` / `TELEGRAM_ALLOWED_USER_ID`, `DISCORD_ALLOWED_AUTHOR_ID`, `SLACK_ALLOWED_USER_ID`) may trigger work; other users in a group must be ignored. The webhook Worker checks a shared secret and a KV replay guard.
- **GitHub events**: `aeon.yml` runs on `issues: labeled`, `workflow_dispatch` and `repository_dispatch`. Issue titles and bodies, dispatch inputs and payloads are attacker-controlled when the repo is public.
- **Everything a skill fetches**: web pages, RSS, X posts, GitHub repos and issues, onchain data. It enters the agent's context, so prompt injection that escapes the capability mode is in scope.
- **Third-party skills and packs** installed with `bin/install-skill-pack` / `bin/add-skill`.
- **The local dashboard** (`apps/dashboard`, Next.js on localhost): its `/api/*` routes write GitHub secrets and dispatch workflows through `gh`. `proxy.ts` + `lib/security/api-gate.ts` gate them with a loopback Host allowlist and same-origin checks against DNS rebinding and cross-site requests.
- **The local MCP server** (`apps/mcp-server`, stdio) and the CLI (`apps/cli`).

## Components that matter most / least
- Most: the read-only capability mode (`scripts/skill_mode.sh`, `harness-adapter/lib/sandbox.sh`, bubblewrap) which must stop read-only skills from writing the repo, calling `gh` or committing; secret handling (`scripts/secretcurl.sh`, `scripts/skill_requires.sh`, anything that could print a secret to logs, outputs, commits or notifications); shell scripts that interpolate message or issue text (command injection, `${{ }}` expression injection in workflows); owner gating in `messages.yml` and the webhook; the dashboard API gate.
- Less: notification formatting (`scripts/notify_format.py`) beyond injection into Telegram HTML or links.
- Out of scope: `memory/`, `output/`, `soul/`, `docs/`, `catalog/` content, the contents of individual `SKILL.md` prompts (they are instructions, not code) unless a skill tells the agent to do something unsafe with secrets.

## How to exercise it
- Script tests: `bash scripts/tests/*.sh` and `python3 scripts/tests/test_notify_format.py` (CI runs these in `.github/workflows/ci-tests.yml`).
- Apps: `npm test` (dashboard + webhook), `npm run typecheck`, `npm --prefix apps/dashboard run dev` for the dashboard.
- Workflows can't run offline; review them statically. `scripts/dry-run.sh` walks the run path without a model.

## How you rate severity
- Critical: anyone other than the operator can run code or read secrets in a fork's Actions runs (for example through an issue, a dispatch payload or a group chat message); secret exfiltration through a canon script; RCE on the operator's machine through the dashboard or CLI.
- High: escape from read-only mode to repo writes, `gh` access or commits; owner-gate bypass that lets a non-owner trigger skills; dashboard API reachable cross-origin or via DNS rebinding; workflow expression or shell injection reachable from issue or message text.
- Medium: prompt injection from fetched content that makes a write-mode skill take an unintended repo action without reaching secrets; secrets leaking only into the operator's own private notifications.
- Low: DoS of a single run, notification formatting bugs, missing hardening.
- Bugs that need the operator's own token, a malicious skill the operator chose to install, or write access to the fork are low unless they reach other users.

## Anything to leave alone
- Write-mode skills having full repo access is by design.
- The webhook and dashboard are opt-in and self-deployed by each operator.
