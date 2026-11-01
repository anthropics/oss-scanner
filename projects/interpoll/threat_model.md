# Threat model

## What this project does and where untrusted input enters
InterPoll is a decentralised, browser-first polling/discussion platform (Vue 3 + Pinia frontend, Node relay servers, GunDB replication, local IndexedDB hash-chain). Actions (votes, posts, comments, polls) are signed by device keys.
Adversarial inputs: everything arriving from peers and relays -- GunDB graph data, WebSocket messages (`relay-server.js`), BroadcastChannel messages, imported keys/backups, invite links, and all HTTP requests to the relay (`/api/*`, OAuth callbacks, `/gun` proxy). Remote users, other peers and a malicious or compromised relay are all untrusted. A relay may delay or censor but must not be able to forge a signed action.

## Components that matter most / least
Most: signature/hash/PoW/replay validation (`src/services/integrity*.ts`, `chainService.ts`, `cryptoService.ts`), `shared-validation/` (used by frontend and relay), the relay vote authorize/confirm flow and duplicate-vote prevention, relay auth/session/OAuth handling, private-community encryption (`encryptionService.ts`, `keyVaultService.ts`, `inviteLinkService.ts`), and XSS in rendering of user content (posts, comments, profiles, images, links).
Least: UI styling, `docs/`, `tools/` (analysis/pilot scripts), `unit_tests/`, mobile/desktop wrappers (`android/`, `src-tauri/`).
Out of scope: third-party dependencies' own bugs, GunDB internals, and anything requiring physical access to a user's unlocked browser profile (keys are local by design).

## How to exercise it
`npm run build` output is in `/src/dist`. Run the dev relay with `node relay-server.js` (port 8080) and the Gun relay with `cd gun-relay-server && node gun-relay.js` (port 8765). `npm test` runs the vitest suite in `unit_tests/`. The production relay (`relay-server/`) is not in the repository.

## How you rate severity
- Forging or replaying a signed action as another identity, bypassing vote authorization or duplicate-vote protection, or relay auth/session bypass: high or critical.
- Stored or reflected XSS reachable from peer-supplied content, or decryption/key disclosure for private communities: high.
- Remote code execution or arbitrary file access on a relay: critical.
- Relay or client DoS from a single unauthenticated request: medium. Rate-limit weaknesses alone: low.

## Anything to leave alone
- Missing hardening that only matters when dev defaults (localhost URLs, example secrets in docs) are deployed unchanged.
- Spam/abuse that the protocol deliberately leaves to client-side filtering.
- Self-XSS that requires the user to paste code into their own console.
