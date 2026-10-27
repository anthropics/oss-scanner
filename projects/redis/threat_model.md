# Threat model

## What this project does and where untrusted input enters
Redis is an in-memory data structure server. Clients speak RESP over TCP, TLS, or a Unix socket.
- Pre-authentication input: anything a client can send before `AUTH` or `HELLO` succeeds, including RESP parsing and the commands allowed without auth.
- Authenticated clients: every command a normal client can send, including `RESTORE` and `MIGRATE` payloads (serialized objects parsed by `rdb.c`), Lua scripts and functions (`EVAL`, `FCALL`, `FUNCTION LOAD`), and the arguments of every data type command. Escaping ACL command, key, or channel restrictions is a vulnerability.
- The cluster bus: messages from other cluster nodes. Bus messages are not authenticated individually, so the bus port is only meant to be reachable by cluster members.
- Replication: a replica applies the RDB and command stream from its primary. A malformed or unusual stream that a well-behaved primary could send is in scope.
- Administrative commands (`CONFIG`, `ACL SETUSER`, `REPLICAOF`, cluster management and slot migration): in scope, but the attacker already holds high privileges.

Trusted: the config file, modules loaded with `loadmodule`, and RDB or AOF files the server loads from its own `dir` at startup. Payloads received over the network (`RESTORE`, replication, the cluster bus) are not trusted.

## Components that matter most / least
- Most: networking and RESP parsing (`networking.c`, `resp_parser.c`), ACL (`acl.c`), data types and their encodings (`t_*.c`, `listpack.c`, `intset.c`, `quicklist.c`, `rax.c`), RDB and `RESTORE` parsing (`rdb.c`), the Lua scripting engine and its sandbox (`eval.c`, `script_lua.c`, `function_lua.c`, `functions.c`), the cluster bus (`cluster_legacy.c`, `cluster_asm.c`), TLS (`tls.c`), and vector sets (`modules/vector-sets`, compiled into `redis-server` unless it is built with `SKIP_VEC_SETS=yes`).
- Less: `redis-cli`, `redis-benchmark`, `redis-check-rdb`, `redis-check-aof`, and `redis-sentinel`.
- Out of scope: vendored code under `deps/` other than Lua, bundled modules under `modules/` other than vector sets (they are not built by default), and the example modules under `tests/modules/`.

## How to exercise it
- Start a server: `/src/src/redis-server --port 6379` (or `/src-asan/src/redis-server` for ASan).
- Send commands with `/src/src/redis-cli`.
- Integration tests are Tcl under `tests/`; run one with `./runtest --single unit/<name>`.
- Keep test parallelism to `--clients 2` and wrap long runs in `timeout`.
- Redis has no separate C unit test binary; the test suite under `tests/` is the unit-level harness.

## How you rate severity
Score every finding with CVSS 3.1 and report the vector.
- AV: `N` for anything reachable over the client protocol or replication. `A` for the cluster bus.
- AC: `L` if a single command or short deterministic sequence triggers it on a default config. `H` if it needs state the attacker does not control, such as active defrag, an in-progress full sync, or a specific eviction or TLS state.
- PR: `N` for pre-auth bugs and the cluster bus. `L` for normal commands. `H` for administrative commands.
- S: `U` for almost everything, including RCE as the user Redis runs as. `C` only if impact escapes that user.
- C/I/A: a crash, assertion, deadlock, or memory exhaustion on one server is `A:H`, even if a replica or cluster survives it. A bounded out-of-bounds read is `C:L`. Corrupting another client's reply stream is `I:L`. Arbitrary memory write or RCE is `C:H/I:H`.

A sanitizer report alone does not set severity. Reproduce it against the normal build in `/src`. An assertion that fires in the normal build is a real crash (`A:H`).

Examples: Lua use-after-free leading to RCE is `AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H` (8.8). Pre-auth output buffer growth is `AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H` (7.5). A malformed cluster bus message that crashes a node is `AV:A/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H` (6.5).

## Anything to leave alone
- Anything that requires `enable-debug-command`, `enable-protected-configs`, or `enable-module-command`. All three default to `no`.
- Running with no password and protected mode disabled. `protected-mode` defaults to `yes`.
- Commands that are slow or memory hungry by design, such as `KEYS` on a large keyspace.
- Reports and patches should target the `unstable` branch, the default branch, with a reproducer as a `redis-cli` command sequence or a Tcl test.

## Disclosure
Findings go privately to the contacts in `project.yaml`. Never put suspected vulnerabilities, reproducers, or unreviewed findings in public issues or PRs. Disclosure decisions belong to the Redis security team, as described in the repository's `SECURITY.md`.
