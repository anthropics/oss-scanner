# SORA Wallet Android security scope

SORA Wallet is a non-custodial wallet for SORA and Polkaswap. The enrolled
`modernize` branch also contains Iroha/Taira wallet and Iroha Connect integration;
the initial validated revision is `2e49467a9d582fcab2df184b311449281b2f3c7c`.
Protect mnemonic phrases, private keys, decrypted credentials, backup material,
and the integrity of transaction authorization. Public account addresses and
watch-only accounts must not become signing authority. User consent must bind the
account, network, recipient, asset, amount, fee, exact transaction/message bytes,
and requesting application.

Treat RPC/Torii/MCP and indexer responses, token metadata, remote configuration,
deep links, QR contents, dApp requests, imported wallet material, encrypted
backups, cloud responses, and corrupted local records as untrusted. Review the
transitions from parsed data to displayed confirmation, signing, durable pending
state, and reported finality. Cancellation, stale responses, crashes, and partial
writes must not authorize a different operation or silently replace keys.

## Source boundaries

- `app/src/main/AndroidManifest.xml` exposes launcher and Iroha Connect deep-link
  entry points. `app/src/main/java/jp/co/soramitsu/sora/irohaconnect/` handles
  `iroha://connect` and `irohaconnect://connect` requests and authentication/UI
  lifecycle transitions; protocol handling is under `common/.../irohaconnect/`.
- Credential import, derivation, and storage flows are under
  `feature_account_impl/src/main/java/jp/co/soramitsu/feature_account_impl/data/repository/`.
  `common/src/main/java/jp/co/soramitsu/common/data/EncryptedPreferences.kt` and
  `common/src/main/java/jp/co/soramitsu/common/util/EncryptionUtil.kt` cross the
  encrypted-storage/Android Keystore boundary. Review missing-key, authentication
  failure, legacy-record, and recovery behavior as well as successful reads.
- `common/src/main/java/jp/co/soramitsu/common/nexus/` contains account/address,
  quantity, transaction hash, signed transfer, authenticated request, and
  Torii/MCP parsing code. Network identity, genesis binding, exact payload bytes,
  canonical representations, proof/status admission, and replay handling matter.
  `common/src/main/java/jp/co/soramitsu/common/network/` bounds HTTP and JSON input.
- Transaction execution and pending/finality handling live under
  `feature_wallet_impl`; external explorer/history input enters through
  `feature_blockexplorer_api` and its implementations. Optional cloud backup
  integration is under `common/.../backup/`. Android Keystore, biometric prompts,
  Google services, native crypto dependencies, and remote chains are separate
  platform/service trust boundaries.

`TairaSigningClient` deliberately trusts the canonical HTTPS testnet node for
confirmation. Its fresh-challenge, network/genesis, height, and hash checks are
not independent consensus-proof verification. Review violations of the stated
binding policy without treating that trusted-server assumption as a hidden
production consensus guarantee.

Prioritize reachable unauthorized signing or secret disclosure, account/network
confusion, transaction substitution, false finality, replay, recovery data loss,
and authentication or encrypted-storage integrity bypasses. Parser denial of
service matters when bounded attacker input reaches the affected entry point.
Distinguish a reachable vulnerability from an unavailable external service or a
feature that has not completed platform/release qualification. A compromised
device OS and chain-consensus compromise are outside this model; malicious dApps,
RPC servers, import files, and malformed persisted data are in scope.

Use synthetic keys and the committed fixtures for reproducers. Do not contact
live signing services, submit transactions, access funded wallets, or use
production cloud accounts or release credentials. Reports should identify the
attacker-controlled input, precise authorization or secret-handling violation,
offline reproduction command, and a focused regression test without logging
secret material.

## Audit image

The full committed source checkout, including `.git`, is at `/src`. The image
installs JDK 21 and Kotlin 2.3.21 with its serialization compiler plugin. Pinned,
checksum-verified libraries match the selected code's repository versions:
kotlinx.serialization 1.9.0, coroutines 1.10.2, Gson 2.13.2, Bouncy Castle 1.78.1,
javax.inject 1, JUnit 4.13.2, and Hamcrest 1.3.

`scanner-core-build` compiles the unchanged portable Nexus/Taira codecs, clients,
and network input admission code directly from `/src`, together with 14 original
JUnit test classes. `scanner-core-test` runs those tests with committed resources
and their existing fake transports. The final Docker build step runs without
network access; both commands remain available for offline regression work.
No implementation stubs, rewritten application sources, or replacement tests
are used. Test names referring to live receipts use saved public fixtures.

This image does not build an APK or run the full Gradle suite. It excludes the
`IrohaKeyDerivation` code/test requiring the app's xcrypto/xsubstrate dependencies
and the explicitly live `NexusLiveTairaReadTest`. Android SDK/NDK, emulator/UI,
hardware Keystore, native bridge, optional cloud backup, and complete dependency
cache are not installed. Those paths remain available for source review, but
their execution requires separate platform setup. Passing the portable tests
does not establish full wallet, device, or release qualification.

The source keeps its BSD-4-Clause license and third-party notices. This product
includes software developed by Polka Biome Ltd., SORA, and Polkaswap.
