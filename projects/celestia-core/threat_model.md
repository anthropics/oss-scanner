# celestia-core threat model

celestia-core is the consensus engine of the Celestia data availability network. It is a fork of CometBFT v0.38 (module path `github.com/cometbft/cometbft`) that runs celestia-app through ABCI. On top of upstream it adds the CAT mempool, erasure-coded block propagation with compact blocks, the data square size and share proofs carried in block data, Celestia RPC and gRPC endpoints for proofs and data commitments, and a tracing subsystem. Protect consensus safety and liveness, the integrity of committed blocks and the proofs served about them, and node availability against peers and RPC clients.

## Existing project guidance

Read the checkout's [CLAUDE.md](https://github.com/celestiaorg/celestia-core/blob/main/CLAUDE.md), the [Celestia ADRs](https://github.com/celestiaorg/celestia-core/tree/main/docs/celestia-architecture) (block propagation, CAT pool, reactor-specific peers, sequence-aware CAT), the [CAT mempool spec](https://github.com/celestiaorg/celestia-core/blob/main/mempool/cat/spec.md), the [p2p channel list](https://github.com/celestiaorg/celestia-core/blob/main/docs/p2p-channels.md), and the upstream [specs](https://github.com/celestiaorg/celestia-core/tree/main/spec).
`CLAUDE.md` lists the active branches and states that the fork keeps minimal divergence from upstream. The checkout's `SECURITY.md` is inherited from upstream and points to the Cosmos program, so do not use it for reporting (see below).
Use the scanned checkout for technical instructions, since linked documentation follows `main`.

## Actors and entry points

Treat every p2p peer as adversarial, including peers that complete the handshake and peers that claim to be validators. Treat any single validator, including the current proposer, as adversarial. Safety is only assumed while more than 2/3 of voting power is honest. Distinguish input any peer can send from input that needs a proposer slot or validator signatures.

Connections start in `p2p/transport.go` and `p2p/conn/secret_connection.go` (the SecretConnection handshake), then pass through `p2p/conn/connection.go` (MConnection framing, flow control, and the Celestia `RecvMessagePrecheck` hook) and `p2p/switch.go`. Review each reactor as a decoder of attacker-controlled bytes and a holder of per-peer state:

- `mempool/cat/` (the only mempool on `main`): seen/want/tx gossip, `validateMempoolBytes` in `mempool/cat/scan.go`, the request tracker, sticky peers, the received buffer, and sequence-aware ordering. Check that a peer cannot evict or block honest transactions, or make a node request or store unbounded data.
- `consensus/reactor.go` and `consensus/state.go`: proposals, votes, vote set bits, and round state. Check equivocation handling and that peer messages cannot drive the state machine into a panic or a stuck round.
- `consensus/propagation/`: compact blocks, have/want of erasure-coded parts, the `CombinedPartSet` of original and parity parts in `consensus/propagation/types/combined_partset.go`, catchup, and the commitment checks in `validateCompactBlock` in `consensus/propagation/commitment.go`. Check whether a proposer or peer can make honest nodes reconstruct a block that differs from the committed `PartSetHeader`, or accept parts or proofs that do not match it.
- `blocksync/` (with `validateBlockSyncBytes` in `blocksync/msgs.go`), `statesync/` (snapshots and chunks), `evidence/` (pool and `evidence/verify.go`), and `p2p/pex/` (address book).

Block contents are checked in `types/block.go` and `types/part_set.go`, including `DataHash`, `SquareSize`, and the transaction hashes, and are stored by `store/store.go`. Share proofs in `types/share_proof.go` use `go-square` and `nmt`. Block execution in `state/execution.go` calls `PrepareProposal`, `ProcessProposal`, and `FinalizeBlock` on celestia-app through `proxy/` and `abci/client/`. Treat the ABCI response as trusted application output, but check how celestia-core handles malformed, oversized, or panicking responses.

The light client in `light/` (`light/verifier.go`, `light/detector.go`) and its proxy in `light/proxy/` consume headers and commits from untrusted primaries and witnesses. Check that a byzantine provider cannot make it accept a header without enough trusted voting power, or hide a fork from the detector.

The signer connection in `privval/` (`signer_listener_endpoint.go`, `signer_client.go`, and the gRPC listener in `grpc_listener.go` with `grpc_tls.go`) talks to a remote KMS. Check that the node cannot be made to double-sign and that a TLS or authentication bypass is not possible on a non-localhost address.

JSON-RPC in `rpc/jsonrpc/server/` and `rpc/core/`, gRPC in `rpc/grpc/`, the trace pull server in `libs/trace/fileserver.go`, and pprof are operator-exposed interfaces. The Celestia routes (`prove_shares`, `prove_shares_v2`, `data_root_inclusion_proof`, `data_commitment`, `signed_block`, `tx_status`, `tx_status_batch`) and the gRPC `BlockAPI` and `BlobstreamAPI` serve proofs that light nodes and rollups rely on, so treat incorrect proofs as integrity bugs. Report resource exhaustion through these interfaces only when it is reachable with default configuration and exceeds the cost an operator would reasonably expect. The unsafe routes are not enabled by default.

## Scope and ownership

The whole repository is in scope for source review. The priorities below guide investigation rather than exclude other code.

Prioritize, in order: a consensus split, double sign, or chain halt reachable from a peer or from less than 1/3 of voting power; acceptance of an invalid or mismatched block, part set, or commit by honest nodes; remotely reachable crashes, deadlocks, or amplification through p2p reactors; light client acceptance of an unverified header; and incorrect share, data root, or data commitment proofs served over RPC.

`scripts/`, `networks/`, `DOCKER/`, `test/`, `docs/`, `cmd/contract_tests`, and `third_party/` are developer and operator tooling. Report them only for a concrete security failure. celestia-app, go-square, and nmt are separate repositories. They remain in scope when celestia-core reaches the affected code, but identify the owner before proposing a fix.

Most of the code is inherited from upstream CometBFT v0.38. For each finding, check whether the same code exists in `cometbft/cometbft` on the v0.38.x line. If it does, say so and name upstream CometBFT as the owner, since the fix and disclosure must be coordinated with them. If the bug lives in a Celestia addition (the CAT mempool, `consensus/propagation`, the Celestia RPC and gRPC routes, `libs/trace`, share proofs, or the `RecvMessagePrecheck` hook) or in a Celestia change to upstream code, say that instead.

## Build and bounded validation

The checkout is `/src`. The node binary is `/src/build/cometbft` (built unstripped), and `abci-cli` is installed on `PATH`. Go modules and the test build cache, including the `deadlock`, `-race`, and `release` variants, are fetched and populated before network access is removed. `GOPROXY=off` and `GOFLAGS=-mod=readonly` make a missing module fail fast instead of hanging. Do not edit `go.mod` or `go.sum`.

A bounded subset of the unit tests runs during the Docker build with the `deadlock` tag, as `make test` uses. The end-to-end suite in `test/e2e` and `make localnet-start` need Docker and cannot run in this image. These are execution limits, not source-review exclusions.

The scanner VM has two CPUs and 8 GB of memory. Keep `-p` and `-parallel` at two and always pass `-timeout`. Packages under `consensus/` and `p2p/` start in-process multi-node networks and are slow. Run single tests with `-run`.

```sh
go test -p 2 -timeout 10m -tags deadlock ./mempool/... ./consensus/propagation/... ./types/...
go test -p 2 -timeout 15m -run 'TestReactorBasic' ./consensus
go test -race -p 2 -parallel 2 -timeout 15m ./mempool/cat
```

Use `randConsensusNet` in `consensus/common_test.go` for in-process validator networks, `MakeConnectedSwitches` in `p2p/test_util.go` for wired peers, `consensus/byzantine_test.go` and `consensus/invalid_test.go` as patterns for a byzantine validator, and `abci/example/kvstore` as the application. Go fuzz targets are `FuzzMempool`, `FuzzP2PSecretConnection`, and `FuzzRPCJSONRPCServer` in `test/fuzz/tests`, `FuzzTxsToParts` in `consensus/propagation/types`, and `FuzzParallelImplementations` in `crypto/merkle`. Bound each run with `-fuzztime` and an external timeout:

```sh
timeout --kill-after=5 300 go test -run '^$' -fuzz='^FuzzP2PSecretConnection$' -fuzztime=120s -parallel=2 ./test/fuzz/tests
```

Reproduce only against in-process test networks and temporary home directories. Never connect to Mainnet Beta, Mocha, Arabica, or other public networks, and never use real keys or funds.

## Evidence and severity

Record the exact revision, build tags, attacker capability (any peer, RPC client, proposer, validator set fraction, light client provider), whether the path is enabled by default and on Mainnet Beta, whether the code is inherited from upstream CometBFT, and the observed consequence. Keep source-only hypotheses separate from tests that reproduce the behavior. For consensus findings, show two honest nodes diverging, a node signing conflicting votes, or an honest node accepting a block, part, or commit it should reject. For resource findings, state what the attacker sends, what the node does in return, and the measured cost.

Rate severity by impact on the live network:

- Critical: a consensus split, double sign, or chain halt triggered by any peer or by less than 1/3 of voting power; honest nodes committing an invalid or mismatched block; or the light client accepting a header without sufficient trusted voting power.
- High: a remotely triggerable crash, deadlock, or sustained denial of service against validators through p2p with default configuration; stalling block propagation or the mempool for honest nodes; or incorrect share or data root proofs served by an honest node.
- Medium: limited-scope degradation, bounded resource amplification, or attacks needing an unusual configuration, an exposed RPC endpoint, or a malicious validator with significant stake.
- Low: issues needing local access, a compromised signer, or other strong preconditions, and defense-in-depth hardening.

A panic, race report, or bug-class label does not determine severity on its own. A panic recovered by a reactor that only disconnects the sending peer is not a chain halt. Keep confidence, remediation urgency, and disclosure timing separate.

Check Git history, upstream CometBFT advisories, and existing tests for the same root cause. Keep patches minimal and follow `CLAUDE.md`. Keep divergence from upstream small, and add a test that fails before the fix and passes after it.

Report findings privately to `security@celestia.org` or through a GitHub security advisory on the repository, as described in the [celestiaorg security policy](https://github.com/celestiaorg/.github/blob/main/SECURITY.md). Do not put suspected vulnerabilities, reproducer details, or unreviewed findings into public issues or PRs. Include the smallest bounded reproducer, actual output, expected result, and evidence limits in each report. Disclosure decisions belong to the Celestia security team.
