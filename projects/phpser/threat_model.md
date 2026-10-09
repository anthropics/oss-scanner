# Threat model

## What this project does and where untrusted input enters
- phpser is a PHP extension (C) implementing a compact binary serializer for PHP values, an alternative to `serialize()`/`unserialize()`. It also provides HMAC-SHA256-signed framing and a `session.serialize_handler = phpser` session handler. There is no vendored third-party code; SHA-256 and HMAC are implemented in-tree.
- Untrusted input is the `$str` argument of `phpser_unserialize()` when the caller passes `allowed_classes` (`false` or an allowlist), and the `$payload` argument of `phpser_unserialize_signed()` for an attacker who does not hold the key. Assume every byte is attacker-controlled: arbitrary tags, lengths, counts, back-references, truncation.
- Memory safety of the decoder is in scope for any wire input regardless of `allowed_classes`, because a crash or corruption is not part of the "trust the source" contract.
- `phpser_serialize()` / `phpser_serialize_signed()` take PHP values. The value graph (references, cycles, shared arrays, objects with `__serialize`/`__sleep`/`Serializable`, enums, lazy objects, property hooks) is in scope when an application can be made to encode it.
- Session data reaches the decoder through the session handler, which uses the unsigned, all-classes-allowed path; it trusts the session store (`SECURITY.md`).

## Components that matter most / least
- Most: `phpser.c` (encoder and decoder: tag parsing, length and count validation, nesting cap, reference and shared-array tables, hash-collision work budget, packed/affine integer runs, object slot mapping, `allowed_classes` enforcement), `phpser_hmac.c` (signed framing, constant-time compare, per-thread key cache), `phpser_sha256.c` (portable and ARMv8/x86 SHA paths), `phpser_session.c`, `phpser_module.c`.
- Out of scope: `bench.php`, `ab.php`, `docs/`, Windows build files.

## How to exercise it
- Built module: `/src/modules/phpser.so`. Run code with `php -d extension=/src/modules/phpser.so -r '...'`, for example `php -d extension=/src/modules/phpser.so -r 'var_dump(phpser_unserialize(phpser_serialize([1, "a" => new stdClass]), ["allowed_classes" => false]));'`.
- Generate valid wire bytes with `phpser_serialize()` and mutate them to reach decoder edge cases; `phpser_serialize_signed()` with a known key produces signed frames, and the signed decoder applies the same structural checks.
- phpt suite: `cd /src && php run-tests.php -q tests/` (the image sets `TEST_PHP_ARGS="-d extension=/src/modules/phpser.so"` and `NO_INTERACTION=1`). Session tests need ext/session, which the Debian PHP loads.
- The PHP binary is the stock Debian build, not sanitizer-instrumented. Valgrind is installed; run with `USE_ZEND_ALLOC=0` so heap errors are visible to it.

## How you rate severity
- Out-of-bounds write, use-after-free, or double free reachable from a crafted payload: high; critical if the attacker controls the written data or location. Dangling pointers or wrong refcounts from reference or cycle handling count here.
- `phpser_unserialize_signed()` accepting a payload without the correct key (HMAC bypass, truncation or length-confusion in the frame): critical.
- `allowed_classes` bypass, meaning a class outside the allowlist instantiated as itself rather than as `__PHP_Incomplete_Class`: high.
- Out-of-bounds read or uninitialized memory disclosed in the decoded value: medium to high, depending on how much and what can leak. A timing leak in HMAC verification beyond whether the key matches the cached one: medium.
- Crash, NULL dereference, or failed assertion on malformed input: medium.
- Bypass of the 512 nesting cap, the hash-collision work budget, or the one-million-element packed budget, or other super-linear CPU or memory from a bounded payload: low to medium.
- Bugs that need attacker-controlled PHP code, the HMAC key, or ini settings: out of scope or low.

## Anything to leave alone
- Decoding attacker bytes with no `allowed_classes` restriction is the documented "trust the source" mode; magic-method side effects (`__wakeup`, `__unserialize`, `__destruct`) in that mode, or in allowlisted classes, are not findings.
- The session handler trusting its store is the standard PHP session model.
- The deliberate divergences from native `unserialize()` listed in `SECURITY.md` (enums filtered by `allowed_classes`, `null` on decode failure, shared arrays captured at first visit, positional object slots dropped for unloaded disallowed classes) are intended.
- Exponential logical size of a decoded DAG (shared arrays, references) is documented; work done by userland code that walks it without identity tracking is out of scope.
- Payloads larger than available memory.
