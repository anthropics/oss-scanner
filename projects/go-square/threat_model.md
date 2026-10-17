# go-square threat model

go-square builds and parses the original data square of the Celestia network. celestia-app uses it in `PrepareProposal`, `ProcessProposal`, `CheckTx`, and blob share commitment validation. celestia-node and rollup clients use it to parse shares and blobs they download. Protect consensus determinism, the integrity of share encoding and blob share commitments, and the availability of nodes that decode untrusted bytes.

## Existing project guidance

Read the checkout's `README.md`, `share/README.md`, `CLAUDE.md`, and `COMPATIBILITY.md`. The [Celestia specs](https://github.com/celestiaorg/celestia-app/tree/main/specs/src) define the share format, the square layout, and the blob share commitment rules. Use the scanned checkout for technical instructions, since linked documentation follows `main`.

## Actors and entry points

Treat transaction senders, block proposers, and peers serving shares as adversarial. Every byte slice passed to the library may come from one of them.

- `tx`: `UnmarshalBlobTx`, `UnmarshalIndexWrapper`, and the fibre transaction types decode attacker-controlled transactions from the mempool and from proposed blocks.
- `share`: `NewShare`, `ParseTxs`, `ParseBlobs`, `ParseShares`, info byte and sequence length parsing, namespace parsing, and blob validation decode attacker-controlled shares.
- Root package: `Builder`, `Construct`, and `Build` lay out a square from untrusted transactions. celestia-app relies on honest nodes building the same square from the same block.
- `inclusion`: `CreateCommitment` and the blob share commitment rules compute values that light nodes and rollups use to verify blob inclusion.

## Scope and ownership

The whole repository is in scope. Prioritize, in order:

1. Non-determinism, or different results for the same input across platforms or Go versions, in square construction, share splitting, or commitments.
2. Panics, unbounded allocation, or super-linear work on attacker-controlled bytes or counts.
3. Two different inputs that produce the same shares or commitment, or parsing that accepts malformed shares that an encoder would never produce.
4. Disagreement between the code and the specs on share layout, padding, or commitment rules.

`internal/test`, `testdata`, and the `random_*` helpers are test support. Report them only for a concrete security failure. `nmt` is a separate repository. It is in scope when go-square reaches the affected code, but name the upstream owner before proposing a fix.

## Build and bounded validation

The checkout is `/src`. Modules and the test build cache are populated before network access is removed. `GOPROXY=off` and `GOFLAGS=-mod=readonly` make a missing module fail fast. Do not edit `go.mod` or `go.sum`.

The scanner VM has two CPUs and 8 GB of memory. Keep `-p` and `-parallel` at two and always pass `-timeout`.

```sh
go test -p 2 -timeout 10m ./...
timeout --kill-after=5 300 go test -run '^$' -fuzz='^FuzzBlobRoundTrip$' -fuzztime=120s -parallel=2 ./share
```

Other fuzz targets live in `share/` (`FuzzTxRoundTrip`, `FuzzSharesNeeded`, `FuzzNewInfoByte`, `FuzzValidSequenceLen`).

## Evidence and severity

Record the exact revision, the function reached, the input, and the observed result. State how the input reaches celestia-app or celestia-node: mempool transaction, proposed block, or shares downloaded from a peer. Keep source-only hypotheses separate from reproduced behavior.

Rate severity by impact on the Celestia network:

- Critical: input that makes honest validators disagree or halt, an invalid square accepted by honest validators, or a forged blob share commitment.
- High: a panic or resource exhaustion reachable from a single transaction, a proposed block, or shares served by one peer.
- Medium: bounded resource amplification, or parsing that accepts malformed input without a demonstrated consensus or commitment impact.
- Low: defense-in-depth hardening and issues that need a caller to violate a documented contract.

A panic alone does not determine severity. Show the path from a real caller. Keep patches minimal, add a test that fails before the fix, and note that any change to encoding or square layout is consensus-breaking for celestia-app.

Report findings privately to `security@celestia.org` or through a GitHub security advisory, as described in the [celestiaorg security policy](https://github.com/celestiaorg/.github/blob/main/SECURITY.md). Do not put suspected vulnerabilities in public issues or PRs.
