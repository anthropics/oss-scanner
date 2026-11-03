# Threat model

## What this project does and where untrusted input enters

Moolah is the lending protocol of Lista DAO, deployed on BNB Smart Chain (and Ethereum). `src/moolah/Moolah.sol` is a Morpho Blue-style isolated lending market: each market is defined by `MarketParams` (loan token, collateral token, oracle, IRM, LLTV) and holds real user funds.

Every external and public function callable by an unprivileged address is an attack surface, and the attacker controls calldata, msg.value, call ordering within a block, flash loans, and any token or contract they deploy themselves. Assume the attacker can also move DEX pool prices within a transaction.

Trusted: holders of `DEFAULT_ADMIN_ROLE` (the Timelock), `MANAGER`, `OPERATOR`, `PAUSER`, curators/allocators of vaults, and the configured oracle feeds (Chainlink, Pyth, Lista multiOracle) when they report correct prices. Market-creation parameters set by `OPERATOR` are trusted.

## Components that matter most / least

Highest priority, in order:
- `src/moolah/` — markets, share accounting, interest accrual, liquidation, bad-debt socialisation, flash loans, authorisation (`setAuthorization`, signatures).
- `src/moolah-vault/` — ERC-4626 curated vaults allocating across Moolah markets (share inflation, allocation, withdrawal queues).
- `src/provider/` — collateral wrappers between users and Moolah: native BNB/ETH, slisBNB (LP minting and delegation), `SmartProvider` (stable-swap LP collateral, also an oracle), `V3Provider` (Uniswap/PancakeSwap V3 concentrated-liquidity position issued as ERC-20 shares).
- `src/broker/` — `LendingBroker` and `CreditBroker` structured borrow positions.
- `src/liquidator/`, `src/oracle/`, `src/interest-rate-model/`, `src/dex/` (stable-swap pools and LP collateral), `src/utils/` (`PositionMigrator`, `SlisBNBxMinter`).

Out of scope: `test/`, `script/`, `broadcast/`, `certora/`, `docs/`, and everything under `lib/` (third-party and other Lista repositories), except where a bug in Moolah code is caused by how it uses them.

## How to exercise it

Foundry v1.8.1, solc 0.8.34, via-IR; the image has `src/` prebuilt. Compiling every test at once under via-IR needs more than 8 GB, so run tests one path at a time, e.g. `forge test --offline --match-path "test/moolah/integration/*"`. Unit tests live in `test/` and mirror `src/`. Tests that call `vm.createSelectFork` need a BSC or Ethereum RPC and cannot run offline; please write proofs of concept as local tests that deploy the contracts and use mock tokens and oracles, following the existing unit tests in `test/moolah/`.

## How you rate severity

- **Critical**: direct theft of user or protocol funds; permanent freezing of funds; minting shares or collateral value out of nothing; borrowing against collateral that is not there; protocol insolvency an unprivileged attacker can cause.
- **High**: temporary freezing of funds or blocking liquidations or withdrawals for a meaningful period; theft of unclaimed yield, fees or rewards; bad debt an attacker can force onto lenders; bypass of role checks or of `setAuthorization`.
- **Medium**: griefing that costs the attacker more than the victim loses but harms users; incorrect interest or share accounting that leaks small amounts per call; view functions or oracles returning wrong values that other contracts rely on.
- **Low**: rounding in the protocol's favour beyond the documented direction, missing events, gas inefficiencies with no security effect.

A finding needs a concrete call sequence by an unprivileged account; please include a Foundry test that demonstrates it.

## Anything to leave alone

- Actions that need a trusted role listed above, or a compromised Timelock, admin key, or oracle provider.
- Market parameters (LLTV, oracle, IRM) chosen by `OPERATOR`; we assess those off-chain.
- Price manipulation of an external oracle feed itself (Chainlink, Pyth) rather than of a price Moolah computes.
- Centralisation, upgradeability (UUPS) as a design choice, and front-running of admin transactions.
- Behaviour of fee-on-transfer, rebasing or otherwise non-standard tokens unless a market listed in production uses one.
