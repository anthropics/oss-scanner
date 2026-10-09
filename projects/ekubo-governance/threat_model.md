# Threat model: Ekubo governance

## What this project does and where untrusted input enters
Token governance for Ekubo:
- `src/staker*.cairo`: stake and delegate a token, and track time-weighted delegation history.
  The staker has no owner.
- `src/governor.cairo`: delegates whose voting weight is above a threshold create proposals, i.e.
  batches of calls. Votes are weighted by average delegation before the proposal starts. Passing
  proposals execute after a delay, from the governor's own address. The governor owns protocol
  contracts and can upgrade itself.
- `src/airdrop*.cairo`: merkle-tree token distribution with an optional refund.
- `l1_proxy/src/*.sol`: owner proxies that let the Starknet governor act on Ethereum L1
  (`StarknetOwnerProxy`, via L2-to-L1 messages) and on L2s (`ArbitrumOwnerProxy` and
  `OPStackOwnerProxy`, via L1-to-L2 messaging). These proxies own deployed Ekubo contracts on EVM
  chains.

All callers are untrusted. Token holders may be adversarial and may hold large flash-borrowed
balances.

## Components that matter most
- The governor and its proposal lifecycle: creation threshold, vote counting, quorum and majority,
  cancellation rules, execution exactly once within the execution window, and voting weight
  snapshot and smoothing. Any way to execute calls without a legitimately passing vote is
  critical.
- Staker accounting: delegation history and the time-weighted averages. Inflating voting weight,
  double counting, or withdrawing more than was staked is critical.
- L1/L2 proxies: message origin authentication (Starknet core messaging, Arbitrum aliasing, the
  OP Stack `L2CrossDomainMessenger` and `xDomainMessageSender`), replay, and payload binding. Any
  caller other than the configured owner reaching `execute` is critical.
- Airdrop: merkle proof verification, double claims, and refund timing.

Out of scope: `*_test.cairo`, `src/test/**`, `l1_proxy/test/**`, `l1_proxy/lib/**`,
`l1_proxy/broadcast/**`, `proposals/**` (proposal calldata records).

## How to exercise it
- Cairo: `snforge test` (run `scarb test`). Put reproducers as snforge tests next to the
  affected `*_test.cairo` file.
- Solidity: `cd l1_proxy && forge test --offline`.

## How we rate severity
- Critical: executing arbitrary calls as the governor or any proxy without a passing proposal;
  stealing staked or airdropped tokens; forging voting weight.
- High: blocking execution of a passed proposal (permanent censorship), or cancelling or
  replaying proposals outside the rules; freezing staked funds.
- Medium: economically bounded vote-weight distortions; griefing that delays but does not block
  governance.
- Low: view inaccuracies and event issues.
