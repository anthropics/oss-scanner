# Bitcoin Safe — threat model for Anthropic OSS Scanner

## Project, security goals, and impact

Bitcoin Safe is a cross-platform, open-source desktop application for managing
Bitcoin cold-storage wallets, including multisignature wallets. It is a wallet
*coordinator*: on mainnet it is designed to use external hardware signers for
seed/key custody and signing, not to store users' seed phrases on the desktop.
It creates, imports, reviews, and broadcasts transactions and partially signed
Bitcoin transactions (PSBTs), handles wallet descriptors and extended public
keys, syncs chain state using compact block filters or optional remote backends,
and supports QR/USB/file-based signer integration and optional plugins.

The key assets are **correct transaction details (recipients, amounts, fee,
change, and signers)**, correct multisig policy and address derivation, wallet
state/integrity, private wallet metadata (xpubs, addresses, balances, labels,
transaction history), and the integrity of downloaded/imported software and
plugins. The scanner should prioritize vulnerabilities that can cause loss of
funds, malicious transaction signing, irreversible wallet backup/recovery errors,
installation of untrusted code, or disclosure of sensitive wallet metadata.

Hardware-signer confirmation is an important *independent* boundary. Do not
assume the application possesses mainnet signing seeds, nor assume hardware
signers can be compromised just because malicious inputs reach the coordinator.
Still investigate deception of the user, misrepresentation of transaction
outputs, derivation/policy substitution, and failures to verify signatures.

## Threat actors, entry points, and trust boundaries

Treat all data obtained from outside Bitcoin Safe as potentially malicious,
including payloads from a trusted-looking but compromised counterparty/device:

- **Signer and transaction inputs:** PSBTs from files, drag-and-drop, QR/BBQr/UR,
  camera and SD card, USB/HWI signer responses, public keys and derivation paths,
  signer fingerprints, signatures, transaction blobs, and QR payload sequences.
- **Wallet/backup/import data:** descriptors, xpubs, multisig configuration,
  watch-only wallet metadata, restore/backup files, labels/BIP329, CSV imports,
  local saved wallet/state files, QR-encoded wallet setup data, and user-controlled
  filenames/paths. Do not rely on file extensions for trust.
- **Network data:** Bitcoin P2P and compact-block-filter peers, Electrum/Esplora
  and custom RPC server responses, transactions, blocks, fee estimates, update
  metadata, and URLs/responses encountered by the application.
- **Collaboration and plugins:** Nostr relays and sync/chat messages; shared
  labels, PSBTs and backups; external plugin manifests, update/index metadata,
  signatures and downloaded source/artifacts, and plugin configuration.
- **Desktop integration:** clipboard, links/URLs, filesystem paths, subprocess
  invocation, web links and external tool output. Hardware access and plugin
  installation are elevated trust transitions.

Threat actors include malicious peers/servers/relays, malicious senders of PSBTs,
QR codes and documents, compromised collaboration devices, and anyone able to
alter lower-trust local files. Differentiate attacks requiring local write access,
physical hardware access, or explicit user installation/approval from remote
or ordinary import attacks. Do not classify intentionally installed arbitrary
third-party plugin code as a vulnerability *by itself*; do test verification,
source integrity, permission boundaries and unsafe automatic execution paths.

## High-priority in-scope code

Audit all first-party source in `bitcoin_safe/`, focusing especially on:

1. **Transaction/PSBT and signing correctness:** `bitcoin_safe/psbt_util.py`,
   `bitcoin_safe/tx.py`, `bitcoin_safe/wallet.py`,
   `bitcoin_safe/wallet_util.py`, `bitcoin_safe/cpfp_tools.py`,
   `bitcoin_safe/signature_manager.py`,
   `bitcoin_safe/input_signature_verifier.py`,
   `bitcoin_safe/input_signer_attribution.py`, `bitcoin_safe/signer.py`,
   `bitcoin_safe/hardware_signers.py`, and signing / send GUI paths.
2. **Multisig, descriptors and persistence:** `bitcoin_safe/descriptors.py`,
   `bitcoin_safe/keystore.py`, `bitcoin_safe/persister/`,
   `bitcoin_safe/config.py`, `bitcoin_safe/labels.py`, import/export,
   recovery/backup and wallet-encryption code.
3. **Untrusted chain/network parsing and synchronization:**
   `bitcoin_safe/cbf/`, `bitcoin_safe/p2p/`, `bitcoin_safe/client.py`,
   `bitcoin_safe/rpc.py`, `bitcoin_safe/network_utils.py`,
   `bitcoin_safe/mempool_manager.py` and backend selection.
4. **Software update and extensibility boundaries:**
   `bitcoin_safe/update_applier.py`, `bitcoin_safe/signature_manager.py`,
   and `bitcoin_safe/plugin_framework/` (especially external plugin catalog,
   source/signature verification, loading and update flows).
5. **GUI, imports and exchange of wallet data:** `bitcoin_safe/gui/`,
   transaction/signer dialogs, wallet setup flows, BIP329/CSV/QR paths,
   and relevant supporting code in `bitcoin_safe/`.

The repository includes tests under `tests/`, especially `tests/non_gui/`.
Analyze first-party misuse/integration of third-party dependencies, but do not
report issues *solely* in independently maintained third-party libraries, bundled
binary artifacts, or external Bitcoin nodes/signers without a first-party defect.

## Security invariants to test

- An imported descriptor or multisig policy cannot silently alter which keys,
  threshold, network, derivation path, or wallet identity the user relies on.
- Displayed recipient/amount/change/fee/inputs match the exact PSBT or raw
  transaction that is actually exported, signed or broadcast; no attacker data
  can substitute a different transaction after confirmation.
- Confirmation and validation of signature inputs cannot be bypassed by
  malformed/wrong-network data, partial or unexpected signatures, or incorrect
  signer attribution; intended key ownership and signing threshold are preserved.
- Untrusted network messages cannot corrupt wallet state, forge payment
  confirmation, disable validation, or trigger unsafe command execution.
- Wallet files and backups cannot be replaced/rewritten by path traversal or
  unchecked input; encrypted data, metadata and secrets are not leaked in logs
  or network requests without an intentional, documented user action.
- Plugins and updates are not fetched/executed across a lower-trust boundary
  without intended authorization and integrity/authenticity checks.
- Malformed imports, QR streams, PSBTs and remote responses fail safely with
  bounded resource usage and an actionable error, not persistent wallet damage.

## Severity guidance

- **Critical:** A realistic exploit enabling immediate theft/misdirection of
  significant funds or remote arbitrary code execution in common use, with a
  clear attacker-controlled path and no independently required hardware/user
  approval step that would ordinarily block it.
- **High:** A practical attack that can cause unauthorized transaction changes,
  false trust in signer/policy/recipient data, reliable integrity compromise of
  wallet backups, bypass of update/plugin authenticity, or major loss of private
  wallet information; privilege or UI confirmation constraints must be stated.
- **Medium:** Exploitable metadata leak, persistent crash/DoS, significant
  import-driven corruption with available recovery, or a security-control
  bypass needing unusual local permissions or explicit user interaction.
- **Low:** Minor information exposure, limited input-handling weaknesses, or a
  defense-in-depth improvement with a credible security consequence.

Rate based on demonstrable *Bitcoin Safe* impact, not simply a dependency CVE
or generic potentially exploitable code pattern. Explain any relevant hardware
confirmation, manual import, plugin opt-in, network or local-access prerequisites.
Avoid inflation of severity for normal public Bitcoin network data, publicly
visible Bitcoin addresses, or valid watch-only wallet operation.

## Public mnemonic fixture for demonstrations

For **any** test, example or proof of concept requiring a 24-word BIP39
recovery phrase, use **exactly `bacon` repeated 24 times**:

```text
bacon bacon bacon bacon bacon bacon bacon bacon bacon bacon bacon bacon bacon bacon bacon bacon bacon bacon bacon bacon bacon bacon bacon bacon
```

This is a checksum-valid BIP39 English mnemonic, but **deliberately public,
trivial to guess, and never suitable for holding real money**. Use only
synthetic/regtest wallets derived from it. Do not substitute personal seeds,
real private keys, randomly created production credentials, or actual user
wallet data. For test cases that need several distinct identities, prefer
public synthetic descriptors/fixtures or explicitly documented regtest-only
derivations; never present this fixture as a secure choice. This fixture is
an example only and does not imply Bitcoin Safe normally stores signing seeds.

## Reproduction and safety constraints

- Prefer deterministic, small, minimal test cases based on `tests/non_gui/`,
  using synthetic keys, xpubs, descriptors, signed fixtures and **regtest** data.
- Keep scanning and PoCs **fully offline**, consistent with the scanner
  environment: no internet, external relays, exchange accounts, actual coins,
  genuine seed material, live services, or physical signers are needed.
- The scanner image pre-installs **Bitcoin Core 29.2** in
  `tests/bitcoin_core/` for the existing `tests/setup_bitcoin_core.py` fixture;
  that fixture can start a local regtest node offline. The `--cbf` pytest
  backend is preferred; no Fulcrum/Electrum backend is provided.
- Begin with `pytest --cbf -q -m 'not integration' --maxfail=1
  tests/non_gui/test_cbf_sync.py tests/setup_bitcoin_core.py` (from `/src`).
  For GUI tests requiring an X display, run with
  `QT_QPA_PLATFORM=xcb xvfb-run -a -s '-screen 0 1920x1200x24' pytest --cbf ...`.
  A missing hardware device, external service or public-network connection is
  not a vulnerability; use offline stubs or the local regtest where appropriate.
- Do not attempt to access real Bitcoin mainnet peers during scan reproduction,
  even when a test fixture can select a mainnet network configuration.
- Respect the distinction between vulnerabilities in this repository and bugs
  only in git/PyPI dependencies (notably `bitcoin-safe-lib`, `bitcoin-usb`,
  `bitcoin-qr-tools`, `bitcoin-nostr-chat`, and `btcpay-tools`). If the flaw is
  in the integration here, identify the first-party call site and show impact.
- Do not use genuine user wallets, publish detailed exploit instructions,
  submit transactions, or initiate network calls from a reproducer.
- Group findings by root cause; distinct call sites of the same underlying
  defect should usually form a single report.

See `report_guidelines.md` and `patch_guidelines.md` beside this file
for expected report and fix formats.
