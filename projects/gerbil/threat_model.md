# Threat model: Gerbil Scheme v0.19

## What this project does and where untrusted input enters
Gerbil is a Scheme dialect and compiler currently built as a layer on top of Gambit Scheme
(Gerbil source -> Gambit Scheme -> C -> native).
It ships a runtime, a macro expander/compiler (`gxc`), an interpreter (`gxi`),
and a large standard library (`std/`).

Source code, macros and build specs are TRUSTED:
compiling or loading attacker-supplied Gerbil code is arbitrary code
execution by design and is not a vulnerability.
Although one of many goals on our TODO list would be to define less-trusted but useful subsets
of Gerbil as #lang dialects, e.g. a subset where only the memory-safe primitives are visible,
one when further some reflective primitives are inaccessible, etc.

In the meantime, untrusted input enters through stdlib modules
that parse or decode external data, notably:
- network protocols: `std/net/http` (server and client), `std/net/websocket`,
  `std/net/request`, `std/net/uri`, `std/net/url`, `std/net/json-rpc`,
  `std/net/smtp`, `std/net/sasl`, `std/net/socks`, `std/net/s3`, `std/net/ssl`
- data encodings: `std/encoding/*` (json, csv, base64, base58, hex, utf16,
  utf32, zlib, protobuf, multibase)
- serialization: `std/serde/*`, and the actor wire protocol in `std/actor/*`
  (messages from remote peers)
- markup and text: `std/text/markup/*` (xml, html, sxml, tal),
  `std/text/pregexp`, `std/text/parser/*`
- database drivers: `std/db/postgresql*` (server responses), `std/db/sqlite*`
- crypto FFI bindings to OpenSSL: `std/crypto/*`
- the data reader (`read` on untrusted text, as opposed to loading code)

## Components that matter most / least
- Most: anything reachable from a network peer
  (`std/net/http/server`, websocket, actor protocol, json/serde decoding),
  and FFI / `(declare (not safe))` code where bad input
  can corrupt memory rather than raise an error.
- Less: client-side parsers fed by servers the user chose to talk to
  (still in scope).
- Out of scope: `src/v0.19-WIP/` and
  any `*.TODO` / `v0.19-TODO` / `v0.19-TODIE` directories
  (unported or slated for removal);
  `src/bootstrap/` (generated code);
  `doc/`; the compiler acting on trusted source.
- Gambit (`src/gambit`, a submodule) is in scope
  only as reached through Gerbil APIs; a pure Gambit bug should say so.

## How to exercise it
- Gerbil is installed at `/opt/gerbil` (`gxi`, `gxc`, `gxtest` on PATH).
  Sources are in `/src/src`.
- Tests live next to modules as `*-test.ss`;
  run one with `gxtest src/std/net/uri-test.ss`,
  or a tree with `gxtest src/std/...`.
- Quick drivers: `gxi -e '(import :std/encoding/json) (displayln (string->json-object "..."))'`.

## How you rate severity
- Critical: memory corruption or RCE reachable from a network peer
  (e.g. HTTP server, actor protocol) with default use.
- High: memory corruption (out-of-bounds, use-after-free)
  from untrusted input anywhere else, including through
  unsafe declarations or FFI; authentication/crypto misuse
  that breaks confidentiality or integrity.
- Medium: request smuggling / parser differentials in HTTP;
  unbounded memory or CPU on small input (DoS) in network-facing code;
  injection in generated output (HTML/SQL/URL escaping) by library helpers.
- Low: DoS in offline parsers;
  an uncaught Scheme exception (a safe, raised error) on malformed input
  is NOT a vulnerability unless it crashes a server that should have kept running.

## Anything to leave alone
- Do not report that loading/compiling/evaluating untrusted code is unsafe.
- Do report that primitives that look safe or purport to be safe are actually unsafe.
  Propose better ways to algorithmically distinguish safe and unsafe primitives.
- Do not report missing input validation that only results in a raised Scheme error in safe code.
- v0.19 is a development branch: API breakage and incomplete ports are expected, not security issues.
