# Threat model — Origin Dollar (OUSD / OETH smart contracts)

## What this project does and where untrusted input enters

Solidity smart contracts for Origin's yield-bearing tokens, deployed on Ethereum mainnet, Base,
HyperEVM and Arbitrum. They custody user funds directly: a vulnerability can mean an immediate,
irreversible loss of on-chain assets.

- **OTokens** (`contracts/token/`): OUSD, OETH, OETHBase — rebasing ERC-20s with credits /
  `rebasingCreditsPerToken` accounting, rebase opt-in/opt-out and yield delegation
  (`README-token-logic.md` documents the account types and invariants). Wrapped ERC-4626 versions:
  `WrappedOusd`, `WOETH`, `WOETHBase`, `BridgedWOETH`.
- **Vaults** (`contracts/vault/`): `VaultCore` (user-facing: `mint`, `requestWithdrawal`,
  `claimWithdrawal(s)`, `rebase`, `allocate`, `addWithdrawalQueueLiquidity`) and `VaultAdmin`
  (privileged configuration). One implementation behind a proxy per token.
- **Strategies** (`contracts/strategies/`): deploy vault funds into external protocols — Morpho /
  ERC-4626, Curve / Aerodrome / Algebra / Hydrex AMOs (which mint and burn OTokens into a pool),
  native ETH staking with beacon-chain proofs (`NativeStaking/`, `contracts/beacon/`), and
  cross-chain strategies over CCTP / CCIP (`crosschain/`, `crosschainV3/`).
- **Periphery**: harvesters and drippers (`harvest/`), zappers (`zapper/`), pool boosters
  (`poolBooster/`), Safe modules (`automation/`), proxies (`proxies/`).

**Untrusted input** is any externally callable function reachable by an arbitrary address: every
public/external function without a role modifier, plus every callback or message from an external
system — token transfers and hooks, AMM pool state (which anyone can move within a transaction,
including with flash loans), cross-chain messages, beacon-chain proofs, and ETH sent to contracts.
Assume the attacker can deploy contracts, sandwich, and order transactions within a block.

**Trusted:** the Governor (timelock), the Strategist and Admin multisigs, the Guardian, the
Operator / Registrator automation EOAs, the proxy admin, and the configured oracles and external
protocols (Morpho, Curve, Aave, Lido, CCTP, CCIP, the beacon deposit contract). A finding that
requires one of them to act maliciously, or to be compromised, is out of scope — **unless** a
lower-privileged role (Strategist, Operator) can exceed the authority the code intends to give
it, e.g. move funds out of the vault/strategy system, or bypass a limit only Governor should change.

## Components that matter most / least

Highest priority:
1. `contracts/token/` rebasing accounting — balance/credit invariants, `totalSupply` vs. sum of
   balances, yield delegation, rounding that can be repeated for profit.
2. `contracts/vault/` — mint/withdraw-queue accounting, rebase and yield-drip limits
   (`README - Yield Limits.md`), `totalValue`, solvency checks, pausing.
3. AMO strategies — anything that lets an outsider extract value by manipulating the pool around
   strategist or permissionless calls, or make the vault mint unbacked OTokens.
4. Native staking + beacon proofs — forged or replayed proofs, mis-accounted validator balances.
5. Cross-chain strategies — forged/replayed messages, balance desync between master and remote.

Lower priority: harvesters, drippers, zappers, pool boosters, `lens/` (view-only),
`automation/` Safe modules (their callers are trusted multisig signers).

Out of scope:
- `contracts/mocks/`, `tests/`, `scripts/` (deployment framework, runs only on our machines),
  `tasks/` (off-chain ops automation), `dependencies/`, `lib/`.
- `OETHPlumeVault`, `OETHPlume`, `WOETHPlume` and other Plume contracts (being shut down).
- `OUSDResolutionUpgrade.sol` (one-shot migration helper).

## How to exercise it

Run from `/src/contracts`. Unit tests use mocks only and work offline:

- all unit tests: `make test-unit`
- one contract: `forge test --match-contract <TestContract> -vvv`
- layout: `tests/unit/<area>/<Contract>/{concrete,fuzz,shared}/`; each `shared/Shared.t.sol`
  shows how the contract under test is deployed and wired. Prefer writing the reproducer as a new
  test next to the closest existing one.

Fork (`tests/fork/`) and smoke (`tests/smoke/`) tests need an RPC endpoint and cannot run here.
Behaviour that depends on a real external protocol should be shown against the closest mock and
the dependency stated explicitly.

## How you rate severity

Rate by concrete on-chain impact, assuming deployed configuration and trusted roles behaving
honestly:

- **Critical** — direct theft or permanent freezing of user funds or protocol-owned funds;
  minting unbacked OTokens; protocol insolvency (OToken supply exceeding backing beyond the
  configured tolerance) triggerable by an unprivileged caller.
- **High** — temporary freezing of funds (e.g. withdrawals blocked until governance acts);
  theft of unclaimed yield; a lower-privileged role (Strategist/Operator) able to steal or
  permanently lose funds.
- **Medium** — griefing with no profit motive that costs users or the protocol funds;
  repeatable rounding leakage that is economically meaningful; denial of service of permissionless
  functions (`rebase`, `allocate`, harvesting) that persists more than a block.
- **Low / informational** — one-off dust rounding, gas inefficiency, missing events or input
  validation on privileged setters, best-practice deviations.

Please include a Foundry test that demonstrates the impact, with the attacker's starting capital
and profit or the victim's loss.

## Anything to leave alone

- "The Governor / Strategist / Admin / proxy admin can drain or upgrade the contracts" — intended
  trust assumption.
- Centralisation, oracle trust, and failures or depegs of integrated external protocols (Morpho,
  Curve, Lido, CCTP, CCIP, …) unless our code mishandles their documented behaviour.
- Rebase opt-out/opt-in and yield-delegation semantics described as intended in
  `contracts/token/README-token-logic.md`.
- Front-running of privileged multisig transactions where the call already carries slippage /
  value-checker protection (`VaultValueChecker`).
- Solidity compiler or OpenZeppelin library issues not triggered by our code.
- Storage-layout concerns: upgrades are checked against the deployed layout by the deployment
  pipeline before broadcast.
