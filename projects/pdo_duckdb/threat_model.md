# Threat model

## What this project does and where untrusted input enters
pdo_duckdb is a PDO driver, written in C, that exposes DuckDB (an in-process analytical database, linked as `libduckdb`) through the standard PDO API, plus the `Pdo\Duckdb` subclass (PHP 8.4+) with `duckdbAppender()`, `duckdbTableNames()`, `duckdbLastProfile()`, and `Pdo\Duckdb\Appender::appendRow()`. Untrusted input enters as:

- **Bound parameters and appended values**: values passed to `bindValue()`, `bindParam()`, `execute([...])`, and `appendRow()`, of any PHP type, converted to DuckDB values. A bound value must never change statement structure.
- **Result data**: every value DuckDB returns, which the driver converts to PHP values in `duckdb_statement.c` (fetch, column metadata, nested LIST/STRUCT/MAP/UNION/ARRAY, DECIMAL, HUGEINT/UHUGEINT, INTERVAL, TIME/TIMESTAMP with time zones, BLOB, BIT, ENUM, UUID, and NULL patterns). Treat table contents and any opened `.db` file as attacker-controlled data.
- **SQL text** is written by the application and trusted by default. One exception: with `open_basedir` set, the driver applies a locked DuckDB sandbox profile (external access off, path allowlists cleared, extension auto-install and load off, configuration locked) meant to contain SQL that the application doesn't fully trust. A query that escapes it to read or write files outside `open_basedir`, or loads an extension from disk, is in scope.
- **DSN and `PDO::DUCKDB_ATTR_CONFIG` options** are application-controlled; the DSN path's `open_basedir` check and the sandbox applied at connect time are in scope.

## Components that matter most / least
- Most: `duckdb_statement.c` (parameter binding, result conversion, column metadata), `duckdb_driver.c` (connect, DSN and config handling, `open_basedir` sandbox, quoting, transactions, the `Pdo\Duckdb` methods), `duckdb_appender.c` (value conversion for appends), `pdo_duckdb.c` (module setup).
- DuckDB itself is a prebuilt upstream library (`/opt/duckdb/lib/libduckdb.so`) and not part of this repository. DuckDB bugs are in scope only when the driver's own code reaches them incorrectly, for example by passing a wrong length, freeing a value twice, or misreading a vector's validity mask. Report other DuckDB bugs upstream.
- Least: `config-tests/` and `scripts/` (CI helpers), `config.w32`.

## How to exercise it
- The driver is built at `/src/modules/pdo_duckdb.so`, installed into PHP's extension dir, and linked against libduckdb 1.5.5 in `/opt/duckdb` (on the loader path). Example: `php -d extension=pdo_duckdb -r '$db = new Pdo\Duckdb("duckdb::memory:"); var_dump($db->query("SELECT [1, NULL]::INT[]")->fetchAll());'`.
- Driver suite: `cd /src && php run-tests.php --show-diff tests/` (the image exports `TEST_PHP_ARGS` to load the module).
- PHP's generic PDO conformance suite is in `/opt/php-src/ext/pdo/tests`: `cd /src && env -u TEST_PHP_ARGS PHP=/usr/bin/php RUN_TESTS=/src/run-tests.php COMMON_DIR=/opt/php-src/ext/pdo/tests DUCKDB_PREFIX=/opt/duckdb EXT=/src/modules/pdo_duckdb.so bash scripts/pdo-common-tests.sh`. It expects `bug_36798` and `bug_43130` to fail (DuckDB SQL dialect).
- Sandbox tests: run with `-d open_basedir=/tmp` and a file DSN under `/tmp`.

## How you rate severity
- Memory-safety bug (overflow, use-after-free, double free) reachable from bound values, appended values, or result data: high. Critical with an attacker-controlled write.
- Out-of-bounds read or information leak into PHP values: medium to high.
- `open_basedir` or sandbox bypass (file read or write outside the allowed paths, loading an extension from disk): high.
- A bound value that alters statement structure: high.
- Crash (null dereference, assertion, uncaught error) on malformed or unusual values: medium.
- Resource exhaustion (huge allocations from result sizes, hangs): low to medium.
- Anything that needs attacker-controlled PHP code, DSN, connection attributes, or ini settings: out of scope or low.

## Anything to leave alone
- SQL injection in application code that concatenates input into SQL.
- Consequences of opening an untrusted `.db` file or loading DuckDB extensions when `open_basedir` is not set.
- State shared between persistent handles with the same DSN, which is by design.
- The TOCTOU between the DSN path check and `duckdb_open_ext`, and extensions loaded before `open_basedir` was set; `SECURITY.md` documents both.
