This threat model tells security reviewers which Salmon Wallet failures can put users, their credentials, or their transactions at risk.

# Threat model

## What this project does

Salmon Wallet is a self-custodial cryptocurrency wallet: users control the credentials that authorize transactions, and Salmon cannot recover or use those credentials for them. This repository contains the browser extension, the iOS and Android applications, and the packages shared by those applications.

The wallet creates or imports accounts, stores encrypted wallet credentials on the user's device, displays balances and transaction history, connects to decentralized applications, prepares transactions, presents them for user approval, signs approved transactions on the user's device, and broadcasts signed transactions directly to the relevant network.

## Security goals

- Wallet credentials, recovery phrases, private keys, passwords, and decrypted account data must remain confidential.
- A transaction must not be signed without a clear, current, and specific user approval.
- The transaction signed must match what the approval screen presented to the user.
- A website, decentralized application, remote service, deep link, QR code, imported file, or blockchain response must not gain wallet authority beyond what the user approved.
- Account origin, network, recipient, asset, amount, fees, and transaction instructions must not be silently substituted or confused.
- The browser extension must isolate trusted wallet screens and signing logic from websites and other extension contexts.
- Stored wallet data must resist tampering, rollback, cross-account confusion, and unauthorized disclosure.
- Security-sensitive behavior must be consistent across the browser extension and mobile applications.
- Optional analytics must not contain wallet credentials or silently become linked to a user's financial activity or identity.

## Security invariants to protect

These hold on `main` today. A change that breaks one is a finding even when no exploit is shown yet.

- The wallet re-checks every transaction Salmon's backend builds (NFT send and burn, lookup-table steps, swaps) against what the screen shows before it signs; the backend is not trusted (`packages/shared/src/core/verify`, `packages/shared/src/powerups/swap`).
- A swap is simulated before signing. It may move only the amounts shown, may pay rent only for token accounts it creates and leaves open for the owner it created them for, and may not hand anyone else the close authority of one of the wallet's token accounts.
- Production builds accept Solana RPC hosts only from the list compiled into the app; the backend's network catalogue cannot choose the node that answers the simulations that gate signing.
- A dApp transaction the preview cannot fully read, a preview that fails, and a durable-nonce transaction never get a one-tap approve: the screen says what it could not determine and requires hold to approve.
- A dApp signing request for an account other than the one the site was approved for is refused, and every signing screen names the signing account.
- On Android, every Mobile Wallet Adapter request from an app whose identity is not verified for that request reads as a claim ("Unverified app claiming to be …") and requires hold to approve; nothing can be approved while verification runs.
- Only an encrypted vault is opened. An unencrypted vault or a password-less legacy record goes to a protect screen that shows only addresses derived from its own seeds.
- Wallet writes from several extension windows are serialised and never write back a wallet another window removed.
- A send moves exactly the amount typed or shown: integer conversion from the typed text, and Token-2022 display multipliers (Scaled UI Amount, Interest Bearing) converted to raw units.
- Optional analytics events that follow an on-chain transaction carry only their UTC day.
- Extension releases are built only from commits on `main`'s first-parent history, and CI keeps no Playwright trace, screenshot or report.

## Untrusted input and trust boundaries

Treat all external data as untrusted, including:

- Requests, messages, origins, metadata, icons, and transaction payloads supplied by websites and decentralized applications.
- Solana and Bitcoin addresses, transaction instructions, serialized transactions, signatures, tokens, metadata, prices, balances, and network responses.
- Responses from Salmon's backend and third-party providers.
- Deep links, universal links, QR codes, clipboard content, imported wallet material, user-entered text, and files selected by a user.
- Browser-extension messages crossing between page scripts, content scripts, background workers, popups, side panels, and approval windows.
- Data read from local storage, secure device storage, caches, migrations, and backups.

The most important trust boundary is between untrusted websites or remote data and the code that displays an approval, accesses decrypted keys, or signs a transaction. A second critical boundary is between encrypted data at rest and decrypted credentials in memory.

## Components that matter most

Give the highest priority to:

- Credential generation, import, derivation, encryption, decryption, locking, unlocking, backup, migration, and deletion under `packages/shared/src/crypto` and `packages/shared/src/storage`.
- Transaction construction, simulation, review, signing, and broadcasting under `packages/shared/src/blockchain` and the corresponding application flows.
- Decentralized-application connection, permission, origin validation, session, and approval flows.
- Browser-extension message routing, externally reachable extension surfaces, content-script boundaries, manifest permissions, and approval-window lifecycle.
- Mobile deep-link handling, application links, clipboard and QR handling, device storage, biometric gates, and screen-capture or background-state exposure.
- Cross-account, cross-network, and cross-platform state handling where stale or confused state could authorize the wrong transaction.
- The device-side checks of backend-built transactions and swap simulations under `packages/shared/src/core/verify` and `packages/shared/src/powerups/swap`, and the RPC allowlist that decides which node answers them.
- Dependency or build behavior that can place malicious code in distributed wallet applications.

The browser extension (`apps/extension`), mobile application (`apps/mobile`), shared logic (`packages/shared`), and shared browser user interface (`packages/ui`) are in scope.

## Out of scope

- Vulnerabilities in Salmon's backend that cannot be triggered or meaningfully exploited through code in this repository.
- Vulnerabilities in third-party services themselves, unless this client handles their responses unsafely or grants them unintended authority.
- Social engineering that does not rely on a product vulnerability.
- Attacks that require a device already fully controlled by the attacker, unless the wallet unnecessarily exposes credentials or makes compromise materially worse.
- Findings based only on unsupported operating systems, modified application packages, or developer-only settings that cannot affect a distributed build.
- Missing rate limits, service availability, or resource exhaustion that can only affect third-party infrastructure and cannot threaten wallet confidentiality, integrity, or user authorization.

### Accepted limits

These are deliberate decisions with their reasons recorded by the team. Report one only with a path that breaks the reasoning, not the limit itself.

- Over-the-air JavaScript updates (Expo) are not code-signed yet; access to Salmon's Expo account is the control until signing ships in its own change.
- A copied recovery phrase or private key is cleared after 60 seconds only while the app or extension is open, or when the user returns to it; operating systems give the app no background timer.
- Android app-switcher protection (FLAG_SECURE) covers only the screens that show a secret, because applying it everywhere blocks every screenshot; the iOS blur covers the app's main window.
- A web dApp opened in a mobile browser can never be verified through Mobile Wallet Adapter; it is allowed with the unverified label and hold to approve.
- Stake accounts, compressed NFTs and Metaplex Core assets are not decoded yet; a transaction touching them gets the "could not determine" state and hold to approve by design.
- A swap's rent allowance can exceed an account's real rent by up to about 60,720 lamports per account.
- The Firefox build is not distributed; findings that exist only in Firefox-specific code are out of scope.
- Under iOS Switch Control and Voice Control, hold to approve is reached through the control's actions menu.

## How to exercise the project

Install dependencies and build the workspaces with:

```sh
pnpm install --frozen-lockfile
pnpm build
```

Useful checks and test entry points include:

```sh
pnpm typecheck
pnpm lint
pnpm test
pnpm test:coverage
pnpm check:i18n
pnpm check:parity
pnpm check:no-secrets
pnpm --filter @salmon/extension build
```

Tests live with the application or package that owns the behavior. Browser-extension end-to-end material is under `apps/extension/.playwright`; mobile end-to-end material is under `apps/mobile/.maestro`.

Do not use real recovery phrases, private keys, production credentials, or funded accounts when producing a reproducer. Use generated test credentials and local fixtures.

## Severity guidance

### Critical

- Extraction of a recovery phrase or private key from a realistic remote or low-interaction attack.
- Signing or broadcasting an attacker-chosen transaction without meaningful user approval.
- A displayed transaction that differs materially from the transaction signed, where exploitation can cause asset loss.
- A remotely exploitable compromise that gives a website or remote service persistent authority over wallet credentials or transactions.
- A supply-chain or update-path vulnerability that can inject code into distributed wallet builds at scale.

### High

- Credential disclosure requiring limited user interaction or a plausible malicious decentralized application.
- Bypass of an approval, origin, account, network, or permission boundary that can lead to unauthorized signing or meaningful asset loss.
- Persistent compromise of wallet state or trusted extension/mobile execution without direct credential extraction being demonstrated.
- A cryptographic, random-number, derivation, encryption, or storage flaw that materially weakens protection of wallet credentials.

### Medium

- Sensitive financial or pseudonymous wallet data disclosure without private-key exposure.
- Transaction-detail spoofing or origin confusion that creates a credible phishing or mis-approval path but does not itself authorize a transaction.
- Denial of service, corrupted local state, or data loss that requires recovery but does not expose credentials or move assets.
- A security control bypass that needs substantial additional conditions before it can affect funds.

### Low

- Limited information exposure, defense-in-depth gaps, or crashes with no credible path to credential exposure, unauthorized signing, persistent compromise, or asset loss.

Do not rate a theoretical issue as critical or high without a concrete path from attacker-controlled input to the claimed impact. Reports should state all required user actions, platform assumptions, permissions, and environmental conditions.

## Report and patch expectations

Each report should identify the affected platform and flow, explain the trust boundary that fails, give minimal reproducible steps using test credentials, state the concrete user impact, and distinguish confirmed behavior from inference.

Proposed patches should preserve self-custody, require explicit approval for security-sensitive actions, avoid logging or persisting secrets, and include a regression test where practical. Do not solve a client-side flaw by sending private keys, recovery phrases, decrypted wallet material, or signed transactions to a backend.

Useful proofs of concept: a unit test or script that feeds a crafted transaction (base64) through the wallet's own checks (for example `assertSolanaTransactionMatches` or `assertSwapPaysWallet`) and shows it is accepted, or a Playwright or Maestro flow against a test wallet. Use devnet or simulation only, never real funds.

Deduplicate by root cause: one report per broken check, listing every entry path (extension, mobile, dApp, backend-built flow) that reaches it.
