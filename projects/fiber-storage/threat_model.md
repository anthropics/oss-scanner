# Threat model: Fiber storage

## Start here

`github.com/gofiber/storage` is 36 independent Go modules that implement one small interface, `storage.Storage` (`Get`, `Set`, `Delete`, `Reset`, `Close`, each with a `...WithContext` twin), over about as many backends. Fiber's `session`, `csrf`, `limiter`, `cache` and `idempotency` middleware keep their state in whichever driver the application hands them. The drivers hold no logic of their own about requests: what matters is what a driver does with a **key** and a **value** it is given, and the keys are built from requests.

That is the whole attack surface, and it is narrow. Most drivers are 250 to 550 lines of glue over a client library. Spend your time in this order:

1. **Key identity.** Two different keys must never name one entry, and one key must name the same entry in `Get`, `Set` and `Delete`. A probe already found backends where this does not hold (see "Hypotheses worth testing", first item). Every driver deserves the same matrix: letter case, trailing space, accents, length, NUL and control bytes, a 4-byte rune, `/`, `.`, `..`, `*`, `%`, `\`, a leading `-`, an empty key, a key that looks like another middleware's prefix (`session:`, `csrf:`, `limiter:`, `idempotency:`).
2. **Keys that make the driver return an error, panic or hang.** Fiber does not recover panics, and its middleware turn a storage error into a 500 or fail open or closed depending on the middleware. A key a client can choose that makes `Set` fail for everyone else's request, or that kills the process, is the finding.
3. **Query construction.** Identifiers (table, collection, keyspace, label) are spliced into SQL, CQL, Cypher and AQL text with `fmt.Sprintf`; keys and values are bound. Verify that is true in every driver, on every path, including `Reset`, the garbage collector and the schema check.
4. **Expiry, garbage collection and `Close`**: an expired entry returned, a live entry deleted by a sweep, a `Set` that lands after `Close`, a collector goroutine that outlives `Close`, a borrowed connection (`NewFromConnection`) that is closed when it should not be. These are races, so use `-race` and many iterations.
5. **Expiry that is not enforced.** `Set` takes an expiration, and the middleware relies on it for sessions, CSRF tokens, rate-limit windows and cached responses. Five drivers accept it and never use it (see "Hypotheses worth testing", second item). Then the drivers that keep an envelope of their own around the value (`leveldb`, `pebble`): the parser reads bytes written by an older version of the driver, and a key the client chose selects which entry is parsed.

If you can run workers in parallel, give each one group and have it read its modules completely: (a) SQL: `mysql`, `postgres`, `mssql`, `sqlite3`, `clickhouse`, `cassandra`, `scylladb`; (b) object and document stores: `s3`, `minio`, `azureblob`, `cloudflarekv`, `firestore`, `dynamodb`, `mongodb`, `couchbase`, `arangodb`, `neo4j`, `surrealdb`, `coherence`, `aerospike`; (c) key-value servers: `redis`, `valkey`, `rueidis`, `memcache`, `etcd`, `nats`; (d) embedded: `memory`, `badger`, `bbolt`, `leveldb`, `pebble`, `ristretto`, `mockstorage`.

Working rules. Give a hypothesis about fifteen minutes; without a lead, move on. Once a root cause has a reproducer and a patch, stop and write it up rather than listing every driver it reaches (list them in one report). Read the tests for what they pin, not in full: a test that asserts a behavior marks it as deliberate. Skip `.github/`, `testhelpers/` and the README pages of modules you are not on.

## What this project does and where untrusted input enters

An application creates a driver (`mysql.New(mysql.Config{...})`, or `NewFromConnection` with its own client), passes it to a Fiber middleware as `Config.Storage`, and the middleware calls it on every request. You are auditing the drivers, not the middleware, not the database and not the client libraries.

Attacker-controlled, through the HTTP client of the application:

- **Keys.** The middleware prefixes them (`session:`, `csrf:`, `limiter:`, `idempotency:`, and the cache's own), but the rest is the client's: the session ID in the cookie (the client sends any string; a lookup of an ID that does not exist is the normal case), the CSRF token the client sends back, the idempotency key header (hashed together with a scope when `KeyScope` is set), the limiter key (the client address by default, or whatever `KeyGenerator` returns, and up to 192 bytes before the middleware hashes it), the cache key (by default the method and the target URI of the request, scheme, host, path and query, or `KeyGenerator`'s). So keys are arbitrary strings of any length and bytes, chosen one request at a time, in any number.
- **Values** are produced by the middleware (a `gob` or MessagePack blob of its own state), not by the client, though they hold client data such as a session's contents or a cached response body, and their size follows the response. Treat values as arbitrary bytes.
- **Expirations** come from the middleware's configuration.

Trusted: the application and its `Config` (host, credentials, table, collection, keyspace, bucket, GC interval, `Reset`), the database server and what is stored in it before the driver starts, and the client libraries. A multi-tenant application that builds `Table` or `Bucket` from a tenant name is the application's choice, but see "Anything to leave alone" and the hypotheses on identifiers.

Defaults that decide severity: `GCInterval` is 10 seconds in the SQL drivers; `Reset` is off; an expiration of 0 means the entry never expires; `Set` with an empty key or an empty value returns nil and stores nothing; `Get` of a missing or expired key returns `nil, nil`.

## What the drivers promise (a violation is a finding)

From `storage.go`, the READMEs and the tests. Each promise ends with the check that tests it.

1. **A key is its own entry.** `Set(k, v)` followed by `Get(k)` returns `v`; `Get(k2)` for any `k2 != k` returns `nil, nil` (or an error), never `v`; `Delete(k)` removes `k` and nothing else. *Check:* the key matrix above, with a driver running against a local server (see "How to exercise it"). The TCK in `testhelpers/tck` pins the ordinary cases; the interesting keys are the ones it does not try.
2. **Expiry.** An entry whose expiration has passed is not returned. A live entry is not deleted by a sweep, and a `Set` is not undone by a sweep that read the old row (several drivers carry comments about exactly this: "an unconditional delete could drop a concurrent Set"). *Check:* `Set` with a short expiration, `Get` just before and after; and many concurrent `Set`s of one key against the collector at a tiny `GCInterval`, with `-race`.
3. **Binary safety.** The value comes back byte for byte, including empty-looking prefixes, NUL bytes, and values larger than a page or a packet. The returned slice is the caller's: mutating it does not change the stored value (the `memory` driver copies). *Check:* round-trip a matrix of values; mutate the result and `Get` again.
4. **No cross-talk between calls.** No pooled buffer, shared slice or reused row reaches another call's result. *Check:* concurrent `Get`/`Set` with unique markers, under `-race`.
5. **`Close` and borrowed connections.** After `Close`, operations return the driver's `ErrClosed` (many drivers have one) or a clean error and never panic; the collector goroutine exits; a connection passed to `NewFromConnection` is left open. *Check:* `Close` twice, `Close` while operations run, then `goleak`-style goroutine counts.
6. **Identifiers are used as given and only as given.** A configured table, collection, keyspace or label is spliced into text once, at construction; a driver that validates identifiers (`cassandra`, `scylladb`, `mssql`, `sqlite3`) does so before it uses them. *Check:* read every `fmt.Sprintf`, `strings.ReplaceAll` and string concatenation that builds a query, and the schema checks.
7. **`Reset` stays inside the driver's namespace.** `Reset` deletes the driver's table, bucket, collection or key prefix, and what the README says beyond that. *Check:* put an unrelated entry beside it and `Reset`. (The `redis` driver documents that it flushes every database; read each README before calling a wide `Reset` a finding.)

The READMEs are the maintainers' statement of intended behavior. When a README says a behavior is intended, a caveat, or something the application must do, that is not a finding; when the code contradicts it, that is.

## Components that matter most / least

Most important, in this order (non-test lines of Go in brackets):

1. **SQL drivers**: `mysql` (444), `postgres` (546), `mssql` (514), `sqlite3` (388), `clickhouse` (339). Most share a design: one table `(k, v, e)` with a 64-character `VARCHAR` key (`TEXT` in postgres), a collector that deletes rows with `e <= now`, and a schema check. The key column's type, collation and length decide what a "different key" means.
2. **Drivers that implement expiry, collection or setup themselves**: `leveldb` (880, a versioned envelope and a collector with a cursor), `pebble` (634, a JSON envelope and a collector with a cursor), `nats` (720, lazy bucket setup and reconnect handlers), `cassandra` (536), `aerospike` (530), and the five that do not expire at all (`s3`, `minio`, `azureblob`, `dynamodb`, `cloudflarekv`).
3. **Drivers that turn a key into a name in someone else's namespace**: `s3`, `minio`, `azureblob` (object or blob name), `firestore` (document ID), `cloudflarekv` (a key in a REST call), `etcd` and `nats` (a subject or key with syntax of its own), `mongodb` and `arangodb` (`_id` or `_key`). What does the backend do with `/`, `..`, a leading `.`, a trailing space, `*`, `>`, an over-long name, a name its own rules reject?
4. **The key-value servers**: `redis`, `valkey`, `rueidis`, `memcache`. Memcached's protocol is text, so a key with a space or control byte is a protocol injection if a client does not refuse it (the client in use does; look for paths that bypass it, such as a batch call or the `Conn()` escape hatch).
5. **Embedded**: `memory` (316), `badger`, `bbolt`, `ristretto`, `mockstorage`. Their concern is the collector, copies and races.

Less important, still in scope: `coherence`, `couchbase`, `neo4j`, `surrealdb`, `scylladb`, `arangodb` (small, mostly parameter binding).

Out of scope: `_test.go` files, `testhelpers/` (test-only modules that need Docker), `.github/`, the root module's `storage.go` (an interface), benchmarks, and the `docs` and README pages.

## Bug classes seen here (hunt for variants)

This checkout's history is shallow (it starts on 2026-10-01, and the last three months of source commits are mostly dependency bumps and workflow changes), so these classes come from reading the code and from probes, not from a list of fixed vulnerabilities. Check `git rev-parse --is-shallow-repository` and, if the history is complete, `git log --since=2026-01-01 --no-merges -i --grep='fix' -- <module>` for the real list and add its classes to this one.

1. **The key column is not a binary-exact string.** MySQL and MSSQL compare `VARCHAR` keys under a collation that ignores case, accents and trailing spaces, so `AbCdEf`, `abcdef` and `resumé`/`resume` are one row. *Siblings:* every driver whose backend normalizes names: MSSQL's default collation, Cassandra and ScyllaDB `text` (exact), Firestore IDs, Azure blob names and S3 keys under a gateway that folds case, DynamoDB, NATS KV key rules, etcd.
2. **A key longer than the backend's limit.** The SQL drivers declare `VARCHAR(64)`; Fiber's limiter keys are up to 192 bytes plus `limiter:`, and its default cache key holds the method, host, path and query of the request. Whatever the backend does with an oversized key (error, truncate, collide) is client-reachable. *Siblings:* memcached's 250 bytes, S3's 1,024, etcd's request size, NATS's subject limits, Firestore's 1,500 bytes, DynamoDB's partition key (2,048 bytes), Cassandra's 65,535, MongoDB's index key limits, ClickHouse and SurrealDB record IDs.
3. **A byte the backend cannot store.** PostgreSQL refuses `\x00` in `TEXT`, MySQL's `utf8` (three-byte) charset refuses a four-byte rune, memcached refuses spaces and control bytes. Each is an error a client can trigger with one request. *Siblings:* invalid UTF-8 where the backend wants UTF-8 (MongoDB, Firestore, DynamoDB, Cassandra, ClickHouse, Neo4j, SurrealDB), NUL where the backend uses C strings.
4. **A key interpreted as syntax.** Redis, memcached and the SQL drivers bind it. Look at: NATS (`.`, `*`, `>` in a key), etcd (a key used as a prefix range), SurrealDB (`models.NewRecordID(table, key)` is typed, a raw query is not), Firestore (`Doc(key)` with a `/` is a path), Azure and S3 (`..`, a trailing `/`), Cloudflare KV (a key placed in a URL path).
5. **Sweep versus write.** The collector reads expired rows and deletes them in a second step; the code has comments and `deleteIfStillExpired` helpers because a plain `DELETE ... WHERE k=?` there drops a `Set` that arrived in between. *Siblings:* any collector or lazy-expiry path that deletes by key rather than by key and expiry.
6. **Lifecycle.** `ErrClosed` latches exist in many drivers (`memory`, `mysql`, `postgres`, `surrealdb` and `scylladb` among them; `Set` after `Close` would never be reclaimed), `NewFromConnection` variants must not close a borrowed client, `New*` panics on a failed connection by design. *Siblings:* the driver that has no latch, the `Conn()` accessor handing out the client after `Close`, a `Reset` or collector pass that runs after `Close`.
7. **Reconnect and lazy setup.** `nats` resolves its bucket lazily and recreates it only if the driver created it; a cluster client in `redis`, `valkey` and `rueidis` fans `Reset` out to every master. *Siblings:* the same logic in `couchbase`, `mongodb`, `azureblob` and `minio` (bucket or collection creation on first use).

## Hypotheses worth testing

Each with its oracle.

1. **Observed, not yet reported. Case, trailing-space and accent aliasing in `mysql`, and by the same design `mssql`.** On MariaDB 10.11 with the driver's own table (`k VARCHAR(64)` with the server's default collation) a probe found: `Set("AbCdEf")` then `Get("abcdef")` returns the value; `Set("token")` then `Get("token   ")` returns it; `Set("resume")` then `Get("résumé")` returns it; `Set` of a 65-byte key fails with `Data too long for column 'k'`; `Set` of a key holding a four-byte rune fails with `Incorrect string value` (the table is `DEFAULT CHARSET=utf8`). `redis`, `postgres` and `memcache` kept `AbCdEf` and `abcdef` apart in the same probe. Nothing in the `mysql` or `mssql` README mentions it. Confirm on the `mysql` image the maintainers test with (`TEST_MYSQL_IMAGE` in `.github/workflows/test-mysql.yml`) if the image can be had, work out what a client gains (session IDs and CSRF tokens whose comparison ignores case lose entropy; two cache or idempotency keys that differ in case share a response; a long limiter or cache key makes every such request fail), and report the severity the guide below gives with a patch (a binary collation such as `utf8mb4_bin` for the key column, `utf8mb4`, a wider key column, or hashing long keys the way `limiter` does) and the migration note. *Oracle:* the key matrix.
2. **Observed in the source, not yet run: five drivers ignore the expiration.** In `s3`, `minio`, `azureblob`, `dynamodb` and `cloudflarekv`, `SetWithContext` takes `exp` and never uses it: the object, blob, item or key is written with no expiry and no TTL attribute, and the READMEs list the signature and say nothing about it (every other driver passes `exp` on or stores a deadline). If that is right, a session, CSRF token, idempotency record, rate-limit window or cached response in these stores outlives its configured lifetime unless the operator has set a bucket lifecycle or a table TTL the driver does not mention. Check each `Set` in the source and then whether the middleware compensates (does `session` store its own deadline and check it on load? does `limiter` keep its own reset time in the value? does `cache` check its own expiry?). If the middleware does not, say what the client gains (a stolen or logged-out session ID that works indefinitely; a limiter that never resets) and report it with a patch (a stored deadline checked on `Get` as `mysql` does, or the backend's native TTL where it has one, such as DynamoDB's TTL attribute, S3 object expiry through a header or lifecycle, Cloudflare KV `expiration_ttl`), or with a README line if the maintainers' intent is that these stores do not expire. *Oracle:* `Set(k, v, 1*time.Second)`, wait two seconds, `Get(k)` must return `nil, nil`.
3. **Long keys through every SQL driver.** `postgres` stored 300 and 1,000 byte keys; `mysql` refused 65. What do `mssql` (`VARCHAR(64)`; truncation or an error), `sqlite3` (the declared length is not enforced), `clickhouse`, `cassandra` and `scylladb` do at 65, 256 and 4,096 bytes, for `Set`, `Get` and `Delete`? Is an oversized `Get` an error or a miss, and is a `Delete` of an oversized key silent? *Oracle:* `Set(k, v)` then `Get(k)` returns `v` or `Set` fails; `Get(k+"x")` never returns `v`.
4. **Memcached protocol bytes.** The `memcache` driver returned `malformed: key is too long or contains invalid characters` for spaces, CR/LF, NUL and over 250 bytes: good. Is every path covered (`Delete`, `GetWithContext`, `Reset`, batch operations, the `Conn()` client used by the application)? *Oracle:* a raw `nc` capture on loopback of what the driver wrote for each key.
5. **Object and document names.** Against a local MinIO (`minio server`, single binary, if it can be had in the image; it cannot be fetched offline) or a fake S3 on loopback you write: what does the driver send for `a/../b`, `./a`, `a//b`, `a/`, a 1,025-byte key, `%2e%2e`? Same for `azureblob` (blob names), `firestore` (`Doc("a/b")`, `Doc(".")`, `Doc("__x__")`), `cloudflarekv` (the key in a URL path: is it escaped?). *Oracle:* a recording HTTP server on loopback and the bytes it received; two distinct keys must produce two distinct, correctly escaped requests; the escaped path must name the key and nothing else.
6. **NATS and etcd key syntax.** NATS KV keys allow a restricted set of characters; what does the driver do for a key with a space, `*`, `>`, a leading `.` or `..`, or one that is not valid UTF-8? etcd: a key that is a prefix of another; a key beginning with `\x00`. *Oracle:* the key matrix against `nats-server` and `etcd` on loopback if you can get them; else read the client library's validation and the driver's calls.
7. **Identifier injection and validation gaps.** `mssql`, `sqlite3`, `cassandra` and `scylladb` validate `Table`; `mysql` and `postgres` interpolate it (postgres splits on `.`), `clickhouse` passes it as a named parameter, `neo4j` splices `Node` into Cypher, `arangodb` binds the collection. This is a hardening gap and not a finding by itself, since `Config` is trusted, unless an identifier can come from a request in a documented usage. Look for any identifier derived from a key or a value (a table per key prefix, a bucket per tenant in the README's examples).
8. **Sweep races.** For each SQL driver and for `leveldb`, `pebble`, `badger`, `bbolt`, `memory`: set `GCInterval` to a few milliseconds, `Set` one key with a 50 ms expiration in a loop from several goroutines while `Get` runs, with `-race -count=20`. *Oracle:* no `Get` returns a value older than the last `Set`'s expiration; no `Get` of a live key returns `nil` because of a sweep.
9. **Envelope parsers.** `leveldb` wraps `(expiry, value)` in a versioned binary envelope, and `decode`, `decodeBinary` and `classify` accept both the versioned and an older unversioned form; `pebble` wraps it in JSON (`CacheType{Data, Created, Expires}`). Can a value that the middleware writes (arbitrary bytes) be misread as the other form, so that `Get` returns a truncated value or treats a live entry as expired, or the collector deletes it? Fuzz `encode` then `decode` over arbitrary values and expirations. *Oracle:* `decode(encode(v, e))` equals `(v, e)` for every `v` and `e`, and the collector keeps every entry that `Get` would return.
10. **Expiration arithmetic.** `Set(k, v, exp)` with `exp` of 1 ns, 999 ms, `math.MaxInt64`, a negative duration. The middleware passes configured values, so this is a hardening matter, but an overflow that turns a long expiration into an immediate or past one (or the reverse) in a session store is worth reporting. *Oracle:* `Get` after `Set` with a positive `exp` returns the value until `exp`, and a negative `exp` does not store a permanent entry.
11. **`Reset` scope.** `Reset` on a driver whose namespace is shared (`redis` flushes every database; the SQL drivers truncate their table; `nats` recreates the bucket; the object stores delete what? by prefix or the whole bucket). *Oracle:* the README, plus an unrelated object beside it.

## Already tried

At commit `30089ff` (`main`, 2026-11-04), on a developer machine with the network on and Go 1.26, outside the scanner image:

- `go build ./...` succeeds in all 36 modules.
- `go test -vet=off -count=1 ./...`, no `-race`, per module: the root module, `memory`, `badger`, `bbolt`, `leveldb`, `pebble` (45 s), `ristretto`, `sqlite3` (58 s), `mockstorage` and `testhelpers/tck` pass. The other 26 modules fail at once because their tests start the database through testcontainers (`rootless Docker not found, failed to create Docker provider`), except `cloudflarekv`, whose tests dial a mock worker on `localhost:8787`. The failures say nothing about the drivers.
- A key probe (the code below, with one constructor line changed) against local servers: MariaDB 10.11 (`mysql` driver), PostgreSQL 16 (`postgres`), memcached 1.6 and Redis 7.0. Results in "Hypotheses worth testing", first item; in short: `redis` and `postgres` are exact for case and trailing space and accept 1,000-byte keys, `postgres` refuses NUL, `memcache` refuses spaces, control bytes and anything over 250 bytes, `mysql` aliases case, trailing space and accents and refuses keys over 64 bytes and four-byte runes.

- A read of every driver's `SetWithContext` for use of `exp`: the five named in the second hypothesis never use it.

Not tried: `-race`, fuzzing, `go vet`, `govulncheck`, any driver other than the four above against a live server, any hypothesis beyond the first (the second only by reading the source), and any of the object stores (their servers cannot run in this image).

## How to exercise it

The image has the checkout at `/src`, Go 1.27, every module's dependencies in the module cache, every package and test binary already compiled (plain and with `-race`), `GOPROXY=off` and `GOTOOLCHAIN=local`. `/src/.oss-scanner/` is the scanner's own untracked copy of the Dockerfile; keep it out of patches. Only loopback is reachable; there is no Docker daemon. The Dockerfile tries to install `redis-server`, `memcached`, `mariadb-server` and `postgresql` (each best effort; check with `which redis-server memcached mariadbd pg_lsclusters`), none of them running. `golangci-lint` is not installed; use `go vet ./...` and `gofmt -l .`.

- **One module at a time.** There is no `go.work`, so run every `go` command inside the module: `cd /src/mysql`. Note that a module's import path may carry a version suffix (`github.com/gofiber/storage/mysql/v2`, `postgres/v3`, `mongodb/v3`, `redis/v3`); a scratch test inside the module uses `package mysql` and needs no import.
- **The tests that do work offline**: the embedded stores. `cd /src/memory && go test -race -count=1 ./...`. The others fail at start because they use testcontainers; use the local servers below instead.
- **Local servers** (commands tried on Ubuntu 24.04 with the same packages; Debian bookworm differs in versions, so use `pg_lsclusters` for the PostgreSQL version):
  - Redis: `redis-server --daemonize yes --bind 127.0.0.1 --save '' --appendonly no`; `redis.New(redis.Config{Host: "127.0.0.1", Port: 6379})`. `valkey` and `rueidis` speak the same protocol and can use the same server.
  - Memcached: `memcached -u nobody -d -l 127.0.0.1`; `memcache.New(memcache.Config{Servers: "127.0.0.1:11211"})`.
  - MariaDB (for `mysql`): `mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld; (mysqld_safe --user=mysql --bind-address=127.0.0.1 &)`, wait a few seconds, then `mariadb -uroot -e "create database fiber; create user 'fiber'@'127.0.0.1' identified by 'pw'; create user 'fiber'@'localhost' identified by 'pw'; grant all on fiber.* to 'fiber'@'127.0.0.1'; grant all on fiber.* to 'fiber'@'localhost';"`; `mysql.New(mysql.Config{Host: "127.0.0.1", Username: "fiber", Password: "pw", Database: "fiber", Table: "zz_keys", Reset: true})`. The driver is for MySQL and MariaDB behaves the same for the collation findings, but state which server you used.
  - PostgreSQL: `pg_ctlcluster <version> main start` (or `service postgresql start`), then `su postgres -c "psql -c \"alter user postgres password 'pw'\""` and `su postgres -c "psql -c 'create database fiber'"`; `postgres.New(postgres.Config{Host: "127.0.0.1", Username: "postgres", Password: "pw", Database: "fiber", Table: "zz_keys", Reset: true})`.
  - `sqlite3` and the other embedded stores need no server (`sqlite3` links C code through cgo; `gcc` is in the image).
  - Anything else (MongoDB, Cassandra, S3, Azure, etc.): not available. Write a loopback fake that records the requests (a few dozen lines of `net/http`) and point the driver's endpoint at it; most drivers take an endpoint or URL in `Config`.
- **History.** `git log --no-merges --format='%h %ad %s' --date=short -- <module> | head -40`; `git log -S'<text>' -- <file>` finds when a line appeared.
- **Races and leaks.** `go test -race -count=20 -run <test> .`; a goroutine count before `New` and after `Close` finds a leaked collector.

### A starting point: the key matrix

Save as `zz_probe_test.go` in the module under test, replace the constructor on the line marked, and run `go test -run TestZZKeys -v -count=1 .`. It stores one value under a key, asks for it under another, and logs what came back. Delete it before you write a patch.

```go
package mysql // change to the module's package name

import (
	"strings"
	"testing"
	"time"
)

func TestZZKeys(t *testing.T) {
	s := New(Config{Host: "127.0.0.1", Username: "fiber", Password: "pw", Database: "fiber", Table: "zz_keys", Reset: true}) // change
	defer s.Close()
	_ = s.Reset()
	try := func(name, setKey, getKey string) {
		if err := s.Set(setKey, []byte("secret-of-"+name), time.Minute); err != nil {
			t.Logf("%-16s Set err: %v", name, err)
			return
		}
		v, err := s.Get(getKey)
		t.Logf("%-16s Set(%q) Get(%q) -> %q err=%v", name, tr(setKey), tr(getKey), v, err)
	}
	try("case", "AbCdEf", "abcdef")
	try("trailing space", "token", "token   ")
	try("accent", "resume", "résumé")
	try("65 chars", strings.Repeat("a", 65), strings.Repeat("a", 65))
	try("64 vs 65 chars", strings.Repeat("b", 64), strings.Repeat("b", 64)+"x")
	try("300 chars", strings.Repeat("c", 300), strings.Repeat("c", 300))
	try("1000 chars", strings.Repeat("d", 1000), strings.Repeat("d", 1000))
	try("NUL byte", "a\x00b", "a\x00b")
	try("NUL prefix", "a\x00b", "a")
	try("space in key", "a b", "a b")
	try("newline", "a\r\nb", "a\r\nb")
	try("4-byte rune", "k-😀-one", "k-😀-two")
	try("slash", "a/b", "a/b")
	try("dot dot", "a/../b", "b")
	try("prefix clash", "session:x", "csrf:x")
}

func tr(s string) string {
	if len(s) > 20 {
		return s[:20] + "..."
	}
	return s
}
```

A result is a finding when `Get` returns the value for a key other than the one it was set under (the `-> "secret-of-..."` line for two different keys), or `Set` fails for a key a client can send, or the process panics. A line that says `-> ""` for different keys is the correct answer.

## How you rate severity

A finding counts when a network client of an application that uses a driver as its README describes can make it misbehave. State the driver, the backend and its version, the middleware and the `Config` the application needs, and the keys the client sends. A finding against the default table or collection layout and a driver's documented configuration weighs more than one that needs an unusual option.

- **Critical**: one client's key reaching another client's entry through a read, an overwrite or a delete, where the keys are strings a client can send (a session, CSRF token or idempotency record of another user returned or replaced by a key that differs only by case, trailing space, truncation, escaping or a prefix of another middleware's namespace), under the driver's default layout. Query injection through a key or value in any driver. Memory corruption or a data race on a returned slice or string. An expired session or token returned as valid.
- **High**: a panic or fatal error in `Get`, `Set` or `Delete` that one unauthenticated request triggers with a key the client chose (Fiber does not recover panics, so the process exits). A key the client can send that makes `Set` fail for a middleware whose failure is fail-open (a limiter that stops limiting) or that denies service to a route (a cache or idempotency key that always errors), under the default layout. Truncation or normalization of a key that merges two entries of a cache or idempotency store so one client's response is served to another. A collector that deletes live entries or a `Close` that leaves the process unable to exit.
- **Medium**: the High classes when they need a non-default option. Case or accent aliasing that only lowers the entropy of a token the client must already know a form of. A client-triggered error that the middleware turns into a 500 for that client only. A leak of goroutines, connections or memory per distinct key beyond what the README says. `Reset` that reaches beyond its namespace without the README saying so. Credentials, DSNs or table names reaching a log or an error text returned to a client.
- **Low**: hardening gaps (an identifier not validated where a sibling driver validates it, a documented but surprising limit, an expiration that rounds in a different direction from its sibling), a crash that only the application's own `Config` can cause.

When a finding sits between two levels, choose the lower and say what would raise it. A deviation from the interface's wording with no security consequence is a bug and not a vulnerability; do not report it.

## How to report

Verify before you report. A finding needs all of these:

1. A reproducer that runs in this image from a clean checkout: a Go test inside the module concerned, the local server it needs and how it was started (or the recording fake), the `Config`, the keys, and what you observed against what the README or the interface promises. For a race, the `-race` output and the iteration count.
2. A check that it is not intended: read the module's README and search its tests (`grep -rn '<behavior>' --include='*_test.go' <module>`; `git log -S'<text>'`). A test that pins the behavior, or a README line that describes it, usually means it is deliberate.
3. A check that it is present on `main` now (`git log --oneline -5 -- <file>`) and in which module version (`git tag --contains <commit>`, if the checkout has tags).
4. A minimal patch against `main` with a regression test written as the module writes its tests (most use `testify` and the TCK in `testhelpers/tck`; the tests that need a container are skipped here, so also give the reproducer that runs against the local server). The test must fail before the patch and pass after it, with `go test -race` on the package. Change only the module concerned; there are no cross-module `replace` directives. A fix that changes a stored layout (a column type or collation, a key encoding) needs a migration note in the module's README, and the SQL drivers already check the schema at start-up (`checkSchema`), which a changed column type would trip.

Report one root cause once, listing each driver it reaches. Say plainly when a finding depends on something this image cannot reproduce (a managed service, Docker, a backend version), and what you checked instead. Do not report best-practice gaps without a concrete key or sequence that misbehaves.

## Dependencies

Each driver depends on a client library for its backend (`pgx`, `go-sql-driver/mysql`, `go-redis`, `aws-sdk-go-v2`, `minio-go`, `mongo-driver`, `gocql`, `nats.go`, `etcd`, the Azure, Google, Couchbase and ClickHouse clients, and others) and on `github.com/gofiber/storage` for the interface. A bug in a client library is out of scope unless the driver's use of it exposes it to a client's key or value; in that case report it against the driver with the reproducer, and say where the fix belongs.

## Anything to leave alone

- `Config` is the application's: connection strings, credentials, TLS settings, table, bucket, collection and keyspace names, `GCInterval`, `Reset`. The constructors panic on a bad configuration or an unreachable server on purpose (`New` has no error return); that is documented behavior.
- `Set` with an empty key or an empty value stores nothing and returns nil, and `Get` of a missing key returns `nil, nil`: that is the interface's contract.
- The `Conn()` accessor hands out the underlying client; what an application does with it is its own.
- The `redis` driver's `Reset` flushes databases, and the READMEs describe what each `Reset` removes; read the README before reporting its reach. The `memory` driver grows with the number of keys, as the middleware that uses it allows; report growth that outlives expiry or `Delete`, not growth with the key count.
- Drivers that share code or behavior with one you already reported (`valkey`, `rueidis` and `redis` are three clients for one protocol; `scylladb` and `cassandra`): list them in the same report.
- Findings that exist only in a client library, a backend server, Fiber's middleware (`session`, `csrf`, `limiter`, `cache`, `idempotency` live in `gofiber/fiber`), or `testhelpers/`, `_test.go` files, READMEs and `.github/`.
- The tests that need Docker (testcontainers), which fail in this image for want of a daemon.
