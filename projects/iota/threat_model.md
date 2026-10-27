# IOTA threat model

## Scope and priorities

IOTA is a proof-of-stake blockchain with an object-based state model and Move
smart contracts. This scan focuses on the core protocol, consensus, Move
execution, and attack surfaces of validators and fullnodes.

Prioritize failures that allow unauthorized asset access, violate ledger safety,
cause nodes to disagree on execution, or prevent the network from making progress.
Node compromise and remotely triggered resource exhaustion are also in scope.

The following paths are starting points, not an exhaustive list. Follow calls and
dependencies across crate boundaries when necessary to assess an in-scope issue.

| Area | Starting points | Security properties to examine |
| --- | --- | --- |
| Transaction validation and execution coordination | `crates/iota-core`, `crates/iota-types`, `crates/iota-transaction-checks` | Signatures, sender and sponsor authorization, replay protection, object ownership and versions, locking, scheduling, and validation before and after consensus. |
| Consensus | `crates/starfish/core`, `crates/iota-core` | Stake-weighted quorums, equivocation handling, block and commit validation, data availability, transaction ordering, and recovery. Include malformed encoded data and reconstruction paths. |
| Move execution | `iota-execution`, `external-crates/move` | Bytecode verification, type and memory safety, resource and reference rules, native functions, gas metering, deterministic execution, and package publication or upgrades. |
| System contracts | `crates/iota-framework/packages` | Asset conservation, capabilities, privileged operations, staking, validator membership, rewards, and epoch transitions. |
| Network and node ingress | `crates/iota-network`, `crates/iota-network-stack`, `crates/iota-tls`, `crates/iota-traffic-controller`, `crates/iota-node` | Peer identity, authorization, parsing, message limits, discovery, state sync, randomness messages, backpressure, and cancellation. |
| Public node APIs | `crates/iota-json-rpc`, `crates/iota-grpc-server`, validator services in `crates/iota-core` | Requests that bypass transaction checks, compromise a node, expose secrets, or cause disproportionate resource use. Trace requests into shared core code. |
| State, checkpoints, and recovery | `crates/iota-core`, `crates/iota-storage`, `crates/iota-node-storage`, `crates/iota-snapshot`, `crates/typed-store` | Checkpoint authentication, effects and state consistency, crash recovery, pruning, and validation of downloaded state. |
| Protocol upgrades | `crates/iota-protocol-config`, `iota-execution`, `crates/iota-framework` | Correct feature gating, execution-version selection, committee transitions, and agreement across supported protocol versions. |

Do not exclude Move VM or verifier code because it lives under `external-crates`.
Dependencies are in scope through their use in the node. Include execution
versions needed for supported operation or historical replay, and identify the
protocol version and feature flags required to reach a finding.

Standalone wallets, SDK features, frontends, explorers, indexer or GraphQL
services, developer tooling, and application contracts are outside the primary
focus. Investigate them when they expose or demonstrate an issue in the core
protocol or node. Example contracts, benchmarks, fixtures, and test-only code are
useful harnesses; bugs confined to them are not production vulnerabilities.

## Adversaries and trust boundaries

- An ordinary user can create accounts, submit transactions, publish arbitrary
  Move packages, choose transaction inputs and gas budgets, and make concurrent
  requests to exposed APIs. Treat these inputs as adversarial even when correctly
  signed or structurally valid.
- Network peers can return malformed, inconsistent, stale, oversized, or delayed
  data and can disconnect at inconvenient points. State sync, discovery, and
  checkpoint download paths must establish the trust their consumers require.
- A validator can be Byzantine despite having a valid committee identity and
  transport credentials. It may equivocate, withhold data, or send malicious
  protocol messages. Authentication alone does not make its contents trustworthy.
- For consensus safety and liveness, assess attacks with Byzantine stake strictly
  below one third of the committee's total voting power. State the exact stake
  and identities required. Evaluate liveness under the protocol's network timing
  assumptions; an indefinite network partition alone is not an implementation bug.
- Operators control their host, configuration, and private keys. Do not assume an
  attacker already controls the victim's filesystem, keys, or administrative
  interfaces. If an attack needs a privileged role or an optional exposure,
  describe that prerequisite and the additional boundary it crosses.

Follow the complete path from an attacker-controlled input to the claimed impact.
Account for signature checks, quorum checks, protocol limits, gas charges, and
other validation on that path. A test that constructs an internal trusted type
directly must explain how an attacker can cause that value in normal operation.

## Security goals

- Transactions cannot spend, transfer, mutate, or destroy assets without the
  authorization required by the object model and the defining Move package.
  Protocol accounting preserves supply and applies fees, rewards, and rebates
  according to the active protocol rules.
- Honest nodes agree on committed transactions, effects, checkpoints, and state.
  Invalid transactions and forged certificates cannot acquire validity through
  a different ingress path, a cache, replay, or an epoch transition.
- Untrusted Move code cannot escape verification or execution constraints, forge
  resources or references, access another package's private state, or consume
  disproportionate resources without effective limits or charges.
- Byzantine peers within the fault bound cannot permanently prevent progress or
  force repeated crashes, corrupt recovery state, or create unbounded work on
  honest nodes.
- Remote input cannot cause code execution in a node or disclosure of private
  keys and other secrets. Public ledger contents are not confidential data.

## Severity guidance

Rate demonstrated impact together with reachability, attacker cost, required
stake or privileges, affected nodes, duration, and recovery requirements. Use the
following as scan triage guidance, not an automatic rating based on a bug class:

- **Critical:** unauthorized asset creation or theft; a consensus safety failure
  such as conflicting finalized state under the fault assumptions; a sustained
  network-wide halt requiring coordinated recovery; or remote code execution
  that compromises validators or their signing keys.
- **High:** a practical attack that persistently disables validators or fullnodes,
  causes major service disruption or state corruption, or crosses a significant
  authorization boundary without demonstrated critical impact.
- **Medium:** bounded service disruption, a recoverable crash of an individual
  node, or a resource amplification issue with limited demonstrated impact.
- **Low:** a limited security impact with substantial prerequisites. Explain the
  violated property rather than reporting hardening preferences as exploits.

A panic is not automatically a network halt. A failing request is not automatically
a process crash. For denial of service, measure request size and rate, CPU, memory,
disk or queue growth, attacker fees, persistence, and recovery where applicable.
Separate inexpensive amplification from saturation that requires comparable
attacker resources. A single malicious validator is a valid adversary; document
its stake instead of dismissing an issue solely because it needs committee access.

## Exercising the code

The checkout is at `/src`. The enrollment Dockerfile builds `iota-node` and
`iota-tool`, compiles the `iota-types` library tests, and fetches dependencies for
the root and Move workspaces. The scan runs offline. Other test targets may need
additional compilation; fetching dependencies does not establish that every test
fixture or external service is available.

Start with a focused existing test or add a regression test near the affected
code. Examples of commands to adapt to the finding are:

```sh
cargo test --locked --offline -p iota-types --lib <test_filter>
cargo test --locked --offline -p iota-core --lib <test_filter>
cargo test --locked --offline -p starfish-core --lib <test_filter>
cargo test --locked --offline --manifest-path external-crates/move/Cargo.toml -p move-bytecode-verifier --lib <test_filter>
```

Useful harnesses include `crates/iota-core/src/unit_tests`,
`crates/iota-adapter-transactional-tests`,
`crates/iota-verifier-transactional-tests`, `crates/iota-framework-tests`,
`crates/iota-e2e-tests`, `crates/test-cluster`, `crates/starfish/simtests`, and
`crates/transaction-fuzzer`. Check their manifests and test instructions at the
scanned revision. Deterministic simulation uses the repository's `cargo simtest`
setup; the enrollment Dockerfile does not currently install that wrapper. Do not
treat a plain `cargo test` run as proof that a scenario passed in the simulator.

Use local test networks and synthetic keys or assets for reproduction. Record
missing tooling, fixtures, or services as validation limitations.

## Reports and proposed fixes

For each finding, include the scanned commit, affected code, protocol version and
configuration, attacker capabilities, reachable entry point, violated security
property, and a minimal reproduction with expected and observed behavior. State
what was executed and distinguish demonstrated impact from possible extensions.

Prefer reproductions through an actual ingress path. When a unit-level harness
is necessary, explain which production checks it includes or bypasses. Include
logs and resource measurements where they substantiate the impact.

Group findings by root cause and describe affected entry points together. Prefer
a focused patch with a regression test. Flag any fix that changes consensus,
serialization, gas accounting, or execution semantics and explain whether it
needs protocol-version gating. Preserve historical replay behavior when proposing
changes to versioned execution code.
