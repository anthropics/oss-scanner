# Threat model

## What this project does and where untrusted input enters
- statgrab is a PHP extension (`statgrab.c`, `php_statgrab.h`) that exposes libstatgrab's read-only host telemetry to PHP: CPU, memory, swap, load, disk I/O, filesystems, network interfaces, page faults, processes, and logged-in users, as `sg_*()` functions and the `Statgrab` class. The image builds it against the patched libstatgrab 0.92.1 vendored in `vendor/libstatgrab/`, statically linked.
- The attack surface is low. Inputs are mostly operating-system data, not data a remote attacker supplies. The realistic sources are:
  - `sg_set_valid_filesystems()` / `Statgrab::setValidFilesystems()`: the only caller-supplied data path (an array of filesystem-type strings converted into a native list). Embedded NULs, non-string elements, empty strings, and very large arrays are the cases to check.
  - Integer arguments that an application might take from a request: the `sg_process_stats()` sort mode and entry count, and the `sg_cpu_percent_usage()` source.
  - Data that other unprivileged local users control and that libstatgrab parses from `/proc`, `/sys`, utmp, and mount tables: process names and command lines (`proc_title`), login names, tty and host fields in utmp, mount points and device names, interface names, and disk names. A local user who can start processes or mount filesystems (for example via FUSE or a user namespace) can put arbitrary bytes and lengths there.
- The wrapper's bugs of interest are in copying libstatgrab structs and vectors into PHP arrays and objects: trusting counts, NULL string fields, duplicate keys, lifetime of library-owned vectors versus PHP values, sorting copies, the snapshot/diff state, and per-thread state under ZTS.

## Components that matter most / least
- Most: `statgrab.c` (all of it).
- Vendored `vendor/libstatgrab/src/libstatgrab/` is in scope only when a bug is reachable through the extension's PHP API on Linux, for example a parsing bug in `process_stats.c`, `user_stats.c`, `disk_stats.c`, or `network_stats.c` triggered by local-user-controlled process, utmp, mount, or interface data. Code for other platforms (`win32.c`, Solaris, BSD, HP-UX, AIX branches) and the `saidar` and `statgrab` command-line tools under `vendor/libstatgrab/src/` are out of scope.
- Out of scope: `tests/`, `package.xml`, `composer.json`, and the CI configure-prefix script.

## How to exercise it
- The module is at `/src/modules/statgrab.so` and installed, so `php -d extension=statgrab` loads it.
- `run-phpt` runs the PHPT suite; pass paths or `run-tests.php` flags to narrow it.
- Quick driver: `php -d extension=statgrab -r 'var_dump(sg_process_stats(0, 5), sg_user_stats(), sg_set_valid_filesystems(["ext4", "tmpfs"]));'`.
- To feed hostile process data, start a process with a crafted `argv`/`comm` (for example `exec -a "$(printf 'x%.0s' $(seq 5000))" sleep 60 &`) and call `sg_process_stats()`. For memory errors, run under valgrind with `USE_ZEND_ALLOC=0`.

## How you rate severity
- Critical: memory corruption with a controlled write reachable by an unprivileged local user through process, utmp, mount, or interface data, or by request data passed to `sg_set_valid_filesystems()`.
- High: any other out-of-bounds write, use-after-free, or double free reachable from those inputs.
- Medium to high: out-of-bounds read or information leak (heap bytes returned in a PHP string), or data the calling process could not otherwise read from the OS.
- Medium: crash or NULL dereference triggered by local-user-controlled system data or by `sg_set_valid_filesystems()` input.
- Low to medium: resource exhaustion, such as unbounded memory or time from a large process table.
- Low or out of scope: bugs that need attacker-controlled PHP code or INI settings, root-only conditions (a malicious kernel, root-written `/proc` or `/sys`), or a crafted host environment the attacker already owns.

## Anything to leave alone
- The telemetry values themselves are not leaks: process lists, logged-in users, and interface counters are what the extension exists to return.
- Behavior when linked against a system libstatgrab older than 0.92 is unsupported.
- Values that differ inside a container (missing disks, zero swap, no utmp entries) are environment artifacts, not bugs.
