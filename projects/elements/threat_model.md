# Threat model: Elements (elements-23.3.x)
Elements is a sidechain-capable fork of Bitcoin Core. It adds confidential transactions (rangeproofs, surjection proofs, blinded addresses), asset issuance and reissuance, and a second, Elements-specific consensus layer on top of Bitcoin's.
## In scope
- Consensus: block and transaction validation, script interpreter (including the Elements opcodes and taproot), sighash handling, rangeproof / surjection proof verification, asset and issuance validation, chain reorganisation.
- P2P networking: message parsing and dispatch, addrman, block/tx relay, headers sync.
- The wallet: descriptor and legacy wallets, key handling, PSBT, signing, key derivation.
- RPC and ZMQ: argument parsing, the RPC surface reachable by an authenticated user, ZMQ notification topics.
- The Qt GUI: parsing of untrusted data received from the node.
- Confidential-transaction cryptography: the secp256k1-zkp integration, blinding, and the generators used for confidential assets.
## Out of scope
- Anything that needs a bug in the C++ compiler, the standard library, or a dependency (Boost, libevent, sqlite, Qt, Berkeley DB, secp256k1-zkp as an external project).
- Attacks that require the operator to run a malicious binary or config.
- Denial of service by resource exhaustion on a local, authenticated interface, unless it is remotely triggerable without a peer identity.
- The build system, packaging and CI.
- Known and documented behaviour, including anything a release note calls out.
## Severity
- Critical: remotely triggerable memory corruption with code execution; consensus inflation (creating or destroying assets or the pegged asset without authorisation); theft of funds.
- High: remotely triggerable crash or memory-safety bug without demonstrated code execution; consensus divergence between two honest nodes; producing a valid proof for a false statement.
- Medium: a bug reachable only by an authenticated RPC user; information disclosure across wallet or key boundaries; a local crash.
- Low: hardening, defence-in-depth, and issues with no demonstrated impact.
## What a good report has
A reproducer that runs offline inside the image, the exact command, the expected and observed behaviour, and why the impact is what you claim. Prefer a real PoC over a theoretical one.
