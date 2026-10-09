# Threat model

## What this project does and where untrusted input enters
Nuclei is a template-based vulnerability scanner, shipped as a CLI (`cmd/nuclei`) and a Go SDK (`lib`). It runs on the operator's machine, or embedded in another service, and talks to targets the operator chose.

Untrusted:
- Everything a scanned target sends back, over every protocol: HTTP, DNS, TCP/network, TLS, WebSocket, WHOIS/RDAP, headless browser pages, and the JavaScript protocol libraries (SMB, LDAP, SSH, MySQL, Postgres, MSSQL, Oracle, Redis, RDP, Kerberos, SMTP, POP3, VNC, Telnet, rsync, IKEv2, gRPC, DCE/RPC, WMI and the rest of `pkg/js/libs`).
- Templates and workflows that are not signed by a trusted key, including those loaded from `-turl`/`-wurl`, custom template repositories, or the SDK. They must not run code (`code` protocol needs `-code` and a valid signature), read or write local files (gated by `-lfa`), read environment variables (gated by `-ev`), or escape the JS or headless sandbox.
- Interactsh server responses (the default OAST servers are third-party to the operator).
- Input files in non-list formats (`-im burp|openapi|swagger|yaml|json`): specs and traffic captures often come from third parties.
- Content fetched from custom template providers (GitHub, GitLab, S3, Azure Blob) and from template/engine updates.
- Uncover and other discovery results fed back in as targets.
- Requests reaching any listener nuclei opens: the DAST server (`-dts`, default `localhost:9055`, optional `-dtst` token), the DAST intercepting proxy (`-dtp`, default `127.0.0.1:9056`, auth required off loopback), and the HTTP API endpoint (`internal/httpapi`).
- Responses from the LLM provider used by `-llm` matchers, and any target data placed in LLM prompts.

Trusted: the operator's flags, config and profile files, secrets file (`-sf`), signed templates, and target lists.

## Components that matter most / least
- Template trust: loading and signature verification (`pkg/catalog`, `pkg/loader`, `pkg/templates`, `pkg/templates/signer`, `pkg/keys`), and the `-code`, `-lfa`, `-ev`, `-esc` and network-policy guards. These must hold on every load path: direct, workflow, DAST, flow/multi-protocol (`pkg/tmplexec`), template URLs, custom providers, and the SDK. A sibling path that skips a check is a real bug.
- Sandboxes: the JS runtime and its libraries (`pkg/js`), headless (`pkg/protocols/headless`, including `file://` and browser flags), and the DSL helpers.
- Protocol handlers and response processing: `pkg/protocols/*`, extractors and matchers (`pkg/operators`), including LLM matchers and prompt construction.
- Listeners: DAST server and proxy (`internal/server`), HTTP API (`internal/httpapi`). Unauthenticated actions, auth bypass, request smuggling into scans, or use as an open proxy are in scope.
- Input parsing (`pkg/input`, including `formats/*`) and fuzzing (`pkg/fuzz`).
- File writes from untrusted data: template install and update (`pkg/installer`, zip extraction), custom provider downloads, project files (`pkg/projectfile`), resume files, stored responses, output and exporters.
- Secrets handling: auth provider (`pkg/authprovider`) must only send credentials to the domains they are scoped to; reporting trackers (Jira, GitHub, GitLab, Gitea, Linear) and exporters (Elasticsearch, Splunk, MongoDB) must not leak their credentials; PDCP upload (`internal/pdcp`) must not leak the API key.
- Reporting output (`pkg/reporting`: Markdown, PDF, SARIF, JSON/JSONL, issue bodies): injection into those formats is in scope.
- SDK: state must not leak between engines or concurrent scans.
- Out of scope: `cmd/` tools other than `cmd/nuclei`, `internal/fuzzplayground` (deliberately vulnerable test server), `internal/tests`, and test fixtures.

## How to exercise it
- `nuclei` is in `/usr/local/bin`; public templates are in `~/.local/share/nuclei/nuclei-templates`. Spin up a local server in the container as the malicious target.
- For headless templates add `-system-chrome` to use the installed Chromium; otherwise nuclei tries to download a browser, which fails offline.
- `SECURITY_CONTEXT.md` at the repo root lists past fixes; do not report them again unless you find an unguarded variant.

## How you rate severity
- Critical: code execution on the nuclei host triggered by a scanned target, by an unsigned template without `-code`, by an input file, or by an unauthenticated request to a nuclei listener.
- High: bypass of signature verification, `-lfa`, `-ev` or network policy; arbitrary file read or write (including zip-slip) from untrusted input; SSRF past an operator-set allowlist; credentials (secrets file, tracker, exporter or PDCP keys) sent to an unrelated host; auth bypass on a nuclei listener.
- Medium: target-triggered crash, hang or unbounded memory/disk use; cross-scan or cross-engine data leaks in the SDK; injection into reports or issue trackers that executes in a viewer.
- Low: terminal escape or markup injection into console output; information leaks with no credential exposure.

## Anything to leave alone
- Signed templates, or `-code`/`-lfa`/`-ev`/`-esc`, behaving as designed once the operator opts in.
- Scanning internal hosts the operator listed as targets.
- Listeners the operator binds to a public address without the token or auth the flags offer.
- Vulnerabilities in third-party dependencies with no reachable path in nuclei.
