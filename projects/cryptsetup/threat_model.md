# Threat model: cryptsetup / libcryptsetup

## What this project does

cryptsetup is the userspace side of Linux block-device encryption and integrity. It consists of:

- **libcryptsetup** (`lib/`) – the library that parses on-disk metadata, derives keys (PBKDF2,
  Argon2), unlocks keyslots and drives the kernel device-mapper targets `dm-crypt`, `dm-verity`
  and `dm-integrity`. It is linked by systemd (`systemd-cryptsetup`, `systemd-cryptenroll`,
  `systemd-veritysetup`, `systemd-homed`), udisks2, initramfs generators, installers and others.
- **CLI tools** (`src/`) – `cryptsetup`, `veritysetup`, `integritysetup`; thin wrappers over the
  library.
- **LUKS2 token plugins** (`tokens/`) – the optional `ssh` token plugin, loaded by `dlopen()`.

Supported on-disk formats: LUKS1, LUKS2 (binary header + JSON metadata, two copies), plain
dm-crypt, loop-AES keyfiles, TrueCrypt/VeraCrypt (TCRYPT), BitLocker (BITLK), Apple FileVault2
(FVAULT2), dm-verity superblock (+ FEC and root-hash signature), dm-integrity superblock, and the
LUKS2 SED OPAL extension.

The library almost always runs **as root**, very often automatically (udev rules, systemd units,
initramfs at boot, desktop auto-mount of removable media). A bug in metadata parsing is therefore
a bug in a root process that is fed attacker-shaped data with no user interaction.

## Where untrusted input enters

Treat everything read from a block device or a file passed as a device/header as
attacker-controlled. Concretely:

1. **On-disk metadata of every supported format** – LUKS1 header and keyslot areas; LUKS2 binary
   headers, both JSON metadata copies, keyslot areas and the header-selection/recovery logic;
   TCRYPT/VeraCrypt headers (including hidden/system volume variants, decrypted with the user's
   passphrase but otherwise attacker-shaped); BITLK metadata blocks, entries and FVE datums;
   FVAULT2 CoreStorage metadata; VERITY superblock, hash tree and FEC area; INTEGRITY superblock.
   Attack scenarios: a malicious USB stick or disk, a downloaded or cloud VM image, an
   "evil maid" who rewrites the header of a laptop disk, a compromised storage backend.
2. **Detached header files** (`--header`), **header backup files** (`luksHeaderRestore`), and
   **LUKS2 metadata imported via `cryptsetup token import` / `--json-file`**.
3. **LUKS2 JSON content that drives behaviour**: segments, digests, keyslot areas/offsets,
   reencryption state (`reencrypt` keyslot, hotzone, resilience mode, checksums), token
   definitions (including which external token plugin name is requested and the fields the
   `ssh` token reads: `ssh_server`, `ssh_user`, `ssh_path`, `ssh_keypath`), flags and
   requirements, labels/subsystem.
4. **Keyfiles and passphrases** – content is trusted (it comes from the user) but size and
   encoding handling (keyfile offset/size limits, UTF-8 / TCRYPT keyfile pooling, loop-AES
   keyfile parsing) must be robust.
5. **Data area contents during online reencryption** – the library reads and rewrites data in
   place, guided by header-controlled offsets and checksums.

Trusted (out of the attacker's control in this model): the command line and API caller,
the kernel and its device-mapper/crypto implementations, linked crypto libraries, json-c,
libblkid, libdevmapper, the external token plugin directory and the plugin `.so` files in it,
root-owned configuration, the kernel keyring of the calling user.

## What a real vulnerability looks like here

In scope (roughly in order of interest):

- **Memory-safety bugs** reachable from crafted metadata or header files: out-of-bounds
  read/write, use-after-free, double free, integer overflow leading to wrong allocation or
  offset, uninitialised memory used in a security decision, unbounded recursion/allocation.
- **Key or secret disclosure**: volume key, passphrase or derived key material leaked to logs,
  debug output, swap-able unlocked memory, other files, other users, or written to disk; key
  material left in memory after it is no longer needed when that is observable by a less
  privileged party.
- **Silent confidentiality/integrity downgrade** triggered by header tampering: a crafted header
  that, after the legitimate user unlocks with their passphrase, makes cryptsetup activate or
  reencrypt the device so that subsequently written data is stored in plaintext, under a key the
  attacker knows, or with integrity protection silently disabled (cf. CVE-2021-4122, where a
  forged reencryption state decrypted data in place). Null cipher acceptance in the wrong place
  falls here.
- **Root-process side effects driven by metadata**: e.g. a header causing a root process to read
  or send an arbitrary local file, load an unexpected plugin, or open
  network connections without the user asking for that token.
- **Wrong cryptography**: incorrect KDF/cipher parameters accepted or computed, keyslot
  verification bypass (unlocking without the correct passphrase), digest checks that can be
  skipped, weak-parameter acceptance that bypasses documented minimums.

## Known design limits (do not report as vulnerabilities)

- LUKS metadata is **checksummed, not authenticated**. Anyone who can write the header can
  destroy it, swap in another header, lower PBKDF cost for *new* keyslots, rename tokens or
  change labels. These are not bugs **unless** they lead to one of the in-scope outcomes above
  (memory corruption, key disclosure, silent plaintext/known-key writes, out-of-bounds writes,
  keyslot bypass).
- Denial of service by corrupting or deleting the header (the volume will not open) is expected.
- An attacker with write access to the **data area** can corrupt or replay ciphertext; dm-crypt
  does not provide integrity unless `--integrity` / AEAD is configured.
- Physical attacks on a running unlocked system, cold-boot, DMA, kernel memory disclosure,
  hardware/firmware flaws in SED OPAL drives, and timing side channels of the underlying crypto
  libraries are out of scope.
- Passphrase strength and user choice of weak parameters on the command line.
- Anything requiring the attacker to control the command line, environment of a root process,
  the plugin directory, or `/etc` is out of scope.

## Components that matter most / least

Highest priority:
- `lib/`
  The bundled reference implementation in `lib/crypto_backend/argon2/` is **not built** in the
  scanner image (Argon2 comes from OpenSSL); findings only there are lower priority.

Medium:
- `tokens/ssh/` (experimental, but runs as root and reads header-supplied fields).
- `src/` CLI argument parsing and keyfile reading (input is trusted, but size/overflow bugs still
  count).

Low / out of scope:
- `tests/`, `tests/fuzz/` harnesses, `scripts/`, `misc/`, `docs/`, `po/`, `man/`, build files.

## How to exercise it (inside the scanner image)

Build outputs (both use the OpenSSL crypto backend, OpenSSL 3.5 with its Argon2 KDF; neither
the bundled Argon2 nor libargon2 is used):
- `/src/build/` – reference build (gcc, `-O2 -g`), tools in `/src/build/src/`.
- `/src/build-asan/` – clang ASan+UBSan build, tools in `/src/build-asan/src/`, libFuzzer
  targets in `/src/build-asan/tests/fuzz/`. `ASAN_OPTIONS`/`UBSAN_OPTIONS` are preset to abort
  on the first error. **Confirm memory-safety findings with the ASan build.**

Metadata parsing works on plain image files without root or device-mapper (luksDump,
bitlkDump, fvault2Dump).

Fuzzers (LUKS2 header with checksum fix-up, LUKS2 on-disk JSON, VERITY/INTEGRITY):

```sh
/src/build-asan/tests/fuzz/crypt2_load_fuzz -dict=/src/tests/fuzz/crypt2_load_fuzz.dict CORPUS/
/src/build-asan/tests/fuzz/crypt2_load_ondisk_fuzz -dict=/src/tests/fuzz/crypt2_load_ondisk_fuzz.dict CORPUS/
/src/build-asan/tests/fuzz/crypt_load_misc_fuzz CORPUS/
```

Library-level reproducers can be small C programs linked against
`/src/build-asan/lib/libcryptsetup.so`. API-level tests:
`/src/build/tests/api-test`, `api-test-2` (need root + device-mapper).

Activation, reencryption, verity/integrity format and most of `meson test -C /src/build` need
root, device-mapper, loop devices and sometimes `scsi_debug`; run them only inside the
privileged scanner VM. Tests that need networking (`ssh-test-plugin`) will not work offline.

## How we rate severity

- **Critical**: memory corruption with demonstrated or very likely code execution from a crafted
  header/image reachable without the passphrase (e.g. on `crypt_load()`, `isLuks`, `*Dump`,
  automatic probing by systemd/udisks); keyslot unlock without the correct passphrase;
  disclosure of the volume key to an unprivileged party.
- **High**: any out-of-bounds write, use-after-free or double free reachable from crafted
  metadata (default for memory corruption without a working exploit); crafted header that after
  a legitimate unlock causes silent plaintext or attacker-known-key writes or disables integrity;
  metadata/reencryption writes outside the device or header bounds; header-restore/lock-file
  races that write or leak arbitrary root-owned files.
- **Medium**: out-of-bounds read with limited information disclosure; key material left in
  memory/logs that is reachable only by root or after compromise; header fields making a root
  process read local files or open connections (token plugins); bugs reachable only after the
  correct passphrase is entered with a crafted header (lower one level when the crafted header
  requires prior write access to the specific victim device *and* user interaction).
- **Low**: crashes from NULL dereference, assertions, unbounded-but-finite CPU/memory use from
  crafted metadata (DoS), leaks on CLI error paths, undefined behaviour without demonstrated
  impact.
- Bugs only reachable by a trusted root caller passing nonsensical CLI/API arguments: Low or
  informational.

## How we would like reports and patches

- Target the `main` branch (`gitlab.com/cryptsetup/cryptsetup`).
- Include a minimal reproducer: preferably a script that generates the crafted image
  (like `tests/generators/`), otherwise a small xz-compressed image, plus the exact command and
  the ASan/UBSan output from `/src/build-asan`.
- State which formats and entry points are affected (`crypt_load` only? needs passphrase? needs
  root/dm?) and the first affected release if known.
- Patches: Linux kernel coding style (tabs), minimal and focused, no unrelated cleanups; fix the
  validation at the parsing/validation layer (e.g. `LUKS2_hdr_validate()` and friends) rather than
  adding checks at a single use site where possible. A regression test (new `tests/generators`
  image for `luks2-validation-test`, or an addition to the relevant `*-compat-test`) is
  appreciated.

## Anything to leave alone

- Do not report the lack of header authentication itself, PBKDF parameter choices, or
  deprecated-but-supported legacy formats/ciphers as vulnerabilities.
- Do not report issues only in the test suite, fuzz harnesses, or `misc/`/`scripts/` helpers.
- Do not report findings that depend on a modified kernel, malicious crypto library, or a
  malicious token plugin installed by root.
- Warnings about meson being "experimental" are expected.
