# celestia-node threat model

celestia-node is the data availability node of the Celestia network. Bridge nodes read blocks from a celestia-core consensus node, extend them into erasure-coded data squares, and serve headers and shares over libp2p. Light nodes sync headers from peers and sample random shares to decide that a block's data is available. Both node types expose a JSON-RPC API for blob submission and retrieval, and sign transactions with a local keyring. Protect the correctness of data availability sampling, the integrity of header sync, share and blob retrieval and their proofs, node availability, and the keys and funds handled by the state module.

## Existing project guidance

Read the checkout's [CLAUDE.md](https://github.com/celestiaorg/celestia-node/blob/main/CLAUDE.md), the [ADRs](https://github.com/celestiaorg/celestia-node/tree/main/docs/adr) (in particular ADR-008 on p2p discovery, ADR-009 on the public API, ADR-012 on DASer parallelization, and ADR-013 on the fibre API), the [shrex spec](https://github.com/celestiaorg/celestia-node/blob/main/specs/src/shrex/shrex.md), and the test guides for [swamp](https://github.com/celestiaorg/celestia-node/blob/main/nodebuilder/tests/README.md) and [Tastora](https://github.com/celestiaorg/celestia-node/blob/main/nodebuilder/tests/tastora/README.md).
`CLAUDE.md` describes the module layout under `nodebuilder/` and the core packages. Older ADRs and docs still mention full nodes and fraud proofs. This checkout only builds bridge and light nodes (`nodebuilder/node/type.go`) and has no fraud proof service, so a light node's safety rests on header verification and sampling alone.
Use the scanned checkout for technical instructions, since linked documentation follows `main`.

## Actors and entry points

Treat every libp2p peer as adversarial, including bootstrappers and peers listed in `TrustedPeers`, which are trusted to be reachable but not to be honest. A light node may be eclipsed by byzantine servers that answer every request. Treat the celestia-core node a bridge connects to as trusted for block contents but not for liveness or well-formed responses. Distinguish input any peer can send from input that needs a signed header, a validator set fraction, an operator flag, or an RPC token.

Headers enter through the go-header exchange and syncer wired in `nodebuilder/header/constructors.go` and through header gossip on pubsub (`nodebuilder/p2p/pubsub.go`). Trace `ExtendedHeader.Validate` and `Verify` in `header/header.go`: the data root must match the DAH, the commit must sign the header, and non-adjacent verification must respect the trusting period. Check subjective initialisation in the syncer (`SyncFromHash`, `SyncFromHeight`, the pruning window checks in `nodebuilder/header/config.go`) and whether a peer can push a light node onto a fork or a stale head.

Light node sampling lives in `das/` (daser, coordinator, workers, checkpoints) and `share/availability/light`, which must reach `DefaultSampleAmount` verified samples before marking a height available. Check whether any error path, timeout, checkpoint, or pruning-window edge marks a height sampled without enough verified samples. Bridge availability and reconstruction are in `share/availability/full` and `share/eds` (`retriever.go`, `validation.go`, `byzantine/`).

Shares move over shwap in `share/shwap`. The shrex client and server in `share/shwap/p2p/shrex` (with `limits.go`, `rate_limit.go`, the peer manager in `peers/`, `shrexsub/` notifications, and `shrex_getter/`) and the bitswap protocol in `share/shwap/p2p/bitswap` decode attacker-controlled bytes on both sides. Every `Verify` method on samples, rows, row namespace data, and range namespace data in `share/shwap` must bind the response to the requested coordinates and the trusted roots. Peer discovery is in `share/shwap/p2p/discovery`, and the libp2p host, resource manager, and connection gater are in `nodebuilder/p2p`. The EDS store in `store/` and `store/file` parses files written by the node, and `pruner/` deletes them.

A bridge reads blocks over gRPC from celestia-core in `core/` (`fetcher.go`, `listener.go`, `exchange.go`, `multisource.go`). Check how it handles malformed or inconsistent blocks and multiple core endpoints.

The JSON-RPC server in `api/rpc` authenticates JWTs signed with the key from `libs/authtoken` and checks `perm:"..."` tags (public, read, write, admin) on each `nodebuilder/*` module interface, using `api/rpc/perms`. It is an operator-exposed interface, but any method callable with a read token, or with no token, is a remote entry point. `--rpc.skip-auth` and CORS settings are handled in `nodebuilder/rpc`. Report resource exhaustion through RPC only when it is reachable with default configuration and exceeds the cost an operator would reasonably expect.

Blob submission and retrieval are in `blob/` (parser, `commitment_proof.go`, service). The state module in `state/` and `state/txclient` builds, signs, and submits transactions with the keyring from `nodebuilder/state/keyring.go` and `libs/keystore`. Check fee and gas handling, which signer is used, and whether a write-permission caller can spend from an account the operator did not intend. `nodebuilder/blobstream` builds data root tuple proofs, and `fibre/` with `nodebuilder/fibre` is a client of validator fibre servers that may be byzantine.

## Scope and ownership

The whole repository is in scope for source review. The priorities below guide investigation rather than exclude other code.

Prioritize, in order: a light node accepting unavailable data as available; accepting an invalid header, a forked header chain, or a share, namespace, or blob proof that does not match the trusted roots; remotely triggerable crashes, panics, or amplification against bridge or light nodes; JWT or permission bypass on the RPC API; and misuse of keys or funds through the state, blob, or fibre modules.

`cmd/cel-shed`, `scripts/`, `docker/`, `celestia-node.mk`, and `nodebuilder/tests` are developer and operator tooling. Report them only for a concrete security failure. go-header, go-square, nmt, rsmt2d, celestia-app, celestia-core, boxo (pinned to a celestiaorg fork), and go-libp2p are separate repositories pinned in `go.mod`. They remain in scope when celestia-node reaches the affected code, but identify the upstream owner before proposing a fix. Do not report a library contract violation without a path from celestia-node.

## Build and bounded validation

The checkout is `/src`. The node binary is `/src/build/celestia`, and `cel-key` and `cel-shed` are at `/src/cel-key` and `/src/cel-shed`. Go modules for the root module and for the separate module in `nodebuilder/tests/tastora`, and the test build cache, are fetched and populated before network access is removed. `GOPROXY=off` and `GOFLAGS=-mod=readonly` make a missing module fail fast instead of hanging. Do not edit `go.mod` or `go.sum`.

Unit tests for `header`, `share`, `blob`, `das`, `store`, `api`, `libs`, and `pruner` run during the Docker build. Integration tests in `nodebuilder/tests` use the swamp in-process network and need the `integration` tag or one of `api`, `blob`, `da`, `nd`, `p2p`, `pruning`, `reconstruction`, `share`, or `sync`. The Tastora suites in `nodebuilder/tests/tastora` (tags `integration` and `fibre_e2e`) need Docker and cannot run in this image, and `nodebuilder/p2p/bootstrap_health_test.go` (tag `bootstrapper_health`) dials public bootstrappers and must not be run. The race detector works offline but recompiles from scratch, so use it only on the package under study. These are execution limits, not source-review exclusions.

The scanner VM has two CPUs and 8 GB of memory. Keep `-p` and `-parallel` at two and always pass `-timeout`. Swamp tests start an in-process consensus network and are slow. Run single tests with `-run`.

```sh
go test -tags fibre -p 2 -timeout 10m ./share/... ./header/... ./das/...
go test -tags fibre -p 2 -timeout 10m ./blob/... ./api/... ./nodebuilder/...
go test -tags integration,fibre -p 2 -parallel 2 -timeout 20m -run 'TestShrexFromLights' ./nodebuilder/tests
```

Use `nodebuilder/tests/swamp` for in-process networks, `header/headertest` for header fixtures, `share/eds/edstest` for squares, and `share/eds/byzantine` for bad encodings. Go fuzz targets are `FuzzBlobUnmarshal` and `FuzzCommitmentProofVerify` in `blob`, `FuzzRowsWithNamespace` in `share`, `FuzzRangeNamespaceDataFromShares` and `FuzzRangeCoordsFromIdx` in `share/shwap`, and `Fuzz_writeReadheader` in `store/file`. The first fuzz run in a package rebuilds its dependencies with coverage instrumentation, which takes about seven minutes on two CPUs. Bound each run with `-fuzztime` and an external timeout that allows for that:

```sh
timeout --kill-after=5 900 go test -run '^$' -fuzz=FuzzCommitmentProofVerify -fuzztime=120s -parallel=2 ./blob
```

Reproduce only against in-process test networks and temporary home directories. Never connect to Mainnet Beta, Mocha, Arabica, or other public networks or their bootstrappers, and never use real keys or funds.

## Evidence and severity

Record the exact revision, node type, build tags, attacker capability (any peer, a set of byzantine peers that eclipse a light node, the connected core node, an RPC token with a given permission, the operator), whether the path is enabled by default, and the observed consequence. Keep source-only hypotheses separate from tests that reproduce the behavior. For availability findings, show a light node marking a height available when the data cannot be reconstructed. For header findings, show an honest node accepting a header that `Validate` or `Verify` should reject. For resource findings, compare the work a node performs with the size of the request and the configured limits, and state the measured cost.

Rate severity by impact on the live network:

- Critical: a light node accepting unavailable data as available, or accepting an invalid or forked header chain, without the attacker controlling more than 1/3 of voting power; a forged share, namespace, or blob inclusion proof accepted against trusted roots; RPC permission bypass that reaches admin or write methods; or signing or spending with the node's key without a write token.
- High: a remotely triggerable crash or sustained denial of service against bridge or light nodes with default configuration; a bypass of a read-permission check; or corruption of the EDS or header store that needs a resync.
- Medium: limited-scope degradation, bounded amplification, slowing down sampling or sync without changing its result, or attacks needing an unusual configuration.
- Low: issues needing local access, a malicious operator, or other strong preconditions, and defense-in-depth hardening.

A panic, sanitizer report, or bug-class label does not determine severity on its own. A panic in an RPC handler that is recovered and only fails one request is not a node crash. Keep confidence, remediation urgency, and disclosure timing separate.

Check Git history and existing tests for the same root cause. Keep patches minimal and follow `CLAUDE.md`. Flag any change to `nodebuilder/**/config.go` or `.proto` files as potentially breaking, and add a test that fails before the fix and passes after it.

Report findings privately to `security@celestia.org` or through a GitHub security advisory on the repository, as described in the [celestiaorg security policy](https://github.com/celestiaorg/.github/blob/main/SECURITY.md). Do not put suspected vulnerabilities, reproducer details, or unreviewed findings into public issues or PRs. Include the smallest bounded reproducer, actual output, expected result, and evidence limits in each report. Disclosure decisions belong to the Celestia security team.
