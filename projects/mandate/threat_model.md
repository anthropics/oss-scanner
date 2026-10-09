# Threat model: Mandate

## What this project does and where untrusted input enters

Mandate is an open-source economic layer for AI agents: one account to earn,
hold, move, spend, and reinvest money across interchangeable financial
providers (Stripe, Coinbase CDP wallets, Lithic cards, bank rails). Mandate
itself never holds or issues money; it brokers provider credentials and keeps
an encrypted double-entry ledger of what moved where.

Untrusted input enters at four boundaries:

1. The MCP server (`packages/mcp`, stdio): tool calls from AI agents. Agents
   are the primary untrusted principal; a compromised, confused, or malicious
   agent must not be able to exceed the spending mandate it was given.
2. The `mandated` daemon HTTP API (Rust/axum, localhost): requests from the
   CLI and the React dashboard. Treat every caller as potentially hostile,
   even on loopback.
3. Provider integrations (`providers/*` via `packages/provider-sdk`): API
   responses, webhooks, and callbacks from Stripe, Lithic, and Coinbase are
   untrusted. A provider returning unexpected data must not corrupt the ledger
   or trigger unintended transfers.
4. The `mandate` CLI: argv and config files controlled by whoever runs it.

## Components that matter most / least

Most: `rust/mandated` (daemon; holds provider credentials and the
SQLCipher-encrypted ledger), `rust/mandate-core` (ledger invariants,
double-entry accounting), `packages/mcp` (the agent-facing tool surface:
spend/transfer tools), `packages/provider-sdk` and `providers/*` (real money
movement). Next: `rust/mandate` CLI.

Less: `web/` (localhost dashboard, display only). Out of scope: `video/`
(marketing render scripts), `docs/`, `qa-learnings/`, `integrations/` sample
assets.

## How to exercise it

- Rust: `cargo build --locked --workspace` produces `target/debug/mandated`
  (daemon) and `target/debug/mandate` (CLI); `cargo test --locked --workspace`
  runs the unit tests.
- TypeScript: `pnpm install --frozen-lockfile && pnpm -r --if-present build`;
  the MCP server runs as `node packages/mcp/dist/index.js`; tests via
  `pnpm -r --if-present test` (web uses vitest, the rest use node --test).
- The daemon stores its encrypted ledger under the configured data directory;
  provider credentials come from environment/config, never from the repo.

## How you rate severity

This is money-moving infrastructure, so the bar is high where funds or
credentials are involved:

- Critical: any unauthorized transfer or spend; ledger tampering or balance
  forgery; exfiltration of provider API keys, wallet keys, or the ledger
  encryption key; authentication bypass that lets one agent act as another.
- High: stored-data exfiltration through the dashboard or MCP surface; SSRF
  or command injection reachable from agent tool calls; auth bypass on daemon
  endpoints that does not directly move money.
- Medium: denial of service against the local daemon; information disclosure
  that does not include credentials or balances.
- Low: missing input validation with no demonstrated money or credential
  impact.

Memory-safety issues in the Rust daemon are high at minimum; if the
corruption is attacker-controlled and reachable from the MCP or HTTP surface,
rate it critical.

## Anything to leave alone

- Do not report the daemon listening on localhost without TLS; that is the
  intended deployment shape for a single-user local daemon.
- Do not report missing rate limiting on the MCP stdio transport; the
  transport is a local pipe, not a network service.
