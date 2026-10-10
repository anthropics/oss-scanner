# Threat model

## What this project does and where untrusted input enters
Valkey is an in-memory key-value server. Clients speak RESP over TCP, TLS, or a Unix socket.
- Pre-authentication input: anything a client can send before `AUTH`/`HELLO` succeeds, including RESP parsing and the commands allowed without auth.
- Authenticated clients: every command a normal client can send, including `RESTORE` payloads, Lua scripts and functions (`EVAL`, `FCALL`), and the arguments of every data type command. Escaping ACL command, key, or channel restrictions is a vulnerability.
- The cluster bus: messages from other cluster nodes. The bus has no per-command authentication.
- Administrative commands (`CONFIG`, `ACL SETUSER`, `REPLICAOF`, cluster management and slot migration): in scope, but the attacker already holds high privileges.

Trusted: the config file and loaded modules.

## Components that matter most / least
- Most: networking and RESP parsing, ACL, data types and their encodings (`src/t_*.c`, listpack, intset, quicklist), RDB loading of client-supplied payloads, the Lua scripting engine including its sandbox, and the cluster bus.
- Less: `valkey-cli`, `valkey-benchmark`, and `valkey-check-*` tools.
- Out of scope: vendored code under `deps/` other than Lua, and the example modules in `src/modules/`.

## How to exercise it
- Start a server: `/src/src/valkey-server --port 6379` (or `/src-asan/src/valkey-server` for ASan).
- Send commands with `/src/src/valkey-cli`.
- Integration tests are Tcl under `tests/`; run one with `./runtest --single unit/<name>`.
- Keep test parallelism to `--clients 2` and wrap long runs in `timeout`.
- Unit tests: `make -C src test-unit`. Run a single test with `cd src/unit && ./valkey-unit-gtests --gtest_filter=<Suite>.<Test>`; the full suite in one process is not isolated.

## How you rate severity
Score every finding with CVSS 3.1 and report the vector. Valkey only issues a CVE for High (7.0+) and Critical findings; Medium and Low are fixed publicly.

- AV: `N` for anything reachable over the client protocol. `A` for the cluster bus.
- AC: `L` if a single command or short deterministic sequence triggers it on a default config. `H` if it needs state the attacker does not control, such as active defrag, an in-progress full sync, or a specific eviction or TLS state.
- PR: `N` only for pre-auth bugs and the cluster bus. `L` for normal commands. `H` for administrative commands.
- S: `U` for almost everything, including RCE as the user Valkey runs as. `C` only if impact escapes that user.
- C/I/A: a crash, assertion, deadlock, or memory exhaustion on one node is `A:H`, even if the cluster survives it. A bounded out-of-bounds read is `C:L`. Corrupting another client's response stream is `I:L`. Arbitrary memory write or RCE is `C:H/I:H`.

A sanitizer report alone does not set severity. Reproduce it against the normal build in `/src`. An assertion that fires in the normal build is a real crash (`A:H`).

Examples: Lua use-after-free leading to RCE is `AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H` (8.8). Pre-auth output buffer growth is `AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H` (7.5). A malformed cluster bus message that crashes a node is `AV:A/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H` (6.5).

## Anything to leave alone
- Anything that requires `enable-debug-command`, `enable-protected-configs`, or `enable-module-command`.
- Running with no password and protected mode disabled.
- Commands that are slow or memory hungry by design, such as `KEYS` on a large keyspace.
- Reports and patches should target the `unstable` branch, with a reproducer as a `valkey-cli` command sequence or a Tcl test.

## Disclosure
Findings go privately to the contacts in `project.yaml`. Never put suspected vulnerabilities, reproducers, or unreviewed findings in public issues or PRs. Disclosure decisions belong to the Valkey security team.
