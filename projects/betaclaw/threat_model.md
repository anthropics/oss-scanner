# BetaClaw threat model

BetaClaw Gateway is a self-hosted, multi-channel AI platform with a web/API and WebSocket control plane, persistent conversations and memory, provider and channel integrations, and configurable agent tools.

## Trust boundaries

- The deployment operator is trusted to configure and administer the instance. The documented Compose setup binds the app to host loopback by default; operators may expose it through an HTTPS reverse proxy.
- Incoming web/API and WebSocket requests, channel webhook payloads, conversation content, attachments, imported configuration, skills, and external provider responses are untrusted.
- Command/tool approvals are policy controls, not a sandbox for untrusted code. Assess whether untrusted input can bypass authentication, authorization, approval, or other documented boundaries.

## Assets

- Authentication/session state and administrative access.
- Model-provider and channel credentials, encryption keys, and webhook secrets.
- Conversation history, attachments, persistent memory, and operator workspaces.
- Integrity of agent tool execution, automation, and channel integrations.

## Findings to prioritize

Prioritize remotely reachable authentication or authorization bypasses; unintended access to another user's or operator's data; credential or secret disclosure; webhook verification bypass; and command/code execution reachable by an unauthenticated or lower-privileged attacker. Include concrete attack paths and distinguish default loopback deployments from deployments exposed through a reverse proxy.

Report lower-impact authenticated issues and denial-of-service cases when they have a practical impact. Do not treat the documented absence of a sandbox for untrusted code as a vulnerability by itself; report paths that cross the stated trust boundaries or contradict the documented approval and authorization controls.
