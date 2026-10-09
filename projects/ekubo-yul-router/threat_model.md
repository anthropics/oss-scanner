# Threat model: Ekubo Yul router

## What this project does and where untrusted input enters
`src/YulRouter.yul` is a hand-written Yul swap router for Ekubo EVM `Core`, deployed in
production and used by the Ekubo interface and MCP server. It takes custom packed route
calldata (token addresses, pool configs, extension forwardees, token wrappers, an optional
recipient and an optional deadline), executes single and multi-hop swaps under one Core lock,
applies a slippage threshold, and settles. It can also be called through `Core.forward`
(execute without settling) and through `quote(bytes)` (execute, then revert with the result).

All calldata is attacker-controlled. Pools, extensions and tokens named in a route may be
malicious. Users hold token approvals to the router, or pay it native ETH, while a swap
executes.

## Components that matter most
- Payment and settlement: who pays (it must always be `msg.sender`), the amounts, native ETH
  handling and refunds, and the recipient. Any way to spend another user's approval or
  balance, or to leave value stranded in the router, is critical.
- Slippage and deadline enforcement, including the aggregate threshold across multi-hop
  splits and sign conventions for exact-in and exact-out.
- Calldata parsing: out-of-bounds reads, length confusion, and hop/token chaining
  mismatches.
- Callback authentication: only Core may call the lock/forward callback selectors, and the
  delegatecall guard must hold.
- `quote` revert-payload handling: a pool or extension must not be able to forge the
  router's result payload.
- `sdk/src`: the encoder must produce calldata that matches the user's intent, including
  the threshold, recipient and deadline.

Out of scope: `lib/**` (forge-std, solady; evm-contracts is reviewed separately), `test/**`,
`benchmarks/**`, `broadcast/**`, `snapshots/**`.

## How to exercise it
Run `forge test --offline` and `cd sdk && bun run test`. Reproducers are most useful as
Foundry tests.

## How we rate severity
- Critical: theft of user funds or approvals; executing with another user's payment; a
  bypass of callback authentication.
- High: a slippage or deadline bypass; paying the wrong recipient; stuck funds; an SDK
  encoding bug that produces an unbounded threshold or a wrong recipient.
- Medium: griefing or DoS of routes; incorrect quote results without fund loss.
- Low: gas inefficiencies and SDK type issues.
