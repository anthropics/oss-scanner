# Threat model

## What this project does and where untrusted input enters
Securely stores (public-key encrypted) secrets, optionally alongside the code committed to git (or whatever), and provides a library for securely retrieving the secrets at runtime without/instead of injecting them as environment variables to prevent against leakage.

Refer to ./README.md in the repo root for overall usage example or client and library READMEs at ./ssclient/README.md and ./securestore/README.md (again relative to the SecureStore project repo root) for further information.

## Components that matter most / least
- Security of secrets serialized to the `secrets.json` store is priority 1; they should remain secure even if this secrets store were leaked (e.g. code repo is hacked and attackers gain access to the secrets store and its history).
- Weaknesses generating keys, nonces, or encrypting secrets
- Secure and timely runtime decoding of `secrets.json` files

## How to exercise it
- Building against `openssl` (`cargo test --release --all-targets --no-default-features --features openssl`) and using the `ssclient` cli utility to create, modify, or retrieve secrets from `secrets.json` stores, using encryption keys derived from passphrases, created from scratch (key-only decryption), or hybrid passphrase + exported compatible key approaches.
- The same but building in `rustls` configuration without openssl (`cargo test --release --all-targets --no-default-features --features rustls`).
- Using the crate API to programmatically retrieve secrets from `secrets.json` with secrets or passphrases, or hybrid key+passphrase support.
- Using the crate API to programmatically modify the secrets store.
- Making arbitrary out-of-band changes to the `secrets.json` file and then attempting any of the above.

## How you rate severity
- Any buffer overflow, use-after-free, or double free is high+ at a minimum. If the overflow is controlled and may lead to RCE then it should be critical.
- `ssclient` misuse (i.e. user accidentally or purposely committing keys to git) is low priority; default workflow should mitigate against this to an extent by automatically excluding key files from `.gitignore` under most scenarios.
- Attacker gaining physical control of the machine is not in scope.

## Anything to leave alone
- Do not report blocking IO as store is loaded or secrets are decoded as DOS vectors.
- Do not consider "hacker looking over shoulders" as a valid scenario; we are aware that in certain configurations; e.g. on wasm, `ssclient` renders entered passphrases to the console and does not mask them until the passphrase has been entered in its entirety due to platform limitations.
- Validating the strength of user-provided passwords/passphrases is out-of-scope and intentionally not checked beyond verifying that it is at least N characters long.
- Securely decryption keys (or decrypted secrets loaded out of the store) encrypted in memory to be resilient to memory dumping or process injection is not a current design goal.
