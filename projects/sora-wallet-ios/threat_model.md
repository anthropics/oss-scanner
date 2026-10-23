# SORA Wallet iOS security context

## Project and audit revision

This repository is the public SORA network and Polkaswap iOS wallet. Enroll the
`modernize` branch used by the application workspace, initially validated at
`84980a95f4e7e48c1f436c67545149c33eea73f3`. The complete repository and Git
history are retained in `/src`; the small Linux harness is not a replacement
for reviewing the complete app.

The wallet manages account creation/import/recovery, local signing, token
balances and transaction activity, SORA2/Polkaswap interactions, and SORA Nexus
network selection. Its current Taira path builds Norito transactions locally,
authenticates fee quotes and signs exact payload bytes with scoped local key
access. Current source treats Taira as a testnet and leaves Nexus production
sending unavailable. Follow those source policies rather than inferring new
production guarantees from a passing test or a hostname.

## Assets, entry points and trust boundaries

Protect mnemonics, private signing keys, PIN/biometric authorization, encrypted
backups, account identity and network selection. An action's displayed sender,
recipient, amount, asset and fee ceiling must match its signed bytes. Do not
cross wallet identities or promote pending/ambiguous transactions to completed
without the required reconciliation.

Treat QR codes, deep links/imported keystores, remote RPC/MCP/explorer responses,
chain/asset metadata, fee quotes, faucet prepare/status responses and persisted
recovery data as potentially malformed. Include oversized inputs, duplicate or
unexpected fields, integer/decimal overflow, network/asset/address substitution,
replay, expiry, cancellation and account switches in reproducers.

Important source paths:

- `SoraPassport/Common/Model/NexusWalletService.swift`: strict JSON admission,
  exact amounts, account/network policy, balances, activity and submission state.
- `SoraPassport/Common/Model/TairaTransactionSigning.swift`: draft/quote binding,
  signer identity, local transaction encoding and HTTPS confirmation policy.
- `SoraPassport/Common/Model/TairaFaucetService.swift`: account binding, bounded
  proof-of-work integration and durable pending-claim recovery.
- `VendorPackages/NexusTransferCodec`: Norito frames, asset checksums, quantities,
  signing preimages/envelopes, fee authorization, challenge binding, faucet wire
  validation and prepare/submit/reconcile state machine.
- `SoraPassport/Common/Crypto`, `Common/URLHandling`, `Common/DeepLink`,
  `Common/WalletQRCaptureService`, and the account/backup/send screens under
  `ModulesRedesign`: key custody and user-input/authorization boundaries.

The Taira confirmation reader explicitly trusts the canonical HTTPS node. Its
challenge, genesis and applied-height checks are not independent consensus-proof
verification. Distinguish an intended trusted-server policy from a demonstrated
violation of its binding checks. Do not run live transfers, real faucet claims
or tests against another person's account; use local fixtures and injected
transports with synthetic keys.

## Build and offline reproduction

The scanner image compiles all six sources and all three original XCTest files
from `VendorPackages/NexusTransferCodec` in `/opt/scanner`. It fetches Apple's
Swift Crypto 3.9.1 at image-build time and retains the compiler, dependencies,
fixtures and test binary. Stable links select Swift's original versioned Clang
so the scanner's additional Ubuntu tooling cannot replace the C compiler used
for offline rebuilds. Run `scanner-core-test` without network, or rebuild
with `scanner-core-build` after editing `/src`.

The harness changes only copies: CryptoKit imports become Apple's Linux Crypto
module; files using URLRequest import FoundationNetworking, and the strict
NSNumber parser imports CoreFoundation explicitly. The two Apple-only
`URLSession.bytes(for:)` implementations remain present behind a platform branch;
Linux's default transport throws instead of sending requests. The original
transport sources in `/src` are untouched, and the original tests exercise fee,
faucet and reconciliation logic through their existing injected transports.
No test cases or assertions are removed.

UIKit, Security/Keychain, biometric gates, camera/QR extraction, Apple streaming
transport, native scrypt integration, device lifecycle, app persistence and
complete Xcode app suites are source-review surfaces in this Linux image.
The faucet tests inject proof-of-work output; they do not qualify native scrypt
or physical-device protections. Report platform prerequisites with reproducers;
do not describe this harness as a full IPA/device build.

## Severity and reports

Unauthorized key disclosure, signing outside the selected account/network,
recipient/amount/fee substitution, transaction replay or a practical path to
fund theft can be critical/high, depending on prerequisites and impact. A
crafted remote response that bypasses a signing/confirmation boundary is more
serious than a cosmetic metadata error. A reproducible parser/state-machine
crash or sustained resource exhaustion is generally medium unless it exposes
keys, causes signing or blocks recovery of funds. Root/jailbreak or a fully
compromised device alone does not demonstrate an app authorization bypass.

Include exact source revision, attacker-controlled input, necessary trust and
user-interaction assumptions, expected versus observed behavior, and a minimal
offline regression. Never include real seed phrases, signing keys, backup
passwords, customer data or confidential scanner reports in public issues.
Retain the repository's BSD-4-Clause license and all vendored component licenses;
this enrollment does not relicense application code or third-party binaries.

This product includes software developed by Polka Biome Ltd., SORA, and Polkaswap.
