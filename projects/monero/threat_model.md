# Monero threat model

`monero-project/monero` is the reference implementation of the Monero cryptocurrency. It builds the daemon (`monerod`), the
wallets (`monero-wallet-cli` and `monero-wallet-rpc`, both on top of `wallet2`), and the tools in `src/blockchain_utilities`.

What we protect, most important first:

1. Supply. Amounts are hidden, so nobody can check the total supply by adding up balances. Inflation
   through a broken range proof, balance check or key-image check could go unnoticed indefinitely.
2. Funds and keys. Theft and burned funds can't be undone.
3. Privacy. Whatever a transaction leaks stays on chain forever. A fix in the next release doesn't help
   transactions already made.
4. Consensus. Every node running released code reaches the same verdict on every block and transaction.
5. Availability. Nodes and wallets stay up and keep syncing. A crash that relay delivers to every node
   counts under consensus, not here.

## Project guidance

The [README](https://github.com/monero-project/monero/blob/master/README.md) takes precedence over this
file. Monero's [Vulnerability Response Process](https://github.com/monero-project/meta/blob/master/VULNERABILITY_RESPONSE_PROCESS.md)
(VRP) is background on how the project rates severity; its contact list and reporting channels don't
apply here. Contribution and style rules are in `docs/CONTRIBUTING.md`. OSS-Fuzz already fuzzes Monero,
so shallow parser crashes have probably been found. Stateful and semantic bugs are a better use of time.

## Where untrusted input enters

- **P2P peers.** Unauthenticated, and cheap to run in bulk. Everything on the levin port: handshakes, peer
  lists, timed syncs, block and transaction notifications, chain requests and responses, fluffy blocks,
  and Dandelion++ relay. Bytes go through epee's levin and portable-storage code (`contrib/epee`), then
  `src/p2p` and `src/cryptonote_protocol`, then the binary serialization in `src/serialization` and
  `src/cryptonote_basic`, and finally validation in `src/cryptonote_core`. Most handlers live in
  `src/p2p/net_node.inl` and `src/cryptonote_protocol/cryptonote_protocol_handler.inl`, about 3,000 lines
  each, so include `*.inl` when searching. A payload is fully parsed before the handler checks the
  connection state. Protocol "responses" are one-way notifications, so their contents don't have to match
  what was requested. Say what an attack costs: nothing, proof of work, a mined block, or fees.
- **Transaction senders and miners, through the chain.** Anyone can put crafted but consensus-valid data on
  chain (`tx_extra`, transaction public keys, output keys, unlock times, many outputs to one key), and any
  small miner can shape a coinbase. Every recipient wallet parses it. This boundary has cost real money:
  wallets have counted one deposit several times because of duplicate transaction public keys, and
  credited outputs that could never be spent. The question is whether a sender can make a wallet report
  funds it can't spend, or miss funds it owns. Start at `wallet2::process_new_transaction`.
- **Daemon RPC clients.** The restricted RPC (`--restricted-rpc`, `--rpc-restricted-bind-port`) is what
  public remote nodes expose, so its callers are remote and untrusted. Restriction is enforced in two
  places: `!m_restricted` on entries in the maps in `src/rpc/core_rpc_server.h` hides a method, and
  `m_restricted` checks inside handlers in `core_rpc_server.cpp` cap or strip results. Check both before
  claiming a restricted client reaches something. The unrestricted RPC is for the operator, and a handler
  only it can reach is generally not a finding. The exception is a request the operator never made. By
  default the daemon RPC is unrestricted, on loopback, with no login, so a cross-site request from a
  browser page reaches it, and nothing checks the `Host` header against DNS rebinding. The epee HTTP
  parser and digest auth run before any login or restriction check, on every RPC server.
- **ZMQ RPC and ZMQ pub.** Operator interfaces. ZMQ RPC is on by default and binds to 127.0.0.1. Exposing
  either to untrusted parties isn't supported, so attacks that assume an untrusted ZMQ client are out of
  scope.
- **Wallet RPC clients.** `monero-wallet-rpc` is driven by a trusted local application. Connecting untrusted
  parties to it isn't supported, so attacks from a wallet RPC client, including on its HTTP and
  digest-auth layer, are out of scope.
- **Remote nodes, as seen by the wallet.** Many users point their wallet at a third-party node, and such a
  node can already do a lot: misreport the chain (hide, delay or invent incoming transfers, give wrong
  heights or balances), refuse to relay, and learn much about the wallet's activity. Those are known and
  not worth reporting. A false chain view is also thrown away when the wallet resyncs against an honest
  node (`wallet2::handle_reorg` calls `detach_blockchain`), so a finding that rests on one has to show
  damage done before that. Reportable: the node corrupting wallet memory or running code in it, getting
  key material, getting the wallet to sign or send a transfer the user didn't approve, or causing an
  irreversible loss of funds. Responses are parsed in `src/wallet` (`wallet2`, `node_rpc_proxy`).
- **Multisig co-signers and cold-signing partners.** Each party is untrusted by the others. Key-exchange
  messages (`src/multisig`), partial signatures and nonces, and the unsigned and signed transaction sets
  passed between a view-only wallet and an offline signer are all attacker input. Most of the checks are in
  `src/wallet/pending_tx_validation.cpp` rather than `wallet2.cpp`, so read both before deciding a blob
  goes unchecked. Denial of service between participants is out of scope for now. A co-signer or signing
  partner who refuses to take part, stalls, sends malformed messages, or crashes or blocks the others'
  wallets can already stop the group from transacting, so that alone isn't a finding. Theft, key
  disclosure, unapproved signatures and memory corruption still count.
- **Files handed to the wallet.** Wallet and keys files, the wallet cache (encrypted without a MAC;
  `wallet2::load_wallet_cache` falls back to parsing it unencrypted), exported outputs and key images,
  payment URIs, addresses and integrated addresses, OpenAlias DNS records, and transaction, spend and
  reserve proofs. A proof that verifies when it shouldn't (`check_tx_proof`, `check_spend_proof`,
  `check_reserve_proof`) is a finding, because its job is to convince someone else.
- **Hardware wallets.** Replies from the device (`src/device`, `src/device_trezor`) are parsed by the host
  and are untrusted. The other direction matters too: a compromised host must not get key material out of
  the device or have it sign something other than what it displays.
- **On-disk data.** The LMDB chain database (`src/blockchain_db`), p2p state, and bootstrap files for
  `monero-blockchain-import`. Say who could produce a malformed file, and how.
- **Tor and I2P.** `src/net`, `docs/ANONYMITY_NETWORKS.md` and the SOCKS client. Leaking a node's real IP,
  or linking a locally submitted transaction to the node that sent it, is a privacy bug.
- **TLS on RPC connections.** The daemon RPC server (`--rpc-ssl`) and the wallet's connection to its daemon
  (`--daemon-ssl`) use epee's TLS code in `contrib/epee/src/net_ssl.cpp` and
  `contrib/epee/include/net/net_helper.h`. Both default to `autodetect`, which is opportunistic: it accepts
  an unverified certificate with a warning, and if the handshake fails it reconnects in plaintext. An
  on-path attacker beating `autodetect` is expected. What counts is getting past verification the user
  asked for: with `enabled`, a pinned fingerprint (`--daemon-ssl-allowed-fingerprints`,
  `--rpc-ssl-allowed-fingerprints`) or a CA file (`--daemon-ssl-ca-certificates`), a connection must not
  succeed with the wrong certificate, a mismatched hostname, or no TLS at all. Memory-safety bugs in the
  TLS and certificate handling count either way. P2P connections don't use TLS.
- **DNS.** Lookups go through libunbound in `src/common/dns_utils.cpp` (`DNSResolver`,
  `load_txt_records_from_dns`) and `src/net/resolve.cpp`. A resolver or on-path attacker controls the
  answers unless DNSSEC rejects them. The users:
  - Seed nodes. A fresh node looks up DNS seeds for its first peers; answers that fail DNSSEC are dropped,
    but unsigned answers are accepted. A way to feed a new node only attacker-chosen peers helps an
    eclipse attack.
  - TXT records from the moneropulse zones, which need valid DNSSEC on at least two domains and a
    majority that agree. They drive the update check (`--check-updates`, default `notify`; `download`
    checks the file's SHA256 against the record), DNS checkpoints (enforced only with
    `--enforce-dns-checkpointing`) and the DNS blocklist (`--enable-dns-blocklist`, off by default; it
    bans the IPs and subnets it lists for a while, see `update_dns_blocklist` in `src/p2p/net_node.inl`).
    Whoever controls those zones is trusted by design. Bugs that let someone else get records accepted
    (a DNSSEC or majority-check bypass), or that make a valid record do more than it should (a blocklist
    entry banning more than it names, a bad entry breaking the rest of the list), count.
  - OpenAlias in the wallet (`addresses_from_url`), which turns a name into a payment address. The user is
    shown the DNSSEC status and asked to confirm. Getting a forged address accepted without a DNSSEC
    failure being reported is a finding.
  - DNS leaks. With `--proxy`, seed and blocklist lookups are turned off unless `--proxy-allow-dns-leaks`
    is set. Any other lookup that reveals a proxied node's or wallet's activity to the local resolver is a
    privacy bug.

  The record parsers (TXT, A, AAAA, TLSA) and OpenAlias parsing handle attacker-controlled bytes when
  DNSSEC is not available, so memory-safety bugs there count.

## Components that matter most and least

Highest priority:

- Consensus validation: `src/cryptonote_core` (`blockchain.cpp`, `tx_pool.cpp`,
  `tx_verification_utils.cpp`, reorgs, difficulty, block weight and fees), `src/ringct` (CLSAG/MLSAG,
  Bulletproofs and Bulletproofs+, amount commitments), `src/crypto` (key derivation, key images,
  hash-to-point, point and scalar checks), `src/hardforks`, and the consensus parts of
  `src/cryptonote_basic`. Bugs here mean inflation, double spends or chain splits.
- FCMP++: `src/fcmp_pp` (curve trees, `tower_cycle`, the C/C++ FFI) and the Rust crate it links,
  `src/fcmp_pp/fcmp_pp_rust`, which pulls `helioselene`, `ec-divisors`, `full-chain-membership-proofs` and
  `monero-fcmp-plus-plus` from monero-oxide at a pinned revision. The code is built and linked into
  `ringct`, but on master nothing in `src/` outside that directory calls it yet: there is no FCMP++
  `RCTType` and no fork version, and Carrot isn't merged. Rate a bug here by what it would do once FCMP++
  activates, and say that it isn't live yet. Once live, a proof that wrongly verifies is inflation or a
  double spend. The crate builds with `panic = "abort"` and `overflow-checks = true`, so any panic or
  overflow a transaction can trigger will abort every node that validates it. Check values crossing the
  FFI in both directions. Only unit tests cover this code (`tests/unit_tests/curve_trees.cpp` and the
  `fcmp_pp` cases in `tests/unit_tests/crypto.cpp`).
- Network-facing parsing: `src/p2p`, `src/cryptonote_protocol` (including `levin_notify` and
  Dandelion++), the levin and HTTP code in `contrib/epee`, and serialization (`src/serialization`, epee
  portable storage). Any peer reaches these.
- `src/rpc`: `core_rpc_server`, the restricted-mode checks, and request size and count limits.
- TLS and DNS: `contrib/epee/src/net_ssl.cpp`, `src/common/dns_utils.cpp`, `src/net/resolve.cpp`, and the
  users of DNS records (seed nodes, `src/common/updates.cpp`, `src/checkpoints`, the DNS blocklist,
  OpenAlias).
- The wallet: `src/wallet`, `src/simplewallet` and `src/device*`, for fund and key safety against crafted
  on-chain data, input files and devices, and against a remote node within the limits above.
- Multisig: `src/multisig` and the multisig paths in `wallet2`. It's labelled experimental, but it's in
  scope. A co-signer must not be able to extract another participant's secrets, bias the shared keys, or
  get a transfer signed that the others didn't approve. Denial of service by a participant is out of
  scope.

Easy to get wrong in consensus code:

- Pool policy is not consensus. The minimum fee, `MAX_TX_EXTRA_SIZE` and the unlock-time rule are checked
  in `tx_memory_pool::add_tx` for relay only; transactions in blocks skip them. Applying a relay rule to
  blocks is a hard fork. The pool also feeds `fill_block_template`, so if the pool keeps a transaction
  that consensus rejects, default miners build invalid blocks.
- Alt-chain blocks are stored and only fully validated when a reorg applies them, and the alt-chain paths
  (difficulty, RandomX seed) have diverged from the main-chain ones before.
- Below the height in the embedded `checkpoints.dat`, fast sync (on by default on mainnet) accepts blocks
  without proof-of-work or input checks.
- Determinism: no floating point in consensus. `assert` is compiled out of release builds, including the
  build in this image, so it doesn't guard anything. `size_t` is 32 bits on i686 and ARMv7, which CI still
  builds, although every release target is 64-bit. Cuprate, a second node implementation, follows the
  same rules, so a monerod quirk can split the network.
- Key images are compared as bytes. That only works because point and scalar decoding reject
  non-canonical encodings, so any new decoder (Rust, `mx25519`) has to accept and reject exactly the same
  inputs.

Lower priority but still in scope:

- `src/blockchain_utilities` and other command-line tools, mostly run by the operator on local files.
- `src/blockchain_db` corruption paths that need an attacker-produced database.
- Bundled third-party code under `external/` (RandomX, LMDB in `db_drivers`, easylogging++, supercop,
  rapidjson, mx25519, polyseed, utf8proc, qrcodegen) and the Rust crates from monero-oxide and crates.io
  are in scope only when Monero reaches the bug with attacker-controlled data. polyseed and utf8proc see
  wallet seeds and user-supplied strings. Name the upstream owner when proposing a fix.

Out of scope:

- Anything that needs more than 50% of the network hash rate (or equivalent luck).
- The project's websites and other live infrastructure. Only the code is in scope.
- `tests/`, test vectors and keys in test data, which are public on purpose.
- The GUI wallet, which lives in a separate repository.
- Untrusted clients of the wallet RPC or the ZMQ interfaces.
- What a remote node can already do to a wallet: misreport the chain, withhold transactions, or learn
  about the wallet's activity.
- Denial of service by a multisig co-signer or a cold-signing partner against the other participants, for
  now: refusing to sign, stalling, sending malformed messages, or crashing or blocking their wallets.
- Features that have been removed: UPnP (`--igd` is still accepted but does nothing), bootstrap-daemon
  mode, and RPC payments.

## How to exercise it

- The checkout is `/src`, with submodules initialised. The build is `/src/build`: RelWithDebInfo with
  `BUILD_TESTS=ON` and a `compile_commands.json`. Binaries (`monerod`, `monero-wallet-cli`,
  `monero-wallet-rpc`, the blockchain utilities) are in `/src/build/bin`, and test drivers are under
  `/src/build/tests`.
- Rust crates, Python test packages and submodules were fetched while the image was built, so rebuilding
  offline works. Use `-j2` on the analysis machine and rebuild only the targets you need.
- There is no sanitizer build. If you need one, configure a separate directory with
  `-DCMAKE_BUILD_TYPE=RelWithDebInfo -DSANITIZE=ON -DBUILD_TESTS=ON`, which instruments the C and C++
  code only. Don't combine `Debug` with `SANITIZE=ON`: that builds the Rust crate with nightly Rust, which
  isn't installed. A full build on two cores takes a long time.
- Tests are in `tests/`:
  - `unit_tests`: gtest. Run with `--data-dir=/src/tests/data` and `--gtest_filter`.
  - `core_tests`: replays generated blocks and transactions through a real `cryptonote::core` on a fake
    chain. This is the place to prove that a block or transaction gets the wrong verdict. Run one scenario
    with `--generate_and_play_test_data --filter=<glob>`; the full run takes hours.
  - `functional_tests`: Python scripts driving `monerod` and `monero-wallet-rpc` on regtest.
  - `performance_tests`.
- Only `unit_tests` ran during the image build, with the filter Monero's CI uses
  (`-DNSResolver.*:AddressFromURL.*:select_outputs.*`). `DNSResolver.*` and `AddressFromURL.*` need the
  network and fail offline.
- The fuzz harnesses in `tests/fuzz` aren't built. To build one, re-run CMake on `/src/build` with
  `-DENABLE_FUZZ_TEST=ON` and build its `<type>_fuzz_tests` target; the libraries already built are
  reused. Each harness reads one input file, and seed inputs are in `tests/data/fuzz/<type>`. CMake
  copies `tests/data` into the build directory at configure time, so re-run CMake after adding a seed.
  Most of the levin harness is disabled with `#if 0`. The list of harnesses is a fair map of what the
  project considers attacker-reachable.
- For daemon or wallet reproductions, run `monerod` with `--regtest` (or `--offline` with a temporary
  `--data-dir`) and fixed difficulty. Never connect test nodes to mainnet, stagenet or testnet, never use
  real wallets or funds, and never run DoS or exploit attempts against the live network.
- Keep CPU, memory, disk and runtime bounded. A full chain is hundreds of gigabytes; build small synthetic
  chains instead.

## How we rate severity

We use the VRP's three levels:

- **HIGH**: affects the network as a whole, loses people's coins, or is catastrophic in scale. Examples:
  inflation or counterfeit outputs; accepting an invalid signature, range proof, membership proof or key
  image (a double spend); a block or transaction that makes nodes disagree; theft or burning of funds; a
  sender or miner making wallets credit funds that don't exist or can't be spent; leaking spend keys;
  remote code execution on `monerod` through P2P or the restricted RPC in the default configuration; a
  crash that any peer can trigger, or that relay delivers to every node, on default settings; a privacy
  leak written into every transaction the reference wallet builds.
- **MEDIUM**: affects individual nodes, wallets or routers, or has to be exploited carefully. Examples: a
  remote crash or memory corruption that needs non-default settings or a specific victim; memory
  corruption in a wallet from a malicious remote node or input file; a restricted-RPC bypass; a privacy
  leak that links transactions to IP addresses; a multisig co-signer extracting another participant's
  secrets; a forged transaction, spend or reserve proof that the wallet accepts; a cross-site request
  that stops or controls a default daemon; a TLS connection that succeeds despite a pinned fingerprint or
  CA that doesn't match; DNS records accepted without valid DNSSEC where it's required, or a forged
  OpenAlias address shown as DNSSEC-valid.
- **LOW**: hard to exploit or low impact. Examples: issues only the trusted local operator or the
  unrestricted RPC can reach, crashes in operator tools from local files, side channels with no practical
  attack, and clean failures.

If a four-level scale is needed, **Critical** is the worst part of HIGH: inflation, theft, a network-wide
chain split, or unauthenticated remote code execution on default nodes.

Denial of service that doesn't crash a node remotely is rated lower. Resource exhaustion counts when it
costs the attacker much less than the victim, and when the effect is measured rather than inferred from a
large allocation in the source.

Sanitizer output, an assertion or a crash class doesn't set severity on its own. Show how an attacker
reaches it and what happens in a normal release build.

## Anything to leave alone

These are the usual reasons a candidate finding in this codebase turns out not to be one. Say in the
report which ones you checked.

- The serializer already bounds it. Before reporting an allocation driven by a peer-supplied count, find
  the bound (or its absence) in the read path in `src/serialization` and
  `contrib/epee/include/serialization`. For Bulletproofs+, proof dimensions are checked in three places:
  the serializer, `expand_transaction_1`, and the first pass of the verifier.
- The parser is more lenient than it looks, or less. epee's portable storage leaves a missing or
  wrong-sized field at its default and keeps going. The consensus serializer fails closed. Check which one
  parses the type.
- A macro already handles it. `CHECK_AND_ASSERT_MES` logs and returns; `CHECK_AND_ASSERT_THROW_MES` and
  `THROW_WALLET_EXCEPTION_IF` throw. A check one or two frames up often makes a local-looking bug
  unreachable, but a plain `assert` doesn't count.
- The network layer catches it. An exception or failed `CHECK_AND_ASSERT` that ends with the peer being
  dropped is usually the intended behaviour.
- The construction constrains it. In the proof code, divisor arithmetic modulo the field prime and
  point-versus-negation handling have looked broken several times and turned out to be fine once the
  rest of the protocol was taken into account.
- It isn't actually concurrent. Name the two call sites that run at once, or the lock that's missing,
  before calling something a race.

## How we would like reports and patches to look

- Back each finding with a reproducer when one is practical: a `core_tests` or `unit_tests` case, a
  functional test, a fuzz input, or an exact command sequence against a regtest or offline node, with the
  actual output and the expected result.
- Some findings, especially those related to cryptography and consensus rules, can't reasonably be shown with a test,
  such as a soundness flaw in a proof system or a check missing from verification. Report those too,
  with a precise argument: the exact code path, concrete values where possible, and why the property
  fails. Say clearly that it wasn't reproduced.
- Keep what you reproduced separate from what you reasoned from the source, and don't present a
  hypothesis as confirmed.
- State the revision, the build options, whether the path is enabled by default, what the attacker has to
  control (a peer, a restricted RPC caller, a remote node, a co-signer, a local file, a local user), and
  any cost such as proof of work or fees.
- Check `git log` and the existing tests for the same root cause, and say if it looks like a duplicate or
  is already fixed.
- Patches should be minimal, target `master`, ideally follow `docs/CONTRIBUTING.md`, and where practical add or
  extend a test that fails before the fix and passes after it. Flag any consensus-rule change as needing
  a network upgrade (hard fork).
- Findings are private. Don't suggest public issues, pull requests or commit messages that reveal that a
  fix is security-related. Disclosure is up to the Monero maintainers.
