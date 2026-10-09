# Threat model

## What this project does and where untrusted input enters
- fastjson is a PHP extension (C) that is a drop-in alternative to ext/json, backed by a vendored, statically compiled, locally patched yyjson 0.13.0. It encodes, decodes, validates, queries RFC 6901 JSON Pointers, sets values by pointer, and applies RFC 7396 merge patches.
- Untrusted input is any string argument that carries JSON or a pointer: `$json` in `fastjson_decode()`, `fastjson_validate()`, `fastjson_pointer_get()`, `fastjson_pointer_exists()`, `fastjson_pointer_set()`; `$pointer` in the pointer functions; `$target` and `$patch` in `fastjson_merge_patch()`; and the file contents read by `fastjson_file_decode()`. Assume every byte is attacker-controlled, including invalid UTF-8, NUL bytes, huge numbers, deep nesting, and truncated documents.
- `fastjson_encode()` / `fastjson_file_encode()` take PHP values. Treat array keys, string contents, and object property values as attacker-influenced (they typically come from decoded requests); the shape of the PHP value graph (references, cycles, objects with `JsonSerializable`, enums) is also in scope when an application can be made to encode it.
- `$flags`, `$depth`, `$associative`, and filenames are normally chosen by the application. Every flag combination (including `FASTJSON_DECODE_RELAXED` and the `JSON_*` flags fastjson honors) and every `$depth` value is in scope for memory safety.

## Components that matter most / least
- Most: `fastjson_decode.c`, `fastjson_directwrite.c` (encoder writing straight into a PHP string), `fastjson_pointer_splice.c` (pointer set and merge patch on raw JSON), `fastjson_encode.c`, `fastjson_alloc.c` (yyjson allocator bound to Zend MM), `fastjson.c` (entry points, argument handling, file I/O through PHP streams, error state).
- Vendored: `vendor/yyjson/yyjson.c` is compiled into the extension with the local patches in `vendor/yyjson/PATCHES.md` (validate-only reader, buffer writer API, control-character and UTF-8 handling, depth-stack bounds). Bugs in it are in scope only when reachable through fastjson's PHP API; yyjson features fastjson never calls are out of scope.
- Out of scope: `bench/`, `scripts/`, `tests/ilp32/validate_stack_growth.c` (a standalone 32-bit test harness), Windows build files.

## How to exercise it
- Built module: `/src/modules/fastjson.so`. Run code with `php -d extension=/src/modules/fastjson.so -r '...'`, for example `php -d extension=/src/modules/fastjson.so -r 'var_dump(fastjson_decode("[1,{\"a\":2}]", true));'`.
- phpt suite: `cd /src && php run-tests.php -q tests/ tests/upstream-json/` (the image sets `TEST_PHP_ARGS="-d extension=/src/modules/fastjson.so"` and `NO_INTERACTION=1`). `tests/upstream-json/` is php-src's ext/json suite retargeted at fastjson, useful as a differential oracle against ext/json (`json_decode`/`json_encode` are also available in the same PHP).
- The PHP binary is the stock Debian build, not sanitizer-instrumented. Valgrind is installed; run with `USE_ZEND_ALLOC=0` so heap errors are visible to it.

## How you rate severity
- Out-of-bounds write, use-after-free, or double free reachable from JSON, pointer, or patch input, or from encoding a PHP value an application would plausibly build from request data: high; critical if the attacker controls the written data or location.
- Out-of-bounds read or uninitialized memory disclosed in output: medium to high, depending on how much and what can leak.
- Crash, NULL dereference, failed assertion, or stack overflow below the configured `$depth` on malformed input: medium.
- Integer overflow or an allocation path that bypasses `memory_limit`: medium; escalate if it leads to memory corruption.
- Resource exhaustion (super-linear CPU in input size) within `memory_limit`: low to medium.
- `open_basedir` or stream-wrapper policy bypass in `fastjson_file_encode()` / `fastjson_file_decode()`: medium.
- Bugs that need attacker-controlled PHP code or ini settings: out of scope or low.

## Anything to leave alone
- `FASTJSON_DECODE_RELAXED` accepts comments, trailing commas, and a leading BOM by design.
- Decoding a huge document that fits within `memory_limit` is expected to use that memory.
- Output or error-code differences from ext/json that do not cross a memory-safety or DoS boundary are not security findings.
