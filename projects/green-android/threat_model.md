# Blockstream App (Green Android) Threat Model

Blockstream App for Android (`Blockstream/green_android`) is a self-custodial Bitcoin, Liquid, and Lightning wallet built with Kotlin Multiplatform and Jetpack Compose. It integrates GDK (Green Development Kit), LWK (Liquid Wallet Kit), Greenlight/Breez Lightning SDKs, and hardware wallet support (Blockstream Jade, Ledger, Trezor) over BLE and USB.

## Assets

- **Wallet secrets**: mnemonics, BIP39 passphrases, PIN/biometric-protected Android Keystore keys, Lightning/Greenlight credentials, and watch-only/descriptor data (`data/`, `domain/`, `androidApp/`).
- **Transaction signing integrity**: the wallet must only sign what was shown to and confirmed by the user (destination addresses, amounts, Liquid asset IDs, fees, RBF/CPFP changes).
- **Privacy**: xpubs, addresses, balances, transaction history, and analytics/crash-reporting boundaries.

## Trust boundaries and where untrusted input enters

1. **Deep links, Android Intents, and App Links**:
   - `bitcoin:`, `liquidnetwork:`, `lightning:`, `lnurl:`, `green:`, and custom intents (`androidApp/`, `domain/`, `compose/`). Malicious links from browsers or other apps must not bypass confirmation screens, steal keys, or trigger unintended intents/WebViews.
2. **QR codes and imported payment/wallet payloads**:
   - BIP21 URIs, BOLT11/BOLT12 invoices & offers, LNURL-pay/withdraw/auth, PSBTs/PSETs, BC-UR animated QR codes, output descriptors, and swap/voucher payloads.
3. **Hardware wallet transports (`hardware/`, `jade/`)**:
   - BLE (`kable`), USB serial, and CBOR/APDU responses from a potentially compromised or malicious external device or MITM on BLE.
4. **Remote backends and third-party APIs (`network/`, `data/`, `gdk/`)**:
   - Electrum servers, Green backend, LWK/Boltz swap servers, Greenlight/Breez LSPs, Blockstream Asset Registry, exchange-rate feeds, and Firebase/Zendesk/WebView surfaces.
5. **Android IPC and storage boundaries (`androidApp/`)**:
   - Exported components (`AndroidManifest.xml`), `FileProvider` / shared files, backup/screenshot protections (`FLAG_SECURE`), Keystore/biometric authentication bypasses, and logging of secrets.

## Components that matter most / least

- **Matter most**: `androidApp/`, `domain/`, `data/`, `network/`, `gdk/`, `hardware/`, `jade/`, `compose/`, `utils/`.
- **Matter least**: `fastlane/`, `metadata/`, `docs/`, `iosApp/` wrappers, UI layout/theming/string translations.

## How to exercise it

- Run unit tests offline:
  `./gradlew --no-daemon --offline test -x :androidApp:testProductionGoogleDebugUnitTest`
- Run a single app test variant:
  `./gradlew --no-daemon --offline :androidApp:testDevelopmentDebugUnitTest`

## How we rate severity

- **Critical**: Theft of funds or private keys/mnemonics; silent signing of modified destinations, amounts, assets, or fees; biometric/PIN/Keystore lock bypass giving access to wallet secrets; arbitrary code execution or exported-component exploit leading to fund loss.
- **High**: Cross-app intent/deep-link spoofing bypassing user confirmation; swap/Lightning/PSBT validation flaws causing loss of funds; logging or leaking mnemonics, private keys, or PINs; TLS verification bypass on sensitive endpoints.
- **Medium**: App crash/DoS on malformed QR/URI/deep-link/server input; privacy leak of addresses/xpubs beyond intended backend connections.
- **Low**: Minor UI/UX issues or bugs requiring physical access to an already-unlocked device or root privileges.

## Anything to leave alone

- Attacks that require a rooted device, ADB access, or an attacker already holding the unlocked device and user PIN/biometric.
- `contrib/blockstream_keys.txt` placeholder/public app keys used in development builds.
