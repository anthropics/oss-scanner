# Threat model: Starknet sequencer (Apollo), v0.14.4 release branch

## What this project does and where untrusted input enters
The sequencer is the Starknet node that accepts transactions, orders them into blocks, executes them, reaches
consensus with the other sequencer nodes, commits state and syncs with L1 and with peers. It is written in Rust;
`crates/` holds the whole workspace.

Untrusted input enters at:
- **The gateway and HTTP server** (`apollo_http_server`, `apollo_gateway`): user-submitted invoke, deploy-account and
  declare transactions, including their signatures, calldata, resource bounds and fees. Anyone on the Internet can send
  these.
- **Declared contract classes**: user-supplied Sierra programs that `apollo_compile_to_casm` and
  `apollo_compile_to_native` compile, and that `apollo_class_manager` stores and serves.
- **Transaction execution** (`blockifier`, `starknet_api`): attacker-written Cairo contracts run in the Cairo VM or as
  natively compiled code, with syscalls into the sequencer's state, fee charging and resource accounting.
- **P2P networking** (`apollo_network`, `apollo_propeller`, `apollo_mempool_p2p`, `apollo_consensus*`,
  `apollo_p2p_sync`, `apollo_protobuf`): messages from other nodes, including malicious ones, decoded from protobuf.
- **The public RPC** (`apollo_rpc`, `apollo_rpc_execution`): read and simulation requests from anyone.
- **L1 and central data** (`apollo_l1_events`, `apollo_l1_gas_price`, `papyrus_base_layer`, `apollo_central_sync`,
  `apollo_starknet_client`): data read from Ethereum and from feeder gateways, which should be validated, not trusted.
- **Proofs** (`starknet_proof_verifier`, `starknet_transaction_prover`): proofs and prover requests supplied by clients.

Configuration files and command-line flags are written by the operator and are trusted.

## Components that matter most / least
Most important:
- `blockifier`: execution correctness, fee and resource accounting, nonce and signature validation, syscall handling,
  state diffs. Any way to execute a transaction differently from the specification, skip fees, or corrupt state.
- `apollo_gateway`, `apollo_mempool`, `apollo_batcher`: transaction validation, admission and ordering.
- `apollo_consensus`, `apollo_consensus_orchestrator`, `apollo_staking`, `apollo_signature_manager`: safety and liveness
  of block agreement; equivocation, signature or proposal validation flaws.
- `apollo_compile_to_casm`, `apollo_compile_to_native`, `apollo_class_manager`: compiling untrusted classes.
- `starknet_committer`, `starknet_patricia`, `starknet_os`, `apollo_storage`: state commitment and the OS program
  whose output is proven.
- `apollo_network`, `apollo_propeller`, `apollo_p2p_sync`, `apollo_protobuf`: remotely reachable parsing and resource
  use.

Less important but in scope: `apollo_rpc`, `apollo_monitoring_endpoint`, `apollo_l1_*`, `apollo_central_sync`.

Out of scope: `deployments/`, `docker-ci/`, `echonet/`, `scripts/`, `apollo_dashboard`, `bench_tools`, `*_test_utils`,
`*_tests` crates, `apollo_integration_tests`, `starknet_os_flow_tests`, and the `*_cli` crates, except where test code
reveals a bug in production code.

## How to exercise it
- The build compiled the test binaries of `starknet_api`, `blockifier`, `apollo_gateway`, `apollo_http_server`,
  `apollo_mempool`, `apollo_batcher`, `apollo_class_manager`, `apollo_compile_to_casm`, `apollo_compile_to_native`,
  `apollo_consensus`, `apollo_consensus_orchestrator`, `apollo_network`, `apollo_protobuf`, `apollo_p2p_sync`,
  `apollo_rpc`, `apollo_storage`, `starknet_committer` and `starknet_patricia`. Run one crate's tests with
  `cargo nextest run ${SCAN_PACKAGES} -E 'package(<crate>)'`: passing the same package set as the build reuses its
  binaries, while a different `-p` set re-resolves features and recompiles. Any other crate's tests also compile
  offline, since every crate is fetched. Do not use
  `scripts/run_tests.py --changes_only`: it diffs against git history the image does not have.
- Leave `RUST_BACKTRACE` unset when running `apollo_compile_to_casm`'s tests; they compare compiler stderr.
- sccache is not installed; `RUSTC_WRAPPER` is set empty to override `.cargo/config.toml`.
- Tests that need GCS system-test blobs or CI credentials will fail offline; ignore them.
- The Cairo 1 compiler releases blockifier's tests download (2.1.0, 2.7.0 and the pinned version) are already in
  `target/bin/cairo_package__<version>/`; use them to compile test contracts.
- `STARKNET_SPECS_DIR` points at the starknet-specs checkout the RPC spec tests read. `SEED=0` is set as CI sets it.
- The node binary is `target/debug/apollo_node`.
- The pinned `starknet-sierra-compile` binary is under `$CARGO_TOOLS_ROOT`. The `starknet-native-compile` binary is not
  installed (it does not fit the build time); exercise native compilation through `apollo_compile_to_native`'s library
  and tests, which link LLVM 19 from `/usr/lib/llvm-19`.

## How you rate severity
- **Critical**: remote, unauthenticated loss or creation of funds; executing a transaction in a way that breaks
  Starknet semantics (wrong state diff, skipped validation or fee charge, nonce or signature bypass); a single malicious
  peer or transaction breaking consensus safety; remote code execution in the node.
- **High**: a single unauthenticated transaction, declared class or P2P message that crashes or halts the sequencer or
  blocks block production; consensus liveness failures caused by a minority of nodes; state commitment mismatches.
- **Medium**: denial of service that needs sustained traffic or sits behind normal rate limits; resource exhaustion in
  RPC; incorrect but non-exploitable accounting.
- **Low**: issues reachable only through operator-controlled configuration, logging problems, and test-only code.
A panic counts as a crash: a remotely triggerable panic in a node component is High.

## Anything to leave alone
- Do not report vulnerabilities in third-party crates unless the sequencer uses them in an exploitable way.
- Do not report findings that need a malicious operator, a compromised L1 node, or control of a majority of sequencers.
