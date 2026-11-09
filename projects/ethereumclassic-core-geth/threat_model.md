# Threat model: Core-Geth

Core-Geth is an Ethereum Classic execution client: a node that verifies and serves Ethereum Classic's
blockchain and builds work for proof-of-work miners. It is derived from go-ethereum, and its Go module
path is still `github.com/ethereum/go-ethereum`. go-ethereum does not support Ethereum Classic, so the
code that implements Ethereum Classic's rules is maintained in `ethereumclassic/core-geth` and has no
upstream review.

## What this project does and where untrusted input enters

Chain rules are configuration rather than code branches. Each network's rules are activation blocks in
`params/config_classic.go`, `params/config_mordor.go` and `params/config_mintme.go`, read through the
interfaces in `params/types/`. A node selects its network from its flags (`cmd/utils/flags.go`):

| Network | Chain ID | Proof of work | Selected by |
|---|---|---|---|
| Ethereum Classic mainnet | 61 | Ethash with ECIP-1099 (etchash), `consensus/ethash` | no network flag, `--classic` or `--mainnet` |
| Mordor, Ethereum Classic's test network | 63 | the same | `--mordor` |
| MintMe.com Coin | 24734 | Lyra2, `consensus/lyra2` | `--mintme` |

`--ethereum`, `--sepolia` and `--holesky` refuse to start. `--dev` and `--dev.pow` start a single-node
developer chain.

Untrusted input:

- **devp2p peers.** A node listens on port 30303 by default and accepts peers it does not know: node
  discovery, the RLPx handshake, and the `eth` and `snap` wire protocols, which carry chain data and
  transactions.
- **Blocks with valid proof of work.** They still come from untrusted miners. Producing one costs
  hashrate, which can be rented, so an attacker who mines a valid block, or a private chain to
  reorganize onto, is in scope.
- **Transactions.** Anyone can send one by paying its fee, through a peer or over RPC.
- **JSON-RPC over HTTP and WebSocket**, when the operator turns it on with `--http` or `--ws`. It binds
  to `localhost` by default and serves the `eth`, `net` and `web3` namespaces unless `--http.api` or
  `--ws.api` names others. Callers of those namespaces are untrusted. Mining pools call `eth_getWork`
  and `eth_submitWork` in the `eth` namespace.
- **GraphQL**, when the operator turns it on with `--graphql`.

Trusted: callers of `admin`, `debug`, `personal`, `miner` and `txpool`, which an operator has to add to
`--http.api` or `--ws.api` on purpose; the IPC endpoint and its local users; the data directory, the
keystore, config files, genesis files and flags.

## What is protected, in order

1. **Consensus, as the Ethereum Classic Improvement Proposals define it.** A node must accept exactly
   the blocks the rules accept. Accepting a block the rules reject, rejecting one they accept, or
   computing a different state root, receipt root, difficulty or block reward is a chain split.
2. **Network availability.** A peer must not be able to crash a node, stall its sync, exhaust its
   memory, disk or CPU, or cut it off from honest peers. The same defect in every node stops the
   network.
3. **Mining.** Miners and pools must get correct work for the head a node follows, and a node must not
   accept a solution the rules reject.
4. **Keys.** The keystore, the node key in the data directory, and what is signed with them.
5. **Durable state.** The chain database and the freezer: crafted input must not corrupt them or leave
   a node unable to restart.

## Components that matter most / least

Most, because only this project maintains them:

- `consensus/ethash`: etchash and ECIP-1099's epoch length (`algorithm.go`), difficulty
  (`difficulty.go`, `consensus_classic.go`), header verification (`consensus.go`), and the remote sealer
  that serves mining work (`sealer.go`, `api.go`).
- `params/mutations/`: block rewards, including ECIP-1017's monetary policy.
- `consensus/lyra2`: MintMe.com Coin's proof of work.
- `params/` and `params/types/`: the chain configurations and the code that reads them.
- `miner/`: building the blocks a node hands out as work.
- `eth/fetcher/` and `eth/handler*.go`: announcing, fetching and importing blocks and transactions
  from peers.
- MESS (ECBP-1100), a chain-selection policy against deep reorganizations: `core/blockchain_af.go`,
  `core/forkchoice.go`, `eth/mess_window.go`. On `main`, MESS applies by default only between
  `ECBP1100FBlock` and `ECBP1100DeactivateFBlock` in `params/config_classic.go` and
  `params/config_mordor.go`. Past that window it applies only when an operator passes `--mess`. MESS
  decides which of two valid chains a node keeps, never whether a block is valid.

Everything else the `geth` binary runs on untrusted input is in scope too, including code identical to
go-ethereum's. When a finding is in code identical to go-ethereum's, say so in the report, since its fix
may need coordinated disclosure.

Core-Geth's earlier v1.12 line shares much of this code: `main` was cut from that line's tree. The v1.12
line's history up to December 2024 is the branch `archive-etclabscore-2024-12`, which is in the image's
git history (`git show origin/archive-etclabscore-2024-12:<path>`). When a finding also applies to the
v1.12 line's code, say so in the report.

Out of scope:

- Proof of stake and the engine API: `consensus/beacon`, `beacon/` and `eth/catalyst`. The engine API is
  registered only for a chain with a terminal total difficulty, which none of the networks above has,
  and for `--dev`.
- `--dev`, `--dev.pow`, and private chains an operator sets up with their own genesis.
- Commands under `cmd/` other than `geth`.
- Test code, `docs/` and `build/`.
- Dependencies, unless the report shows attacker input reaching the defect through code in
  `ethereumclassic/core-geth`.

## How to exercise it

- `build/bin/` holds every command under `cmd/`, `geth` among them, built as `make all` builds them.
  Every package's tests are compiled.
- Fixtures: `tests/testdata` (Ethereum's consensus tests), `tests/testdata-etc` (Ethereum Classic's),
  `tests/evm-benchmarks`, `tests/spec-tests` (the execution-spec-tests fixtures) and `tests/etcvectors`.
- `go test ./<package>/...` runs a package's tests. `make test` runs the whole suite and takes a long
  time. `make test-coregeth` runs this client's own suites: fork and feature equivalence, Clique
  consensus equivalence, and the import of simulated chains (`tests/regression/simulated/`) with the
  built `geth`.
- Two `consensus/ethash` tests generate a full Ethash dataset and caches, so on a small machine the
  package needs more than `go test`'s 10-minute default timeout:
  `go test -short -timeout 30m ./consensus/ethash/`.
- Go fuzz targets, run with `go test -fuzz`: `core/types`, `core/vm`, `rlp`, `trie`,
  `eth/protocols/snap`, `accounts/abi`, `accounts/keystore`, `common/bitutil`, `internal/era/e2store`
  and the packages under `tests/fuzzers/`.
- To run a node, use a private chain: `geth --dev`, `geth --dev.pow`, or `geth init` with your own
  genesis and `--nodiscover`. Do not connect to Ethereum Classic mainnet, Mordor or MintMe.com Coin.
  `tests/live_etc` (build tag `live`) talks to live network endpoints and is not for a scan.

## How you rate severity

- **Critical:** a consensus failure that a remote party can trigger on any network above; remote code
  execution; theft of keys, or of funds a node controls; a defect a peer can use to stop nodes started
  without extra flags from following the chain until an operator steps in, such as a crash loop, a
  corrupted database or a stall that a restart does not clear.
- **High:** an unauthenticated peer can crash a node started without extra flags, or exhaust its memory,
  disk or CPU, at little cost, where a restart recovers it; a miner or pool is handed wrong work, or a
  node accepts a solution the rules reject.
- **Medium:** a denial of service that needs sustained resources, or that reaches a node only through
  RPC in its default namespaces; a bounded resource drain; a leak of information a node should keep
  local.
- **Low:** anything that needs a trusted caller, local access or the operator's own configuration, and
  hardening with no demonstrated impact.

A finding that needs a non-default flag, such as `--mess`, `--graphql` or a namespace added to
`--http.api`, names the flag and is rated one level below the same impact on a node started without it.
A finding that affects only Mordor or only MintMe.com Coin says so.

## Anything to leave alone

- Ethereum mainnet and its test networks. This client follows Ethereum's upgrades only through Cancun,
  and their flags refuse to start.
- Behavior the Ethereum Classic rules require where they differ from Ethereum's. A difference from
  go-ethereum is a finding only when it also breaks an Ethereum Classic rule.
- A dependency's or the Go toolchain's version alone, with no path from attacker input.
