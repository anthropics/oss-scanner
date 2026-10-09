# Threat model

## What this project does and where untrusted input enters

sccache is a ccache-like compiler cache written in Rust. The `sccache` binary wraps a compiler
invocation (C/C++, Rust, CUDA, HIP, MSVC, ...), hashes the inputs, and either returns a cached
artifact or runs the real compiler and stores the result. The same binary acts as a thin client
and as a long-lived per-user server that does the work. It also ships `sccache-dist`, a scheduler
and build server for distributed compilation.

Untrusted input enters in these places:

- **Cache contents.** Remote caches (S3, GCS, Azure, Redis, Memcached, WebDAV, GitHub Actions,
  OSS, COS) are often shared by many machines and CI jobs, and anyone with write access to the
  bucket can put entries there. Treat every entry read from storage as hostile. sccache unpacks
  entries (zip and compressed blobs, see `src/cache/cache_io.rs` and `src/cache/`) and writes the
  object files, dep files, stderr and so on to paths on disk. Path traversal or writing outside
  the expected output paths, symlink tricks, and memory corruption or panics while decoding are
  in scope. So are crashes and hangs on malformed entries. Note that a malicious entry can always
  hold a malicious *object file* for the expected output path. That is a known limitation of a
  shared cache with untrusted writers, not a finding on its own.
- **Cache key computation.** Two compilations that produce different output must not share a
  key. Anything that leaves out an input affecting the output (an argument, an env var, an
  included file, the compiler binary, `SCCACHE_BASEDIRS` normalization, preprocessor "direct
  mode" in `src/compiler/preprocessor_cache.rs`) so that an attacker can get their artifact
  served for someone else's compilation is in scope (cache poisoning).
- **Compiler command lines and source files.** The argument parsers in `src/compiler/` (`args.rs`,
  `gcc.rs`, `clang.rs`, `msvc.rs`, `nvcc.rs`, `rust.rs`, ...) parse arguments, response files
  (`@file`) and dep-info / preprocessor output written by the compiler. Build systems pass these
  from project files, so they can come from an untrusted repository. sccache must not run a
  command or write a file that the plain compiler invocation would not have.
- **The local client/server protocol** (`src/protocol.rs`, `src/server.rs`). The server listens
  on `127.0.0.1:4226` by default (or a Unix socket with `SCCACHE_SERVER_UDS`) and runs compilers
  with the argv, cwd and environment the client sends. There is no peer authentication, so on a
  multi-user host another local user can connect. Report problems in decoding these messages
  (crashes, excessive allocation). Report privilege issues only with a concrete multi-user
  scenario and an explanation of why it goes beyond the documented design.
- **Distributed compilation** (`src/dist/`, `src/bin/sccache-dist/`). The scheduler and build
  servers accept HTTP requests from clients and from each other, authenticated with tokens or
  JWTs (`DANGEROUSLY_INSECURE` exists and is out of scope). Build servers receive toolchain
  tarballs and input archives from clients and run the compiler inside bubblewrap with an overlay
  filesystem (`build.rs`) or a Docker container. Escaping the sandbox, writing outside the build
  directory while unpacking toolchains or inputs, authentication bypass, one client reading or
  tampering with another client's job or toolchain, and pre-auth crashes are all in scope. The
  client side must also treat results returned by a build server as untrusted (output paths in
  particular).
- **Configuration.** The config file and `SCCACHE_*` environment variables are trusted. Exposing
  credentials from config (cloud keys, dist tokens) in logs, stats output, error messages or
  network traffic to an unintended host is in scope.

## Components that matter most / least

- Most important: `src/cache/` (especially entry decoding and writing outputs), the cache key
  logic in `src/compiler/compiler.rs`, `c.rs`, `rust.rs` and `preprocessor_cache.rs`,
  `src/dist/` and `src/bin/sccache-dist/`, `src/server.rs` and `src/protocol.rs`.
- Also in scope: the per-compiler argument parsers, `src/lru_disk_cache/`, `src/util.rs`,
  `src/config.rs`, `src/dist/client_auth.rs` (OAuth flow with a local HTTP listener).
- Less important: `src/jobserver.rs`, the stats and CLI formatting code.
- Out of scope: `benches/`, `tests/` (fixtures and harness), `scripts/`, `snap/`, `docs/`,
  `flake.nix`, and third-party crates unless sccache uses them in an unsafe way.

## How to exercise it

- Everything is pre-built in `/src/target/debug`: `sccache` (all default storage backends and the
  dist client) and `sccache-dist`. Rebuild offline with `cargo build --offline --locked` and
  `cargo build --offline --locked --features dist-server --bin sccache-dist`.
- gcc, clang and rustc are installed so real compilations can be cached. A quick loop:
  `SCCACHE_DIR=/tmp/cache SCCACHE_START_SERVER=1 SCCACHE_NO_DAEMON=1 SCCACHE_LOG=debug ./target/debug/sccache`
  in one shell, then `./target/debug/sccache gcc -c tests/test.c -o /tmp/t.o` in another. The
  local disk cache in `SCCACHE_DIR` is the easiest way to plant crafted cache entries.
- `redis-server` and `memcached` are installed for testing those backends locally, for example
  `redis-server --daemonize yes` and `SCCACHE_REDIS_ENDPOINT=redis://127.0.0.1:6379`.
- Tests: `cargo test --offline --locked --lib --bins --tests -- --test-threads 1`. Integration
  tests start a real sccache server and must run one at a time. The `dist-tests` feature builds
  `tests/dist.rs`, which needs Docker and is not usable in this image.
- `sccache-dist` can be run locally with a token-auth scheduler and build server config (see
  `docs/Distributed.md`). The bubblewrap builder needs root or user namespaces.

## How you rate severity

- Critical: code execution on a machine that only *reads* from a shared cache (beyond receiving a
  malicious object file, see above), escaping the sccache-dist sandbox to run code on the build
  server host, or authentication bypass on the scheduler/build server leading to code execution.
- High: writing files outside the intended output paths from a cache entry or dist result;
  cache-key collisions that let an attacker serve their artifact for a different compilation;
  one dist client tampering with another client's builds; leaking cloud or dist credentials.
- Medium: denial of service of the sccache server or the dist scheduler/build server from
  untrusted input (panics, hangs, unbounded memory), and information leaks between dist jobs.
- Low: issues that need control of trusted configuration, or of the same user account that runs
  the sccache server.

## Anything to leave alone

- Do not report that the `DANGEROUSLY_INSECURE` auth modes are insecure.
- Do not report that a writer to a shared cache can store a bad object file for the matching key.
- Do not report that the configured compiler or a `SCCACHE_*` variable runs arbitrary programs;
  the user picked them.
- Do not report that the local server listens on TCP localhost by default; that is documented.
  Problems that follow from it (see above) are fine to report with a concrete scenario.
- Proposed patches should keep the cache key format stable unless the fix needs a change, and
  should say so when they change it (it invalidates every existing cache).
