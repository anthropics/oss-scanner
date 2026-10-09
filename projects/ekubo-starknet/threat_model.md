# Threat model: Ekubo Protocol Starknet contracts

## What this project does and where untrusted input enters
Ekubo is an AMM on Starknet. `src/core.cairo` is a singleton that holds every pool's tokens and
state. Callers lock Core, perform swaps, position updates, withdrawals and payments through a
callback, and must settle all per-token deltas before the lock is released.

Assume every external caller is an attacker. Anyone can initialize pools with any token pair, fee,
tick spacing and extension address, lock Core, deploy their own extension, and supply token
contracts that are malicious or reentrant.

## Components that matter most / least
Highest priority, because these hold or account for user funds:
- `src/core.cairo`: lock/delta accounting, `pay`/`withdraw`, saved balances, tick and liquidity
  bookkeeping, fee growth, protocol fee collection.
- `src/math/**` and `src/types/**`: sqrt-ratio/tick math, `muldiv`, liquidity and amount
  rounding, `i129`, and packed types. Rounding must always favour the pool.
- `src/positions.cairo` and `src/owned_nft.cairo`: NFT-owned liquidity and authorization of who may
  withdraw or collect.
- `src/extensions/**` (TWAMM, limit orders, oracle): extension hooks run inside Core's lock.
- `src/router.cairo`: user swap paths, slippage and recipients.
- `src/revenue_buybacks.cairo` and `src/streamed_payment.cairo`.
- `src/components/upgradeable.cairo` and `src/components/owned.cairo`: access control on upgrade
  and owner functions.

Lower priority: `src/lens/**` (read-only helpers), `src/math/string.cairo`.

Out of scope: `src/tests/**`, `scripts/**`. `packages/ekubo_swap_anonymizer` is a separate
package and in scope at medium priority.

## Trust assumptions
- Contract owners (Ekubo governance) are trusted to upgrade and configure. Any path by which a
  non-owner reaches an owner-only or upgrade function is critical.
- An extension can only affect pools that opted into it. An extension or token that affects other
  pools, or Core's balances of other tokens, is critical.
- Losses that only hit LPs of a pool using a non-standard or malicious token are at most medium.

## How to exercise it
- Run `scarb build` and `snforge test`. Tests live under `src/tests/**`, and that is where a
  reproducer should go (snforge test).

## How we rate severity
- Critical: theft or permanent freezing of funds held by Core, Positions or an extension;
  breaking Core solvency; minting liquidity, fees or position value without paying for it;
  unauthorized upgrade or ownership change.
- High: theft of unclaimed fees or TWAMM/limit-order proceeds; freezing funds for more than a day;
  manipulating oracle or TWAMM prices materially more cheaply than intended; Router ignoring
  slippage or paying the wrong recipient.
- Medium: rounding in the attacker's favour that is economically small or needs unusual
  preconditions; bounded griefing of a single pool or position.
- Low: lens inaccuracies, event errors, owner-only misconfiguration.

## How we would like reports and patches
- One root cause per report, with a self-contained snforge test as the reproducer.
- Minimal patches that preserve storage layout, because these contracts are upgradeable.
