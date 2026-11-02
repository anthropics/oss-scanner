# Threat model

The project's own statement of its security model is `SECURITY.md` in the repository. Read it first; this file
restates it for the scanner and adds where to look.

## What this project does and where untrusted input enters

Frostsnap is bitcoin self-custody using FROST threshold Schnorr signatures (secp256k1, via the `schnorr_fun` crate).
Each signing device is an ESP32-C3 holding one share; a coordinator app (Flutter UI over a Rust backend) drives key
generation, signing, backup and restore over USB serial. A threshold `t` of `n` devices must cooperate to sign.

The model has three cases. Each names what is trusted, so each makes a different party the untrusted input:

1. **Every device corrupt, coordinator honest, attacker remote.** A remote attacker sees only what reaches the chain
   and the network. Malicious firmware must not be able to smuggle key material out through a signature, a nonce, or
   any other message that ends up on-chain or on the wire. Here **device-to-coordinator messages are untrusted**: the
   coordinator must constrain what devices can put into signatures and nonces.
2. **Physical attacker with fewer than `t` distinct shares** (a device, a backup, or malicious firmware on a device,
   counted once per share). No funds may be lost. Here **device flash, backups and anything a physical holder can
   present** are untrusted. Restore rebuilds only from shares presented.
3. **Corrupt coordinator, fewer than `t` corrupt devices**, with the user checking the device's own screen. Here
   **coordinator-to-device messages are untrusted**. What the device displays is the security boundary:
   - at key generation, the threshold, the number of devices, and a security check code that must be identical on
     every device;
   - at signing, every destination and amount leaving the wallet, and the fee (a single change output back to the
     wallet is deliberately not listed).

Entry points:
- Serial framing and message decoding: `frostsnap_comms` (`ReceiveSerial`, `WireCoordinatorSendBody`,
  `WireDeviceSendBody`, bincode). Devices are daisy-chained, so a device also relays bytes addressed to other devices.
- Device protocol state machine: `frostsnap_core/src/device*` (keygen, signing, nonces in `device_nonces.rs`,
  restoration, share encryption in `symmetric_encryption.rs`).
- Coordinator protocol state machine: `frostsnap_core/src/coordinator*`, `coord_nonces.rs`, `nonce_stream.rs`,
  `master_appkey.rs`, `tweak.rs` (BIP32-style derivation of the threshold key).
- Transactions: `frostsnap_core/src/bitcoin_transaction.rs` and `psbt.rs` (what the device is told it is signing and
  how that becomes the displayed destinations, amounts and fee); `frostsnap_coordinator/src/bitcoin/psbt.rs` for PSBTs
  imported from files or QR codes.
- Firmware upgrade: `device/src/ota.rs`, `device/src/secure_boot.rs`, `frostsnap_secure_boot`,
  `frostsnap_coordinator/src/firmware_upgrade.rs`. A coordinator can stream an image; the device checks it against
  the announced digest and, with secure boot enabled, its signature.
- Genuine-device check: `frostsnap_comms/src/genuine_*`, `frostsnap_coordinator/src/genuine_check.rs`,
  `device/src/flash/genuine_certificate.rs`.
- Backups: `frost_backup` (share encoding as words, checksums, recovery from shares), and entry of a physical backup
  on the device.
- Network: the coordinator's Electrum client, with TLS certificates pinned trust-on-first-use
  (`frostsnap_coordinator/src/bitcoin/tofu`), and nostr event signing (`frostsnap_core/src/nostr.rs`).

## Components that matter most / least

Most: `frostsnap_core`, `frostsnap_comms`, `device/` (OTA, secure boot, flash storage of shares and nonces),
`frost_backup`, `frostsnap_secure_boot`, and the signing, keygen, PSBT and firmware-upgrade parts of
`frostsnap_coordinator`. In `frostsnap_widgets`, the screens that show keygen parameters, the check code, and sign
prompts (destinations, amounts, fee) are security-critical, because case 3 rests on them being correct and
unambiguous.

Less: the rest of `frostsnap_coordinator` (settings, persistence plumbing), the rest of `frostsnap_widgets`.

Out of scope: the Flutter/Dart app in `frostsnapp/lib`, `tools/`, `frostsnap_factory` (runs in the factory during
provisioning), `frostsnap_fonts`, `cst816s` (touch driver), `macros/`.

The cryptography lives mostly in `secp256kfun`, `schnorr_fun` and `vrf_fun`. A flaw there that breaks the model
above is in scope here, but report it as a Frostsnap finding: those repositories are public.

## How to exercise it

The image builds and tests these crates offline:
`cargo test --locked --all-features -p frostsnap_core -p frostsnap_comms -p frostsnap_coordinator
-p frostsnap_embedded -p frost_backup -p frostsnap_secure_boot -p frostsnap_widgets`.

- `frostsnap_core/tests/env/` simulates a coordinator and devices passing messages; `endtoend.rs`, `malicious.rs`,
  `proptest.rs`, `restoration.rs` and `nonce_generation.rs` build on it. A malicious-coordinator or malicious-device
  reproducer is easiest written as a new test against this environment.
- `frostsnap_core/tests/wire_format.rs` and the `*_backward_compat.rs` tests pin the wire format.
- `frost_backup/tests/` cover encoding, checksums and recovery; `frostsnap_coordinator/tests/real_psbts.rs` uses real
  PSBT fixtures; `frostsnap_secure_boot/tests` verify signed firmware fixtures.
- Firmware crates (`frostsnap_device`, `frostsnap_cst816s`) only build for `riscv32imc-unknown-none-elf`; the image
  type-checks them but cannot run them. Reason about device code by reading it, and reproduce device-side logic
  through `frostsnap_core`, which the firmware calls into.
- The Flutter FFI crate `frostsnapp/rust` is not built (it needs flutter_rust_bridge codegen).

## How you rate severity

- **Critical:** anything that breaks one of the three cases and moves funds or exposes key material. Examples: key
  or share material recoverable from signatures, nonces or other on-chain or on-wire data under case 1; nonce reuse
  or predictable nonces; fewer than `t` shares sufficing to sign or reconstruct; a device signing for a destination,
  amount or fee other than what it displayed; keygen where every device shows the same check code yet the key is not
  the one the devices jointly generated; a device with secure boot enabled accepting firmware that is not correctly
  signed.
- **High:** the same breaks needing an extra unlikely precondition, or leaking partial secret information; a backup
  that encodes or restores to a different share than claimed without detection; a restore that silently produces a
  different or smaller wallet than the shares presented.
- **Medium:** a display or flow that makes one of the required user checks misleading or easy to skip, such as an
  ambiguous or truncated address or amount; weaknesses in the genuine-device check.
- **Low:** everything in the list below.

## Anything to leave alone

These are listed in `SECURITY.md` as not breaking the model. Rate them low, or do not report them:
- crashes, panics, hangs, local denial of service (e.g. the app crashing the device or vice versa), resource
  exhaustion and memory usage;
- anything that only stops a transaction from being signed, since a corrupt party can always refuse;
- privacy and metadata leakage, including address clustering and network observation;
- timing variation and side channels in code that never touches secret material;
- missing hardening, unused attack surface, dependency advisories with no path to funds moving;
- griefing that strands funds without moving them to an attacker (e.g. change parked at a derivation index the wallet
  will not immediately rescan);
- corrupt devices refusing to sign, or giving backup words that do not reconstruct their share (ransom). This is a
  known limitation, not a break.

Also do not report:
- `frostsnap_factory/genuine/dev/secret_key.hex` and `frostsnap_secure_boot/tests/fixtures/test-signing-key.pem`.
  They are development and test keys, published deliberately.
- Attacks that work only because the user skipped a check the model requires (the device's check code, threshold,
  device count, destinations, amounts, fee).
- Devices without secure boot enabled running unsigned firmware.
