# Threat model

## What SpiderMonkey is and where untrusted input enters

SpiderMonkey is Firefox's JavaScript and WebAssembly engine. In Firefox it runs
untrusted JavaScript and WebAssembly code.

The build in this image is the JS shell, at `/obj-asan/dist/bin/js`.

**Only report issues that reproduce with `--fuzzing-safe`.** Anything that needs a
testing function or behavior that `--fuzzing-safe` disables is *not a bug*, at any
severity. Other shell flags (for example `--ion-eager`, `--no-threads`) are fine
to use, but always list them.

## Components that matter most

Most important:

* the JS JITs and Wasm compilers: `js/src/jit` and `js/src/wasm`;
* the GC (`js/src/gc`);
* the runtime and built-ins under `js/src/vm`, `js/src/builtin`, `js/src/frontend`, `js/src/irregexp`.

Out of scope:

* any assertion failures or crashes that do not reproduce with `--fuzzing-safe`;
* correctness bugs, such as incorrect output, with no security impact;
* the `Debugger` API: web content can't reach it;
* the shell itself (`js/src/shell`), the test harnesses, and tests or testing functions;
* vendored third-party code (ICU, and other code under `intl/` and `third_party/`),
  unless reachable from script with attacker-controlled input;
* code disabled at compile time or not available in this JS shell build (includes
  JIT backends for other architectures);
* everything in this checkout outside `js/src`. `mfbt/` and the Rust crates the engine
  uses are in scope only when reached through the engine.

## How to exercise it

* Shell: `/obj-asan/dist/bin/js --fuzzing-safe test.js`. It's a debug build with
  optimization and AddressSanitizer, with the mozconfig at `/mozconfig-asan`.
  Rebuild after a change with `./mach build`.
* Debug-only `MOZ_ASSERT`s are on in this build.

## How we rate severity

We use https://wiki.mozilla.org/Security_Severity_Ratings/Client.

Critical or high:

* memory corruption reachable from script: out-of-bounds read or write,
  use-after-free, type confusion;
* a `MOZ_ASSERT` failure whose condition guards memory safety (rate it by what
  happens in a release build, where the assertion is not compiled in).

Low:

* clean crashes that cannot be exploited: `nullptr` dereference,
  unconditional safe crashes (`MOZ_RELEASE_ASSERT` or `MOZ_CRASH`);
* `MOZ_ASSERT` failures without a memory-safety consequence in release builds;
* correctness bugs (wrong results) that have no path to memory corruption.

## Anything to leave alone

* minor correctness or spec edge cases (incorrect output) that aren't security relevant;
* timeouts and stack overflows ("too much recursion").

## How we would like reports and patches to look

* A reduced `.js` file (possibly with an inline Wasm module), the exact
  shell flags (must always include `--fuzzing-safe`), the commit it was tested
  against, and the ASan or assertion output.
* Ideally written as a jit-test test case for `js/src/jit-test/tests/`
  (with a `// |jit-test| ...` header for the flags).
* Minimal patches against `main` of https://github.com/mozilla-firefox/firefox.
