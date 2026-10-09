# Threat model: Ekubo Protocol EVM contracts

## What this project does and where untrusted input enters
Ekubo is an AMM deployed on Ethereum mainnet and several L2s. `src/Core.sol` is an ownerless,
permissionless singleton that holds every pool's tokens and state. Callers acquire a lock
(`FlashAccountant`), perform any sequence of swaps, position updates and transfers, and must settle
all token deltas to zero before the lock releases.

Assume every external caller is an attacker: anyone can initialize a pool with any token pair, any
fee/tick spacing and any extension address, lock Core, call any public function, deploy their own
extension, and choose token contracts. Tokens are arbitrary ERC-20s (including malicious or
reentrant ones); native ETH is supported. Calls into Core happen via the lock callback, so reentrancy
and callback ordering are part of the attack surface.

## Components that matter most / least
Highest priority (holds or accounts for user funds):
- `src/Core.sol`, `src/base/FlashAccountant.sol`: solvency, delta accounting, lock/forward logic,
  saved balances, tick/liquidity bookkeeping, fee growth, protocol fees.
- `src/math/**`, `src/libraries/**`, `src/types/**`: sqrt-price/tick math, liquidity/amount
  rounding, packed storage types. Rounding must always favour the pool.
- `src/Positions.sol`, `src/base/BasePositions.sol`, `src/Orders.sol`, `src/FreePositions.sol`,
  `src/FreeLP.sol`: NFT-owned liquidity and TWAMM orders; authorization of who can withdraw/collect.
- `src/extensions/**` (TWAMM, Oracle, MEVCapture, BoostedFees, SignedExclusiveSwap, Ve33) and
  `src/VeToken.sol`, `src/Ve33*.sol`: extension hooks run inside Core's lock.
- `src/Router.sol`, `src/base/BaseRouter.sol`: user-facing swap paths, slippage and recipients.
- `src/Auctions.sol`, `src/Incentives.sol`, `src/TokenWrapper*.sol`, `src/SavedBalancesWrapper.sol`,
  `src/PositionsRevenueBuybacks.sol`, `src/base/RevenueBuybacks.sol`, `src/ManualPoolBooster.sol`.

Lower priority: `src/lens/**` (read-only quoters/data fetchers), `src/*Metadata*.sol` and other
token-URI renderers, `script/**`.

Out of scope: `lib/**` (forge-std, solady), `test/**`, `broadcast/**`, `snapshots/**`.

## Trust assumptions
- Core has no owner and no upgrade path. Owned periphery contracts (e.g. Positions, Orders) are
  owned by Ekubo governance; owner powers are trusted, but report any owner path that can reach
  user principal.
- An extension can only affect pools that opted into it. A malicious extension draining its *own*
  pool is expected; a malicious extension or token affecting *other* pools or Core's balances of
  other tokens is critical.
- Non-standard tokens (fee-on-transfer, rebasing, blocklists): losses confined to LPs of pools that
  use such a token are at most medium. Anything letting such a token take value from other pools,
  or from Core's balance of a different token, is critical.
- Gas griefing that only costs the attacker gas is out of scope.

## How to exercise it
- `forge build` and `forge test --offline` (run with `--offline`; dependencies are vendored).
  `test/FullTest.sol` has a base fixture with Core, Positions, Router and extensions deployed.
- Invariant suites: `test/SolvencyInvariantTest.t.sol`, `test/TWAMMInvariantTest.t.sol`.
- Proofs of concept are most useful as a new Foundry test extending `FullTest`.

## How we rate severity
- Critical: theft or permanent freezing of user or protocol funds held by Core, Positions, Orders
  or any extension; breaking Core solvency (Core owes more of a token than it holds); minting
  liquidity/fees/position value without paying for it.
- High: theft of unclaimed fees or yield; temporary freezing of funds (> 1 day); oracle or TWAMM
  price manipulation materially cheaper than the intended cost; Router paying the wrong recipient or
  ignoring slippage bounds.
- Medium: rounding errors in the attacker's favour that are economically small or need unusual
  preconditions; griefing that blocks a specific pool or position for a bounded time.
- Low: view/lens inaccuracies, event errors, metadata rendering bugs, owner-only misconfiguration.

## How we would like reports and patches
- One root cause per report, with a self-contained Foundry test as the reproducer.
- Patches should be minimal and keep storage layout and gas usage close to the current code; note
  any gas snapshot impact (`forge snapshot --offline`).
- Group issues sharing a root cause across contracts into one report.

## Anything to leave alone
- Known design decisions: any address can create pools with arbitrary tokens and extensions; the
  `audits/` folder lists prior findings already fixed or acknowledged.
- Compiler warnings suppressed by `ignored_error_codes` in `foundry.toml`.
