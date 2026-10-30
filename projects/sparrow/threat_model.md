# Sparrow Wallet threat model

Sparrow is a desktop Bitcoin wallet focused on security and privacy. The application (`src/main/java/com/sparrowwallet/sparrow`) is JavaFX, with a
Lanterna terminal UI (`terminal/`) over the same model. Two submodules are built with it and ship in the same release:

- **drongo** (`drongo/src/main/java/com/sparrowwallet/drongo`): the Bitcoin library. Keys and BIP32 derivation, mnemonics (BIP39, SLIP39, codex32,
  Electrum), transactions and scripts, sighash computation and signing (libsecp256k1 over JNI), PSBT (BIP174/370), output descriptors, addresses,
  silent payments (BIP352/374/375), BIP47, BIP322, BIP353 DNSSEC resolution, BIP21 URIs, header and merkle verification, coin selection, and the
  `Wallet` model.
- **lark** (`lark/src/main/java/com/sparrowwallet/lark`): USB hardware wallet communication (Trezor, KeepKey, Ledger, BitBox02, Coldcard, Jade).

Sparrow holds private keys for software wallets, stores them encrypted at rest, coordinates hardware and airgapped signers, and talks to an Electrum
server or the user's Bitcoin Core node. Most users connect to a public Electrum server or their own private one. `SECURITY.md` in the repository
root is the published policy; this file narrows it for automated review.

## Security goals, in priority order

1. **Key material never leaks.** Seeds, mnemonics, BIP39 passphrases, xprvs, WIF keys, the wallet password and the keys derived from it must not
   reach a server, a log at the default level, an export or QR a user would read as public, or an unencrypted file when the wallet is encrypted.
2. **Sparrow signs only what the user was shown.** The signed transaction must pay the outputs, amounts and fee shown in the transaction tab and
   diagram (`transaction/HeadersController`, `control/TransactionDiagram`). In scope: output or change substitution, change misidentified as the
   user's own, fee inflation through misstated input amounts, sighash types that leave outputs uncommitted, signing with a key or derivation path
   outside the wallet, and a hardware device being sent something other than what was reviewed.
3. **Addresses and descriptors are correct.** Receive and change addresses, descriptors, multisig quorums and silent payment outputs must match
   the wallet's keys and policy and what the other cosigners derive. A wrong address is a fund loss even if nothing is "attacked".
4. **Wallet confidentiality at rest.** An encrypted wallet file must not be readable or downgradable to plaintext without the password.
5. **Network privacy as configured.** When a proxy or Tor is configured, Sparrow must not connect around it, resolve names locally for proxied
   destinations, or send addresses, xpubs or transactions to a party the configuration did not choose.
6. **State integrity from the server.** A server must not be able to fabricate a confirmed balance or confirmation depth, or make the wallet build
   a transaction from data it invented (fee, amounts, input set).

## Scope and priorities

Everything shipped in the release binaries is in scope. Highest priority, roughly in order:

- **Signing and sighash**: drongo `crypto/ECKey`, `crypto/SchnorrSignature`, `protocol/Transaction` (`hashForLegacySignature`, `hashForWitnessSignature`,
  `hashForTaprootSignature`), `protocol/TransactionSignature`, `psbt/PSBTInput.sign`, `wallet/Wallet.sign`, `Wallet.getSigningNodes`, `Wallet.finalise`.
- **PSBT handling**: drongo `psbt/PSBT`, `PSBTInput`, `PSBTOutput`, and their checks: `PSBTInput.verifyUtxo`, `verifySigHash`, `verifySignatures`,
  `PSBT.verifyCombinedSignatures` (and `verifyCombinedOutputScripts`/`InputScripts`/`Utxos`/`SigHashes`), `verifyFinalizedSignatures`,
  `validateSilentPayments`. In Sparrow, `AppController.addTransactionTab` / `handleTransactionMerge` and the combine path in `HeadersController`
  where device and cosigner signatures are adopted. Signatures are verified centrally at combine time, not per device.
- **Key derivation and secrets**: drongo `crypto/HDKeyDerivation`, `DeterministicKey`, `ExtendedKey`, `wallet/Bip39MnemonicCode`, `wallet/slip39/*`,
  `wallet/bip93/Codex32`, `crypto/BIP38`, `crypto/DumpedPrivateKey`, `wallet/Keystore`, `wallet/DeterministicSeed`, `wallet/MasterPrivateExtendedKey`.
- **Address and descriptor generation**: drongo `OutputDescriptor`, `address/*`, `protocol/ScriptType`, `protocol/Script`, `protocol/Bech32`,
  `protocol/Base58`, `silentpayments/*`, `bip47/*`, `wallet/Wallet.checkWallet`, `Wallet.getFreshNode`.
- **Transaction construction, fees, change and coin selection**: `Wallet.createWalletTransaction`, `TransactionParameters`, `WalletTransaction`, the
  `*UtxoSelector` classes and `*TxoFilter`s; in Sparrow `wallet/SendController`, `wallet/PaymentController`, `control/CoinTextFormatter` (amount entry).
- **Wallet storage and encryption**: Sparrow `io/Storage`, `io/db/DbPersistence` (H2 with pre-open `validateStore` and `validateSchema`),
  `io/JsonPersistence`, `io/ECIESInputStream`/`ECIESOutputStream`; drongo `crypto/Argon2KeyDeriver`, `ECIESKeyCrypter`, `AESKeyCrypter`, `EncryptedData`.
- **Server data integrity**: `net/ElectrumServer` (merkle verification `verifyConfirmedReferences`/`verifyMerkleProofs`, tip validation
  `getAnnouncedTipValidationError`, unsigned-spend detection `getUnsignedTransactions`, fee derivation in `getTransactions`), `net/SubscriptionService`,
  `net/HeaderStore`, drongo `protocol/HeaderChainState`, `HeaderCheckpoints`, `MerkleBranch`, `BlockHeader`.
- **Payjoin and other protocol clients**: `payjoin/Payjoin` (BIP78 proposal checks), `net/Auth47`, `net/LnurlAuth`, `paynym/PayNymService`,
  drongo `dns/*` (BIP353) and `uri/BitcoinURI`.
- **Imports and QR decoding** (see the trust table: these matter for integrity, not availability).
- **lark**: response parsing in each device stack and the data returned to Sparrow (xpubs, signatures, registrations).

Lower priority: UI presentation that does not change what is signed or stored, the terminal UI where it mirrors a desktop path already covered,
exchange rate display.

Out of scope: `buildSrc/`, `build.gradle` and packaging (`src/main/deploy/`, jpackage, WiX, udev rules), `.github/`, `docs/`, `repackage.sh`, test
code and fixtures under `src/test`, `drongo/src/test` and `lark/src/test`. Third-party dependencies (Jetty via tern, dnsjava, H2, Flyway,
BouncyCastle, hummingbird, zbar, Tor) count only where Sparrow reaches the affected code with attacker input; name the dependency and the path.

## Attackers and trust boundaries

Ask who the adversary is and what else that position already gives them before reasoning from the code. A finding whose adversary already holds a
strictly better channel than the one described (the screen, the camera, the local account, the user's own node) is not a finding.

- **Public Electrum servers** (Untrusted). `net/ElectrumServer`, `net/TcpTransport` and the TLS/proxy/Tor transports, `SimpleElectrumServerRpc`,
  `BatchedElectrumServerRpc`, `SubscriptionService` notifications (headers, script hash status, silent payments). The hardcoded list is `net/PublicElectrumServer`. On mainnet,
  with verification on (the default), it is mandatory (`isVerificationMandatory`): a server that cannot prove inclusion is rejected.
- **The user's private Electrum server (`ELECTRUM_SERVER`)** (Untrusted for funds and confirmation state; trusted not to withhold service). Same paths. Often reached
  remotely or over Tor. Merkle proofs are verified; a server that does not implement them downgrades verification for the session by design.
- **A network attacker between Sparrow and a server** (Untrusted). TLS in `TcpOverTlsTransport`: trust-on-first-use with leaf pinning in `<home>/certs/`, CA validation
  where a `.cacert` is saved. A changed certificate prompts the user. Plain TCP is the user's explicit choice.
- **The user's configured Bitcoin Core node (`BITCOIN_CORE`, via `net/cormorant` or `net/Bwt`)** (Trusted). `net/cormorant/bitcoind/BitcoindTransport`, `BitcoindClient`.
  Merkle and signature verification are deliberately off for this server type. A finding whose attacker is the configured node is out of scope. **Exception:** the
  connection *test* flow (`ServerSettingsController`, terminal `ServerTestDialog`), where the user has not yet decided to trust the endpoint.
- **HTTP services: fee rates, exchange rates, broadcast relays, version check, PayNym** (Untrusted). `net/FeeRatesSource`, `ExchangeSource`, `BroadcastSource`,
  `VersionCheckService` (Bitcoin signed message against a pinned address), `paynym/PayNymService`, `control/PayNymAvatar`. All through tern's `HttpClientService` except
  the avatar.
- **Payjoin receivers** (Untrusted). `payjoin/Payjoin.requestPayjoinPSBT` and its proposal checks. The `pj=` URL must be https or http onion.
- **Auth47 and LNURL-auth services** (Untrusted). URIs via `AppServices.openAuth47Uri` / `openLnurlAuthUri`; `net/Auth47`, `net/LnurlAuth`. The user selects a wallet and
  confirms.
- **DNS (BIP353)** (Untrusted; DNSSEC is the boundary). drongo `dns/DnsPaymentResolver`, `AuthenticatingResolver`, `PersistingResolver`, `RecordUtils`; proof chains
  carried in PSBT outputs are verified offline.
- **PSBTs and transactions from any source** (Untrusted for funds safety). File, drag and drop, OS open-file events, command line, pasted text, QR
  (`AppController.openTransactionFile`/`FromText`/`FromQR`, `addTransactionTab`), cosigner and coordinator PSBTs, `MessageSignDialog` (BIP322 PSBTs). Sparrow must sign
  and display exactly what is there.
- **QR codes, including animated UR and BBQr** (Untrusted content; the camera is the channel). `control/QRScanDialog` (hummingbird `URDecoder`, `LegacyURDecoder`,
  `io/bbqr/BBQRDecoder`, `pNofM` parts, SeedQR, Base43), `control/WebcamService`, `io/ZBar`. Whoever controls what the camera sees can show any payload, so frame splicing
  is not a separate attack.
- **Wallet, keystore and label imports from other software** (Untrusted for integrity). The importers in `io/` (`ColdcardSinglesig`, `ColdcardMultisig` and its six
  subclasses, `Bip129`, `Electrum`, `SpecterDesktop`, `SpecterDIY`, `Descriptor` incl. `PdfUtils`, `CaravanMultisig`, `Samourai`, `Sparrow`, `KeystoneSinglesig`, `Jade`,
  `WalletLabels` (BIP329, can set `spendable`)), `AppController.attemptImportWallet` fallback, descriptor and xpub entry, `SendToManyDialog` CSV. An import must not
  silently produce a wallet different from the one the file describes (wrong quorum, wrong keys, anyone-can-spend).
- **Wallet files opened by the user** (Untrusted for code execution only). `io/db/DbPersistence` and `JsonPersistence`. A crafted `.mv.db` must not execute code or read
  and write files (H2 linked tables, triggers, aliases, generated columns, `FILE_READ`, etc.). A crafted file that merely fails to open is not a finding.
- **`bitcoin:`, `auth47:`, `lightning:` URIs** (Untrusted). OS handlers (`AppServices.addURIHandlers`, `openURI`), command-line arguments (`parseFileUriArguments`), the
  address field, QR. drongo `BitcoinURI` parses BIP21 including `pj`, `pjos` and the silent payment parameter.
- **Clipboard** (Untrusted content, entered by user action). Address, amount, descriptor, xpub, WIF and mnemonic fields; `SendToManyDialog` paste; `LabelCell`.
- **Hardware wallets (lark)** (Private keys trusted; responses untrusted for integrity). `io/Hwi` and `control/DevicePane`. Signatures, xpubs, fingerprints and
  registrations come back from the device. The device screen is the trust anchor for addresses and outputs; Sparrow does not compare a displayed address with its own. A
  malformed response that only stalls or aborts the device flow is robustness, not security. Jade supplies its own pin-server URLs (`JadeDevice` http_request), by design.
- **Smartcards (`io/ckcard`, `io/satochip`, `io/keycard`)** (As hardware wallets). Contributed by the device makers. Properties of a vendor's documented card protocol go
  to the vendor, not here.
- **Local user, OS, home directory, `config`, state directory, certificate and header caches, the single-instance socket (`instance/Instance`), the Cormorant loopback
  listener, JVM options and launch command** (Trusted). Anything that needs same-user file system access, control of the launch environment or system properties, or code
  running in the JVM is out of scope (symlinks on save, file modes inside the owner-only wallets directory, a hand-edited `config`, local processes talking to loopback
  listeners).
- **Someone watching the screen or holding the unlocked machine** (Out of scope).

## What counts

Report:

- Any path from untrusted input to key material disclosure, or to signing a transaction other than the one shown.
- A crafted PSBT, transaction, URI, QR payload, import or server response that changes outputs, amounts, fee, change detection, derivation, sighash or
  the input set without the UI showing it, or that gets a signature or finalized field adopted that was not verified against the open PSBT's own UTXOs.
- An address, descriptor or silent payment output computed wrongly from valid input (a mismatch with Bitcoin Core or the relevant BIP vectors).
- A server fabricating a confirmed transaction or confirmation depth that reaches the wallet or transaction tab despite merkle verification, or
  turning verification off on the mandatory tier, or disabling unsigned-spend detection.
- Code execution or file access from a wallet file, PSBT, import or server response.
- Encrypted wallet contents readable without the password, or a path that writes an encrypted wallet unencrypted.
- With a proxy or Tor configured: a connection that bypasses it, local DNS resolution of a proxied destination, or wallet data sent to an endpoint
  the configuration did not select.
- A remote party (a server, or an on-chain transaction anyone can send to the wallet) persistently preventing the wallet from opening or spending,
  e.g. one relay-standard output that breaks coin selection for every send.

Do not report (each has been assessed and dispositioned; reopen only with a new mechanism):

- Anything whose attacker is the configured Bitcoin Core node, except the connection test flow. Missing proof or signature checks for that server
  type are intended.
- Fabricated **unconfirmed** transactions or **omitted** history from an Electrum server. The protocol cannot close these. The private-server
  verification downgrade when proofs are unavailable is intended; the public tier fails closed.
- Fee estimates inflated by a server or HTTP source: the excess pays a miner, not the attacker, and high-fee warnings are server independent. CPFP
  prefill from a server-reported parent fee is accepted by decision (RBF derives the fee locally).
- Information that is inherent to the connection type chosen: an Electrum server learns the wallet's script hashes; for silent payments it receives
  the scan private key (BIP352 server-side scanning, disclosed in the UI). With no proxy configured, clearnet servers and HTTP services are contacted
  directly, as configured. Local network Electrum servers bypass the proxy by design. A clearnet Core RPC endpoint is never proxied, so credentials
  do not cross a Tor exit, and the UI warns when it is neither local nor onion.
- Unbounded reads, allocations or decompression from a file the user chose to open, or a crafted wallet file that fails to open. Missing socket
  deadlines and byte ceilings in the transport classes are one known piece of work, not individual findings.
- Logged secrets or script hashes at DEBUG or INFO. The root log level is `warn` and only a command-line flag lowers it.
- The BIP78 payjoin output substitution itself (spec mandated); redirect following on HTTP requests (a tern change); a payjoin receiver signing over
  a misdeclared amount (its transaction is invalid).
- Smartcard attestation not performed outside setup, BitBox02 attestation being advisory, and properties of the Coinkite card wire protocol.
- Jade's device-supplied pin-server URLs (a Blockstream design that must support loopback and onion deployments).
- Side channels in pure-Java ECDSA, BIP340 all-zero aux randomness (matches Bitcoin Core), and private keys or mnemonic Strings remaining on the
  heap (`clearPrivate` drops references; that is not a wipe and is not expected to be).
- Plain `multi()` imported as `sortedmulti()` (deliberate; a warning where a check fails because of it is the expected behaviour), and BIP370
  sequence zeroing in `PSBT.matches` / `getTransaction(true)`.
- Exponent notation accepted in Send to Many CSV but not in the amount field; grouping separators visibly canonicalised in the amount field.
- Hide Amounts not covering a control, CSV formula injection in exports, a PSBT filename or label shown as the recipient (the address is shown).
- The passphrase dialog's live master fingerprint, QR frame splicing, races on device events that need the user to start, cancel and restart an
  operation against a hostile device, and the on-device address display not being compared on the host.
- Public-server certificate pins that expire being re-learned (intended); the Tor binary version (blocked on the upstream packager).
- Code paths that only run outside the jpackage image: `NativeUtils` extraction to a temp directory and `applicationDefaultJvmArgs`. Native libraries
  load from `$java.home/lib` in a release build. `Argon2KeyDeriver` uses weak parameters only when `org.gradle.test.worker` is set.

Past fixes worth checking for siblings the fix did not reach: transaction bodies hashed against the requested txid (`VerboseTransaction`,
`ElectrumServer`); merkle and tip verification (announced tip below the last checkpoint, transaction tab confirmations, confirmation counts from an
unlinked tip); sighash and UTXO handling in PSBT signing; a finalized PSBT merged without signature checks; payjoin receiver UTXO amounts; multisig
import validation. This project's reviews have repeatedly found a fix applied at one site and missed at its twin (desktop vs terminal, constructor vs update
method, one importer vs another).

## Severity

These follow the four levels in `SECURITY.md`. The maintainers assign the final severity.

- **Critical**: loss or theft of funds, or disclosure of seeds, private keys or the wallet password, reachable from a remote or untrusted source
  with no unusual user action: a public Electrum server, a network attacker, a payjoin receiver, or any party able to send a transaction to the wallet.
  Code execution from a server response. Anything that affects users at scale in the default configuration.
- **High**: signing a misrepresented transaction from a crafted PSBT, URI, QR or import that the user opens in the normal course of a workflow
  (wrong outputs, change hijack, fee inflation, uncommitted outputs, wrong derivation); wrong addresses or descriptors from valid input; code
  execution or file access from a wallet file the user opens; encrypted wallet contents readable without the password; with Tor or a proxy
  configured, a connection or DNS lookup that bypasses it and ties wallet data to the user's IP address; a fabricated confirmed balance on the
  mandatory verification tier.
- **Medium**: denial of service a malicious server or a received transaction causes and that persists across reconnects or restarts (the wallet will
  not open, sync or spend); fabricated confirmation state on a private server or the transaction tab; integrity failures in imports that change the
  wallet but are shown before use (e.g. quorum or cosigner changes visible in Settings); privacy leaks to a configured party beyond what the
  connection type implies.
- **Low**: anything requiring an unlikely user action or non-default configuration, a crafted file whose only effect is a crash or failure to open
  that a restart clears, transient stalls of the connection service, minor information leaks.

Give a severity and the reason, naming what the attacker controls and what they gain. Do not inflate it. A finding that does not show what an
attacker gains and what access they need is a bug, not a vulnerability; do not send non-security bugs.

## Reports and reproducers

The scan runs offline with no display. Reproducers should be JUnit 5 tests with crafted inputs that run under `./gradlew`, not anything needing a
live network, a running GUI, a real hardware wallet or a real Electrum or Bitcoin Core server. Code reading alone is not enough; include a passing
control case.

- Run the suites with `./gradlew :drongo:test`, `./gradlew :lark:test` and `./gradlew test` (Sparrow), or a single class with
  `--tests <fully.qualified.Name>`. Java 25, Gradle 9 wrapper. Sparrow's `test` task excludes the `checkpoint` tag (it needs the network) and sets
  `sparrow.home=build/test-home`.
- Never start the JavaFX platform in a test (`Platform.startup`, `JFXPanel`); there is no display. Code that only runs on the FX thread should be
  reproduced at the model layer below it.
- Bound every blocking call (`assertTimeoutPreemptively`, as in `TcpTransportTimeoutTest`), so a hang reproducer cannot hang the build.
- Use test networks (`Network.set(Network.TESTNET)`, reset in `@AfterEach`) and plain BIP32 `tpub`/`xpub` encodings for test keys, not SLIP-132.
- Use throwaway keys only.

Good starting points:

- PSBT parsing, combining, finalizing and signing: drongo `psbt/PSBTTest` (includes the BIP174 invalid vectors).
- Transactions, sighash, fee derivation: drongo `protocol/TransactionTest`, `ScriptTest`; key and signing primitives: `crypto/ECKeyTest`,
  `HDKeyDerivationTest`, `Bip322Test`, `BIP38Test`, `DLEQProofTest`.
- Descriptors, addresses and wallets: drongo `OutputDescriptorTest`, `address/AddressTest`, `wallet/WalletTest`, `wallet/KeystoreTest`, `PolicyTest`,
  `silentpayments/SilentPaymentUtilsTest`, `bip47/PaymentCodeTest`, `uri/BitcoinUriTest`, `dns/DnsPaymentResolverTest` (offline proof chains).
- Headers and proofs: drongo `protocol/MerkleBranchTest`, `HeaderChainStateTest`, `HeaderCheckpointsTest`, `BlockHeaderTest`; Sparrow
  `net/HeaderStoreTest`, `HeaderSyncTest`, `TransactionProofTest`.
- Server responses without a server: Sparrow `net/ElectrumServerTest`, `ElectrumServerRpcTest`, `SubscriptionServiceTest`, `VerboseTransactionTest`,
  `TransactionFeeTest`, `UnconfirmedSpendTest`, `SilentPaymentsScanCacheTest`; Core-side `net/cormorant/bitcoind/*` and `electrum/RequestHandlerTest`.
- Payjoin: Sparrow `payjoin/PayjoinTest`, `PayjoinURITest`. Auth: `net/Auth47Test`, `LnurlAuthTest`.
- Imports and storage: Sparrow `io/IoTest` subclasses (`ColdcardMultisigTest`, `Bip129Test`, `CaravanMultisigTest`, `DescriptorTest`, `ElectrumTest`,
  `WalletLabelsTest`, ...) with fixtures in `src/test/resources/com/sparrowwallet/sparrow/io/`; `io/DbPersistenceTest` and `StorageTest` (`@TempDir`)
  for crafted wallet files; `io/bbqr/BBQRDecoderTest`; `io/keycard/TinyBERTLVTest`.
- Device responses: lark `trezor/thp/FakeTransport` with `ChannelTransportTest`, `trezor/V1ProtocolTest`, `BitBox02SignatureTest`,
  `ledger/command/GetMerkleLeafProofCommandTest`.

For each report give the revision, the source locations, the entry point and what the attacker controls, the configuration it needs (server type,
proxy, wallet type, device), the reproducer, expected and observed behaviour, and the concrete impact. One root cause per report: group sites that
share it. Check the history and tests first for a fix or a test asserting the behaviour as intended.

## Patches

Minimal, matching the surrounding style: four-space indents, `if(` and `for(` with no space before the parenthesis, lines up to 180 characters, no
wrapping before that. Put the fix where the logic lives:

- PSBT and signing checks belong in drongo as `verifyXxx()` methods throwing `PSBTSignatureException`, called by Sparrow, which shows the message.
  Reuse existing helpers in `PSBT`, `PSBTInput`, `SilentPaymentUtils` and `Utils` rather than adding new classes.
- Device-specific limitations belong in lark, not in drongo transaction construction.
- HTTP client behaviour belongs in tern, which is not in this tree; do not import Jetty into Sparrow.
- Prefer detecting, correcting and warning over gating normal behaviour when an attack is rare and detectable.
- Describe the fixed behaviour in commits, comments and tests, not the attack.

Include a regression test that fails before the patch and passes after, and a test of the normal path the patch must keep working.
