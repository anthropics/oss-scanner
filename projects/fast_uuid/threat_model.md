# Threat model

## What this project does and where untrusted input enters
fast_uuid is a C PHP extension that generates, parses, formats, and converts UUIDs (versions 1 to 8, nil and max). It has a procedural API (`uuid_v4()`, `uuid_v7()`, `uuid_to_bin()`, `uuid_is_valid()`, batch generators, and more), a `FastUuid\Uuid` class API, and a PHP compatibility layer in `compat/` that mirrors ramsey/uuid on top of the class API. Untrusted input enters as:

- **Strings parsed as UUIDs**: `fromString()`, `isValid()`, `uuid_is_valid()`, `uuid_to_bin()`, `fromHexadecimal()`, `fromInteger()` (decimal 128-bit), the namespace argument of v3/v5, and `__unserialize()`/`__set_state()` data. The parsers accept a tolerant set of forms (braces, `urn:uuid:` prefix, case, hyphenation), so they must reject anything else without reading past the input.
- **Bytes**: `fromBytes()`, `uuid_from_bin()`, `uuid8()`/`uuid_v8()` input, and v3/v5 names up to 16 MiB.
- **Numbers**: timestamps for `uuid_v7_at()`, `uuid7()`, and `fromDateTime()`, node and clock-sequence values for v1/v2/v6, and batch counts.
- **Generator output** is the other security property: v4 output, and the random parts of v7, must be unpredictable to anyone who sees other output.

## Components that matter most / least
- Most: `fast_uuid.c`: parsers and validators; formatters including the SSSE3 (x86) and NEON (AArch64) hex paths and their scalar fallbacks; the 128-bit decimal conversions; the randomness code: a per-thread buffer refilled by AES-256-CTR with fast key erasure when hardware AES is present (FIPS-197 known-answer test at startup), otherwise by `php_random_bytes`, with reseeding every `FU_DRBG_RESEED_BYTES` and a `pthread_atfork` child handler; and the v7 monotonic counter.
- `compat/` is PHP userland code; logic bugs there are in scope at lower severity than memory-safety bugs in C.
- Least: `bench/`, `docs/`, Windows and macOS build glue.

## How to exercise it
- The extension is built at `/src/modules/fast_uuid.so` and installed into PHP's extension dir: `php -d extension=fast_uuid -r 'var_dump(FastUuid\Uuid::fromString("{0190A1B2-C3D4-7E5F-8A9B-0C1D2E3F4A5B}"));'`. `php -d extension=fast_uuid --ri fast_uuid` reports which formatter and RNG backend are active.
- Suite: `cd /src && php run-tests.php --show-diff tests/` (the image exports `TEST_PHP_ARGS` to load the module). CI also builds with `CFLAGS=-DFU_DISABLE_SSSE3` to test the scalar formatter; rebuild with that flag (or `-DFU_DISABLE_AES`) to reach the fallback paths.

## How you rate severity
- Memory-safety bug (overflow, use-after-free, out-of-bounds write) reachable from a parsed string, bytes, or numeric argument: high. Critical with an attacker-controlled write.
- Out-of-bounds read or information leak (including leaking generator state or buffer contents): medium to high.
- Predictable, repeated, or weak randomness in `uuid_v4()`, `uuid4()`, the default generators, or the random bits of v7 (state not reseeded after `fork()`, key or counter reuse, buffer served twice, a broken AES path used after a failed self-test, an RNG failure that returns zeros instead of throwing): high.
- A validator that accepts a string the parser then misreads, or a round trip (string to bytes to string) that changes the UUID: medium.
- Crash on malformed input: medium.
- Resource exhaustion (huge batch counts, 16 MiB names): low to medium.
- Anything that needs attacker-controlled PHP code or ini settings: out of scope or low.

## Anything to leave alone
- `uuid_v4_fast()` and `uuid_v4_fast_bin()` use a non-cryptographic xoshiro256** PRNG and are documented as unsuitable for security-sensitive identifiers.
- The limits `SECURITY.md` documents: reading process memory recovers up to the current buffer and, with hardware AES, output until the next 64 KiB reseed; clones restored from one VM snapshot can repeat up to 64 KiB of output per thread before the next reseed.
- The `compat/` validator being stricter than `FastUuid\Uuid::isValid()` is documented.
