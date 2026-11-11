# Threat model

## What this project does and where untrusted input enters
- ext-php-rs is a Rust library for writing PHP extensions. It wraps the Zend C API (zvals, strings, hash tables, objects, classes, exceptions, SAPI) in safe Rust types, and `crates/macros` generates the `extern "C"` glue for `#[php_function]`, `#[php_class]`, `#[php_impl]`, `#[php_enum]`, `#[php_interface]` and `#[php_module]`.
- The promise is: an extension author who writes only safe Rust cannot cause undefined behavior, whatever the PHP script does. The goal of this scan is to find places where that promise breaks.
- Untrusted input is the PHP script that calls the extension. It controls every argument value and type (scalars, strings with any bytes, arrays with any keys and nesting, references, objects of any class, closures, iterators, generators), the call order, re-entry through callbacks, exceptions thrown from callbacks, `clone`, `unset`, `serialize`, `var_dump`, `(array)` casts, `gc_collect_cycles()` and object destruction at any time.
- Trusted: the extension author's code and their `unsafe` blocks, the PHP engine, the build environment, and the `php.ini` configuration.

## Components that matter most / least
- Most: `src/types/` (Zval, ZendStr, ZendHashTable, ZendObject, ZendClassObject, callables, iterators, references), `src/args.rs` and `src/convert.rs` (argument parsing and FromZval / IntoZval), `src/boxed.rs` and `src/rc.rs` (refcounts and ownership), `src/zend/handlers.rs` (object handlers, property table, `get_gc`), `src/exception.rs`, `src/zend/try_catch.rs` and `src/zend/bailout_guard.rs` (exceptions, panics and `longjmp` bailouts), `src/closure.rs`, and the code that `crates/macros` generates.
- Medium: `src/builders/` and class, module, INI and constant registration; `src/embed/` and the SAPI wrappers (`src/zend/output.rs`, `src/zend/headers.rs`); the observer API (`src/zend/observer.rs`, `src/zend/*_observer.rs`).
- Out of scope: `crates/cli` (cargo-php, a developer tool), `crates/php-build`, `build.rs`, `unix_build.rs` and `windows_build.rs` (build time, trusted input), `crates/introspection` (stub rendering), `benches/`, `guide/`, and anything that needs the extension author to write `unsafe` code wrongly.

## How to exercise it
- PHP 8.5 debug build (`ZEND_DEBUG`, so engine assertions like `HT_ASSERT_RC1` fire) with the embed SAPI is installed in `/usr/local`. Sources are in `/opt/php-src`.
- All tests: `cargo test --workspace --features closure,embed,anyhow,smartstring,observer,indexmap --no-fail-fast`.
- `tests/src/integration/` is the main harness: each module is a Rust extension (built as the `tests` cdylib) plus `.php` scripts that the test runs with `php -d extension=...`. To try a new input, add a `#[php_function]` there, or write a script and run `php -d extension=target/debug/libtests.so script.php` after `cargo build -p tests`.
- `examples/hello_world.rs` is a small standalone extension: `cargo build --example hello_world`, then `php -d extension=target/debug/examples/libhello_world.so`.
- `tests/sapi*.rs` and the `embed` feature run PHP code in-process through `ext_php_rs::embed::Embed`.
- Memory errors are easiest to see with `USE_ZEND_ALLOC=0` and valgrind, or the debug PHP's assertions. `ZEND_DONT_UNLOAD_MODULES=1` keeps symbols for the extension in backtraces.

## How you rate severity
- Critical: memory corruption (use-after-free, double free, out-of-bounds write, type confusion) that a PHP script can trigger through an extension written in safe Rust, with a plausible path to code execution.
- High: any other undefined behavior reachable from a PHP script through safe Rust: out-of-bounds read, refcount underflow, dangling reference, invalid enum value, a Rust panic or a `longjmp` that unwinds across `extern "C"` without being caught, data race on ZTS PHP.
- Medium: a safe API that is unsound only with an unusual but legal call pattern from the extension author; memory leaks that a script can grow without bound; a crash (abort, assertion) with no memory corruption.
- Low: leaks bounded per request, wrong error messages, wrong `TypeError` versus `ValueError`, stub generation mistakes.
- Not a vulnerability: unsound behavior that needs `unsafe` in the extension author's code, issues only on unsupported PHP versions (below 8.1), issues in the PHP engine itself (report those to PHP).

## Anything to leave alone
- Do not report the `unsafe` functions in the public API as bugs by themselves. They are `unsafe` on purpose and document their contract. Report them only when the documented contract is not enough to make a call sound.
- Cycles through zvals held inside a Rust struct are not reported to the GC and leak. This is known.
- Windows-only code paths cannot be tested in this image.
