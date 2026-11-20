# GDK (Green Development Kit) Threat Model

GDK is Blockstream's cross-platform C++ and Rust wallet core library, powering Blockstream App (Android, iOS, Desktop Qt) and third-party Bitcoin and Liquid wallets. It implements BIP32/BIP39/BIP85 key derivation, descriptor/PSBT/PSET transaction construction and signing, Liquid Confidential Transactions (blinding/unblinding, rangeproofs/surjection proofs), 2FA and CSV timelock recovery for multisig wallets, PIN-based key encryption, and Electrum / Green backend network protocols.

## Assets

- **Wallet secrets**: mnemonics, BIP32 master/account keys, private signing keys, Liquid master blinding keys, PIN client secrets (`gdk_pin_client`).
- **Signing integrity**: transactions and PSBTs/PSETs must only sign the exact destinations, amounts, Liquid asset IDs, fees, and inputs authorized by the caller.
- **Privacy**: xpubs, addresses, blinding factors, and transaction history.

## Trust boundaries and where untrusted input enters

1. **Electrum servers (`subprojects/gdk_rust/gdk_electrum/`)**:
   - Block headers, transaction histories, raw transactions, Merkle proofs, fee estimates, and script-hash notifications. An Electrum server may be malicious or MITM'd (especially over plaintext or custom servers). Raw transactions must be verified against txids, and Liquid asset/blinding proofs must not be forgeable.
2. **Green multisig backend & PIN server (`src/ga_session.cpp`, `src/session_impl.cpp`, `subprojects/gdk_rust/gdk_pin_client/`)**:
   - WebSocket/WAMP messages, HTTP responses, unblinded/partial transactions, 2FA challenges, and encrypted PIN blobs.
3. **Asset Registry & external metadata (`subprojects/gdk_rust/gdk_registry/`)**:
   - Asset definitions, icons, tickers, precision, and domain verification metadata. A compromised registry must not spoof asset precision/ticker or corrupt memory.
4. **PSBTs, PSETs, URIs, and QR / BC-UR payloads (`src/`, `src/bcur_*.cpp`)**:
   - Partially signed Bitcoin/Liquid transactions, BIP21 URIs, BC-UR fragments, and JSON parameters passed into GDK's C/JSON API (`include/gdk.h`, `src/ga_strings.cpp`).
5. **Hardware wallet responses (`src/signer.cpp`, `src/jade*`)**:
   - Signatures, xpubs, and blinded values returned by external devices.

## Components that matter most / least

- **Matter most**: `src/` (C++ session logic, transaction/PSBT/PSET creation & validation, Liquid blinding/unblinding, AES-GCM/PIN crypto, BC-UR decoding) and `subprojects/gdk_rust/` (`gdk_common`, `gdk_electrum`, `gdk_pin_client`, `gdk_registry`, `gdk_rust`).
- **Matter least**: `docs/`, `docker/`, `gitlab/`, `downloads/`.

## How to exercise it

- Run C++ unit tests: `cd /src/build-gcc && ctest --output-on-failure`
- Run Rust unit tests offline: `cargo test --locked --lib --manifest-path /src/subprojects/gdk_rust/Cargo.toml`
- Run targeted Rust crate tests: `cargo test --locked -p <crate> --manifest-path /src/subprojects/gdk_rust/Cargo.toml`

## How we rate severity

- **Critical**: Theft or loss of funds (e.g., signing wrong outputs/amounts/assets, silent fee inflation, nonce reuse/key leakage, broken Liquid rangeproof/blinding verification); remote code execution / memory corruption reachable from network, Electrum, registry, BC-UR, or PSBT/PSET inputs.
- **High**: PIN/key-storage cryptographic bypass; 2FA/timelock bypass; Liquid asset-ID or amount confusion leading to mis-signed transactions; memory safety bugs in C++ or `unsafe` Rust reachable from untrusted data.
- **Medium**: Server-triggered crashes/DoS (panics, OOM, uncaught exceptions) on untrusted input; privacy leaks (e.g., leaking blinding keys or unintended network calls).
- **Low**: Minor logic bugs requiring local caller misuse or malformed trusted local config.

## Anything to leave alone

- An Electrum server lying about unverified balances/history where SPV proof verification is not enabled or not supported by the protocol.
- Issues assuming an attacker already controls local process memory or the host filesystem where an unencrypted session runs.
