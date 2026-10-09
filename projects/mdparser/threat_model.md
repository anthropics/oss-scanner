# Threat model

## What this project does and where untrusted input enters
- mdparser is a PHP extension (C) that parses CommonMark + GFM Markdown and renders it to HTML, XML, or a PHP array AST. The parser is a vendored, locally patched md4c; the renderers are mdparser's own.
- Untrusted input is the `string $source` argument of `MdParser\Parser::toHtml()`, `toInlineHtml()`, `toXml()`, `toAst()` and the static `Parser::html()`, `xml()`, `ast()`. Assume every byte of it is attacker-controlled (arbitrary length up to the 256 MiB `MDPARSER_MAX_INPUT_SIZE` cap, invalid UTF-8, NUL bytes, pathological nesting).
- `MdParser\Options` (constructor arguments and the `strict()`/`github()`/`permissive()` presets) is chosen by the application, not the attacker. Every option combination is in scope for memory safety; the attacker controls only the Markdown.
- Default `toHtml()` output (`unsafe: false`) is meant to be safe to embed in a page: raw HTML is escaped, dangerous URL schemes are dropped, and GFM `tagfilter` is on. See `docs/security.md`.

## Components that matter most / least
- Most: `mdparser_md4c_html.c` (renderer, URL scheme filter, escaping, heading anchors, nofollow, smart punctuation), `mdparser_md4c_ast.c`, `mdparser_md4c_xml.c`, `mdparser_md4c_util.c`, `mdparser_md4c_slug.c`, `mdparser_md4c_vendor.c` (Zend-bailout guard and per-parse allocation registry around md4c), `mdparser_parser.c`, `mdparser_options.c`.
- Vendored: `vendor/md4c/md4c.c` and `vendor/md4c/entity.c` are compiled into the extension, with the local patches listed in `vendor/VENDOR.md`. Bugs in them are in scope only when reachable through the extension's PHP API with some `Options` combination. `vendor/md4c/md4c-html.c` is not compiled; ignore it.
- Out of scope: `bench/`, `examples/`, `scripts/`, `tests/oom/` harness code, and Windows build files.

## How to exercise it
- Built module: `/src/modules/mdparser.so`. Run code with `php -d extension=/src/modules/mdparser.so -r '...'`, for example `php -d extension=/src/modules/mdparser.so -r 'echo (new MdParser\Parser)->toHtml("# hi");'`.
- phpt suite: `cd /src && TEST_PHP_ARGS="-d extension=/src/modules/mdparser.so" NO_INTERACTION=1 php run-tests.php -q tests/` (the image sets these variables already). `077` skips unless `ASAN_OPTIONS` is set; `tests/fixtures/` and `tests/parity/` hold larger Markdown corpora.
- The PHP binary is the stock Debian build, not sanitizer-instrumented. Valgrind with `USE_ZEND_ALLOC=0` works against it.

## How you rate severity
- Out-of-bounds write, use-after-free, or double free reachable from Markdown input: high; critical if the attacker controls the written data or location.
- Out-of-bounds read or uninitialized memory disclosed in output: medium to high, depending on how much and what can leak.
- XSS in `toHtml()`/`toInlineHtml()` output with `unsafe: false`, or with `unsafe: true, tagfilter: true` for the tags the filter covers (URL scheme filter bypass, raw HTML escaping bypass, attribute breakout): high.
- Crash, NULL dereference, failed assertion, or Zend bailout that leaves state corrupt on malformed input: medium.
- Resource exhaustion (super-linear CPU or memory in input size, stack exhaustion below the 1000-level AST depth cap): low to medium.
- Bugs that need attacker-controlled PHP code, attacker-chosen `Options`, or ini settings: out of scope or low.

## Anything to leave alone
- `unsafe: true` with `tagfilter: false` passes raw HTML through by design.
- `toAst()` and `toXml()` are structural views and do not sanitize URLs or raw HTML (`docs/security.md`, "Not in scope"); unsanitized content there is not a finding.
- Attribute-level HTML sanitizing, CSP, and Unicode homograph detection are documented non-goals.
