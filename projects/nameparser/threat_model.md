# Threat model

## What this project does and where untrusted input enters
- `iliaal/nameparser` is a pure-PHP (8.3+, ext-mbstring) library that splits a full-name string into salutation, first, middle, initials, last name (with prefixes), suffix/credentials, and nickname. It has no I/O, network, filesystem, or shell access.
- Treat the string passed to `Parser::parse(string $name)` (`src/Parser.php`) as fully untrusted: it comes from web forms, CSV imports, and registries such as NPI, and can be any byte sequence, including invalid UTF-8, control characters, combining marks, and very long input.
- Outputs are the `Name` object (`src/Name.php`: getters, `getAll()`, `toArray()`, `__toString()`, `getSource()`, `getConfidence()`) and `Confidence::assess()` (`src/Confidence.php`). The library returns plain text and does no HTML, SQL, CSV, or shell escaping. Escaping output for its sink is the caller's job. A finding that only shows `<script>` or `'; DROP` surviving into a name part is not a bug.
- Trusted configuration: the constructor's language list and the `set*()` setters (`setWhitespace`, `setNicknameDelimiters`, `setMappers`, `setMaxSalutationIndex`, `setMaxCombinedInitials`, `setSurnameFirst`). The application sets these, not an end user.

## Components that matter most / least
- Most: tokenisation and normalisation in `src/Parser.php` (`normalize()`, `tokenizeWords()`, `splitStructuralCommas()`) and `src/StructuralCommaSplitter.php`; `src/Text.php` (input budgets, grapheme handling, the process-wide key caches); the mappers in `src/Mapper/` (especially `NicknameMapper` delimiter nesting, `SuffixMapper`, `SalutationMapper`, and `InitialMapper` combined-initial expansion); `src/CommaCredentialTail.php`; `src/Confidence.php`.
- Documented resource limits that findings should be measured against: `Text::MAX_INPUT_BYTES` (1 MiB) and `Text::MAX_INPUT_TOKENS` (65536), both raising `\LengthException`; `NicknameMapper::MAX_NESTING_DEPTH` (64); bounded static caches in `Text` (4096 short keys, 256 long keys up to 4096 bytes) and the per-parse token memo in `Parser` (1024 entries).
- Relevant bug classes:
  - ReDoS or catastrophic backtracking in any `preg_*` call reachable from `parse()` or `Confidence::assess()`, including with PCRE JIT disabled (`pcre.jit=0`).
  - CPU or memory that grows superlinearly in input size within the byte and token budgets, or a way around those budgets (for example, normalisation that expands input after the byte check).
  - Uncaught errors other than the documented `\LengthException`: `TypeError`, `ValueError`, warnings from `mb_*`/`preg_*` on malformed UTF-8, or a `null` from a failed `preg_replace` that is then used.
  - State bleed across `parse()` calls in a long-running worker (static caches in `Text`, memoised mappers), and output parts containing text absent from the input.
- Least: `src/Language/` dictionaries (data only), and dev tooling (`.php-cs-fixer.dist.php`, PHPStan config).

## How to exercise it
- `vendor/bin/phpunit` runs the whole suite offline (the image sets `memory_limit=256M`, as CI does). `tests/PerformanceTest.php` holds the linear-time and bounded-memory regression checks; `tests/RobustnessTest.php` covers malformed input.
- One-off driver: `php -r 'require "vendor/autoload.php"; var_dump((new Iliaal\NameParser\Parser())->parse($argv[1])->toArray());' -- "Dr. Jane Q. Doe-Smith, MD"`.
- `vendor/bin/phpstan analyse` is installed for static checks.

## How you rate severity
- High: data from one `parse()` call appearing in the result of a later call (shared static state), because it discloses one user's input to another in long-running workers.
- Medium: a single crafted input within the 1 MiB / 65536-token budget that causes ReDoS, catastrophic backtracking, a hang, superlinear CPU taking over 5 seconds, or unbounded memory in a default-configured `Parser`; a way around the input budgets; an uncaught error or fatal error other than `\LengthException`.
- Low: misparses with no security effect (wrong field assignment, casing errors). Report these only when they are systematic.
- Low or out of scope: anything that requires attacker control of `set*()` configuration or language dictionaries. Out of scope: output that is unsafe only because the caller didn't escape it for HTML, SQL, CSV, or shell.

## Anything to leave alone
- Don't report the `\LengthException` thrown for input over the byte or token limit; that is the intended behaviour.
- Don't report naming or casing choices for real names (for example, `Do` vs `DO`) unless they cause one of the bug classes above.
