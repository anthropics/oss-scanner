# Threat model: Cap

## What Cap is and where untrusted input enters
Cap is an open-source proof-of-work CAPTCHA. A client is served a challenge, solves it by brute-forcing PoW in the browser (WASM), and submits a solution the server verifies and exchanges for a short-lived token. A relying application later checks that token server-side.

- **`core/` (`capjs-core`)** is the verification library, and most inputs are attacker-controlled.

- **`standalone/` (`cap-standalone`)** is an Elysia HTTP server that wraps `core` and exposes it over the network with an admin dashboard. Its routes take untrusted request bodies, query strings, cookies and headers. Entry points: the challenge/redeem routes (`src/cap.js`), the `/siteverify` server-to-server verification endpoint (`src/siteverify.js`), admin auth (`src/auth.js`, `admin_key` login and session cookies), rate limiting (`src/ratelimit.js`), secret hashing (`src/secret-hash.js`), and the GeoIP lookup (`src/ipdb.js`, maxmind, parses client IPs). 

## Components that matter most to least
1. `core/crypto.js`, `core/prng.js`, `core/hashwx.js`, `core/rsw.js` — token signing/verification, challenge randomness, and the proof-of-work hashing. Highest priority. A predictable PRNG, a token-forgery or signature-bypass, a length-extension or timing issue, or any path that accepts a solution without the claimed work is the worst case.
2. `core/index.js`, `core/detect.js`, `core/instrumentation.js` — public API surface and bot-signal collection.
3. `standalone/src/*.js` — HTTP handlers, admin auth, siteverify, rate-limit enforcement, GeoIP parsing, the local store.
4. Lower priority, client-side or non-server: `widget/` (browser widget), `wasm/` (Rust solver, not built here), `demo/`, `bench/`, `docs/`, `assets/`.

## How we rate severity
Following Cap's security policy, a CAPTCHA bypass report must come with a working fix to be actionable.

- **Critical**: token forgery or accepting a token the server never issued; accepting a solution without the required proof-of-work; admin-auth bypass (`admin_key`/session); remote code execution.
- **High**: a practical CAPTCHA bypass that still needs some work factor; a predictable or weak PRNG that lowers challenge difficulty; secret/key disclosure; authenticated-to-unauthenticated privilege issues.
- **Medium**: extreme denial of service (including algorithmic complexity in verification or hashing), rate-limit bypass, stored or reflected issues in the admin UI.
- **Low / informational**: findings that need an unrealistic attacker position, or defense-in-depth suggestions.