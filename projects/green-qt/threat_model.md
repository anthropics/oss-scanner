# Blockstream App (Green Qt Desktop) Threat Model

Blockstream App for Desktop (`Blockstream/green_qt`) is a cross-platform C++20 / Qt 6 / QML desktop wallet for Bitcoin, Liquid, and Lightning. It embeds GDK (Green Development Kit), LWK (Liquid Wallet Kit), GLSDK (Greenlight), and supports software wallets plus hardware wallets (Blockstream Jade, Ledger) over USB HID, serial, and BLE. It also uses a watchdog + `--ui` multiprocess model and custom Crashpad/Sentry minidump stripping (`tools/patches/`) to prevent wallet secrets from leaking in crash reports.

## Assets

- **Wallet secrets**: mnemonics, seeds, PIN-encrypted wallet files, GPG-encrypted or local keystore data, Lightning/Greenlight credentials (`src/`).
- **Transaction signing integrity**: transactions, PSBTs/PSETs, and hardware wallet signing requests must reflect exact destinations, amounts, Liquid assets, and fees displayed in the QML UI.
- **Crash dump / log hygiene**: minidumps and logs must never contain process memory, register state with secrets, private keys, or mnemonics.

## Trust boundaries and where untrusted input enters

1. **Payment URIs, links, and imported files (`src/`, `src/controllers/`, `src/handlers/`, `src/resolvers/`)**:
   - `bitcoin:`, `liquidnetwork:`, `lightning:` URIs, BIP21 parameters, BOLT11/BOLT12 invoices, LNURL, PSBTs/PSETs, and watch-only/descriptor files.
2. **QR codes (`src/`, `ZXing`)**:
   - Camera and image QR decoding including BC-UR animated QR payloads.
3. **Hardware wallet transports (`src/jade/`, `src/ledger/`)**:
   - USB HID, serial port, and BLE messages from external hardware devices.
4. **Remote services (`src/glsdk/`, `src/lightning/`, GDK/LWK backends)**:
   - Electrum servers, Green backend, Greenlight/Boltz swap endpoints, Blockstream Asset Registry, update checks, and Qt WebEngine / QML web views (`QtWebEngine`).
5. **Crashpad / IPC (`src/`, `tools/patches/`)**:
   - Watchdog and UI process IPC, local single-instance socket (`KDSingleApplication`), and minidump sanitization.

## Components that matter most / least

- **Matter most**: `src/` (controllers, handlers, resolvers, wallet/tx logic, `src/jade/`, `src/ledger/`, `src/glsdk/`, `src/lightning/`), `qml/` security-critical confirmation/signing flows, `tools/patches/`.
- **Matter least**: `i18n/`, `assets/`, `doc/`, `installer.iss.in`, visual styling/theming in `qml/`.

## How to exercise it

- Build: `cmake --build /src/build -j"$(nproc)"`
- Run unit tests offscreen: `QT_QPA_PLATFORM=offscreen ctest --test-dir /src/build --output-on-failure`
- List tests: `./tools/test.sh list`

## How we rate severity

- **Critical**: Theft of funds or private keys/mnemonics; remote code execution (e.g., via Qt WebEngine, URL handling, QR/PSBT parsing, or local IPC); silent modification of signed transaction outputs/amounts/assets; crash-dump leakage of live keys/mnemonics.
- **High**: Hardware wallet confirmation/address-verification bypass; memory corruption (UAF, buffer overflow) reachable from network, QR, PSBT, or USB/BLE input; local privilege/authentication bypass around wallet lock.
- **Medium**: Remote crash/DoS on malformed server, QR, URI, or device data; unintended network leaks of addresses/xpubs.
- **Low**: UI glitches or issues requiring an attacker who already has full local user code execution.

## Anything to leave alone

- Attacks assuming an attacker already controls the local user OS account or physical unlocked desktop session.
- Pure visual/layout/translation defects in `qml/` or `i18n/`.
