# Threat model

## What this project does and where untrusted input enters
lchash is a small C PHP extension that provides a string-keyed hash table backed by a vendored, header-only klib khash (`khash.h`). It has a procedural API with one table per request (`lchash_create()`, `lchash_insert()`, `lchash_find()`, `lchash_destroy()`) and an `LcHash` class with `$obj[$key]` dimension access (read, write, isset/empty, unset) for any number of tables. It has no network, file, or deserialization input.

Untrusted input is the key and value bytes, and their lengths, that an application forwards from its users: binary strings with embedded NULs, empty keys, very long keys, colliding keys, and non-string offsets (ints, floats, null, objects) used as `$obj[$key]`. A table size (`n_entries`) forwarded from user input is also in scope. The order and choice of API calls is written by the application author.

## Components that matter most / least
- Most: `lchash.c`, including the object handlers (`lchash_read_dimension`, `lchash_write_dimension`, `lchash_has_dimension`, `lchash_unset_dimension`), capacity enforcement, refcounting of stored `zend_string` keys and values, and teardown in `lchash_destroy()`, request shutdown, and object free.
- `khash.h` is vendored but compiled into the extension; bugs in it count when reached through the PHP API.
- Least: `bench/`.

## How to exercise it
- The extension is built at `/src/modules/lchash.so` and installed into PHP's extension dir: `php -d extension=lchash -r '...'`.
- Suite: `cd /src && php run-tests.php --show-diff tests/` (the image exports `TEST_PHP_ARGS` to load the module).

## How you rate severity
- Memory-safety bug (overflow, use-after-free, double free) reachable through ordinary API use with attacker-chosen keys, values, or sizes: high. Critical with an attacker-controlled write.
- Out-of-bounds read or information leak (stale or foreign memory returned as a value): medium to high.
- Crash on unusual but valid input (binary keys, offset types, capacity limits): medium.
- Resource exhaustion (huge allocations from `n_entries`, hash-flooding with colliding keys): low to medium.
- Bugs that need attacker-controlled PHP code or ini settings, for example an unusual call sequence an application would not write, reflection, or `dl()`: out of scope or low.

## Anything to leave alone
- The procedural API keeping the first value on duplicate insert, and `LcHash` overwriting, are documented behaviour.
- Performance compared with PHP arrays is documented in the README and is not a finding.
