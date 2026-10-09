# Threat model: Ekubo MCP server

## What this project does and where untrusted input enters
This is a public, stateless MCP server on Cloudflare Workers. AI agents call its tools to
discover tokens, pools and positions and to get **unsigned** transaction plans (ERC-8410
execution plans and artifact references) for Ekubo and other protocols (Aave, Morpho, Sky,
Lido, Merkl, Aerodrome, Uniswap, Safe, and the Across/LayerZero/LI.FI bridges). Wallets
such as Ekubo Cloud Wallet simulate the plans and have users sign them.

Untrusted input comes from:
- all MCP tool arguments, since agents may be prompt-injected or malicious;
- upstream API responses (Ekubo API and quoter, 0x, bridge aggregators, protocol APIs)
  and RPC results. Treat these as possibly compromised or spoofed;
- token metadata such as names and symbols, which is attacker-chosen.

## Components that matter most
- Transaction construction: any plan whose calldata, target, value, recipient, spender,
  approval amount, slippage bound or deadline differs from what the tool's inputs and
  description promise. Examples are an unlimited approval to an unexpected spender, a
  recipient taken from upstream data instead of the user, or a missing minimum-out.
  `src/execution-plan.ts`, `src/core.ts`, `src/swap-deadline.ts`, `src/transfers.ts`, `src/positions.ts`,
  `src/orders.ts`, `src/ve33.ts`, `src/safe.ts`, `src/allowance-reset.ts`, and the
  per-protocol modules.
- Artifact store and references: integrity binding, tampering, cross-request confusion,
  and SSRF through URLs.
- Output that agents read as instructions (prompt injection through token names or
  upstream text into tool results).
- Rate limiting, request size and expensive-call DoS on the public Worker.
- Jurisdiction and restricted-token metadata (`src/jurisdiction-policy.json`,
  `src/token-restrictions.ts`) being silently wrong or missing.

Out of scope: `test/**`, `docs/**`, `skills/**`, `script/**`, generated
`contracts.generated.json` (report a wrong address as a construction bug instead).

## How to exercise it
Run `bun run test`. Most modules expose pure builders that can be tested with fixtures. Put
reproducers as `bun test` cases under `test/`.

## How we rate severity
- Critical: a plan that sends user funds or approvals to an attacker-chosen address when
  the inputs did not ask for it, or remote code execution or secret disclosure from the
  Worker.
- High: missing or ineffective slippage, deadline or minimum-out; wrong chain or contract
  address; artifact-integrity bypass; SSRF.
- Medium: prompt-injection vectors in tool output; public DoS; wrong but non-exploitable
  read data.
- Low: schema and doc mismatches.
