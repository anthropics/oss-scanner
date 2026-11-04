# chia-blockchain threat model

chia-blockchain is the reference node for the Chia network: a full node that validates blocks and transactions and
relays them over an unauthenticated P2P network, plus a mempool, farmer, harvester, timelord, wallet and data layer.
Consensus-critical work is split between this Python code and Rust: block and spend validation, CLVM execution and
cost accounting, and the streamable wire types live in `chia_rs` (source at `/deps/chia_rs`), and the CLVM interpreter
in `clvm_rs` (source at `/deps/clvm_rs`). `/deps/VERSIONS` records which versions this image uses.

## What we protect

1. Consensus: every node accepts and rejects the same blocks, whatever the platform, cache state, restart or reorg
   history. No inflation, no theft through validation, no chain split. A divergence between the Python and Rust
   validation paths, or between mempool and block validation, is in scope.
2. Availability: an unauthenticated peer cannot crash, stall or exhaust a full node, keep it off the heaviest chain,
   or stop it relaying blocks and transactions.
3. Block production: untrusted transactions cannot make a farmer's unfinished block invalid, push its creation past
   the signage-point deadline, or evict honest fee-paying transactions cheaply.
4. Funds: with no attacker access to the local machine, the wallet does not lose coins or keys, sign what the user did
   not approve, or accept an offer whose outcome differs from what it showed the user.
5. Durable state: the blockchain and coin databases stay consistent across crashes, restarts and reorgs.

## Who is trusted

| Source | Trust | Notes |
|---|---|---|
| Full-node P2P peers (`chia/server/`, `chia/full_node/full_node_api.py`) | Untrusted | TLS identities are free to create, so many inbound peers are cheap. State how many connections an attack needs and whether rate limits (`chia/server/rate_limits.py`, `rate_limit_numbers.py`) apply. |
| Wallet peers connecting to a full node | Untrusted | The light-wallet protocol (subscriptions, coin state requests) is reachable by anyone. |
| Spend bundles submitted by peers | Untrusted, costly | They pay fees and CLVM cost. State the fee and cost an attack needs. |
| Blocks with valid proof of space and time | Untrusted, costly | A farmer can create them; state whether an attack needs winning a block. |
| Offers, puzzles and solutions handed to the wallet | Untrusted for funds safety | The wallet must take exactly what the offer showed. |
| RPC clients (`chia/rpc/`, daemon websocket) | Trusted | Bound to localhost and authenticated by the node's private TLS certificate. Issues only an RPC client can trigger are bugs, not vulnerabilities, unless they bypass that authentication. |
| Farmer ↔ harvester ↔ timelord links | Semi-trusted | Normally the operator's own machines on a private network. Lower severity than full-node P2P. |
| The local machine: `~/.chia`, `config.yaml`, keyring, databases | Trusted | Anything needing local or file write access is out of scope. |

## Components that matter most

- `chia/full_node/` (block and transaction processing, sync, weight proofs, `mempool_manager.py`, `mempool.py`,
  `eligible_coin_spends.py`), `chia/consensus/` (header and body validation, `blockchain.py` reorg logic),
  `chia/server/` and `chia/protocols/` (connection handling, message parsing, rate limits).
- Where these call into `chia_rs` / `clvm_rs`. The Rust code is in scope where attacker data reaches it through this
  node; bugs only reachable through the Rust crates' own APIs belong to their own enrolments.
- `chia/wallet/` for offer handling (`trade_manager.py`, `trading/`) and coin selection.

Lower priority or out of scope:

- `chia/_tests/`, `benchmarks/`, `tools/`, `build_scripts/`, the GUI submodule.
- The data layer (`chia/data_layer/`) and the plotters: off by default; a finding there is lower severity.
- Wallet reorg handling bugs: functional bugs, not security issues.

## What counts as a vulnerability

- A remote crash: an `assert`, unhandled exception or Rust panic reachable from P2P input that kills the service.
  An exception caught by the per-message handler that only drops the connection is not.
- CLVM cost mispricing: a spend or block whose real CPU time or memory is far out of line with its CLVM cost. Compare
  against a cost-proportional baseline such as plain SHA-256 at the same cost, and give the wall-clock time for a
  block at the maximum cost (`MAX_BLOCK_COST_CLVM`).
- Resource exhaustion from one peer or message: about a second or more of CPU in the event loop, or growth to 1 GiB
  of memory, or state that grows without bound across reconnects. Per-peer state bounded and freed on disconnect is
  expected; measure one peer, then say how far the total scales given global limits.
- Liveness bugs that honest peers repair by re-announcing (dropped signage points, infusion points, end-of-slot
  bundles or transactions that another peer re-sends) are not vulnerabilities unless the attacker can keep the victim
  from recovering while it still has honest peers.
- Mempool replacement by the rules in `mempool_manager.py` (superset, fee-per-cost, minimum fee bump) is intended.
  Report only a deviation from those rules or a way around them.
- Findings that need a leaked API key, TLS private key or RPC certificate as the entry point are out of scope.
- Findings at or before a past soft- or hard-fork height that the fork already closed are not reports.

## Severity

- Critical: network-wide: a chain split between nodes or between the Python and Rust paths, inflation or theft
  through consensus, a crash any peer can trigger on every node (including by propagating a block or transaction),
  remote code execution.
- High: persistent damage to one node (database corruption, state divergence that survives restart), or a remote
  crash or stall of a node in the default configuration that does not propagate; wallet loss of funds or keys.
- Medium: single node, transitory (restart or dropping the peer recovers): resource exhaustion as above, a crash or
  stall needing semi-trusted access (farmer/harvester/timelord links) or non-default features.
- Low: transitory single-node issues with unlikely preconditions or minimal effect.

Every report needs a file and line, the path from untrusted input to the defect, and a reproducer that runs in this
image. Mark measurements as measured or extrapolated.

## How to exercise it

- `/src/.venv` is active: `chia`, `pytest`, `mypy` are on `PATH`. The test suite is under `chia/_tests/`;
  block-level tests use the pre-generated chains in `/root/.chia` through `chia/_tests/util/blockchain.py` and
  `chia/simulator/block_tools.py`. `chia/_tests/core/mempool/`, `chia/_tests/core/full_node/` and
  `chia/_tests/blockchain/` are the closest starting points for reproducers.
- `chia/simulator/` runs a full node in simulation mode; `chia/_tests/connection_utils.py` connects a test peer to it.
- The chia_rs Python extension is built from `/deps/chia_rs` with debug info. `cargo test` works offline in
  `/deps/chia_rs` and `/deps/clvm_rs`; both have cargo-fuzz targets under `fuzz/` directories.
