# celestia-app threat model

celestia-app is the state machine of the Celestia data availability network. It is a Cosmos SDK application that runs on celestia-core, a CometBFT fork, through ABCI. It orders and commits blob data in the data square, settles payments for blobs published through fibre, and bridges assets through IBC and Hyperlane. Protect consensus determinism and liveness, the integrity of the data square and its commitments, funds and supply, fibre payment settlement, and node availability.

## Existing project guidance

Read the checkout's [AI invariants](https://github.com/celestiaorg/celestia-app/blob/main/docs/ai/invariants.md), [AGENTS.md](https://github.com/celestiaorg/celestia-app/blob/main/AGENTS.md), [specs](https://github.com/celestiaorg/celestia-app/tree/main/specs/src), module READMEs under `x/`, [fibre README](https://github.com/celestiaorg/celestia-app/blob/main/fibre/README.md), [multiplexer README](https://github.com/celestiaorg/celestia-app/blob/main/multiplexer/README.md), and the past audit reports under `docs/audit`.
The invariants INV-1 to INV-7 in `docs/ai/invariants.md` state what the maintainers treat as security properties. Use them to frame findings.
Use the scanned checkout for technical instructions, since linked documentation follows `main`.

## Actors and entry points

Treat transaction senders, peers relaying transactions, and fibre clients as adversarial. Treat any single validator, including the current proposer, as adversarial. Safety is only assumed while more than 2/3 of voting power is honest. Distinguish input any account can submit from input that needs a proposer slot, validator signatures, governance approval, or a module owner.

Transactions enter through `CheckTx` in `app/check_tx.go` and the ante chain in `app/ante`. Trace `BlobTx` unwrapping, share commitment validation, gas and fee checks, message count limits, and parameter filters through to the mempool. Blocks enter through `app/prepare_proposal.go` and `app/process_proposal.go`. `ProcessProposal` must independently verify every property `PrepareProposal` establishes, including square size, share layout, PFB and PFF placement, and the data root. Check whether the `CheckTx` result caches in `app/pfb_tx_cache.go` and `app/pff_sig_cache.go` let a proposer skip a check that a different node never performed. Then follow `FinalizeBlock`, begin and end blockers, and upgrades.

Review the custom modules: `x/blob` (PayForBlobs), `x/fibre` (escrow, payment promises, replay protection, timeouts, withdrawals), `x/valaddr` (fibre host registry), `x/forwarding` (Hyperlane forwarding address derivation and permissionless forwarding), `x/zkism` (SP1 Groth16 proof verification and one-time message authorization), `x/mint` (inflation), `x/minfee`, and `x/signal` (upgrade signalling). Check supply conservation, escrow accounting across deposit, settlement, timeout and withdrawal, replay windows, and authorization of message IDs. Also check the ICA host allowlist in `app/ica_host.go` and the governance parameter filters.

The fibre server in `fibre/` and `fibre/cmd` is a validator-operated gRPC service reachable by unauthenticated clients. Trace shard uploads, payment promise verification against the app node, the hand-written scatter codec in `fibre/internal/grpc`, the shard codec, storage, pruning, and downloads. The fibre client also consumes data from servers that may be byzantine. Review `pkg/rsema1d`, `pkg/da`, `pkg/inclusion`, `pkg/proof`, and `pkg/wrapper` as decoders and verifiers of attacker-controlled bytes.

The multiplexer in `multiplexer/` replays history from genesis and switches between embedded v3 to v9 binaries and the native v10 app at upgrade heights. Review version switching, process lifecycle, and the gRPC bridge between celestia-core and the embedded apps. Any behavior change at existing heights that is not gated by app version (INV-7) breaks sync for new nodes.

gRPC, REST, and CometBFT RPC queries are operator-exposed interfaces. Report resource exhaustion through them only when it is reachable with default configuration and exceeds the cost an operator would reasonably expect.

## Scope and ownership

The whole repository is in scope for source review. The priorities below guide investigation rather than exclude other code.

Prioritize, in order: non-determinism or panics reachable from ABCI that can halt the chain; acceptance of an invalid block or data square by honest nodes; inflation, theft, or bypassing payment for blobs or fibre data; remotely reachable crashes or amplification against nodes and fibre servers; and incorrect proofs or commitments that would mislead light nodes and rollups.

`tools/`, `scripts/`, `test/`, `local_devnet/`, `docker/`, and `observability/` are developer and operator tooling. Report them only for a concrete security failure. The embedded v3 to v9 binaries are prebuilt release artifacts, so report issues in them against the release branch that produced them. celestia-core, the celestiaorg cosmos-sdk fork, go-square, nmt, and hyperlane-cosmos are separate repositories pinned in `go.mod`. They remain in scope when celestia-app reaches the affected code, but identify the upstream owner before proposing a fix. Do not report a library contract violation without a path from celestia-app.

## Build and bounded validation

The checkout is `/src`. The multiplexer binary is `/src/build/celestia-appd`, and the fibre server is `/src/build/fibre`. Go modules, the embedded release binaries, and the test build cache are fetched and populated before network access is removed. `GOPROXY=off` and `GOFLAGS=-mod=readonly` make a missing module fail fast instead of hanging. Do not edit `go.mod` or `go.sum`.

`make test-short` and the multiplexer tests run during the Docker build. The end-to-end suite in `test/docker-e2e` needs Docker and cannot run in this image. The race detector works offline but recompiles from scratch, so use it only on the package under study. These are execution limits, not source-review exclusions.

The scanner VM has two CPUs and 8 GB of memory. Keep `-p` and `-parallel` at two and always pass `-timeout`. Packages under `app/test` start in-process multi-validator networks and are slow. Run single tests with `-run`.

```sh
go test -p 2 -short -timeout 10m ./x/... ./pkg/...
go test -p 2 -timeout 15m -run 'TestProcessProposal' ./app/test
go test -tags multiplexer -p 2 -timeout 10m ./multiplexer/...
```

Use `test/util/testnode` for in-process networks, `test/util/malicious` for a byzantine proposer, and `test/util/blobfactory` and `test/util/testfactory` for transactions. Go fuzz targets are listed in `scripts/test_fuzz.sh`. Bound each run with `-fuzztime` and an external timeout:

```sh
timeout --kill-after=5 300 go test -run '^$' -fuzz=FuzzShardCodecReadNoPanic -fuzztime=120s -parallel=2 ./fibre
```

Reproduce only against in-process test networks and temporary home directories. Never connect to Mainnet Beta, Mocha, Arabica, or other public networks, and never use real keys or funds.

## Evidence and severity

Record the exact revision, app version, build tags, attacker capability (any account, proposer, validator set fraction, governance, module owner), whether the path is enabled on Mainnet Beta, and the observed consequence. Keep source-only hypotheses separate from tests that reproduce the behavior. For consensus findings, show two honest nodes diverging, or an honest node accepting a block that `ProcessProposal` should reject. For resource findings, compare the work performed with the gas paid or the protocol bound, and state the measured cost.

Rate severity by impact on the live network:

- Critical: a chain halt or consensus split triggered by one transaction or by less than 1/3 of voting power; inflation or theft of funds; settling fibre data or blob inclusion without paying; or an invalid data square accepted by honest validators.
- High: a remotely triggerable crash or sustained denial of service against validators or fibre servers with default configuration; permanent loss of escrow or bridged funds needing a privileged but non-malicious actor; or a version-gating error that breaks sync from genesis.
- Medium: limited-scope degradation, bounded resource amplification, or attacks needing an unusual configuration or a malicious validator with significant stake.
- Low: issues needing local access, governance collusion, or other strong preconditions, and defense-in-depth hardening.

A panic, sanitizer report, or bug-class label does not determine severity on its own. A panic recovered by the SDK that only fails one transaction is not a chain halt. Keep confidence, remediation urgency, and disclosure timing separate.

Check Git history and existing tests for the same root cause. Keep patches minimal and follow `AGENTS.md`. Gate any consensus-breaking fix behind an app version, and add a test that fails before the fix and passes after it.

Report findings privately to `security@celestia.org` or through a GitHub security advisory on the repository, as described in the [celestiaorg security policy](https://github.com/celestiaorg/.github/blob/main/SECURITY.md). Do not put suspected vulnerabilities, reproducer details, or unreviewed findings into public issues or PRs. Include the smallest bounded reproducer, actual output, expected result, and evidence limits in each report. Disclosure decisions belong to the Celestia security team.
