# Threat model — Password Safe

Password Safe (https://pwsafe.org) is a C++ password manager that stores
credentials in an encrypted database file. It is used on Windows (MFC UI),
Linux and macOS (wxWidgets UI), and has a CLI (`pwsafe-cli`). All platforms
share the same `src/core` library for cryptography, key derivation, and
file-format handling.

## What the project does and where untrusted input enters

Password Safe reads and writes password database files in two formats:

- **V3 (.psafe3)**: Twofish in CBC mode with a 256-bit key derived from the
  master password via SHA-256 iterated hashing (stretching). An HMAC-SHA-256
  authenticates the entire payload.
- **V4 (.psafe4)**: AES-256 with a different key-derivation
  mechanism; adds attachment (blob) records.

Untrusted data enters through:

1. **The database file** — the primary attack surface. A malicious or corrupted
   `.psafe3` / `.psafe4` file supplied to an unsuspecting user is the most
   realistic threat. Every byte of the decrypted payload is therefore
   untrusted: record headers, field lengths, field types, and field values.
2. **XML import** (`File → Import → XML`) — the application reads an XML file
   through XercesC. A malicious XML file is fully in scope.
3. **CSV / plaintext import** — similar to XML but simpler.
4. **The master password itself** — attacker-chosen passwords are not
   exploitable by definition, but the key-derivation path (SHA-256 stretching)
   must be timing-safe.
5. **The command-line interface** (`src/ui/cli`) — command-line arguments and
   the database path; mostly trusted in practice but in scope for the scanner.

## Components that matter most

**Critical:** `src/core` — everything here handles secret data.

- `src/core/crypto/` — AES, Twofish, SHA-1, SHA-256, HMAC-SHA-1/256, key
  wrapping (`KeyWrap`), TOTP, Blowfish. Any memory-safety bug or timing leak in
  these is high or critical.
- `src/core/PWSfileV3.cpp`, `PWSfileV4.cpp` — parse the encrypted database
  record-by-record after decryption. Field-length integers come from untrusted
  data; integer overflows, OOB reads/writes, and use-after-free here matter.
- `src/core/PWScore.cpp` — the central in-memory database; manages item
  lifetimes and handles import/export logic.
- `src/core/XML/` — the XercesC XML parser wrapper used during import. Attacker
  controls the entire document.
- `src/core/PWSprefs.cpp` — preferences are stored and loaded from disk (untrusted); some
  are also stored in the database and therefore come from untrusted input.

**In scope but lower priority:**

- `src/ui/wxWidgets/` and `src/ui/cli/` — UI and CLI code. These are typically
  trusted-input paths (the local user drives them), but issues that allow
  privilege escalation or that expose the in-memory key are still wanted.
- `src/os/` — OS abstraction layer (clipboard, file I/O, PRNG wrapper).

**Out of scope:**

- `src/ui/Windows/` (MFC UI) — not built in this image; Windows-only.
- `Misc/`, `install/`, `help/` — non-code assets.
- `src/test/` — test code is trusted.

## How to exercise the project

The image is a single build tree at `/src/build`. Key binaries:

- **`/src/build/src/test/coretest`** — GoogleTest binary covering AES, Twofish,
  SHA-1/256, HMAC-SHA-1/256, key wrap, file V3/V4 parsers, item data model,
  XML import, TOTP, and command handling. Run from any directory:
  `cd /src && ./build/src/test/coretest` or with a filter:
  `./build/src/test/coretest --gtest_filter=FileV3*`.
- **`/src/build/src/ui/cli/pwsafe-cli`** — the command-line interface;
  `pwsafe-cli --help` lists options. Useful for feeding crafted database files:
  `pwsafe-cli --passphrase 'correct horse' --read-passwd some_entry /tmp/test.psafe3`.
- **`/src/build/src/ui/wxWidgets/pwsafe`** — the GUI binary; it can open a
  database file from the command line. Requires a display (set `DISPLAY` or use
  `xvfb-run`).

Test data (sample `.psafe3` files) are in `src/test/data/`.

The XML schema for import is `xml/pwsafe.xsd`; the binary checks conformance on
import.

## How to rate severity

Password Safe protects high-value secrets (master passwords, stored credentials)
for a potentially large number of end users. We rate based on real-world
exploitability of the database file as the primary attack vector.

**Critical:**

- An attacker can recover the master password or plaintext credentials from a
  database file without knowing the master password (authentication bypass,
  decryption oracle, key-derivation weakness with practical exploitation).
- Remote code execution achievable by opening a crafted database file or
  importing a crafted XML/CSV file (e.g., a heap overflow in the parser that
  gives control of the instruction pointer).

**High:**

- Memory corruption (heap overflow, OOB write, use-after-free) triggered by
  parsing a crafted database or import file, even without a demonstrated exploit
  chain; the severity reflects the potential for RCE.
- Timing side channel in the master-password check, key derivation, or HMAC
  verification sufficient to mount a practical offline attack on the master
  password.
- An HMAC or integrity check that can be bypassed, allowing a silent modification
  of the stored credentials.
- Sensitive memory (plaintext passwords, session keys) leaked into a log, error
  message, or any externally observable channel.

**Medium:**

- OOB read or information disclosure that reveals portions of the decrypted
  database or in-memory keys but does not by itself allow credential recovery.
- Denial of service: a crafted database file causes an infinite loop, excessive
  memory allocation, or a crash with no apparent code-execution path.
- Integer overflow or underflow in a length field that does not directly enable
  memory corruption but causes incorrect behaviour (e.g., silent truncation of a
  stored password).
- Failure to zeroize a key or password buffer that was documented to be
  zeroed, if plaintext remains in memory after it should have been erased.

**Low:**

- Minor information disclosure not directly tied to credentials (e.g., leaking
  metadata about entry count).
- Numeric edge-case bugs in non-security-critical paths that only produce wrong
  output.
- Weak PRNG usage in non-secret contexts (e.g., UI randomness), not affecting
  key generation.

## Things to leave alone

- The MFC Windows UI (`src/ui/Windows/`) is not built here.
- Deprecated algorithm support (SHA-1 for old V3 databases) is kept for
  compatibility; its cryptographic weakness is known and documented.
- Memory-safety bugs in third-party code pulled in as system libraries
  (wxWidgets, XercesC, OpenSSL). Our wrappers around them are in scope.
- The XercesC XML parser itself is a system library and out of scope; how
  Password Safe drives it is in scope.
- Qt / Android / iOS UI variants not present in this repo.
