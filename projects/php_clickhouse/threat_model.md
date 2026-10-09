# Threat model

## What this project does and where untrusted input enters
php_clickhouse is a PHP extension (C++) that speaks ClickHouse's native binary TCP protocol, with optional TLS and LZ4/ZSTD compression, through a vendored and locally patched copy of clickhouse-cpp. It runs inside the PHP process of the application that uses it. Untrusted input enters in two directions:

- **Server to client (primary).** Everything read off the socket: handshake and server info, exceptions, progress/profile/log packets, compressed frames, and data blocks (column type names, row counts, column payloads). Assume the server, or anything on the path when TLS is off or `ssl_skip_verify` is set, is malicious or compromised and sends arbitrary bytes. Decoding lives in `lib/clickhouse-cpp/clickhouse/client.cpp` (packet dispatch), `base/` (wire format, compression, socket/TLS), `types/type_parser.cpp` (column type names), `columns/` (column loaders), and the conversion of decoded columns to PHP values in `typesToPhp.cpp`, `clickhouse.cpp`, `metadata.cpp`, and `query_log.cpp`.
- **Application to client.** Values that applications forward from their own users: `$params` for `select*()`/`execute()` (client-side `{name}` identifier substitution and server-side `{name:Type}` parameters, see the placeholder code in `clickhouse.cpp`), row values passed to `insert()`, `insertAssoc()`, `write()`, `selectWithExternalData()`, TSV/CSV streamed through `insertFromStream()`, and table, database, and partition names passed to helper methods such as `tableSize()`, `partitions()`, `dropPartition()`, `showTables()`. The SQL string, connection array, settings, and callbacks are written by the application author and are trusted.

## Components that matter most / least
- Most: `typesToPhp.cpp` (PHP to column and column to PHP for every type, including Nullable, Array, Tuple, Map, LowCardinality, Decimal, Int128/UInt128, Date/DateTime64/Time64, Enum, JSON, IPv4/IPv6, UUID, FixedString), `clickhouse.cpp` (placeholder substitution, insert paths, stream import/export, result shaping, statement iterator), and the clickhouse-cpp decoding paths named above.
- In scope with a condition: bugs in vendored code under `lib/clickhouse-cpp/` (clickhouse-cpp itself, `contrib/lz4`, `contrib/zstd`, `contrib/cityhash`, `contrib/absl`) only when reachable through the extension's PHP API, for example by a server response or by a value passed to a PHP method. Our local edits to clickhouse-cpp are listed in `lib/clickhouse-cpp/LOCAL_PATCHES.md` and `patches/upstream/`; bugs those edits introduce are ours.
- Least: `bench/`, `docs/`, `scripts/` (CI helpers), and Windows-only code in `config.w32`.

## How to exercise it
- The image has the extension built with TLS at `/src/modules/clickhouse.so` and installed into PHP's extension dir, so `php -d extension=clickhouse` loads it.
- The image also carries the same pinned ClickHouse server CI uses, listening on 127.0.0.1 and 127.0.0.2 only (127.0.0.2 lets the TLS hostname-mismatch test run): native 9000 and native TLS 9440 (cert and CA in `/etc/clickhouse-server/certs/`), user `test` with password `test`. Start it with `clickhouse-test-server` (it daemonizes and waits for the port; logs in `/var/log/clickhouse-server/`). The environment already exports `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWD`, and the TLS variables the phpts read.
- Full suite: `clickhouse-test-server && cd /src && php run-tests.php -j1 --show-diff tests/`. Use `-j1`; the phpts share tables. Without the server, server-dependent phpts skip and only the offline ones run.
- To test hostile-server behaviour, write a small fake server (Python or PHP socket listener on 127.0.0.1) that replays a captured handshake and then sends crafted packets, and point `new ClickHouse(["host" => "127.0.0.1", "port" => <port>])` at it. A real handshake and data block can be captured from the bundled server with `tcpdump -i lo` or a socket proxy.

## How you rate severity
- Memory-safety bug (overflow, use-after-free, double free, type confusion) reachable from server responses or from application-forwarded values: high. Critical when it gives an attacker-controlled write.
- Out-of-bounds read or information leak (heap memory returned to PHP or sent to the server): medium to high, by how much and what leaks.
- Crash (abort, uncaught C++ exception, null dereference, assertion) on malformed server data or input values: medium.
- A bound value that changes statement structure (escaping `{name}` identifier validation, or breaking out of a `{name:Type}` parameter): high.
- TLS verification bypass when verification is on (hostname or CA check skipped or wrong): high.
- Resource exhaustion (unbounded allocation driven by a length or count field, infinite loop, hang despite configured timeouts): low to medium.
- Anything that needs attacker-controlled PHP code, the SQL string, connection options, settings, or ini values: out of scope or low.

## Anything to leave alone
- `ssl_skip_verify => true` disabling certificate checks is documented behaviour, not a finding.
- SQL injection from applications that concatenate input into the SQL string is out of scope; placeholders exist for that.
- Server-side ClickHouse bugs are out of scope.
