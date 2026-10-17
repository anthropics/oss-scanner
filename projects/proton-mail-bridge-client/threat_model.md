# Threat model

## What this project does and where untrusted input enters
Proton Mail Bridge Client is an MCP server and CLI (TypeScript, Node 24) that lets an AI assistant read and send mail through a local Proton Mail Bridge over IMAP/SMTP, with a local SQLite index. Entry points to treat as untrusted:
- Received mail: headers, HTML and plain bodies, attachments, calendar invitations (`.ics`, parsed by `src/utils/ical-reply.ts`), `List-Unsubscribe` headers, Message-ID / References chains. The sender is an attacker.
- MCP tool arguments: they come from a language model that may itself have been steered by hostile mail (prompt injection). The policy gates in `src/utils/runtime-policy.ts` (read-only mode, send/destructive confirmation, outbound recipient restriction) are the security boundary for this path.
- Files the user points tools at (attachment save paths, import/export).

## Components that matter most / least
Most: policy gates and everything that sends mail or changes/deletes mailbox state; parsing of received content (HTML to Markdown, iCalendar, address and header parsing, attachment handling, file path handling for saved attachments); the multi-account routing (an id prefix selects the account, so one account must never act on another's behalf); local stores (credentials never in logs or results; `~/.proton-mail-bridge-client` files).
Least: the CLI formatting code, the shell completion generator, scripts under `scripts/` and `src/scripts/` used for releases and setup. Out of scope: Proton Mail Bridge itself, Proton's servers, the MCP SDK and other third-party dependencies (report them upstream), and the user's own machine being compromised.

## How to exercise it
`npm test` runs about a thousand offline tests with a stubbed IMAP/SMTP harness (`test/`); MCP tools can be called through the in-memory client used in `test/respond-to-invite.test.mjs` and `test/all-tools-dispatch.test.mjs`. There is no real mailbox in the image.

## How you rate severity
- Anything that makes the server send mail, delete mail or write files the user did not authorize (policy-gate bypass, cross-account action, path traversal on save, header or iCalendar injection that reaches a recipient) is high; critical if it needs no user interaction beyond receiving a message.
- Credential or mail-content disclosure to a third party is high.
- Denial of service from a single received message (ReDoS, unbounded memory) is medium.
- Issues that need local write access to the data directory, or a malicious Bridge, are low.

## Anything to leave alone
Do not report: the absence of authentication on stdio MCP transport (it is a local child process by design), the plain-text IMAP/SMTP connection to the local Bridge on 127.0.0.1 (that is how Bridge works), or missing rate limiting.
