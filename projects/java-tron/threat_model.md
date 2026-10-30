# Threat model: java-tron

## What this project does and where untrusted input enters

java-tron is the reference full-node implementation of the TRON protocol. It runs DPoS consensus with 27
Super Representatives (SRs) producing blocks in turn, executes smart contracts in the TVM (an EVM-compatible
virtual machine), keeps chain state in LevelDB or RocksDB, and serves HTTP, JSON-RPC and gRPC APIs.

Treat all of the following as attacker-controlled:

- **P2P traffic from any peer**: TCP messages before and after the handshake (HELLO, inventory, block and
  transaction fetch, chain sync) and UDP node discovery. Any host can connect to a public node.
- **Transactions from any account**: any user can submit signed transactions of every contract type, including
  contract deployment (arbitrary bytecode) and contract calls (arbitrary calldata). Every node that receives,
  packs or validates a block executes them.
- **API requests**: public nodes expose HTTP, JSON-RPC and gRPC APIs to the internet without authentication.
- **Blocks from peers**: only the scheduled SR can sign a valid block, but a single SR may be malicious or
  misconfigured. The protocol assumes more than two thirds of SRs are honest; issues that need a colluding
  supermajority are out of scope.

Node configuration files, the local database directory and the local admin interfaces (admin IPC socket and
admin HTTP bound to localhost) are trusted. They are only in scope when reachable by a remote party.

## Components that matter most / least

Most important:

- `actuator/`: transaction execution and the TVM (`org.tron.core.vm`), including precompiled contracts,
  energy accounting and contract storage.
- `consensus/` and `framework/.../core/db/Manager.java`: block production, block and transaction validation,
  fork switching and solidification.
- `chainbase/`: state stores, snapshots and the revoking (rollback) layer.
- `p2p/` and `framework/.../core/net/`: peer handling, message decoding, sync and relay.
- `crypto/`: signature verification and key recovery.
- `framework/.../core/services/`: HTTP, JSON-RPC and gRPC API handlers.

Lower priority:

- `plugins/` (offline database tools run by the operator), `example/`, `docker/`, `start.sh`, and test code.

## How to exercise it

- The image is built on x86_64 with JDK 8 (java-tron requires JDK 8 on x86_64 and JDK 17 on aarch64).
- There is no network after the build. Run Gradle offline, for example:
  `./gradlew --offline :framework:test --tests 'org.tron.core.db.ManagerTest'`.
- Most consensus and execution behaviour can be reproduced as a JUnit test under `framework/src/test` or
  `actuator/src/test`; existing tests start an in-process chain (for example `ManagerTest`,
  `BlockMsgHandlerTest`, and the TVM tests under `org.tron.common.runtime.vm`).
- `AGENTS.md` describes the build, the test layout and the invariants CI enforces.

## How we rate severity

- **Critical**: honest nodes running the same version reach different state or reject each other's blocks
  (consensus divergence); unauthorized movement, creation or freezing of funds; or a party that is not an SR
  majority can stop block production or solidification network-wide.
- **High**: an unauthenticated peer, transaction sender or API caller can crash a node, exhaust its memory, or
  make it stop processing blocks; TVM behaviour that differs from the EVM in a way that breaks contract safety;
  a single malicious SR can cause a fork that does not resolve on its own.
- **Medium**: denial of service that needs significant sustained resources from the attacker; information
  disclosure through public APIs; a single malicious SR causing a temporary fork.
- **Low**: log injection, issues that need local access or a misconfiguration, and hardening suggestions.

Notes for rating and reproducing:

- Transaction execution is limited by wall-clock CPU time per transaction by design. A difference that comes only
  from timing variance between nodes is not a consensus bug by itself; explain why the outcome is deterministic.
- Many behaviours are gated by a fork version (block version) or a chain parameter set by committee proposal.
  State which gates must be active for a finding, and whether it applies with current mainnet parameters
  (`/wallet/getchainparameters`).

## How we would like reports and patches

- Name the branch or commit, the affected file and line, and a reproducer: preferably a JUnit test that fails before
  the fix, otherwise exact steps on a private chain.
- Patches that change consensus behaviour (execution results, validation, state layout) must be gated behind a new
  fork version or chain parameter so that historical blocks replay unchanged. Patches that only change node-local
  behaviour (networking, caching, APIs) do not need a gate.
- Do not use `java.lang.Math`; CI requires `StrictMathWrapper` for cross-JVM determinism.
- Keep patches minimal and do not add or upgrade dependencies.

## Anything to leave alone

- Duplicates of issues we already track privately are handled on our side; you do not need to check for them.
- Do not report the absence of TLS on P2P, HTTP or gRPC ports by itself; operators terminate TLS in front of the
  node.
