# Diesel threat model

## Purpose and trust boundaries

Diesel is a SQL query-builder and ORM written in Rust. It generates SQL from a Rust DSL that is checked at compile time for correctness. It also features a layer 

The following crates are in scope for any review:

- `diesel_derives`
- `diesel`
- `diesel_migrations`
- `diesel_migrations/migrations_internals`
- `diesel_mgirations/migrations_macros`
- `diesel_table_macro_syntax`
- `diesel_attribute_parser`
- `diesel_dynamic_schema`
- `diesel_cli`
- `diesel_infer_query` (part of `diesel-cli`)

Any test and example code is out of scope. Command line parameters passed to `diesel-cli` are considered to be trusted.

Diesel generally assumes that the schema of the connected database is trusted, unless otherwise stated. This specifically applies to the schema generation code in `diesel_cli`.

The following classes of vulnerabilities are considered in scope:

- Any sort of unsound unsafe code
- Any sort of code injection, unless caused by connecting to a trusted schema
- Prepared statement caching issues
- Unexpected performance issues
- Undocumented panics
- Invalid SQL constructed via typed DSL

## Build and offline tests

The image contains the full checkout at `/src`, a Rust toolchain including clippy, nextest and miri. The Cargo.lock file is pregenerated at image build time to include all necessary dependencies into the image. Database setups for PostgreSQL, MySQL, MariaDB and SQLite are already preconfigured.

The following commands can be used to run tests:

```sh
cargo xtask run-tests # runs all tests for all backends

cargo xtask run-tests postgres # run tests for postgresql
cargo xtask run-tests mysql # run tests for mysql
cargo xtask run-tests sqlite # run tests for sqlite
cargo xtask run-tests mariadb # run tests for mariadb

cargo xtask run-tests $backend -- $test-name # run only the specific test for the specified backend
cargo xtask run-tests $backend -F serde_json # run tests with a specific feature enabled

cargo xtask clippy # run clippy

# See `cargo xtask run-tests --help` and `cargo xtask clippy --help` for more configurations

# Run Compile test (to verify invalid SQL is rejected at compile time)
cargo test --manifest-path diesel_compile_tests/Cargo.toml

# Run fuzzing setup (see `fuzz/Cargo.toml` for a list of all targets)
cargo +nightly fuzz run --fuzz-dir fuzz pg_array

# Run tests with sanitizers enabled:
RUSTFLAGS="-Zsanitizer=address" cargo +nightly -Z build-std test -p diesel_tests --features "sqlite libsqlite3-sys libsqlite3-sys/bundled libsqlite3-sys/with-asan" --target x86_64-unknown-linux-gnu
RUSTFLAGS="-Zsanitizer=address" cargo +nightly -Z build-std test -p diesel --no-default-features --features "sqlite __with_asan_tests" --target x86_64-unknown-linux-gnu
RUSTFLAGS="-Zsanitizer=address" cargo +nightly -Z build-std test -p diesel_tests --features "postgres pq-sys pq-sys/bundled pq-src/with-asan" --target x86_64-unknown-linux-gnu
RUSTFLAGS="-Zsanitizer=address" cargo +nightly -Z build-std test -p diesel --no-default-features --features "postgres __with_asan_tests" --target x86_64-unknown-linux-gnu
RUSTFLAGS="-Zsanitizer=address" cargo +nightly -Z build-std test -p diesel --features "mysql _with_asan_tests"
RUSTFLAGS="-Zsanitizer=address" cargo +nightly -Z build-std test -p diesel_tests --features "mysql mysqlclient-sys mysqlclient-sys/bundled mysqlclient-src/with-asan" --target x86_64-unknown-linux-gnu

```

Diesel supports the following targets:

Operating systems:

- Linux
- Windows
- MacOS
- WASM (for the SQLite backend only)

CPU Architectures:

- x86_64
- aarch64

Any other platform might work but is not tested in the CI setup

## Assessing and reporting findings

For each finding include the exact version, feature flags and a reproducing test-case. Seek to write small regression reproduction cases. Verify that the test actually fails.

