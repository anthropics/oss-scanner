# Threat model: Turso Database

## What this project is

Turso is an in-process SQL database engine written in Rust, compatible with SQLite's SQL dialect, file
format and C API, with a Postgres frontend (dialect and wire protocol) built on the same core. It ships as:

- `core/`: the engine. SQL translation (`core/translate`), the bytecode VM (`core/vdbe`), the storage
  layer (`core/storage`: b-tree, pager, page cache, WAL, encryption, checksums, SQLite on-disk format in
  `sqlite3_ondisk.rs`), MVCC (`core/mvcc`), I/O backends (`core/io`: POSIX, io_uring, memory), built-in
  functions, JSON, vector and extension loading (`core/ext`, `core/native_ext`).
- `sqlite/parser`: the SQLite SQL parser. `postgres/parser`, `postgres/frontend`: the Postgres dialect.
- `cli/`: the `tursodb` shell. It can also run as an MCP server (`--mcp`) and as a sync server
  (`--sync-server <addr>`, `--sync-dir`), which listen on sockets.
- `postgres/server`: a Postgres wire-protocol server that exposes the engine over TCP.
- `sync/engine`, `sync/sdk-kit`: the client-side sync engine that replicates a local database with a
  remote (Turso Cloud); it parses data received from the network.
- `serverless/`: thin HTTP clients for Turso Cloud (`serverless/PROTOCOL.md`).
- `bindings/`: the language bindings. `bindings/c` (`turso_sqlite3`) is the SQLite-compatible C API;
  `bindings/rust` is the `turso` crate; Python, JavaScript and Java bindings sit on `sdk-kit`.
- `extensions/`: loadable extensions (regexp, csv, crypto, uuid, fuzzy, ipaddr, completion).

## Where untrusted input enters

Treat all of these as attacker-controlled unless noted:

1. **Database files, WAL files and journal files on disk.** Turso opens SQLite-format files that may come
   from anywhere (a download, another process, a different engine). A crafted file must not cause memory
   unsafety, out-of-bounds reads, unbounded allocation, infinite loops or a crash that the application
   cannot catch. This is the highest-value surface: `core/storage`, especially `sqlite3_ondisk.rs`,
   `btree.rs`, `wal.rs`, `pager.rs`, `page_cache.rs`, `encryption.rs`, `checksum.rs`, and the record /
   varint / overflow-page decoding they use.
2. **SQL text and bound parameters** from the application. The application is trusted to choose what SQL
   to run, but the engine must survive any SQL: parser, translator and VM bugs reachable from SQL (stack
   overflow on deep nesting, integer overflow in offsets and sizes, out-of-bounds register or cursor
   access, affinity/type confusion in `core/vdbe/value.rs`, bad arithmetic in built-in functions, JSON,
   vector and date/time functions) are in scope. SQL injection in the application's own code is not.
3. **Network protocols**: the Postgres wire protocol (`postgres/server`, `postgres/client`), the sync
   server and sync engine (`cli/sync_server.rs`, `sync/`), the MCP server (`cli/mcp_server.rs`), and
   the serverless clients. Anything parsed from a socket is untrusted: message framing, lengths, protocol
   state machines, authentication and authorization, and anything that lets one client read or write
   another client's or another database's data under `--sync-dir`.
4. **The C API and bindings** (`bindings/c`, `sdk-kit`, `sync/sdk-kit`). Callers are trusted, but the FFI
   layer must uphold the SQLite contract: no use-after-free or double free through handle misuse that
   SQLite itself tolerates, correct lifetimes for returned pointers, correct `sqlite3_bind_*` /
   `sqlite3_column_*` bounds behaviour.
5. **Extensions** loaded via `.load` / `sqlite3_load_extension` and virtual tables are trusted code once
   loaded; bugs in the engine's handling of what they return (`core/vtab.rs`, `core/ext`) are in scope.
6. **Environment and configuration**: PRAGMAs, connection URIs and encryption keys are chosen by the
   application. Report cases where a setting silently weakens a documented guarantee (for example an
   encryption or checksum mode that does not do what its name says).

## What matters most

In order of importance:

1. Memory safety and `unsafe` code in `core/` (storage, page cache, buffer pool, io_uring, SIMD, MVCC
   skiplist, `fast_lock`, allocator code under `core/alloc`), in the C API and in `sdk-kit`.
2. Durability and integrity: committed data that is lost, silently corrupted, or returned wrongly after a
   crash, checkpoint, WAL recovery, `BEGIN CONCURRENT` / MVCC commit, vacuum, or sync. A bug here is a
   security issue for us even when the input is well-formed.
3. Isolation: a transaction reading uncommitted or torn state, or two writers both believing they
   committed, especially under MVCC and the multi-process / shared-WAL paths.
4. Crafted-file and crafted-SQL robustness (panics, aborts, hangs, unbounded memory).
5. Network-facing components: authentication, authorization, resource exhaustion, protocol confusion.
6. Encryption at rest (`core/storage/encryption.rs`): key handling, nonce reuse, unauthenticated
   plaintext metadata, page-level oracles.

## Out of scope / lower value

- `testing/`, `perf/`, `fuzz/`, `tlaplus/`, `examples/`, `docs/`, `scripts/`, `tools/`, `sql_generation/`
  and anything under `*/conformance/upstream` (third-party test corpora). Bugs only reachable from test
  harnesses, benchmarks or the `fuzz` / `simulator` cargo features are not security issues.
- Documented SQLite incompatibilities listed in `COMPAT.md` and `postgres/COMPAT.md` are known
  differences, not bugs, unless they lead to memory unsafety or data loss.
- The `tursodb` interactive shell's local-only conveniences (dot commands, history, syntax highlighting).
- Dependencies: report a vulnerable dependency only if Turso reaches the vulnerable code.
- Timing side channels in anything other than encryption key handling.

## How we rate severity

- Memory corruption (out-of-bounds write, use-after-free, double free, type confusion) reachable from a
  database file, SQL, or a network protocol: **critical** if attacker-controlled data reaches the
  corrupted memory, otherwise **high**. A memory-unsafe path only reachable through a misused `unsafe`
  C API in a way SQLite also forbids: **medium**.
- Out-of-bounds read / info leak from a crafted file or protocol message: **high**.
- Authentication or authorization bypass, or cross-database / cross-client data access, in the Postgres
  server, sync server or sync engine: **critical**.
- Silent loss or corruption of committed data, or wrong query results on valid data due to a storage,
  WAL, MVCC or checkpoint bug: **high**; **critical** if it is easy to trigger in normal use.
- Isolation violations (dirty reads, lost updates) under supported settings: **high**.
- Panic, abort, infinite loop, stack overflow or unbounded memory growth from a crafted file or protocol
  message: **medium** (this is an in-process library: a panic takes down the host application). From
  SQL the application itself wrote: **low** unless the SQL is ordinary and short.
- Resource exhaustion in the network servers from an unauthenticated client: **medium**.
- Encryption weaknesses that allow plaintext recovery: **high** or **critical**; weaknesses that only
  leak structure (page counts, which pages changed): **low**.
- Anything that needs a loaded malicious extension or a malicious application binary: **informational**.

## How to exercise it

Everything is built in debug mode under `/src/target/debug` and every crate is already fetched, so these
work with no network. `target/debug/tursodb` and the extension libraries are the plain `cargo build` the
Makefile, `make test-compat` and the Python runner expect. Every workspace test binary was compiled with
`--all-features` too, but running `cargo nextest ... --all-features` relinks `tursodb` with every feature
(page checksums on, test extension built `static`), which breaks the TCL and Python suites until a plain
`cargo build --locked` restores it. Either switch rebuilds about 30 crates offline in a minute or two.

- `./target/debug/tursodb [file.db]` is the shell; `tursodb --help` lists modes and experimental flags.
  `scripts/limbo-sqlite3` wraps it for the SQLite-style tests.
- `cargo nextest run -p turso_core` runs the engine's unit tests; `cargo nextest run -p core_tester`
  the integration tests under `tests/` (`fuzz_tests` and `pending_byte_tests` are slow; CI skips them).
  CI's full invocation: `cargo nextest run --workspace --all-features --locked --no-fail-fast
  --exclude memory-benchmark -E 'not binary(fuzz_tests) and not binary(pending_byte_tests)'`.
  Sync tests want `LOCAL_SYNC_SERVER=../../target/debug/tursodb` (already set in the image).
- `make test-compat` runs the TCL compatibility suite in `testing/system` (needs the debug `tursodb`).
- `uv run --package turso_test test-shell` and friends (see `Makefile`) drive the Python test runner.
- `testing/simulator` is a deterministic simulation tester (`cargo run -p limbo_sim`) and `testing/stress`
  a stress tester; `fuzz/` has cargo-fuzz targets (schema, expressions, scalar functions, casts).
- `sqlite3` is installed for differential testing against real SQLite. `rusqlite` is bundled in tests.
- `COMPAT.md` says which SQLite features are implemented; do not spend time on ones marked missing.

## How we want reports and patches

- A reproducer we can run: a SQL script for `tursodb`, a database file plus the statements that trigger
  the bug, a Rust test under `tests/integration`, a `.test` file for `testing/system`, or a small client
  for the network protocols. Say which commit you built.
- For memory-safety and durability bugs, show the failing invariant (sanitizer output, a wrong row, a
  file that fails `PRAGMA integrity_check` after the sequence).
- Patches should be minimal, follow the surrounding style, keep existing comments, and include a
  regression test that fails without the fix. `cargo fmt` and `cargo clippy` run clean in CI.

## Leave alone

- `expect`/`assert` on genuinely impossible states inside `core/` that the report cannot reach from any
  input listed above.
- Clippy-level findings, unused `unsafe`, or theoretical issues with no reachable trigger.
- Performance regressions and benchmark results, unless they are an algorithmic DoS from untrusted input.
- Behaviour of experimental flags (`--experimental-*`) beyond crashes and memory safety: they are
  opt-in and unfinished.
