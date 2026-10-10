# Aimeos Sanitizer

## Security contract

This PHP library sanitizes untrusted UTF-8 HTML fragments. `Sane::strict()` uses
a fixed allow-list for untrusted rich text. `Sane::html($input, $allow)` is a
broader compatibility profile that removes known dangerous content and supports
explicit exceptions for trusted content. Review both profiles, their shared
policy and resource limits, and both parser backends.

PHP 8.4+ uses the native HTML5 DOM API; older runtimes use Masterminds HTML5.
The PHP 8.5 image can exercise both backends directly through the shared security
corpus, but it does not replace testing on the complete supported PHP matrix.

Prioritize executable content surviving sanitization, mutation XSS on browser
reparsing, malformed-markup and namespace differentials, URL scheme or trusted
prefix bypasses, unsafe embedding attributes, and practical CPU or memory
exhaustion. Include repeated sanitization and both document and fragment parsing
where relevant. Examine pre-parse limits as well as post-parse tree traversal.

## Intended behavior and limitations

Sanitized output is an HTML fragment for an HTML content context in a UTF-8
document. It is not escaped for JavaScript, CSS, attributes or other contexts.
Reinterpreting retained text or attributes as HTML downstream is outside that
contract. Invalid UTF-8, ambiguous markup and over-budget input may return an
empty string intentionally.

Strict mode removes IDs, names, classes, data attributes, foreign content and
other capabilities specified in `Policy`. The compatibility profile intentionally
retains more content; do not apply the strict allow-list to it when reporting
findings. Broad exceptions such as `['script' => true]` are explicitly trusted
capabilities. Demonstrate a bypass of the actual selected policy, including the
documented restrictions that still apply when an exception is enabled.

URL-prefix checks do not fetch redirects or inspect remote resource contents.
Raster data-image checks validate declared MIME types, not decoded image bytes.
These documented limits alone are not sanitizer bypasses.

## Exercising the project offline

Source and Composer development dependencies are in `/src`. PHP 8.5 includes
native HTML5 DOM support, and Masterminds HTML5 and Chromium are installed during
the online build. No database or external service is needed.

```sh
vendor/bin/phpunit
vendor/bin/phpstan analyze --no-progress --debug
scanner-browser
timeout 30s php -d memory_limit=64M tests/benchmark.php
```

`scanner-browser` generates the repository's `tests/browser.php` harness and runs
it in headless Chromium, then requires its JSON result to report `passed: true`.
The harness includes document and `innerHTML` reparsing, sandboxed execution,
positive controls and image checks. Its CSP blocks external resources. Chromium
runs without its process sandbox inside the scanner's isolated environment.
This is Chromium coverage, not proof of behavior in every browser engine.

The build runs PHPUnit, PHPStan and browser checks but retains the image if a
check fails. Inspect their output and rerun relevant checks when investigating.
The optional benchmark has a separate timeout; timing depends on the machine
and is not a substitute for the functional resource-limit tests.

## Reports

Provide the exact input bytes, public API call, profile and exceptions, PHP and
parser versions, output, and browser insertion context. For XSS, demonstrate
execution with a harmless marker and include a positive control. For resource
exhaustion, include input size, memory, runtime and a baseline comparison.
Rate severity by demonstrated reachability and impact, and propose a focused
regression test across both backends where possible. Preserve compatibility
with the library's supported PHP versions in proposed patches.
