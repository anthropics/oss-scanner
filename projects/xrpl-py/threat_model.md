# xrpl-py: threat model and severity guide for the scanner

xrpl-py is the Python SDK for the XRP Ledger (ISC licensed, https://github.com/XRPLF/xrpl-py, docs
https://xrpl-py.readthedocs.io). Services, bots and wallets use it to derive keys, sign transactions and talk to
`xrpld` servers. A bug here can lose funds without any server being at fault, so signing and key handling matter
most. The package is `xrpl/`; tests are in `tests/` (unit, integration and faucet).

## Where untrusted input enters

- **Server responses** (`xrpl/clients`, `xrpl/models/response.py`, `xrpl/asyncio`). JSON-RPC and WebSocket replies,
  subscription messages and `tx_blob` values come from a server, or from someone on the path to it. A hostile or
  compromised server is a realistic attacker. A client that accepts a wrong value (a different transaction than
  was submitted, a forged validated flag, wrong balances) is in scope.
- **Binary codec** (`xrpl/core/binarycodec`): decoding hex blobs into objects and encoding transaction JSON into
  the signing blob. Look for crashes, unbounded loops or memory, round trips that change a value, and any case
  where the signed bytes differ from what the caller asked for (field omission or reordering, amount precision,
  `definitions.json` mismatches, multisign signer ordering).
- **Keys and seeds** (`xrpl/core/keypairs`, `xrpl/wallet`): entropy, seed and mnemonic derivation, signature
  determinism and malleability (secp256k1 through ECPy, and ed25519), constant-time behavior, and secrets in logs
  or exceptions.
- **Addresses** (`xrpl/core/addresscodec`): base58 and checksum handling, X-address tags and flags. Accepting an
  invalid address, or mapping one string to a different destination or tag, is in scope.
- **Amounts and numbers** (`xrpl/models/amounts`, `xrpl/utils`): XRP drops, issued-currency values, rounding,
  exponent range and conversion helpers (`xrp_to_drops`, `drops_to_xrp`). A difference from the server's rules can
  change what is paid.
- **Model validation** (`xrpl/models`): transaction dataclasses accept user dicts and validate them. Validators
  that accept fields the server later reads differently are in scope.

## What matters most, and what is out of scope

Most important, roughly in order:

1. **Signing and encoding integrity**: the bytes that are signed differ from what the caller asked for.
2. **Key and seed security**: weak or predictable key generation, secret disclosure, secrets sent to a server.
3. **Wrong acceptance of server data**, with the server as the attacker.
4. **Address and destination handling.**
5. **Denial of service by crafted input**: a response or blob that hangs, crashes or exhausts memory.

Out of scope, or not what we mean by security:

- Third-party dependencies themselves (`ECPy`, `base58`, `httpx`, `websockets`, `pycryptodome`, and so on). Our use
  of them is in scope; a bug inside the upstream library is theirs.
- The test tree, docs, `tools/` and `.github/`: these assume trusted input.
- The optional native add-on `xrpl/ext/confidential` ships as a separate distribution; treat it as lower priority.
- Faucet and network defaults that point at public test networks.
- Deliberate caller choices: connecting to an untrusted server over plain `ws://` or `http://`, or passing a
  hostile object that the type hints forbid.
- Economic behavior that is within XRP Ledger protocol rules (fees, reserves).

## The image: how to build, run and exercise it

The checkout is `/src`; `git -C /src rev-parse HEAD` names the commit under scan. Everything runs offline. The
package and its dev dependencies are installed in `/src/.venv` (Python 3.11). Run commands from `/src` with
`poetry run`, for example:

- Unit tests: `poetry run python -m unittest discover tests/unit` (one module: `poetry run python -m unittest
  tests.unit.core.binarycodec.test_main`). Integration and faucet tests need a ledger and will not work.
- A short script: `poetry run python -c "from xrpl.core import binarycodec, keypairs; ..."`.
- A fake server can feed hostile responses to the client classes; the mocks under `tests/unit` show how.

Where novel bugs are most likely: the decode/encode round trip, amount and number handling, transaction models
whose validation differs from the server, and client handling of unexpected response shapes. The key derivation
primitives have had more review.

## How we rate severity

- **Critical**: key or seed recovery or disclosure; a signature over different content than the caller asked for;
  predictable key generation; remote code execution.
- **High**: accepting forged or altered server data as validated or correct in a way that can cause fund loss; an
  address or tag parser that maps to a different destination; signature malleability that affects transaction
  identity.
- **Medium**: a crafted response or blob that crashes or hangs the process; incorrect amount rounding with bounded
  impact; secrets written to logs or errors.
- **Low**: missing validation that the server rejects anyway; disclosure of nonsecret data.
- **Not a bug**: input that fails with a clear exception, a rejected transaction, or behavior that follows protocol rules.

## Things to leave alone

- Style, lint (flake8, black, isort) and type-hint-only issues.
- Deprecated APIs kept for compatibility, except for signing or key issues.
- Issues that exist only in tests or docs examples.

## How we would like reports and patches to look

One finding per report, with the commit, the exact command or script, and its output. State who controls the
input (a server, a user) and what the attacker gains. Patches should be a minimal diff against `main` in the
surrounding style, with a regression test under `tests/unit` and a `CHANGELOG.md` entry.
