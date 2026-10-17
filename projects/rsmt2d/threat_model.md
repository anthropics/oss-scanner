# rsmt2d threat model

rsmt2d implements the two-dimensional Reed-Solomon encoding behind Celestia data availability sampling. celestia-app extends the original data square into the extended data square and computes its row and column roots. celestia-node repairs squares from sampled shares and builds bad encoding fraud proofs from `ErrByzantineData`. Protect the correctness of the encoding, repair, and byzantine data detection.

## Existing project guidance

Read the checkout's `README.md`, `CLAUDE.md`, and the audit report in `audit/`. The [2D Reed-Solomon paper](https://arxiv.org/abs/1809.09044) and the [Celestia specs](https://github.com/celestiaorg/celestia-app/tree/main/specs/src) describe the scheme. Use the scanned checkout for technical instructions, since linked documentation follows `main`.

## Actors and entry points

Treat block proposers and full nodes serving shares as adversarial. A repairing node holds only trusted row and column roots.

- `ComputeExtendedDataSquare` and `ComputeExtendedDataSquareWithBuffer` extend proposer-supplied shares. Honest nodes must compute the same roots.
- `ImportExtendedDataSquare` and `ExtendedDataSquare.UnmarshalJSON` accept squares from peers.
- `Repair` reconstructs a square from partial, attacker-chosen shares and must return `ErrByzantineData` when shares do not match the roots.
- The `Codec` implementation in `leopard.go` wraps `klauspost/reedsolomon`. The tree constructor wraps `nmt`.

## Scope and ownership

The whole repository is in scope. Prioritize, in order:

1. `Repair` accepting a square whose shares do not match the trusted roots, or failing to detect bad encoding.
2. `ErrByzantineData` that blames honest data or carries shares that cannot back a valid fraud proof.
3. Different roots for the same input across nodes, platforms, or Go versions.
4. Panics, unbounded allocation, or super-linear work on attacker-controlled squares, share sizes, widths, or roots.

`klauspost/reedsolomon` and `nmt` are separate projects. They are in scope when rsmt2d reaches the affected code, but name the upstream owner before proposing a fix.

## Build and bounded validation

The checkout is `/src`. Modules and the test build cache are populated before network access is removed. `GOPROXY=off` and `GOFLAGS=-mod=readonly` make a missing module fail fast. Do not edit `go.mod` or `go.sum`.

The scanner VM has two CPUs and 8 GB of memory. Keep `-p` and `-parallel` at two and always pass `-timeout`. Large squares are slow, so run single tests with `-run`.

```sh
go test -p 2 -timeout 15m ./...
timeout --kill-after=5 300 go test -run '^$' -fuzz='^FuzzRepair$' -fuzztime=120s -parallel=2 .
```

Other fuzz targets: `FuzzRepairCorrupted`, `FuzzRepairRootsLength`, `FuzzComputeAndImportExtendedDataSquare`, `FuzzUnmarshalJSON`, and `FuzzLeoRSCodec`.

## Evidence and severity

Record the exact revision, square width, share size, the shares and roots supplied, and the call made. Keep source-only hypotheses separate from reproduced behavior.

Rate severity by impact on the Celestia network:

- Critical: `Repair` returning a square that does not match the trusted roots, or bad encoding that goes undetected.
- High: a panic or resource exhaustion reachable from shares or roots supplied by one peer or proposer, or `ErrByzantineData` that wrongly blames honest data.
- Medium: bounded resource amplification, or accepting malformed input without a demonstrated integrity impact.
- Low: defense-in-depth hardening and issues that need a caller to violate a documented contract.

Keep patches minimal and add a test that fails before the fix. A change to encoding output breaks compatibility with celestia-app and celestia-node, so call it out.

Report findings privately to `security@celestia.org` or through a GitHub security advisory, as described in the [celestiaorg security policy](https://github.com/celestiaorg/.github/blob/main/SECURITY.md). Do not put suspected vulnerabilities in public issues or PRs.
