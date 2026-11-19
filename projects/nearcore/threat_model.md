# nearcore

nearcore is the reference node implementation of NEAR Protocol. It validates and
executes a sharded blockchain, communicates with peers over P2P connections, and
serves JSON-RPC. Security policy: https://github.com/near/nearcore/blob/master/SECURITY.md.
Architecture and protocol references are in docs/architecture and docs/ChainSpec.

## Trust boundaries

- Remote P2P peers and RPC callers may be malicious. Treat message framing,
  compressed/serialized payloads, requests, blocks, chunks, transactions, state
  sync responses, proofs, and smart-contract Wasm as adversarial where the
  protocol permits an attacker to supply them.
- Distinguish unauthenticated peers, authenticated non-validator peers, malicious
  validators, transaction signers, and contract authors. State the peer positions,
  stake, signatures, fees, gas, deposits, or prior state an attack requires.
- Preserve NEAR's consensus trust assumptions: demonstrate an implementation
  failure within those assumptions. Behavior requiring the attacker to control
  a consensus-breaking stake threshold is not by itself an implementation bug.
- Local administrators, node configuration, validator keys, and the local data
  directory are trusted. A forged database or privileged test hook is relevant
  only if ordinary remote input or a realistic node failure can create the same
  condition. Unauthorized remote key exposure remains in scope.

## Priorities

1. Consensus safety and deterministic validation/execution: invalid blocks,
   chunks, proofs or transactions accepted; valid state diverging across honest
   nodes; state-root disagreement; unauthorized minting, spending or state changes.
2. Availability: remotely reachable crashes, memory corruption, algorithmic or
   allocation amplification, unbounded retained state/queues, costly disk work,
   and ways to cheaply stall or isolate honest nodes. Include lifetime and
   concurrency limits, not just the cost of one decode.
3. Transaction/receipt processing, access keys and nonces, gas and fee accounting,
   refunds, cross-shard delivery, async callbacks, congestion control and yielding.
4. Wasm preparation/validation/execution, compiler isolation, host functions,
   memory/register boundaries, crypto verification, and metering correctness.
5. State sync, epoch sync, resharding, trie/flat storage, persistence and recovery
   when an untrusted input or realistic failure can reach the affected path.

NEAR cross-contract calls run asynchronously in separate receipts. Receipt order,
failure/rollback boundaries, delayed or postponed work, and the distinction between
signer and immediate predecessor matter. Do not assume atomic synchronous calls.
Consensus, network, storage and runtime component tests establish different things;
name the actual execution boundary a reproducer exercises.

## Reports and severity

Provide the source commit, affected API/entry point, configuration and features,
protocol version, attacker capabilities, exact input/state and expected versus
actual behavior. Prefer a minimal regression test, TestLoop scenario, or local
node script. Demonstrate how the input reaches the code through a realistic trust
boundary; an internal helper accepting an impossible state is insufficient.

Critical/high impact can include a demonstrated safety violation, unauthorized
fund/state changes, remote code execution, validator-key exposure, or a feasible
severe network/node availability failure. State whether the impact is on one node,
many nodes, one shard, or the whole network, and account for attacker costs and
the system's existing admission, validation and resource limits.

For resource attacks, measure optimized code without sanitizers and distinguish
transient allocation from retained memory and aggregate simultaneous work.
Measurements from the supplied development/test build are not production cost
estimates. For a panic or assertion, verify the consequence in the relevant
production profile; a debug-only assertion alone does not establish a remote crash.
Document optional, off-by-default or unreleased features explicitly.

TestLoop and test_features expose privileged adversarial controls. These are useful
to arrange a scenario, but they do not establish that a remote attacker can cause
the same state. The supplied neard binary uses default node features without
test_features, sandbox or nightly. No mainnet/testnet access or real keys/funds
are needed. Third-party dependency defects should be reported to their upstream.
Do not disable checks, update snapshots or weaken assertions to hide a failure.

## Environment and reproduction

The checkout is available at /src (physical location /work/nearcore). The image
retains Rust 1.95.0 with the checked-in toolchain components, Wasm target and
rust-src, Python harness dependencies, locked Cargo sources including Git sources,
built test contracts, the node binary and compiled test harnesses. Rust target
flags are preserved. Clang and lld are used for native compilation and linking.

The existing dev-artifacts profile shares node/test artifacts. Line-table debug
information is retained, incremental caching is disabled, and normal rebuild/test
parallelism is two. The profile uses development assertions and dependency
optimizations; check production-profile behavior for security-impact claims.
Initial setup uses up to eight available CPUs. RocksDB and Snappy static archives
are compiled once from the locked Cargo sources and reused by the node and test
build graphs. C++ uses line-table debug information; native intermediate object
files are removed after linking, while libraries and Rust build artifacts remain
available for offline rebuilds. No system RocksDB replacement is used.

Run the prepared baseline offline:

```sh
nearcore-tests
nearcore-local-smoke
```

The baseline uses Nextest 0.9.150 with the repository's default fast-test filter,
process-per-test isolation and test_features. It selects the near-network,
near-vm-runner and near-runtime libraries plus the four TestLoop basic examples
(transfer, contract deploy/call, account create/delete, and RPC block query).
The standard filter excludes slow/ultra-slow tests; the public-STUN lookup is also
excluded. Local STUN/network tests still run. The slower tests remain compiled
and can be selected explicitly for a focused investigation.
The separate local smoke check starts the default-feature node with a fresh
single-validator local genesis and requires it to produce blocks through height 3.

For a focused regression, follow AGENTS.md, for example:

```sh
cargo test --locked --profile dev-artifacts -p near-runtime --features test_features \
  --lib verifier::tests::test_validate_transaction_invalid_signature -- --exact --show-output
```

The larger TestLoop suite is compiled and available for focused scenarios; see
test-loop-tests/README.md and test-loop-tests/src/examples. This baseline is not
the entire nearcore CI matrix. Do not run the protocol schema check or update the
OpenAPI specification unless explicitly requested.
