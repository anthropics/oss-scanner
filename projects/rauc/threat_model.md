# RAUC threat model

## What it does and where untrusted input enters

RAUC (https://rauc.io) installs update bundles on embedded Linux devices. On the
device it runs as root, as the `rauc service` D-Bus daemon or the `rauc` CLI.
The same binary creates, signs and inspects bundles on developer hosts.

A bundle (`*.raucb`) is a SquashFS image (manifest plus images) followed by a
CMS signature. The `verity` and `crypt` formats add a dm-verity hash tree; the
legacy `plain` format does not. The signer certificate is checked against the
keyring in `system.conf` before any bundle content is used.

Untrusted input, most important first:

1. **Bundles**, from local storage or streamed over HTTP(S). Everything up to
   and including signature verification handles attacker-controlled bytes:
   `src/signature.c`, `src/bundle.c`, `src/manifest.c`, `src/crypt.c`.
2. **Network input** (`src/nbd.c`, `src/network.c`, `src/polling.c`,
   `src/hash_index.c`): server responses, ranges, redirects, chunk data. The
   NBD helper drops to `streaming_user` (default `nobody`); the root main
   process parses what it fetches.
3. **The D-Bus interface** (`src/service.c`): the default policy in
   `data/de.pengutronix.rauc.conf` lets any local user call the root service,
   including `InstallBundle` with a path or URL and an options dictionary
   (`tls-*`, `http-headers`, `ignore-*`, `transaction-id`).
4. **Bootloader state and status files** (`src/bootloaders/*.c`,
   `src/status_file.c`, `src/event_log.c`): changing these needs root or
   physical access, so they are semi-trusted.

Trusted: `system.conf`, keyrings, the rootfs, root's command line, and bundle
content after its signature verified (the signing key holder is the vendor).
Bundle creation (`rauc bundle`, `resign`, `convert`, `encrypt`, `extract`) runs
on a host with operator input; `--no-verify` is an explicit opt-out.

## Components

Most important: the parsing and verification files above; the install path
(`src/install.c`, `src/update_handler.c`, `src/update_utils.c`, `src/mount.c`,
`src/dm.c`, `src/slot.c`, `src/artifacts.c`, `src/emmc.c`, `src/mbr.c`,
`src/gpt.c`); `src/shell.c` and the handler/hook mechanism in `src/install.c`,
which export manifest- and slot-derived values to shell scripts run as root;
D-Bus and option handling in `src/service.c` and `src/main.c`; the commands
built in `src/bootloaders/*.c` and `src/bootchooser.c`.

Out of scope: `contrib/`, `docs/`, `test/`, `fuzz/`, `qemu-test*`, build and
style scripts, and the third-party libraries in `subprojects/*.wrap`. The
keys, certificates and bundles under `test/` are intentional fixtures.

## How to exercise it

- `build/rauc` (gcc, debug info). `build/rauc info --keyring
  test/openssl-ca/dev-ca.pem test/good-bundle.raucb` exercises the whole
  verification path; `--no-verify` skips it. Ready-made bundles are in
  `test/*.raucb`, configs in `test/*.conf`, the test PKI in `test/openssl-ca/`.
- `meson test -C build --suite rauc` runs the C tests (`build/test/*-test`) and
  `pytest` tests (`test/test_*.py`, need `MESON_BUILD_DIR=/src/build`). Tests
  needing loop devices, mounts or device-mapper skip when not root and fail as
  root without those devices; run them as `rauc-ci` (`su rauc-ci -c ...`).
- `./qemu-test` runs the full suite in a VM (kernel `bzImage` is in `/src`);
  `./qemu-test test=<name>` runs one test, `./qemu-test shell` opens a root
  shell in the VM. Without `/dev/kvm` it is slow but works.
- `build-fuzz/fuzz/manifest_fuzzer` and `build-fuzz/fuzz/bundle_fuzzer` are
  clang/ASan libFuzzer binaries (seed corpora and dictionary in `fuzz/`).
- The image is RAUC's CI container (`ghcr.io/rauc/rauc/rauc-ci`), so `desync`,
  SoftHSM, `nginx` (`test/nginx.conf`, `test/test_http.py`) and qemu are there.

## Severity

- **Critical**: installing or executing content not signed by a key in the
  configured keyring (verification bypass, unverified data mounted or written
  to a slot, defeated chain or revocation checks), or memory corruption during
  bundle, signature or manifest parsing that yields code execution;
  unauthorised access to encrypted bundle contents.
- **High**: memory corruption in root code paths reachable from an unverified
  bundle, the network or an unprivileged D-Bus caller; local privilege
  escalation (D-Bus, `plain` bundle TOCTOU protections, predictable temp files
  or mount points); leaving the device unbootable from untrusted input; TLS
  or pinning options silently ineffective.
- **Medium**: crash, hang or unbounded memory in the root service from a
  crafted bundle or server, when the device stays bootable; memory corruption
  only in the unprivileged NBD helper; bugs in bundle creation tools.
- **Low**: anything requiring a verified bundle or root-writable files, issues
  in `contrib/`, tests or docs, and robustness of `--no-verify`.

## Reports and patches

A small script that builds a crafted bundle (with `rauc bundle` and the test
PKI, or by patching bytes of a `test/*.raucb`) and shows the failure with
`build/rauc` or a fuzzer is the ideal reproducer. Patches as `git diff` against
`master`, formatted with `./uncrustify.sh`, keeping GLib >= 2.64 and OpenSSL
>= 3.0; a test in `test/` is welcome.

## Leave alone

- `--no-verify`, the D-Bus policy allowing any local user to call the service,
  and signed bundles running handler scripts as root are documented design.
- The committed test PKI, keys, CRLs, bundles and their passwords.
- Deprecated OpenSSL 3.0 engine APIs (PKCS#11 engine support is intentional)
  and GLib APIs deprecated after the pinned maximum version.
- The `plain` format is known weaker than `verity` and the docs recommend
  `bundle-formats=-plain`; report bypasses of its mitigations, not the design.
- Resource exhaustion that needs a validly signed bundle.
