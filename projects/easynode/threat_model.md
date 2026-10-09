# EasyNode Security Threat Model

## 1. Project overview

EasyNode (https://github.com/chaos-zhu/easynode) is a self-hosted management panel for Linux and Windows servers. It offers browser-based SSH and SFTP, remote command execution, bulk operations, stored server credentials, scripts, Docker administration, and AI-assisted operations. The repository includes a Koa.js/Node.js server (`server/`), Vue-based web interface (`web/`), and Flutter native clients (`native/`).

A vulnerability in EasyNode can have consequences beyond the panel itself: the application may be entrusted with powerful credentials and remote administrative access to multiple machines. Please treat the ability to cross from a low-privilege or unauthenticated context into these operations as the primary security risk.

This document describes security goals and review priorities, not a claim that all described safeguards have already been implemented. Determine actual security behavior from code and tests.

## 2. Assets and security objectives

Protect:
- Panel administrator accounts, passwords, MFA secrets, sessions, and API authorization state.
- SSH private keys, passwords, tokens, remote server connection profiles, and other stored secrets.
- Remote hosts and their files, processes, Docker resources, and command-execution capabilities.
- Uploaded/downloaded files, scripts, backups, logs, and configuration records.
- AI provider API keys, prompts, conversation history, and tool-execution permissions (where supported).
- Tenant/user boundaries, if present in the implementation; do not assume multi-tenancy without evidence.

Security goals:
1. No unauthenticated user should obtain administrative functionality, sensitive configuration, or remote-host access.
2. Every HTTP, WebSocket, and Socket.IO operation must enforce appropriate authentication and authorization independently of UI restrictions.
3. One session or connection must not access another's SSH/SFTP channels, files, messages, or credentials.
4. User-controlled inputs must not cause unintended local shell execution, filesystem access, or remote commands.
5. Secrets must not leak through APIs, logs, error messages, bundles, or insecure transport.
6. AI-generated or untrusted text must not bypass the authorization required for privileged tools.

## 3. Entry points and trust boundaries

### Public or lower-trust interfaces
- HTTP(S) REST endpoints, including authentication, bootstrap, and account-management routes.
- WebSocket / Socket.IO events and long-lived SSH terminal sessions.
- WebSFTP file paths, uploads, downloads, filenames, archives, and metadata.
- Import/export of host profiles, credentials, and scripts.
- Web UI and native-client requests, browser-stored data, and cross-origin interactions.
- Incoming remote-host output (SSH stdout/stderr, filenames, terminal escape sequences).
- AI prompts, external model responses, tool parameters, retrieved content, and remote command output.

### Trust boundaries
1. Internet or LAN client -> EasyNode HTTP and WebSocket handlers.
2. Authenticated panel session -> privileged panel operations and stored credentials.
3. EasyNode backend -> remote SSH/SFTP/RDP/Docker/other host services.
4. Remote server-controlled bytes -> backend parsers and browser/native renderers.
5. AI model / untrusted context -> tool execution and privileged host operations.
6. Persistent database / config / logs -> application responses and diagnostic output.

## 4. High-priority vulnerability classes

### Authentication and sessions
- Authentication bypass, unintended public endpoints, weak default credentials, password reset and MFA bypass.
- Session fixation, incorrect expiration or invalidation, forged or predictable session tokens, missing cookie flags.
- CSRF, CORS and origin validation problems; WebSocket authentication at handshake and per sensitive event.
- Broken rate limits or other remotely exploitable weaknesses affecting login or recovery.

### Authorization and isolation
- IDOR/BOLA in server, credential, script, task, session, and file identifiers.
- Access-control discrepancies between REST routes, Socket.IO handlers, UI and native clients.
- Cross-session SSH stream hijack, terminal control, host confusion, and unauthorized command execution.
- Improper privilege checks during import/export, bulk operations, and destructive actions.

### Command, path and parser injection
- Local OS command injection via hostnames, ports, paths, shell parameters, scripts, diagnostic utilities or Docker commands.
- Remote command injection where an attacker controls parameters outside the intended remote-host trust boundary.
- SFTP directory traversal, unsafe path joining, symlink handling, arbitrary file read/write and archive extraction.
- SSRF or network pivoting from user-controlled target addresses, if those actions exceed the intended and authorized host-management scope.
- Prototype pollution, unsafe deserialization, template injection, and unsafe parsing of imported content.

### Sensitive data and browser security
- Plaintext or recoverable secret exposure through unauthenticated/low-privilege endpoints.
- Leaks through logs, errors, exported configurations, client bundles or browser storage.
- Stored/reflected/DOM XSS, especially when displaying terminal output, logs, filenames, scripts or AI output.
- Unsafe HTTPS/proxy configuration and secret-bearing traffic exposed in transit.

### AI-assisted administration
- Prompt injection causing unapproved privileged tool invocation, secret disclosure or command execution.
- Missing confirmation or authorization checks for destructive AI tools.
- Tool argument injection through model-produced commands, paths and host identifiers.
- Confusion between untrusted remote content and trusted system/developer instructions.

### Dependencies and deployment
- Exploitable dependency vulnerabilities with concrete reachability from EasyNode's features.
- Dangerous production defaults, exposure of internal services, leaked setup credentials or writable sensitive files.

## 5. Severity guidance

Use impact and realistic attack prerequisites, not CVSS alone. Provide a suggested severity plus the exact privilege, configuration and interaction required.

- **Critical**: Internet-reachable unauthenticated RCE on the panel or on managed hosts; unauthenticated disclosure of a broadly useful set of managed-host credentials; authentication bypass granting full panel administration; or a remotely exploitable flaw allowing broad compromise of managed infrastructure with minimal prerequisites.
- **High**: Authenticated low-privilege escalation to administrator or another user's servers; remote command execution without the required authorization; sensitive credential disclosure; arbitrary local file access with high-impact targets; exploitable stored XSS that plausibly compromises an administrator session; or CSRF leading to privileged remote-server commands under realistic conditions.
- **Medium**: Scoped information disclosure, meaningful but limited authorization bypass, exploitable CSRF/XSS with constrained impact, or injection requiring substantial privileges or unusual configuration.
- **Low**: Security-hardening issues with limited practical exploitability; no direct secret exposure or meaningful privilege boundary crossing.

If the deployment model only has a single administrator, do not invent low-privilege roles. Distinguish (a) an unauthenticated internet attacker, (b) an authenticated panel administrator, (c) an attacker controlling a managed SSH host, and (d) an attacker controlling content rendered by the UI. A panel admin intentionally running commands on an owned host is not by itself a vulnerability.

## 6. Scope and exclusions

Focus on the repository's first-party code and realistically reachable behavior. Review `server/` first, then `web/`, followed by security-relevant `native/` code. Review deployment scripts and configuration when a defect creates a real exposure.

Do not report expected administrative capabilities as vulnerabilities without an unintended trust-boundary crossing. Do not perform scanning against real hosts, production deployments, or third-party services. Use synthetic accounts, test keys, local mocks, and container-local services. Avoid destructive commands and any attempt to exfiltrate real secrets.

Exclude speculative dependency CVEs with no reachable attack path unless the affected package and relevant code path are clearly identified.

## 7. Report and patch expectations

For each finding, provide:
1. Exact source file(s), line references, and relevant call or event path.
2. Entry point, attacker control, required privileges, security boundary crossed, and impact.
3. Minimal, safe, reproducible proof of concept, preferably an automated test using local fixtures or mocks.
4. Clear reproduction conditions, including relevant authentication state and deployment configuration.
5. A minimal patch consistent with the existing architecture and backward-compatibility constraints.
6. Regression tests covering the exploit and permitted behavior.
7. A severity assessment and notes on any uncertainty or unverified assumptions.

Prefer independently verifiable, high-confidence findings over large numbers of speculative findings. Where the build or test environment blocks dynamic verification, explicitly label the finding as not dynamically verified.
