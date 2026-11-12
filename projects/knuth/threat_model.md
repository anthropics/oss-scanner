# Knuth threat model

## Purpose and assets

Knuth is an MIT-licensed Bitcoin Cash node and C++ development toolkit, with a
native node executable and a C API. It validates and relays blocks and
transactions, maintains chain state and the UTXO set, and provides mining and
RPC interfaces. Protect consensus correctness, UTXO and token accounting,
chain-state durability, availability, and the integrity of data returned to
applications. Treat public-network data as untrusted.

## Trust boundaries

- **P2P:** Inbound and outbound peers, discovered addresses, message lengths,
  serialized objects, scripts, signatures and token data are attacker-controlled.
  Review parsing bounds, resource limits, connection lifecycle and concurrency,
  mempool admission, transaction relay and block processing. Connecting as a peer
  confers no administrative authority.
- **Consensus and synchronization:** Examine the native batch validation path as
  well as traditional transaction validation. Above trusted checkpoints, and with
  full validation enabled, all applicable consensus checks must run with the
  correct network, activation context and resolved prevouts. Below configured
  trusted checkpoints, the fast synchronization path deliberately relies on the
  checkpoint-anchored header chain and matching block bodies while constructing
  the UTXO set. Skipping historical signature checks in this explicitly trusted
  mode is intentional; bypassing validation outside its trust boundary is not.
  Distinguish consensus rules from mempool or relay policy.
- **State and concurrency:** Prioritize UTXO-Z integration, token metadata
  persistence, cross-batch prevout resolution, undo/reorganization behavior,
  asynchronous ownership, cancellation and shutdown. State that survives a
  restart must preserve validation-relevant metadata and accounting.
- **RPC and mining:** The native JSON-RPC service accepts administrative and
  application requests. Establish the actual configured authentication, binding
  and method permissions before assigning impact; do not assume every deployment
  exposes RPC publicly or that all methods require identical privileges. Review
  authorization boundaries, parsing, submitblock, mempool admission and mining
  templates. An invalid block obtained through RPC still must not bypass native
  consensus validation. Document whether an exploit needs RPC credentials,
  explicit remote exposure, a mining participant or valid proof of work.
- **Native WebSocket transport:** This build enables the optional P2P WebSocket
  transport. Its framing, handshake, resource accounting and interaction with the
  underlying P2P state are additional network surfaces. Distinguish this native
  transport from the browser/WebAssembly runtime, which this image does not build.
- **C API:** Review lifetime and ownership contracts, exception barriers,
  caller-supplied buffers and lengths, conversions and serialization. Distinguish
  malformed untrusted data reaching a supported API from a caller already able
  to execute arbitrary native code in the same process.

The main source areas are src/infrastructure, src/domain, src/network,
src/blockchain, src/database, src/node, src/node-exe and src/c-api. Dependencies
used by these paths matter; identify whether a problem belongs to a dependency
or its integration. This configuration uses consensus=False, the default native
validator, not the optional alternate consensus library. Other RPC backends,
WebAssembly and alternate currencies require separate builds.

## Severity and evidence

Rate demonstrated impact and reachability, with explicit prerequisites. Consensus
acceptance divergence, unauthorized spending and remotely reachable code execution
can be critical; explain the rule, activation and network consequences. Memory
corruption and persistent denial of service can be high depending on reachability.
Bounded resource exhaustion, recoverable failures and configuration-dependent
issues require proportionate ratings. Expected administrative operations are not
an authentication bypass. A regtest reproduction proves local behavior; explain
separately what an attacker would need on a production network.

## Build and offline verification

The Dockerfile follows the project's GCC 16 Ubuntu CI environment and Conan
configuration. Network-dependent setup is completed during the image build.
Sources, dependency cache, build tree, compilation database and unstripped Knuth
binaries remain available in /src. Knuth is built without optimization, with line-level debug symbols
and frame pointers; dependencies retain their Release configuration. Unit tests use local fixtures; no blockchain download,
production wallet or external peer is needed.

Inside the finished image, from /src:

```sh
# Core suites registered as complete Catch2 shards, run sequentially.
ctest --test-dir build/build/Release --output-on-failure -j1 \
  -R '^kth_(infrastructure|domain|network|blockchain|node|capi)_test[.]shard-'

# Run an individual suite directly when investigating a reproducer.
./build/build/Release/src/blockchain/kth_blockchain_test
```

Run the finished container with --network none; local loopback remains available.
Use temporary databases, regtest and disposable keys for reproductions. Do not
connect investigations to live networks or use real funds. These commands are
verification instructions, not a claim that the container has already passed.
