# BlueWallet threat model

BlueWallet is a self-custodial Bitcoin and Lightning wallet for iOS and Android, written in TypeScript on React Native. Private keys are generated and stored on the device, transactions are built and signed on the device, and the app talks to remote servers for chain data, Lightning and prices. It supports HD wallets (BIP44/49/84/86, Electrum seeds, aezeed, SLIP-39, BIP38), watch-only wallets used with hardware signers through PSBTs, multisig vaults, BIP47 payment codes, Silent Payments sending, Payjoin (BIP78), custodial Lightning through LNDHub, and Ark/Lightning through Arkade.

## Assets

- Seeds, mnemonics, passphrases and private keys (including multisig cosigner keys and Lightning/Ark secrets such as LNDHub credentials).
- Funds: the wallet must sign only what the user was shown and approved: the same destinations, amounts and fee.
- Extended public keys, descriptors, addresses and transaction history (privacy).
- Encrypted storage: with "encrypt storage" on, wallet data is AES-encrypted with the user's password (`blue_modules/encryption.ts`, `class/blue-app.ts`). Plausible deniability keeps a second storage bucket opened by a different password; the presence of the real bucket must not be revealed by the fake one.

## Where untrusted input enters

Treat all of these as attacker-controlled:

- **Electrum server responses** (`blue_modules/BlueElectrum.ts`): history, balances, raw transactions, fee estimates, headers. The server may be malicious or impersonated. BlueWallet does not do SPV proofs, so a server can lie about balance or history; that alone is a known limitation. It is in scope when server data makes the wallet sign something the user did not approve: an inflated fee, a wrong change amount, or a wrong input set, for example through RBF bump or cancel and CPFP (`class/hd-segwit-bech32-transaction.ts`, `screen/transactions/`). Raw transactions from the server must be checked against their txid before they are used.
- **Lightning and Ark backends**: LNDHub servers (`class/wallets/lightning-custodian-wallet.ts`), Arkade/Ark servers and Boltz swaps (`class/wallets/lightning-ark-wallet.ts`, `blue_modules/arkade-*`), LNURL pay/withdraw/auth endpoints (`class/lnurl.ts`, `screen/lnd/`), and BOLT11 invoices.
- **Payment requests**: QR codes (including animated BC-UR and BBQr, `blue_modules/ur`, `blue_modules/bc-ur`, `blue_modules/bbqr`), BIP21 `bitcoin:` URIs with `amount`, `label`, `lightning=` and Payjoin `pj=` parameters, Payjoin receiver responses (`blue_modules/payjoin-client`, `class/payjoin-transaction.ts`), Azteco vouchers (`class/azteco.ts`), BIP47 notification transactions and payment codes.
- **PSBTs and coordination files**: PSBTs from hardware wallets or cosigners (`screen/send/psbtWithHardwareWallet.tsx`, `screen/send/psbtMultisig.tsx`, `util/combinePSBTs.ts`), `.psbt` files, multisig setup and `.bwcosigner` files (`class/multisig-cosigner.ts`, `class/wallets/multisig-hd-wallet.ts`).
- **Imported material** (`class/wallet-import.ts`, `class/wallet-descriptor.ts`): mnemonics, WIF and BIP38 keys, xpubs and other SLIP-132 keys, output descriptors, JSON exports from other wallets, `lndhub://` and `arkade://` strings.
- **Deep links and shared files** (`class/deeplink-schema-match.ts`): `bitcoin:`, `lightning:`, `bluewallet:` (including `setelectrumserver` and `setlndhuburl`), `lapp:` and widget links. A link may prefill a screen but must not move funds or change a server without the user confirming.
- **Clipboard** (`blue_modules/clipboard.ts`, `blue_modules/clipboardPayment.ts`, `screen/ClipboardDetected.tsx`).
- **Third-party HTTP APIs**: fiat exchange rates (`models/fiatUnit.ts`, `blue_modules/currency.ts`), mempool fee estimates, the push notification server (`blue_modules/notifications.ts`). A wrong fiat value is expected to be possible; it should not change the BTC amount signed.

## Components that matter most

- `class/wallets/`: key derivation, address generation, coin selection, transaction building and signing, message signing.
- `class/hd-segwit-bech32-transaction.ts`: RBF and CPFP, built from server-supplied transactions.
- `blue_modules/BlueElectrum.ts`: parsing and caching of server data.
- `class/blue-app.ts`, `blue_modules/encryption.ts`, `blue_modules/start-and-decrypt.ts`: storage, encryption and plausible deniability.
- `class/wallet-import.ts`, `class/deeplink-schema-match.ts`, `class/lnurl.ts`, `blue_modules/payjoin-client/`, `util/combinePSBTs.ts`: parsers of untrusted input.
- `screen/send/` and `screen/transactions/`: what the user is shown before signing, which must match what is signed.

Less important: pure UI components (`components/`), localization (`loc/`), theming, widgets.

## Out of scope

- The third-party servers themselves (Electrum servers, LNDHub, Arkade, Boltz, rate APIs, block explorers, the push server). Report how BlueWallet handles their responses, not bugs in them.
- Attacks needing a rooted or jailbroken device, malware on the device, or physical access to an unlocked device.
- Native build tooling and project files under `android/` and `ios/`, `fastlane/`, `reproducible-builds/`, CI, and `tests/`.
- CVEs in dependencies with no reachable path from BlueWallet code.
- A malicious server reporting a wrong balance or history with no effect beyond display, and privacy leaks inherent in talking to an Electrum server the user chose (it learns the user's addresses).

## How we rate severity

- **Critical**: remote loss of funds, remote extraction of a seed or private key, or the wallet signing an attacker-chosen transaction without user consent.
- **High**: misleading the user into approving a wrong amount, destination or fee (the confirm screen differs from what is signed); leaking xpubs, seeds or seed-derived data to a third party; bypassing storage encryption or revealing the real bucket under plausible deniability.
- **Medium**: denial of service of the wallet (crash loop, wallet that cannot be opened, inability to spend); cache poisoning with no impact on funds.
- **Low**: hardening and defense in depth.

Give a severity and the reason; do not inflate it. Do not send non-security bugs.

## How to exercise it

The image has `/src` with `node_modules` installed and TypeScript checked (`npx tsc`). Run the unit tests offline with `bluewallet-oss-test` (that is `npx jest tests/unit/`), or one file with `npx jest tests/unit/<file>`. Some unit tests are skipped without the mnemonics CI passes in environment variables. `tests/integration/` needs live Electrum and HTTP servers and does not work offline; mock the server instead (see how `tests/unit/` stubs `BlueElectrum`).

## Reports

Please include a reproducer as a jest unit test under `tests/unit/` wherever possible, that fails before your patch and passes after, plus a minimal patch. Name the file and function, the attacker's position (malicious Electrum server, crafted QR, crafted PSBT, and so on), and what the user has to do.
