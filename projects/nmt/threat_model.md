# nmt threat model

nmt implements the Namespaced Merkle Tree used by Celestia. Each row and column root of the extended data square is an NMT root. celestia-app, celestia-node, and rollup clients use NMT proofs to prove that shares of a namespace are included in a block, and that no other shares of that namespace exist. Protect the soundness and completeness of those proofs.

## Existing project guidance

Read the checkout's `README.md`, `docs/spec/nmt.md`, `docs/nmt-lib.md`, `docs/proof-format.md`, and the audit report in `docs/audit`. The Quint model in `nmt_quint_model` describes intended behavior. Use the scanned checkout for technical instructions, since linked documentation follows `main`.

## Actors and entry points

Treat block proposers, full nodes serving shares and proofs, and anyone who supplies a proof as adversarial. A verifier holds only a trusted root.

- Proof verification: `VerifyNamespace`, `VerifyInclusion`, `VerifyLeafHashes`, `VerifySubtreeRootInclusion`, `ComputeRootWithBasicValidation`, and absence and empty range proofs. Every proof field is attacker-controlled.
- Proof decoding: `ProtoToProof`, `Proof.UnmarshalJSON`, and `ToLeafRanges`.
- Hashing: `NmtHasher` in `hasher.go`, including leaf and node validation, namespace ordering, and the ignore max namespace rule.
- Tree building: `Push`, `Root`, and `ProveRange` on leaves supplied by a proposer.

## Scope and ownership

The whole repository is in scope. Prioritize, in order:

1. A proof that verifies for shares not in the tree, or for an incomplete set of shares of a namespace.
2. An absence proof that verifies for a namespace that is present.
3. Two different leaf sets with the same root, or namespace range checks that can be bypassed.
4. Panics, unbounded allocation, or super-linear work during proof verification or decoding.

`nmt_quint_model`, `imgs`, and test files are support material. Report them only for a concrete security failure.

## Build and bounded validation

The checkout is `/src`. Modules and the test build cache are populated before network access is removed. `GOPROXY=off` and `GOFLAGS=-mod=readonly` make a missing module fail fast. Do not edit `go.mod` or `go.sum`.

The scanner VM has two CPUs and 8 GB of memory. Keep `-p` and `-parallel` at two and always pass `-timeout`.

```sh
go test -p 2 -timeout 10m ./...
timeout --kill-after=5 300 go test -run '^$' -fuzz='^FuzzProveVerifyNamespace$' -fuzztime=120s -parallel=2 .
```

## Evidence and severity

Record the exact revision, the tree, the proof, the namespace, and the verifier call. Show a proof that verifies when it should not, or a reproducer for a crash. Keep source-only hypotheses separate from reproduced behavior.

Rate severity by impact on the Celestia network:

- Critical: a forged inclusion, completeness, or absence proof that verifies against an honest root.
- High: a panic or resource exhaustion reachable from a proof or leaves supplied by one peer or proposer.
- Medium: bounded resource amplification, or accepting malformed proofs without a demonstrated forgery.
- Low: defense-in-depth hardening and issues that need a caller to violate a documented contract.

Keep patches minimal and add a test that fails before the fix. A change to hashing or proof format breaks compatibility with celestia-app and celestia-node, so call it out.

Report findings privately to `security@celestia.org` or through a GitHub security advisory, as described in the [celestiaorg security policy](https://github.com/celestiaorg/.github/blob/main/SECURITY.md). Do not put suspected vulnerabilities in public issues or PRs.
