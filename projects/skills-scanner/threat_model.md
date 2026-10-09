# Threat model: skills-scanner (`skillscan`)

## What this project does and where untrusted input enters

`skillscan` is a security scanner for AI agent tooling. It walks a developer's machine or a repository, discovers
skill bundles, MCP server configs, hooks, slash commands, agent definitions and harness files for Claude Code,
Claude Desktop, Cursor, Windsurf, Cline, Codex CLI and Gemini CLI, runs a rule engine over them, and emits JSON,
SARIF, Markdown or an HTML dashboard. It can also post results to SIEMs, alerting services and the HTS-ASPM
platform.

The scanner is run by a defender against content that is assumed hostile. Every artifact it reads is attacker
controlled, because the whole point is to find malicious or poisoned skills. Untrusted input enters through:

- `SKILL.md` files and their YAML-ish frontmatter (`src/skillscan/parse/skill_md.py`), including name,
  description, `allowed-tools` and every bundled file beside them.
- MCP server JSON configs found by `src/skillscan/discover/mcp.py` (`.mcp.json`, `claude_desktop_config.json`,
  `~/.cursor/mcp.json` and the other per-host locations listed in that module's docstring), and the
  `settings.json`, agent and command files found by `src/skillscan/discover/claude.py`.
- Bundled Python and JavaScript source inside a skill, which `src/skillscan/rules/deep_scan.py` and
  `deep_scan_js.py` parse with `ast` and regexes. These files must only ever be parsed, never imported or run.
- Bundled `.pyc` files inspected by `src/skillscan/rules/bytecode.py`.
- Marketplace reputation JSON (`src/skillscan/marketplace/reputation.py`) and allowlist JSON
  (`src/skillscan/allowlist.py`).
- YARA rule files, when the optional `yara-python` extension is installed (`src/skillscan/rules/yara_pack.py`).
- The local SQLite scan store (`src/skillscan/store.py`) used for drift detection between runs.
- Responses from outbound services when configured: VirusTotal (`src/skillscan/integrations/virustotal.py`) and
  the optional Anthropic-backed judge (`src/skillscan/rules/nl_judge.py`).

Attacker goals worth modelling: get the scanner to execute code from a skill it is analysing, make the scanner
read or exfiltrate files outside the scan root, crash or hang the scanner so a malicious skill is never reported,
hide a finding (bypass a rule the scanner claims to implement), or smuggle markup through a reporter so the
dashboard or SARIF consumer executes it.

## Components that matter most and least

Most important:

- `src/skillscan/parse/`, `src/skillscan/discover/`, `src/skillscan/rules/` (the parsers and rule engine that
  touch attacker-controlled bytes), in particular `deep_scan.py`, `deep_scan_js.py`, `bytecode.py`, `hidden.py`,
  `secrets.py`, `static.py`, `mcp.py` and `yara_pack.py`.
- `src/skillscan/reporters/` and `src/skillscan/dashboard.py`, which embed attacker-controlled strings
  (skill names, descriptions, file paths) into Markdown, SARIF JSON and HTML. Stored XSS in the dashboard, or
  escaping bugs that let a skill rewrite its own finding, are in scope.
- `src/skillscan/store.py` (SQLite) and `src/skillscan/allowlist.py`: path handling and the trust decisions
  derived from them.
- `src/skillscan/cli.py`: argument handling, the `scan`, `inventory`, `dashboard`, `push` and `agent`
  subcommands, and anything that turns a CLI flag into a filesystem path.

Lower priority or out of scope:

- `src/skillscan/alerts/`, `src/skillscan/siem/`, `src/skillscan/hts_aspm/`, `src/skillscan/fleet/`: outbound
  integrations that only send data to operator-configured endpoints with operator-supplied credentials. In scope
  only where attacker-controlled scan content can change the destination, leak the credential, or inject into
  the payload format.
- `src/skillscan/visualizer/`: rendering helpers; same XSS concern as the dashboard, otherwise low value.
- `examples/`, `docs/`, `tests/`: not shipped. The test fixtures intentionally contain fake secrets and
  deliberately malicious-looking skills.
- The `nl_judge` rule is off by default and needs an API key; bugs reachable only with `--judge` are lower
  severity than the same bug in the default path.

## How to exercise it

- The checkout is `/src`; the package is installed in editable mode from `/src/src/skillscan` and `skillscan`
  is on `PATH`. Python 3.12. There are no runtime dependencies; `yara-python` is installed if its wheel was
  available at build time.
- Unit tests (152 at the time of writing, all offline):

```sh
cd /src && python -m unittest discover -s tests
```

- `skillscan demo` plants a small deliberately vulnerable project in a temp dir and scans it. It is the fastest
  end-to-end reproducer.
- To reproduce against a crafted skill, create `<dir>/.claude/skills/<name>/SKILL.md` plus any bundled files,
  or `<dir>/.mcp.json`, and run:

```sh
skillscan scan <dir> --no-user-global --format json
skillscan scan <dir> --no-user-global --format sarif
skillscan dashboard <dir> --no-user-global --output /tmp/report.html
```

`--no-user-global` keeps a reproducer confined to `<dir>` instead of also walking `~/.claude`, `~/.cursor` and
the other per-user locations.

- `skillscan inventory <dir>` runs discovery only, without the rule engine, which isolates parser bugs from rule
  bugs.
- Good fixtures to start from live in `tests/` (`test_rules.py`, `test_deep_collusion.py`, `test_smoke.py`).

## How you rate severity

- **Critical**: a skill, MCP config or bundled file causes `skillscan` to execute attacker code (import, eval,
  deserialization, shell), or to write outside its output paths, in the default `scan` invocation.
- **High**: reading files outside the scan root through a crafted path; a reliable crash or unbounded hang
  (e.g. catastrophic regex backtracking, decompression or recursion) triggered by a single artifact, because a
  scanner that dies on a malicious skill fails open; stored XSS in the HTML dashboard from skill content; a
  bypass that lets content a documented rule is meant to catch pass silently (for example a `curl | bash`
  dropper or a hidden Unicode payload the `hidden` rule should flag).
- **Medium**: the same crash or bypass when it needs a non-default flag (`--judge`, YARA packs, `agent` mode);
  injection into SARIF or Markdown output that a downstream tool would misinterpret; leaking an operator
  credential into a report.
- **Low**: false positives, cosmetic output issues, and rule gaps that are not claimed by the documentation.
- Denial of service that needs an artifact larger than a few megabytes, or more than a few seconds of CPU on a
  single file, is low unless it is super-linear.

## Anything to leave alone

- Do not report that `skillscan` reads files all over the home directory: discovery of `~/.claude`,
  `~/.cursor` and similar is its purpose and runs as the invoking user.
- Do not report the fake secrets, wildcard `allowed-tools` or `curl | bash` strings in `tests/`, `examples/`
  or the output of `skillscan demo`; they are intentional fixtures.
- Outbound HTTP in `alerts/`, `siem/`, `integrations/` and `hts_aspm/` uses operator-configured URLs and
  tokens; reporting that these send data to the configured endpoint is not a finding.
- Reports go to `vasanth@hts.consulting`. A proposed patch as a unified diff against `main` is most useful.
