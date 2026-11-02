# Threat model

## What this project does and where untrusted input enters
`mdadm` manages Linux Software RAID devices (md). It runs with `root` privileges (CLI invocations, `mdmon` background monitoring, systemd services, and `udev` auto-assembly rules).

Untrusted inputs enter primarily through:
1. **On-disk metadata and superblocks:** Reading and parsing metadata formats (`0.90`, `1.x`, DDF, IMSM) from unmounted block devices, newly hotplugged drives (e.g., untrusted USB enclosures), or loopback disk images.
2. **Configuration and command-line arguments:** `/etc/mdadm.conf` and CLI flags are generally trusted (root-controlled), but arguments passed via automated scripts or dynamic udev events may contain unsanitized drive paths or identifiers.
3. **Array monitor communications:** Local socket communications used by `mdmon` and monitor routines.

## Components that matter most / least
- **Matters Most:**
  - Superblock and metadata parsing routines: `super0.c`, `super1.c`, `super-ddf.c`, `super-intel.c`.
  - Assemble and probe logic invoked automatically by udev rules upon device detection (`Assemble.c`, `Incremental.c`, `Probe.c`).
  - `mdmon` monitor daemon and inter-process communication logic (`msg.c`, `monitor.c`).
- **Matters Less (but in scope):**
  - Array management operations (`Create.c`, `Grow.c`, `Manage.c`) that are only triggered by explicit admin action.
  - Informational queries (`Detail.c`, `Examine.c`, `Query.c`).
- **Least / Out of Scope:**
  - Test suites (`test`, `tests/`), build scripts, and auxiliary packaging files.

## How to exercise it
- CLI subcommands that parse metadata can be tested directly on synthetic or mutated raw disk images:
  - `mdadm --examine <image_file>`
  - `mdadm -A --scan` / `mdadm -I <image_file>`
- Built-in test harnesses and regression scripts under the repository `tests/` directory (e.g., `./test --keep-going`).
- Custom libFuzzer/AFL harness targeting metadata unpack functions (`load_super*()`, `examine_super*()`).

## How you rate severity
`mdadm` runs as root; memory safety issues in parsing code can lead to direct privilege escalation or arbitrary code execution in the context of root/udev workers.
- **Critical:** Controllable heap/stack buffer overflows, arbitrary memory writes, or remote/local code execution triggers when parsing raw disk superblocks/metadata without requiring explicit administrative invocation (e.g., triggered via udev auto-assembly upon hotplugging a device).
- **High:** Memory corruption (out-of-bounds reads/writes, double-free, use-after-free) in offline examination commands (`--examine`, `--detail`) requiring explicit invocation on an untrusted disk image.
- **Medium:** Unchecked integer overflows, uncontrolled memory leaks causing daemon crashes (`mdmon`), or NULL pointer dereferences leading to denial of service during automatic assembly.
- **Low:** Information leaks or minor denial-of-service crashes in non-automated CLI actions.

## Anything to leave alone
- Crashes or undefined behavior caused by invalid inputs passed to direct root-only destructive administrative commands (e.g., invalid flags passed during manual `--create` operations where the user already has full root execution capability).
- Vulnerabilities that require prior arbitrary write access to `/etc/mdadm.conf` or `/etc/default/mdadm` (if an attacker has root write permissions to `/etc`, local privilege escalation is already achieved).
- Bugs inside third-party vendor utilities or non-default external build targets unless directly linked into the core `mdadm` or `mdmon` binaries.
