# Erigon threat model

Erigon is an Ethereum execution client with an embedded consensus client (Caplin). It syncs and
validates the chain, serves JSON-RPC/Engine/Beacon APIs, gossips blocks and transactions over devp2p
and libp2p, downloads historical snapshots over BitTorrent, and can run validator duties. A consensus
divergence or a remotely triggerable crash hits every node on the same version at once, so it is a
network-level problem, not a single-host one.

## Binaries in scope
- `erigon`: the node. Primary target.
- `downloader`: standalone snapshot downloader/seeder (BitTorrent), same code as the embedded one.
- `capcli`: Caplin operator CLI; some commands fetch states, blocks and blobs from a beacon API URL.
- `integration`: operator/developer CLI that runs or rewinds sync stages on a local datadir.

They are in `/src/build/bin`. Other `cmd/` tools are not built and are out of scope.

## Where untrusted input enters
- devp2p: RLPx handshake and framing, eth/* wire messages, discv4/discv5 packets, ENR, DNS discovery
  (`p2p/`, `execution/p2p/`, `p2p/sentry/`, `txnprovider/txpool/`).
- Caplin libp2p: gossip topics, req/resp, discovery, SSZ decoding (`cl/sentinel/`, `cl/gossip/`,
  `cl/ssz/`, `cl/cltypes/`, `cl/phase1/`).
- Block and transaction content from any source, including the Engine API (blocks come from
  arbitrary proposers): EVM, state transition, receipts, trie commitment (`execution/vm/`,
  `execution/exec/`, `execution/stagedsync/`, `execution/types/`, `execution/rlp/`,
  `execution/commitment/`).
- Public JSON-RPC over HTTP/WebSocket and GraphQL (`rpc/`, `cmd/rpcdaemon/`, `node/rpcstack.go`),
  and the Beacon API (`cl/beacon/`).
- Snapshot files and torrent metadata from BitTorrent peers; integrity rests on pinned hashes
  (`db/downloader/`, `db/snapcfg/`, `db/preverified/`, `db/seg/`, `db/recsplit/`).
- `capcli`: responses from the beacon API URL it is pointed at. The operator chooses the URL, but a
  malicious or compromised endpoint must not cause code execution or silent acceptance of an invalid
  state.

## Trusted
- The node operator, CLI flags and config files.
- The local datadir, except freshly downloaded snapshot data before verification.
- The holder of the Engine API JWT secret, as an API caller. The payloads it passes are still
  untrusted.
- Admin/debug RPC namespaces are assumed not to be exposed publicly; report issues there at lower
  severity.
- `integration` acts only on a local datadir chosen by the operator. Report its bugs only if
  untrusted chain data stored in that datadir triggers them.

## How we rate severity
- Critical:
  - Consensus divergence from the Ethereum specification (accepting an invalid block or rejecting a
    valid one).
  - Creating, stealing or burning ETH.
  - Remote code execution.
  - Leaking validator or node private keys.
  - An unauthenticated remote crash or halt of the node: any panic, OOM or deadlock reachable from
    p2p, gossip, BitTorrent, or a block or transaction.
  - Bypassing snapshot hash verification.
  - Anything that causes a validator to be slashed.
- High:
  - Unauthenticated remote resource exhaustion that degrades sync or tip-following without a crash.
  - Peer-scoring bypass that enables eclipse attacks.
  - DoS of default-enabled public RPC namespaces with small requests.
  - Memory-safety bugs in cgo code (MDBX, crypto, precompiles) reachable from untrusted input.
- Medium:
  - DoS that requires large or sustained request volume.
  - Issues that require an exposed non-default RPC namespace.
  - Information leaks that expose no key material.
  - `capcli` mishandling a malicious beacon endpoint without code execution.
- Low: issues that require operator misconfiguration or local access, including `integration`.

## Out of scope / leave alone
- Test code and testdata, `tools/`, `dashboards/`, `docs/`, and `cmd/` tools other than the four
  binaries above.
- Go module dependencies, unless the bug is reachable through Erigon code; then report it against
  Erigon.
- Expected resource use by a node syncing from genesis, and the cost of archive-node RPC queries such
  as `debug_trace*` and `trace_*`.

## How to exercise it
- The checkout is at `/src` and the binaries are in `/src/build/bin`.
- Test binaries are pre-compiled. Prefer targeted package tests, for example
  `go test -run TestX ./p2p/discover/`.
- Go fuzz targets exist (`grep -r 'func Fuzz'`); run one with
  `make fuzz PKG=./db/seg FUZZ=FuzzCompress FUZZTIME=60s`.
- Large spec fixtures (EEST, consensus-specs) are not in the image.
- The network is off and `GOPROXY=off`.

## Reports and patches we want
- State the affected chain or fork, the flags required (default or non-default), and the attacker
  position: remote peer, RPC client, block proposer, torrent peer, or beacon endpoint.
- Give the reproducer as a Go test in the affected package, and the patch as a minimal diff that
  includes that test.
- When the code is shared with go-ethereum, say so, because coordinated disclosure with other
  clients may be needed.