# Threat model: taproot-assets (tapd)

## What this project does and where untrusted input enters

`tapd` is the Taproot Assets daemon. It issues assets onto Bitcoin, transfers
them off chain by passing proofs between parties, commits them into taproot
outputs, and moves them over Lightning as asset channels priced by an RFQ
(request for quote) negotiation. What it is responsible for is not only the BTC
in its wallet but the asset units it holds and the balances it reports to its
users and to its peers.

The chain decides where an asset's history is anchored, but almost nothing an
asset means is on chain. Units, provenance, and ownership live in proof blobs
that arrive over the network, so the parsers and the verifier for those blobs
are the real attack surface: a gap in proof or state transition validation is
not a crash, it is inflation.

Untrusted input arrives over these transports:

1. **Asset proof blobs.** `proof.Blob` decoded through `proof/file.go`
   (`File.Decode`) and `proof/encoding.go`, verified in `proof/verifier.go`
   (`BaseVerifier.Verify`, `VerifyProofSuffix`). Proofs arrive from a proof
   courier (`proof/courier.go`), from a Universe server, from a transfer
   counterparty, and from the local file archive (`proof/archive.go`).
2. **Universe server responses.** `rpcserver/rpcserver.go` implements
   `unirpc.UniverseServer` (`InsertProof`, `QueryProof`, `AssetRoots`,
   `MultiverseRoot`, `SyncUniverse`, and the federation config calls). Peers
   serve the same surface to us as clients, through `universe/syncer.go`,
   `universe/federation.go`, and `rpcserver/universe_rpc_diff.go`. Payloads
   include MS-SMT roots, inclusion and exclusion proofs, leaves, and cursors.
3. **Asset transfer packets.** `tappsbt/decode.go` (`NewFromRawBytes`,
   `NewFromPsbt`) parses a versioned PSBT carrying virtual packets, proofs, and
   alt leaves, from a counterparty or from the local user.
4. **RFQ messages.** `rfqmsg/` encodes requests, buy and sell accepts, rejects,
   and HTLC custom records as TLV. They travel inside Lightning custom records,
   so they are peer bytes, decoded by `rfqmsg/request.go` and siblings, and
   acted on by `rfq/manager.go`.
5. **Asset channel messages.** `tapchannelmsg/wire_msgs.go` defines the funding
   messages (`ProofChunk`, `TxAssetInputProof`, `TxAssetOutputProof`,
   `AssetFundingCreated`, `AssetFundingAck`), decoded in `rpcserver/rpcserver.go`
   and consumed by `tapchannel/aux_funding_controller.go`. A Lightning peer
   chooses every byte.
6. **Authenticated mailbox traffic.** `authmailbox/server.go`
   (`SendMessage`, `ReceiveMessages`, `RemoveMessage`) takes proof-courier
   messages from anyone who can present an on-chain anti-spam outpoint, with
   receiver-key authorization for retrieval and deletion.
7. **Supply commitment data.** `universe/supplyverifier/` pulls commitments,
   events, and provenance from remote servers into local accounting.
8. **Addresses and RPC.** `address/address.go` (`DecodeAddress`) parses a
   bech32-style address string. `taprpc/` defines the gRPC and REST surface,
   authorized in `rpcperms/interceptor.go` against `taprpc/perms.go`. A local
   RPC client is trusted only as far as its macaroon says, and the public
   proof-courier mode deliberately exposes a few methods without one.

Two boundaries change what a finding means. First, `lnd` signs and broadcasts
while `tapd` decides what is worth signing, so a defect in `tapd`'s decision is
where asset authority actually sits. Second, the locally authoritative path (the
wallet's own records, mints, and transfers) and the remote path (proofs and
universe data from peers) have different trust levels and must be reasoned about
separately. Remote data does not become local truth because it arrived, and a
remote root proves nothing about spendability.

## Components that matter most

Ordered by damage if the component is wrong.

1. **`vm/vm.go` with `tapscript/tx.go` and `asset/`.** The asset virtual machine
   decides whether one asset state may become another. `tapscript/tx.go` builds
   the virtual transaction whose single input commits to the MS-SMT root over the
   input assets and whose single output commits to the new asset; the witness is
   a Schnorr signature over it. `vm/vm.go` (`Engine.Execute`,
   `validateStateTransition`, `validateSplit`, `validateWitnessV0`,
   `checkLockTime`) enforces amount conservation, identity continuity, witness
   coverage, collectible indivisibility, and timelocks. `asset/encoding.go` and
   `asset/asset.go` define what an asset is and how it serializes. A missing
   check here is inflation or theft with no chain-level backstop.
   Every previous asset must be consumed exactly once by an authorizing witness, and ordinary
   transfers must conserve units exactly across all inputs, outputs, and splits. Signatures must
   bind the intended inputs, output asset, split root and total, and lock times. Transition forms
   and validation modes must not be interchangeable: witness-only, suffix, or timelock-skipping
   validation must never be consumed as proof of full validity or current ownership.
   Only a validated genesis or grouped-genesis transition may introduce new units. Grouped
   issuance must prove membership under the intended group key and bind that authorization
   to the new asset genesis.
2. **`commitment/` and `mssmt/`.** `commitment/asset.go` and
   `commitment/tap.go` build the per-asset and per-output commitments;
   `mssmt/tree.go`, `mssmt/compacted_tree.go`, `mssmt/proof.go`, and
   `mssmt/arith/arith.go` are the Merkle sum tree they are made of. The sum at
   each node is what bounds value, so a wrapping sum, a mispaired sibling, a root
   that depends on insertion order, or a full-tree versus compacted-tree
   divergence destroys the accounting proof verification rests on. A verifier
   that accepts a derived root without agreeing on sum is accepting free units.
   Roots, sums, and proofs for the same committed contents must be deterministic across insertion
   order and tree implementation. Split leaves must jointly conserve the root's units, duplicate
   commitment keys must not silently replace value-bearing leaves, and callers must never publish
   or accept an incomplete construction. Canonical encodings and checked arithmetic are security
   and interoperability requirements.
3. **`proof/`.** `proof/verifier.go` turns an untrusted blob into a "this asset
   is real and owned" answer, checking chain linkage, inclusion at the anchor
   output, exclusion from every other output of that transaction, split
   construction, spent-input and spender markers, genesis reveals, and the
   transition itself through the VM. `proof/file.go` and `proof/encoding.go`
   are the parsers in front of it, `proof/meta.go` decodes the metadata reveal,
   and `proof/activation.go` decides which evidence a proof must carry at a
   given height.
   A fully verified history must connect every transition to its authorized predecessors back to
   genesis or an explicitly trusted root, and bind the final anchor transaction and output. Split
   roots must be bound by their root locator, and spent-input evidence must prevent a second
   verified spend. Historical validity, current canonical ownership, and spend eligibility are
   different claims. Invalid or partial proofs must never become verified wallet state.
4. **`universe/`.** `universe/archive.go` and `tapdb/universe.go` store and
   serve leaves; `universe/syncer.go` and `universe/federation.go` pull them from
   remote servers and push ours out. The server we sync from and the server we
   push to are peers, not operators. What matters: every remote leaf is verified
   before storage, a failed sync does not promote partial remote data, a local
   tree is not overwritten by a remote one, and pagination and retry terminate.
   Supply commitments are accounting claims, not authority: verification must reconstruct their
   mint, burn, and ignore trees from verified proofs, bind each update to the previous on-chain
   commitment, and accept the result only when the recomputed root matches.
5. **`rfq/` with `rfqmsg/` and `rfqmath/`.** `rfq/manager.go` routes messages
   between peers, `rfq/negotiator.go` decides whether to accept a peer's request
   or fill a local offer, and `rfq/order.go` installs the interceptor policy
   (`AssetSalePolicy`, `AssetPurchasePolicy`) that admits or rejects individual
   HTLCs against a quote. Each accepted quote, and every HTLC using it, must remain bound to the
   originating request, counterparty, direction, asset or verified group, applicable channel
   context, rate, fill limit, and expiry. Replay, concurrency, and restart must not let settled
   value plus unresolved reservations exceed the agreed fill. Unit/millisatoshi conversions in
   `rfqmath/` must use the protocol-defined rounding direction and reject overflow. Invoice
   credit must derive only from valid asset value actually delivered under the applicable quote.
6. **`tapchannel/` with `tapchannelmsg/`.** `tapchannel/aux_funding_controller.go`
   negotiates funding with a peer, validates the proofs it sends, and hands
   `lnd` a funding descriptor; `tapchannel/aux_leaf_signer.go` and
   `tapchannel/commitment.go` sign and verify asset commitments inside the
   channel; `tapchannel/aux_invoice_manager.go` decides whether an inbound asset
   HTLC settles an invoice; `tapchannel/aux_closer.go` and
   `tapchannel/aux_sweeper.go` resolve. Every peer message in
   `tapchannelmsg/wire_msgs.go` is attacker-chosen.
   Local, remote, and unresolved asset balances must conserve the funded inventory through every
   update. Taken together, the Bitcoin commitment, auxiliary commitments, and asset witnesses must
   bind the channel state, HTLC allocation, and exact asset transitions. Funding must bind
   peer-proven assets to the actual funding transaction and outpoint; identifiers outside a proof
   are only selectors and must agree with verified content. Both parties must derive the same
   balances, output allocation, and auxiliary leaves. Cooperative close, force close, breach, and
   sweep must preserve every nonzero entitlement in an enforceable output with the required
   proofs and keys.
7. **`authmailbox/`.** `authmailbox/server.go` is an internet-facing mailbox run
   by third parties. Anyone can send; retrieval requires proof of control of a
   receiver key. What matters: deletion authorization binds the exact receiver
   and message set, a stored message survives a disconnect, and parsing and
   backlog replay are bounded.
8. **`address/` and `tappsbt/`.** Address decode selects network, address
   version, asset version, asset or group target, and courier. Untrusted packets, keys, tweaks,
   and derivation hints must reproduce the committed keys and scripts before signing. Every
   previous asset must be consumed once across the whole transfer, all active and passive assets
   sharing a consumed anchor must be accounted for, and nonzero change must remain spendable by
   the wallet. The funded or signed transaction returned by `lnd` may add permitted BTC funding
   and change, but it must preserve the authorized asset-bearing inputs, outputs, commitments,
   and virtual transitions; those fields must be revalidated before broadcast. No later mutation
   may change what an asset signature authorizes.
9. **`tapdb/`.** The durable record of what we own, reserved, and published:
   `tapdb/assets_store.go`, `tapdb/asset_minting.go`, `tapdb/universe.go`,
   `tapdb/migrations.go`. Bugs here are rarely directly exploitable but turn a
   transient failure into a permanent loss, and SQLite/Postgres parity matters.
   Persist enough intent and recovery material before irreversible effects. Database and proof
   state, reservations, and asynchronous notifications must reconcile to one durable logical
   operation after retry or restart, without duplicate credit, incorrect reservation release,
   lost proof obligations, or forgotten broadcasts. Before changing durable state, chain events
   must be checked against the intended outpoint and the current canonical chain.
10. **`rpcserver/` with `rpcperms/`.** Macaroon enforcement, the public
    proof-courier allowlist, and the per-method permission map. The RPC surface
    is a trusted-user interface, but the public mode is not.

## Out of scope or low priority

- **Generated code.** `taprpc/*.pb.go`, `taprpc/*.pb.gw.go`,
  `taprpc/*.pb.json.go`, `taprpc/*_grpc.pb.go`, and everything under
  `tapdb/sqlc/` is generated by protoc and sqlc from `taprpc/**/*.proto` and
  `tapdb/sqlc/queries/*.sql`. Do not report defects in the generated files. Do
  report a defect in the hand-written caller, or a problem the generator
  faithfully reproduces from a `.proto`, such as a field typed as a value where
  absence must be distinguishable from zero.
- **`itest/`.** Gated by the `itest` build tag; the harness needs a Bitcoin node
  plus a running `lnd` per node, and `make build-itest` fetches `chantools` from
  the network. Not shipped code, and not runnable offline.
- **`docs/`.** Prose, plus `docs/examples/basic-price-oracle` (its own module)
  and `docs/examples/basic-portfolio-pilot`, built by `make
  build-docs-examples`. Sample integration code; not the daemon.
- **`tools/` and `bench/`.** A separate linters/generators module and
  load-generation fixtures. `bench/` is a useful source of valid proofs, but
  neither is shipped.
- **`tapreorg/chainsim/`.** A simulated chain used by tests. A "bug" that needs
  the simulator to misbehave is not a bug in `tapd`.
- **`fn/memory.go`.** Reflection-based size estimation using `unsafe`. Treat as
  opaque unless you show memory corruption rather than miscounting.
- **`cmd/tapcli` and RPC calls made by a human.** A local operator with an admin
  macaroon is trusted. A report needing the operator to hand the daemon a
  malformed request is low value unless the same bytes can arrive from a peer.
- **Genuinely third-party behaviour.** A defect inside `btcd`, `btcwallet`,
  `lnd`, `lndclient`, or `github.com/lightningnetwork/lnd/tlv` is upstream's.
  Report it only if `tapd` hands them input it should have rejected first.

## How to exercise it

The image is a Go image built from a clean checkout of
`https://github.com/lightninglabs/taproot-assets` on `main`. The root `go.mod`
declares `go 1.27.3`; the extra Go modules in the tree are `taprpc/`, `tools/`,
and `docs/examples/basic-price-oracle`, none of which the root build needs.
Modules are downloaded during the image build, so the scan must not fetch
anything: keep `GOPROXY` off and add no dependency.

Build and test with the tags the project uses: `make/testing_flags.mk` sets
`DEV_TAGS = dev monitoring` and `make unit` runs `go test` with
`-tags="dev monitoring nolog"`.

```
go build -gcflags='all=-N -l' ./...
go test -count=1 -tags="dev monitoring nolog" ./...
go test -count=1 -tags="dev monitoring nolog" -run '^$' ./...   # compile test binaries only
go test -count=1 -tags="dev monitoring nolog" ./vm/ ./commitment/ ./mssmt/...
```

`make unit pkg=vm` narrows that to one package and
`make unit pkg=proof case=TestProofFileVerification` to one case. `make
unit-race` adds `-race`, `lowscrypt`, and pins
`GOEXPERIMENT=nosizespecializedmalloc`. The test surface is table-driven and
needs no chain:

- **The VM.** `vm/vm_test.go` (`TestVM`, `TestSplitRootAmount`,
  `TestRelativeLockUnknownInputHeight`, `TestBIPTestVectors`) builds transitions
  from named helpers and compares the error to a sentinel.
  `vm.New(newAsset, splitAssets, prevAssets, opts...)` then `Engine.Execute()` is
  the entry point; `vm.WithChainLookup` takes a stub. `asset/mock.go` has
  `RandAsset` and `RandGenesis`.
- **Commitments and MS-SMT.** `commitment/commitment_test.go` covers
  `NewAssetCommitment`, `TapCommitment.Upsert`/`Delete`/`Merge`, splits, and alt
  leaves. `mssmt/tree_test.go` and `mssmt/proof_test.go` exercise both
  `FullTree` and `CompactedTree`; comparing them over one operation sequence is
  the cheapest way to show a divergence.
- **Proofs.** `proof/verifier_test.go`, `proof/proof_test.go` (which holds
  `TestProofFileVerification`), and `proof/encoding_test.go` are table-driven
  over encoded blobs. `proof/mock.go` and `proof/testdata/` let you build a valid
  proof and mutate one field.
- **Universe.** `universe/archive_test.go`, `universe/syncer_test.go`,
  `universe/federation_test.go`, and `universe/syncer_delta_test.go` use
  in-process fakes (`newTestArchive`, `mockMultiverse`). A remote server can be
  simulated with a `bufconn` gRPC server; `proof/courier_test.go` registers
  `universerpc.RegisterUniverseServer` against a local listener.
- **RFQ.** `rfq/order_test.go` installs a policy and feeds it HTLCs: the shortest
  path from a crafted custom record to an admitted or rejected HTLC.
- **Channels.** `tapchannel/aux_funding_harness_test.go` and
  `tapchannel/aux_funding_controller_test.go` drive a funding negotiation between
  two in-process controllers, the practical substitute for two `lnd` nodes.
  `tapchannel/aux_invoice_manager_test.go` covers settlement decisions.
- **Persistence.** `tapdb` tests run on SQLite by default, or on Postgres with
  `-tags="test_db_postgres"`. Prefer SQLite: it needs no live server.
- **Parsers.** Twelve `Fuzz` targets exist and are the right home for a decoder
  finding: `proof/fuzz_test.go` (`FuzzProof`, `FuzzFile`, `FuzzFileProofDecode`),
  `asset/asset_test.go`, `commitment/fuzz_test.go`, `mssmt/fuzz_test.go`,
  `rfqmsg/fuzz_test.go`, `tapchannelmsg/fuzz_test.go`, `address/address_test.go`,
  `backup/fuzz_test.go`, and `internal/ecies/ecies_test.go`. Run one with
  `go test -run '^$' -fuzz='^FuzzProof$' -fuzztime=60s ./proof/`; `make fuzz`
  uses `FUZZPKG` from `make/fuzz_flags.mk`.

What the image cannot do: there is no Bitcoin node, no `lnd`, no proof-courier
server. `itest/` cannot run at all, and anything needing a confirmed
transaction, a real header, or an `lnd`-signed output must be reproduced against
a substitute: a stub `asset.ChainLookup`, `proof/mock.go` for anchors, a
`bufconn` gRPC server for universe peers, a mock peer messenger for channel
funding. Concurrency findings show up reliably only under `-race`; prefer a
deterministic interleaving hook over a statistical reproducer.

A reproducer needing a live chain, a second node, or an operator server is still
in scope; say which substitute you used and what production adds. Expectations do
rise with the size of the claim: a claim of asset inflation should be expressible
against a stub, because the VM, commitment, and proof layers all are.

## How we rate severity

Rate on demonstrated impact in a real deployment, not on where the code sits or
how unusual the input is. Two readers with this section should reach the same
number for the same bug.

**Critical.**

- Any path by which an attacker gains asset units they were not issued, spends
  units they do not hold, or causes a victim to accept units that do not exist
  on the canonical chain. A validation gap in `vm/vm.go`, `tapscript/tx.go`,
  `commitment/`, `proof/verifier.go`, or the MS-SMT sum arithmetic that yields
  inflation belongs here even when the reproducer is a unit test with no
  network.
- Any way to make a commitment or proof verifier accept one anchor output as
  committing to two different asset sets, or to make a spent asset appear
  unspent and spendable again.
- Remote, unauthenticated memory corruption in a parser reachable from proof,
  universe, mailbox, RFQ, channel, address, or packet bytes.
- Remotely triggerable divergence between two honest nodes about whether a
  transition or proof is valid, where the divergence itself moves value.
- Silent loss: a path that signs away or strands a user's units while reporting
  success.

**High.**

- Missing or bypassable authorization that lets a remote peer sound like another
  peer, or replay another peer's quote, channel message, or proof into a context
  where it has an effect it was not signed for. Quote and response session
  binding is the canonical example.
- A remote, authenticated-peer denial of service that is cheap to repeat and
  unbounded: an allocation sized by an attacker field, an unbounded goroutine or
  subscription per message, a sync loop that never terminates against a
  non-progressing server, a lock an attacker can hold. Raise to critical if it
  needs no authentication, or if it blocks safety-critical recovery such as
  proof delivery, input unlocking, or sweeps, rather than merely degrading
  service.
- Acceptance of unverified remote state as trusted local state: a universe leaf
  stored or served as valid without verification, or a remote root treated as
  authoritative for local ownership.
- Corruption of durable state reachable from normal operation that makes an
  asset unrecoverable after restart.

**Medium.**

- A panic, nil dereference, bad integer conversion, or index-out-of-range
  reachable from peer or file input where the process survives or restarts and
  no value moves. `tapd` dying on a malformed proof from a courier is real and
  worth fixing, but it is not critical.
- Bounded resource amplification: a kilobyte of input producing tens of
  megabytes of allocation, or an in-memory backlog that needs the attacker to
  first stake something real.
- Confidentiality loss of one user's non-key data to another user or to an
  unauthenticated caller. Asset metadata and universe leaf data disclosed past
  the configured export policy belongs here.
- A fee, dust, or coin-selection bug that leaves the wallet short of BTC
  without touching asset units.

**Low.** Missing validation with no demonstrable effect on value, liveness, or
confidentiality; an invariant a later layer independently enforces; a redundant
or unreachable check; a crash needing an already-compromised peer, a compromised
operator, or a hand-edited local database; hardening suggestions and log noise;
anything requiring the caller of an exported function to violate its documented
contract.

**Out of scope for a rating, though still worth reporting:** style, lint, unused
code, and test-only defects. A finding confined to `itest/`, `bench/`, or a mock
is not a production vulnerability; report it at low at most, with the reason
stated. A dependency bug is not our bug; rate the `tapd`-side mistake that let it
matter.

Two tie-breakers. Who must the attacker be? Unauthenticated remote beats
authenticated remote beats local peer beats local operator, and each step down is
one severity step. What do they get? Asset units and spend authority outrank
data, which outranks availability. A crash only a peer who already funded a
channel can trigger ranks below one anyone with a TCP connection can trigger.

## Report and patch preferences

- Lead with the claim in one sentence: what breaks and what the attacker gains.
- A runnable Go test in the package at fault, calling the exported API with a
  literal input and asserting the bad outcome, is the ideal reproducer. Where a
  fixture exists (`vm/vm_test.go`'s transition helpers, `proof/mock.go`,
  `asset/mock.go`, `mssmt/mock.go`, the `proof/testdata/fuzz` corpus), extend it.
- For a parser finding a fuzz target is often the cleanest artifact: add the
  crashing input to the seed corpus and name the `Fuzz` function. Say whether the
  input survives a round trip.
- When the path needs peers, chain data, or an operator, express the reproducer
  against the narrowest substitution that still fails and name it: a stub
  `asset.ChainLookup`, an in-process gRPC universe server, a mock peer
  messenger, `internal/test/mock.go`'s `MockSigner`. State what production adds
  and what you could not check offline.
- A patch is welcome and should be minimal and local: add the check, return the
  error, keep the existing sentinel so downstream `errors.Is` still works. Do
  not restructure a decoder, rename exported types, or change an interface in
  `tapscript/interface.go` or `universe/interface.go` without saying why.
- Do not weaken a check to make a reproducer pass, add a test-only bypass, or
  change a serialized format to dodge a validation problem; these formats are
  consensus between implementations.
- Group findings sharing a root cause into one report. The same missing check in
  an encoder, a decoder, and a caller is one finding.
- State the commit tested, the package and function, the tags, and whether you
  needed `-race`.
- If a finding is a hypothesis rather than a demonstrated effect, say so in those
  words. A labelled unproven concern about a value-bearing path is useful; an
  unproven concern dressed as an exploit is not.

## Anything to leave alone

Specific false-positive generators in this codebase:

- **Saturating arithmetic that is deliberate.** `vm/vm.go`'s `overflowSafeAdd`
  clamps at `math.MaxUint64` on purpose: it computes a comparison bound for a
  timelock, where a clamp fails closed. Likewise `mssmt/arith/arith.go` (`Add`,
  `CheckAdd`) returns `ErrOverflow` rather than wrapping by design; show a call
  site that discards the error, not that the function can fail.
- **`-N -l` build flags.** The image builds with `DEV_GCFLAGS := -gcflags
  "all=-N -l"`, so optimisation is off: variables live longer, stacks are larger,
  generated code differs. Do not report "the secret is not zeroed", "this is
  slower than it should be", or any timing or memory-ceiling observation that
  holds only without optimisation.
- **Test-only helpers and mocks.** `asset/mock.go`, `proof/mock.go`,
  `mssmt/mock.go`, `tappsbt/mock.go`, `rfq/mock.go`,
  `tapchannel/aux_funding_harness_test.go`, `internal/test/mock.go`, and the
  `chainsim` package are deliberately permissive: fixed randomness, signers that
  accept anything, keys derived from constants. A weakness in any of them is not
  a finding. `internal/test/helpers.go` uses `math/rand` under a
  `//nolint:gosec` comment, as intended.
- **Unknown odd TLV types must be ignored.** Forward compatibility is a
  requirement: unrecognised odd record types must be skipped and unknown even
  types rejected. `internal/test/generic.go` has `RunUnknownOddTypeTest` for
  exactly this. Decoding that accepts extra unknown odd fields is behaving
  correctly.
- **Findings that need the caller to have already violated a documented
  contract.** Several verifiers take a caller-supplied input set or root and
  document that the caller owns its contents. `vm.New` is given the
  `commitment.InputSet` to validate against; `verifyOptions.trustedRoot` in
  `proof/verifier.go` is reachable only through `VerifyProofSuffix`, whose
  caller supplies the trust boundary on purpose; `vm.WithSkipTimeLockValidation`
  exists so partial validation can run without chain access. A finding must show
  bytes arriving from outside the process, or a path that promises full
  verification reachable with such a relaxation silently applied.
- **Cryptographic primitives that are already right.** `internal/ecies/ecies.go`
  uses HKDF-SHA256 and ChaCha20-Poly1305 from `golang.org/x/crypto`. Do not
  report non-constant-time comparison of a public key, a nonce derived rather
  than random when it comes from a unique input, or ciphertext length revealing
  plaintext length. `asset/burn.go`'s burn key tweaks a NUMS point with the
  outpoint, asset ID, and script key: the result is provably unspendable, and
  "spendable by whoever knows the tweak" is not a finding because the tweak is
  public.
- **`tapscript/script.go`'s anyone-can-spend asset script.** The channel funding
  script tree deliberately commits to `OP_TRUE` at the asset level; the BTC
  output is a 2-of-2 MuSig2, as the comment above
  `NewChannelFundingScriptTree` says.
- **The `tapd`/`lnd` key split.** `lnd` holds the internal key and `tapd` the
  taproot tweak, so neither alone can spend. Reporting that is reporting the
  security model.
- **SQLite versus Postgres differences the code handles.** `tapdb` supports both
  with backend-specific files (`tapdb/test_sqlite.go`, `tapdb/test_postgres.go`).
  A difference in error text, code, or isolation level is not a finding unless an
  accepted protocol state differs. Retry on serialisation failure is expected.
- **Reorgs beyond the configured depth.** `tapd` reconciles within
  `reorgsafedepth`; inconsistency after a deeper reorg is outside the guarantee.
- **Startup validation failures in `tapcfg/`** abort the daemon by design. A
  rejected config is not a denial of service.
- **Generated `tapdb/sqlc` and `taprpc` code**: report the `.sql` or `.proto`
  only when the generated result is insecure.
