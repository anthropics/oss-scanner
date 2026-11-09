# xrpl.js: threat model and severity guide for the scanner

xrpl.js is the main JavaScript/TypeScript SDK for the XRP Ledger (ISC licensed, https://github.com/XRPLF/xrpl.js).
It runs in Node.js and in browsers, and wallets, exchanges and web apps use it to create keys, sign transactions
and talk to `xrpld` servers. A bug here can lose users' funds without any server being at fault, so signing and
key handling matter most.

The repository is an npm/lerna monorepo. Packages under `packages/`:

- `xrpl`: the client (WebSocket connection, request/response types, transaction models and validation, `Wallet`,
  signing, multisign, autofill, `Client.submitAndWait`).
- `ripple-binary-codec`: encodes and decodes the XRPL binary format (transactions, ledger objects, amounts,
  `definitions.json`).
- `ripple-keypairs`: seed, key pair, signature and address derivation (secp256k1 and ed25519).
- `ripple-address-codec`: base58 addresses, seeds, X-addresses, node and account public keys.
- `@xrplf/isomorphic`: wrappers for hashing and WebSocket across Node and browser.
- `@xrplf/secret-numbers`: encode and decode a seed as secret numbers.
- `@xrplf/mpt-crypto`: a WASM module for confidential MPT cryptography.

## Where untrusted input enters

- **Server responses and WebSocket messages** (`packages/xrpl/src/client`, `src/models`). Anything an `xrpld`
  server, or someone on the path to it, sends back is untrusted: JSON responses, subscription events, and
  `tx_blob` values. A hostile or compromised server is a realistic attacker, so a client that accepts a wrong
  value (a different transaction than was submitted, a forged validated flag, wrong balances) is in scope.
- **Binary decoding** (`ripple-binary-codec`): hex blobs from servers or users parsed into objects. Look for
  crashes, unbounded loops or memory, and inputs that decode to a different object than the one that was signed.
- **Binary encoding and signing**: user-supplied transaction JSON turned into the signing blob. Any case where the
  signed bytes differ from what the application displayed or validated is a serious bug (field omission or
  reordering, amount precision, `definitions.json` mismatches, `SigningPubKey` and `Account` consistency,
  multisign signer ordering).
- **Key and seed handling** (`ripple-keypairs`, `secret-numbers`, `Wallet`): entropy source, seed and mnemonic
  derivation, signature determinism and malleability, and any path that logs or returns secrets.
- **Address and seed parsing** (`ripple-address-codec`): base58 and checksum handling, X-address tags and flags,
  accepting an invalid address or silently changing the destination or tag.
- **Amount and number handling**: XRP drops and issued-currency values (`BigNumber`/`Decimal` use, rounding,
  exponent range, negative and zero values). A parsing difference from the server's rules can change what is paid.
- **Browser use**: the web bundles run in pages that hold users' keys. Prototype pollution, DOM or script
  injection through values the library returns, and unsafe use of `eval`/`Function` are in scope.

## What matters most, and what is out of scope

Most important, roughly in order:

1. **Signing and encoding integrity**: the bytes that are signed differ from what the caller asked for.
2. **Key and seed security**: weak or predictable key generation, secret disclosure, nonconstant-time operations with a
   plausible observer, or secrets sent to a server.
3. **Wrong acceptance of server data**: the client reports a transaction as validated, or a balance, address or
   amount as correct, when it is not, with the server as the attacker.
4. **Address and destination handling**: a parser that maps one string to a different address or tag.
5. **Denial of service by crafted input**: a response, blob or JSON value that hangs or crashes the process,
   or exhausts memory.
6. **Memory safety in the WASM module** (`mpt-crypto`) and its JavaScript glue.

Out of scope, or not what we mean by security:

- Third-party dependencies themselves (`@noble/*`, `bignumber.js`, `ws`, `lodash`, and so on). Our use of them is in
  scope; a bug inside the upstream library is theirs.
- The test, build and tooling trees: `packages/*/test`, `packages/*/tools`, `.github/`, `docs/`, webpack and
  karma config, and `scripts/`. These assume trusted input.
- Faucet and network defaults that point at public test networks.
- Deliberate caller choices: connecting to an untrusted server over `ws://`, passing a seed the caller already has,
  or calling the library with arguments the TypeScript types forbid.
- Economic behavior that is within XRP Ledger protocol rules (fees, reserves).

## The image: how to build, run and exercise it

The checkout is `/src`; `git -C /src rev-parse HEAD` names the commit under scan. Everything runs offline.
Dependencies are in `/src/node_modules`, and every package is built (`packages/*/dist`).

- Run the unit tests for one package: `cd /src && npm test --workspace=ripple-binary-codec` (also
  `ripple-keypairs`, `ripple-address-codec`, `xrpl`). Integration tests need a running ledger and will not work.
- Drive the code with a small script: `node -e "const {Wallet, encode, decode} = require('/src/packages/xrpl'); ..."`
  or import from `/src/packages/ripple-binary-codec/dist` and `/src/packages/ripple-keypairs/dist`.
- A mock WebSocket server can feed hostile responses to `Client`; the unit tests under `packages/xrpl/test` show how.

Where novel bugs are most likely: the decode/encode round trip (a value that encodes and decodes to something
different), amount and number parsing, transaction validators that accept fields the server later reads
differently, and `Client` handling of unexpected response shapes. The key derivation primitives have had more review.

## How we rate severity

- **Critical**: key or seed recovery or disclosure; a signature over different content than the caller asked for;
  predictable key generation; remote code execution in Node or the browser.
- **High**: accepting forged or altered server data as validated or correct in a way that can cause fund loss; an
  address or tag parser that maps to a different destination; signature malleability that affects transaction
  identity.
- **Medium**: a crafted response or blob that crashes or hangs the process; incorrect amount rounding with bounded
  impact; secrets written to logs or errors.
- **Low**: missing validation that the server rejects anyway; information disclosure of nonsecret data; behavior
  that needs the caller to pass a hostile object directly.
- **Not a bug**: input that fails with a clear error, a rejected transaction, or behavior that follows protocol rules.

## Things to leave alone

- Style, lint and type-only issues.
- Deprecated APIs kept for compatibility, except for memory safety or signing issues.
- Issues that exist only in the unit tests or docs examples.

## How we would like reports and patches to look

One finding per report, with the commit, the exact command or script, and its output. State who controls the
input (a server, a user, a page) and what the attacker gains. Patches should be a minimal diff against `main` in
the surrounding style, with a regression test next to the existing tests, and a `HISTORY.md` entry for the package.
