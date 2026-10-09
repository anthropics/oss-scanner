# Threat model — gray-btw

https://github.com/vstaln/gray-btw

Side conversations inside a session - ask without hijacking the main thread.

gray-btw is a plugin for the [gray](https://github.com/vstaln/gray) agent harness. It side conversations inside a session - ask without hijacking the main thread.

## Untrusted input

Everything the plugin receives is attacker-influenced: tool arguments are chosen by a model that may have ingested hostile content (webpages, files, prompt injections), and any data the plugin fetches (HTTP APIs, files, subprocess output, other MCP/tool results) is untrusted on the way back in. The plugin runs inside or alongside the agent process with the user's privileges and may handle credentials or session data.

## In scope

- Command/path injection: model-controlled strings reaching `bash`, filesystem paths, URLs, SQL, or subprocess arguments.
- Exfiltration: secrets, tokens, session content or file contents sent to endpoints the user didn't approve; sensitive data written into logs/transcripts a model can read back.
- Approval/boundary bypass: actions that should need confirmation running without it; reads or writes outside the workspace.
- Unsafe parsing: deserialization of model/plugin/network-controlled data, template/glob expansion, regexes on hostile input (ReDoS).

## Out of scope

- The gray core harness, model providers, and issues requiring the user to run attacker-supplied binaries.
## Severity calibration

Rate by real-world impact to the user running this code:
- **Critical**: remote/unauthenticated code execution, credential or token exfiltration, silent data loss.
- **High**: code execution or file writes the user didn't ask for, auth/sandbox/permission bypasses, secrets leaked into logs or transcripts.
- **Medium**: scoped data corruption, denial of service, issues needing user interaction to trigger.
- **Low**: cosmetic, recoverable, or purely theoretical issues.

Reports with a reproducer and a proposed patch are the most useful; theoretical findings without a concrete attack path are low value.
