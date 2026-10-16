# Threat model

## What this project does and where untrusted input enters

Caravan is a stateless, client-side coordinator for Bitcoin multisig wallets: the Caravan Coordinator web app
(`apps/coordinator`) and the `@caravan/*` libraries it is built on (`packages/`), which are also published to npm.
It never holds private keys; it handles xpubs, addresses, PSBTs and signatures.

Untrusted input includes imported PSBTs, wallet configuration files, xpubs and derivation paths, QR/BC-UR payloads,
data returned by hardware signing devices, and responses from block explorers or bitcoind.

## Scope

In scope: the coordinator app and the `@caravan/*` packages in this repository.

Out of scope: hardware signing device firmware, external block explorer or API services, and build tooling
(`eslint-config`, `typescript-config`, `build-plugins`).

## How to exercise it

The repository is at `/src`, already installed (`npm ci`) and built (`npx turbo run build`).

- Unit tests (vitest): `npx turbo run test --filter=@caravan/<pkg>` (e.g. `@caravan/psbt`, `@caravan/bitcoin`,
  `@caravan/wallets`), `npx turbo run test --filter=caravan-coordinator`, or `npx vitest run` inside a package directory.
- Built packages are in `packages/*/dist`; small Node scripts that import them are the easiest way to drive the parsers.
- Fixtures with real xpubs, PSBTs and wallet configs: `packages/caravan-bitcoin/src/fixtures.ts` and
  `packages/caravan-wallets/src/fixtures`.
- The built coordinator is in `apps/coordinator/build`; `npx vite preview` in `apps/coordinator` serves it locally.
- The Playwright end-to-end tests (`apps/coordinator/e2e`) need browsers and a bitcoind regtest node, so they cannot run
  in the scan environment.

## How you rate severity

- Critical: loss of funds, signing a transaction other than the one the user reviewed, or a wrong receive/change address.
- High: crafted input that changes the amounts, outputs or fees shown to the user, or XSS reachable through imported data.
- Medium: privacy leaks (e.g. xpubs or addresses sent to third parties) and denial of service from malformed input.
- Low: issues that require an already-compromised browser, machine or signing device.

The signing device's screen is the user's final check. An attack that needs a compromised machine, browser or chain
backend (e.g. bitcoind RPC) and also needs the user to approve a signature without verifying what their signing
device displays is Low.
