# Threat model

<!-- For the OSS Scanner. Free text; the scanner reads it before it starts. -->

## What this project does and where untrusted input enters

Spin is a framework for building, distributing and running serverless WebAssembly applications: the `spin` CLI
(src/) and a runtime (crates/) built on Wasmtime and the WebAssembly component model. An application is a
`spin.toml` manifest naming one or more components and the triggers that invoke them. `spin up` starts an HTTP
server (crates/trigger-http) or a Redis subscriber (crates/trigger-redis) and runs a component instance for each
request or message with exactly the capabilities the manifest grants it. WASIp2 and legacy components get a fresh
instance per request; WASIp3 components (`wasi:http/handler@0.3.0`, the default world) are reused for up to 128
requests, 16 at a time, in one store (crates/trigger-http/src/lib.rs, server.rs), so host code multiplexes the
bodies, streams and futures of concurrent requests through one instance.

A component is the sandboxed, potentially hostile party, and the host code in this repository is the boundary
around it: `spin up -f <registry reference>` runs applications other people pushed; applications compose
third-party components from registries (`spin deps`, HTTP middleware) that run with the capabilities the manifest
grants; and embedders rely on crates/factor-* for the capability checks. One `spin` process runs one application.
The embedders are SpinKube's containerd-shim-spin (one application per pod inside a container, pinned to a Spin
release, listening on 0.0.0.0:80 behind a Kubernetes ingress) and Fermyon's separate production runtime behind
Fermyon Wasm Functions / Akamai Functions, which is multi-tenant and depends on a subset of Spin's crates but is not
this repository's HTTP trigger. The February 2026 advisory affected "all embedders of Spin" running untrusted
content, so a bug in a shared crate reaches those hosts.

Untrusted input enters at:

- **Inbound HTTP** to the server `spin up` runs (crates/trigger-http: server.rs, headers.rs, wasi.rs, wasip3.rs,
  wagi.rs, spin.rs; routing in crates/http and crates/routes). Anyone on the Internet sends these. Everything in the
  request is attacker-controlled, including `Host`, forwarded-for headers and any header whose name collides with
  the `spin-*` metadata headers Spin synthesises (headers.rs). Host code derives values from the request and must
  never let them steer a host-side decision: CVE-2024-32980 (GHSA-f3h7-gpjj-wcvh, Critical 9.1) was the inbound
  `Host` header being used as the origin of `self` requests. The self-request origin and the service-chaining target
  come from the bound address and the manifest. For Wagi, every header becomes an `HTTP_*` environment variable and
  the query string becomes argv (crates/http/src/wagi, crates/trigger-http/src/wagi.rs). Redis messages to
  crates/trigger-redis are the same for a Redis-triggered application.
- **WebAssembly components**, and everything they do through the host interfaces Spin implements: WASI
  (crates/factor-wasi, including sockets), outbound HTTP, Redis, MySQL, PostgreSQL and MQTT (crates/factor-outbound-*),
  key-value stores (crates/factor-key-value, crates/key-value-*, including `wasi:keyvalue`), SQLite
  (crates/factor-sqlite, crates/sqlite*), variables (crates/factor-variables, including `wasi:config`), LLM inference
  (crates/factor-llm), telemetry (crates/factor-otel, `wasi:otel`), and the service-chaining path by which one
  component calls another (`*.spin.internal`). The legacy `fermyon:spin/http` outbound interface
  (crates/factor-outbound-http/src/spin.rs) and the legacy `fermyon:spin/inbound-http` executor
  (crates/trigger-http/src/spin.rs) are still linked for every component. A component must stay within what its
  manifest grants it: `allowed_outbound_hosts`, `files`, `key_value_stores`, `sqlite_databases`, `variables` and
  `ai_models`.
- **Composed third-party components**: `[component.X.dependencies]` and HTTP middleware are linked into the
  application component (crates/compose, crates/dependency-wit, src/commands/deps). Imports they are not allowed to
  `inherit` are satisfied by the deny adapter in crates/capabilities (a checked-in deny_adapter.wasm that refuses
  every call); it plugs the host interfaces it exports and leaves unknown imports for the host to satisfy. The WASI
  p1 adapters in crates/componentize/adapters are likewise Spin-shipped guest code that runs inside every
  wasm32-wasip1 application.
- **Responses from every backend** a component is allowed to reach: HTTP (crates/factor-outbound-http), Redis,
  MySQL, PostgreSQL, MQTT (crates/factor-outbound-*), the key-value and SQLite backends (crates/key-value-*,
  crates/sqlite-*, including libSQL over HTTP), remote LLM endpoints (crates/llm-remote-http), with TLS in
  crates/factor-outbound-networking/src/tls.rs. Host code parses these and, for SQL rows and keys, streams them into
  the guest through Spin's own `StreamProducer` (crates/wasi-async). CVE-2026-27887 (GHSA-mv4f-6ffm-32wx, Moderate
  6.9) was unbounded host-side buffering of such responses; the 128 MiB cap `MAX_HOST_BUFFERED_BYTES`
  (crates/world/src/lib.rs) is the fix, applied to the database, key-value, LLM and legacy HTTP interfaces but not to
  the legacy executor's and Wagi's request-body buffering.
- **Registry artifacts**: `spin registry pull`, `spin up -f <registry reference>` and `spin registry push`
  (crates/oci: client.rs, loader.rs, validate.rs). Whoever pushed the artifact, and whoever controls a mutable tag,
  is untrusted. Layer and locked-app bytes are verified against their digests; artifacts are not signed. The locked
  application (`spin.json`) is then parsed by host code, in the CLI and inside SpinKube pods: component ids, `files`
  paths (placed under `/assets/<id>/`), host requirements and chaining targets from it are untrusted input.
  The user's registry credentials (registry-auth.json, Docker credential helpers; crates/oci/src/auth.rs) are an
  asset: `spin registry push` must send them to the registry alone, never to a host a redirect names.
- **Components and WIT packages fetched for `dependencies`, `spin deps add` and target environments**
  (crates/loader/src/local.rs `load_registry_source` and `load_http_source`, src/commands/deps, crates/environments):
  `wasm-pkg-client` discovers registries through `https://<host>/.well-known/wasm-pkg/registry.json`, re-resolves
  version requirements on every `spin up` (there is no lockfile for component dependencies), verifies only the
  sha256 the registry itself publishes, and reads credentials from the wasm-pkg config file; environment
  definitions are fetched by URL and the environment catalogue is a git clone of spinframework/spin-environments.
  The registry and the network are untrusted; the fetched bytes are parsed by wasm-tools and wac before Wasmtime
  sees them. Remote component sources (`source = { url, digest }`) are sha256-verified (crates/loader/src/http.rs).
- **Plugins and templates** fetched over the network: `spin plugins install` (crates/plugins: manager.rs, store.rs,
  manifest.rs, git.rs, catalogue.rs; the index is a git clone of github.com/spinframework/spin-plugins, or a manifest
  given with `--url`/`--file`) and `spin templates install --git|--tar` (crates/templates: git.rs, source.rs,
  writer.rs). The user chooses the index, manifest or repository; the download host and the archive contents are
  not trusted: archives must be unpacked safely, the manifest's sha256 must be enforced before unpacking, and the
  manifest's `name` becomes a directory under the plugin store.
- **Precompiled code**: with the `unsafe-aot-compilation` cargo feature (crates/trigger/src/loader.rs), Spin loads
  Wasmtime-precompiled components with `Component::deserialize_file`, which Wasmtime documents as arbitrary code
  execution if the bytes are untrusted. The SpinKube shim enables it and gates it on its own precompile cache. This
  image does not build the feature, but any path by which registry-origin bytes could reach it is in scope.
  `spin up` also uses Wasmtime's on-disk compile cache unless `--disable-cache`; that cache is the operator's.

Trusted: whoever runs `spin up` and writes spin.toml and runtime-config.toml on that machine, the files they mount
(the manifest's `files` and `exclude_files` globs are operator-authored; the loader's path checks are lexical), and
the environment and secrets they provide, including a `.env` file in the current directory. `spin build` runs the
manifest's `command` by design; `spin doctor` may download and run toolchain installers; `spin <unknown-subcommand>`
runs an installed plugin binary with the user's environment; `runtime-config.toml` is read only when
`--runtime-config-file` names it. In hosted deployments these are two parties: the application developer writes
spin.toml (baked into the image or pushed with `spin registry push`), and the platform writes runtime-config.toml
(spin-operator generates it from the SpinApp resource). A manifest is still not a host trust boundary for this
repository, except for the locked-application content that hosted code parses (see High). The host's CA store, the
Wasmtime compilation cache directory and the caches under $XDG_CACHE_HOME/spin are the operator's. The hosting
platform's own code (Kubernetes, runwasi, Akamai's control plane) is outside this repository.

## Components that matter most / least

Most, in this order:

1. The permission checks between a component and the outside world. crates/outbound-networking-config
   (allowed_hosts.rs, blocked_networks.rs): `allowed_outbound_hosts` is matched on the URL's host name, scheme and
   port, never on resolved addresses; wildcards expand to the application's own component ids for `*.spin.internal`;
   `self` and `self.alt` are the server itself. IP-level policy is only the operator's `[outbound_networking]
   block_networks` runtime config (crates/factor-outbound-networking/src/runtime_config), applied to the resolved
   addresses just before connecting; it must be honoured on every outbound path (wasi:http and the legacy HTTP
   interface, WASI sockets, Redis, MySQL, PostgreSQL, MQTT). TLS is not one stack: the `client_tls` runtime
   configuration (platform roots through rustls-platform-verifier plus webpki roots, custom roots, mTLS;
   crates/factor-outbound-networking/src/tls.rs) applies only to outbound HTTP; Redis, MySQL and PostgreSQL use
   native-tls with system roots, MQTT the spinframework/rumqtt fork's rustls with platform roots, libSQL hyper-rustls
   with webpki roots, and `spin registry` native-tls. crates/factor-wasi: preopened directories are read-only unless
   `--allow-transient-write`; raw sockets are authorised by IP literal or CIDR only, never by host name, cannot
   listen, and guest DNS through `wasi:sockets/ip-name-lookup` is never enabled. crates/factor-key-value and
   crates/factor-sqlite (store and database labels; guest SQL runs in the bundled SQLite C library inside the host
   process, where the authorizer in crates/sqlite-inproc forbids `ATTACH` of host files), crates/factor-variables
   (which variables each component may read), and crates/capabilities (the deny adapter that enforces `inherit` for
   dependencies and middleware; its export list must cover every interface version Spin links).
2. The HTTP trigger and the host side of wasi:http (crates/trigger-http, crates/http, crates/routes,
   crates/factor-outbound-http): request parsing and routing; the host-provided request metadata headers
   (`spin-client-addr`, `spin-full-url`, `spin-path-info`, `spin-matched-route` and the other `spin-*` headers in
   headers.rs), which must not be forgeable by the client; request and response bodies and streaming; Wagi
   (CGI-style) execution; outbound requests including self requests and service chaining (an interceptor in
   outbound_http.rs that runs after the allow-list check, calls the target component directly with a synthetic route,
   so it bypasses the router, reaches `route = { private = true }` endpoints at any path and reports the client as
   0.0.0.0:0: by design); and the WASIp3 path: instance reuse and request cancellation in server.rs
   (`HttpWorkerState`, `HttpHandlerState`), the p2-on-p3 bridge in wasi.rs (`handle_2026_03_15`), the WIT-version
   shims that re-wrap streams and futures (crates/factor-wasi/src/wasi_2026_03_15.rs,
   crates/factor-outbound-http/src/wasi_2026_03_15.rs), Spin's `StreamProducer` (crates/wasi-async) and resource
   table (crates/table). The classes to look for there are the ones in Wasmtime's 2026 advisories: a host-created
   stream or future viewed with a different payload type, guest-controlled host allocation through stream writes or
   list arguments, handles or raw reps reused across resource types, a store kept in use after a trap, a `call_async`
   future dropped on timeout, and one request's body or stream delivered to another request's task. Outbound HTTP
   connections are pooled per application while TLS configuration (roots, client certificates) is selected per
   component and host (crates/factor-outbound-networking/src/tls.rs), so a pooled connection established under one
   component's identity being reused for another is a boundary to check.
3. Host code that unpacks untrusted archives and files: crates/oci (artifact layers written to the local cache, the
   `files` they carry, and `resolve_component_content_refs` in loader.rs, which also runs inside SpinKube pods on
   tenant-supplied artifacts; client.rs pre-allocates from registry-declared sizes), crates/plugins (plugin tarballs,
   unpacked with permissions preserved into a directory named by the manifest), crates/templates (template
   repositories and tarballs rendered to disk), crates/loader (asset copying and `files` mounts; registry-sourced apps
   are additionally guarded by `is_safe_to_join`), and the dependency fetch in crates/loader/src/local.rs.
4. How Spin configures Wasmtime: crates/core (engine configuration: epoch interruption is enabled but `spin up` arms
   no deadline, there is no per-instance memory limit unless `SPIN_MAX_INSTANCE_MEMORY` or runtime config sets one,
   the pooling allocator allows 4 GiB per memory and `SPIN_MAX_INSTANCE_COUNT` (1000) instances, every default
   Wasmtime proposal stays enabled including GC, exceptions, tail calls, threads, memory64 and component-model
   async, and the remaining limits are Wasmtime's built-in ones: 100,000 component handles, 128 MiB hostcall fuel,
   1,000,000 resources, 512 KiB Wasm stack, with host functions running on the 1.5 MiB left of the 2 MiB async
   stack, where exhaustion aborts the process); crates/trigger (including the `unsafe-aot-compilation` loader);
   crates/factors, crates/factors-executor (store creation, per-instance state reset between requests, and the
   `cpu-time-metrics` call hook), crates/runtime-factors; the three WASI snapshot layers Spin implements itself
   (crates/factor-wasi/src/wasi_2023_10_18.rs, wasi_2023_11_10.rs, wasi_2026_03_15.rs, sockets.rs and their
   counterparts in crates/factor-outbound-http); and component composition in crates/compose, crates/capabilities
   and crates/componentize. No WASI p1 host functions are linked: wasm32-wasip1 modules are componentized with the
   prebuilt adapters in crates/componentize/adapters, which run inside the sandbox, so p1-host advisories do not
   apply. CI checks deny_adapter.wasm by its WIT, not its bytes. Start with the WASIp3 and component-model-async
   paths: that is where Wasmtime's 2026 advisories concentrate.
5. Everything else a component can call: the remaining crates/factor-* crates (crates/factor-outbound-mqtt hands
   the guest's URL to Spin's own fork of rumqtt, which Spin maintains), crates/connection-semaphore (connection
   quotas), crates/tls, crates/llm-local (the prompt, the inferencing parameters and the embeddings input are the
   component's and enter native inference code under one engine lock per application), and the key-value
   (crates/key-value-aws, -azure, -redis, -spin), sqlite and variables provider crates (the Azure ones are the legacy
   SDK line, which receives no upstream fixes). Embedders isolate applications through store labels and the `app_id`
   partition keys these providers take; the CLI keeps default stores per application under `.spin/` and shares state
   between applications only when the operator points them at the same state directory or backend.

Least, but in scope: the CLI's own commands (src/commands, crates/build, crates/doctor, crates/terminal,
crates/environments, crates/dependency-wit) and crates/telemetry (an inbound `traceparent` is propagated to outbound
requests; collectors come from `OTEL_*` environment variables).

Out of scope for this scan: bugs inside the Bytecode Alliance crates (wasmtime, wasmtime-wasi, wasmtime-wasi-http,
cranelift-codegen, wasm-tools, wac): report those to the Bytecode Alliance. Their policy counts only tier-1 platforms
(x86_64 Linux-gnu, macOS, Windows) while Spin also ships aarch64 Linux and musl binaries, and it does not count
compile-time denial of service (Low here). In scope: Spin's use and configuration of those crates, which the Bytecode
Alliance leaves to embedders (limits and deadlines, which proposals are enabled, trusting values a guest returns,
keeping a store in use after an error, the `deserialize` trust boundary, the snapshot layers and the p3 glue), and the
pinned version: if Cargo.lock names a release of one of those crates with a published advisory whose affected path
Spin exposes, report it as a dependency finding at the advisory's own severity (Wasmtime patches only the current
release, the previous one and its LTS lines, so a stale minor cannot be patched in place). The same rule applies to
every other dependency that handles input from a component, a request or a registry (the bundled SQLite, the rumqtt
fork, rust-oci-client, libsql, candle and tokenizers, the cloud SDKs): the bug is upstream's, the pin is Spin's. Also
out of scope: the language SDKs (Rust, JavaScript, Python, Go, .NET), the plugins kept in other repositories
(including the trigger plugins sqs, mqtt, cron and command, spin-test, and the kube, aka, cloud and platform plugins),
the SpinKube repositories (containerd-shim-spin, spin-operator, runtime-class-manager, runwasi); docs/, examples/, the
template content under templates/, hack/, scripts/, deploy/, supply-chain/; test-only code (tests/,
crates/factors-test, crates/test-codegen-macro, crates/ui-testing); and the `extern-dependencies-tests`, `llm-metal`,
`llm-cublas` and `experimental-wasm-features` cargo features, which this image does not build. The WIT contracts under
wit/ and crates/world, and the CLI's handoff to external trigger plugins (crates/trigger/src/cli.rs), are in scope.

## How to exercise it

Everything is built in the dev profile with default features. The `spin` binary is /src/target/debug/spin and is on
PATH. cargo runs offline (CARGO_NET_OFFLINE=true) against a cache that holds every crate the workspace, the test
components and the Rust templates need, so rebuilding after a patch works, as does `spin build` of a Rust app.
Debug info is line tables only (file and line in backtraces and under gdb, no variables): full debug info makes the
test binaries several times larger. For full debug info in one crate, add `[profile.dev.package.<crate>]` with
`debug = 2` to $CARGO_HOME/config.toml and rebuild; only that crate and what links it rebuild.

- Run an application: `cd /src/examples/http-rust && spin up --listen 127.0.0.1:3000` (its component is already
  built), then `curl http://127.0.0.1:3000/hello`. To make one from a template, first install the repository's
  templates with `spin templates install --dir /src --update` (the directory that holds templates/), then
  `spin new -t http-rust --accept-defaults myapp`, `cd myapp`, `spin build` and `spin up`.
- Test applications and components: the applications under tests/testcases/ and tests/runtime-tests/tests/ (each a
  spin.toml), and the guest components under tests/test-components/components/, compiled for wasm32-wasip1 into
  target/debug/build/test-components-*/out/wasm32-wasip1/debug/*.wasm. Each component exercises one host interface
  (outbound HTTP, key-value, SQLite, sockets, variables, wasi:http, ...), and is the quickest way to try a
  behaviour from the guest side: copy one, change it, `cargo build --target wasm32-wasip1` it, and point a spin.toml
  at it. tests/test-components/README.md explains the layout. The outbound-http component uses the legacy
  `fermyon:spin/http` interface and integration-wasi-http-v0.2.0-rc-2023-11-10 the 2023 snapshot, which is how to
  exercise the legacy paths.
- Unit tests: `cargo test --workspace -- --skip integration_tests --skip runtime_tests` (what `make test-unit`
  runs). The whole-workspace selection and the root package on its own (plain `cargo test`, `cargo test --test
  ...`) are both prebuilt. Selecting one crate with `-p` makes Cargo re-resolve features for it and recompile its
  dependencies: seconds for a leaf crate such as spin-outbound-networking-config, minutes for one that pulls in
  Wasmtime. To run one crate's tests without that, filter by name across the workspace instead, as in
  `cargo test --workspace -- allowed_hosts`.
- Runtime tests (a manifest plus components, run against the runtime in-process): `cargo test --test runtime --
  --skip conformance_tests --skip llm`. `conformance_tests` downloads its cases from GitHub and cannot run offline;
  `llm` asserts the error of a build without the `llm` feature (the Makefile runs these tests with
  `--no-default-features`) and fails under the default features built here. Tests whose `services` file names a
  Docker service (redis, mysql, postgres) are compiled out without the extern-dependencies-tests feature.
- Integration tests (the CLI, end to end): `cargo test --test integration -- --nocapture`. The tests that need
  Docker or other language toolchains (the Go, Zig, Grain, Python, PHP and JavaScript templates; a registry) are
  compiled out. Offline, 43 of the 47 pass as built. `http_rust_template_smoke_test` clones the templates from
  GitHub first and cannot pass without a network. `test_timer_trigger` compiles examples/spin-timer on its first
  run (its crates are cached; the compile took four minutes on four cores and leaves a 5 GB target directory
  there). `http_request_deadline_interrupts_wasip2_loop` and `legacy_apps` are timing-bound (two seconds, two
  minutes) and fail when run in parallel with the rest in this debug build; run them alone, with `--test-threads=1`.
  The Makefile runs the suite in the release profile; the dev profile only takes longer.
- tests/README.md, tests/runtime-tests/README.md and tests/testing-framework/README.md describe the test harness;
  AGENTS.md and CONTRIBUTING.md describe the repository.

## How you rate severity

The question for any finding is which trust boundary above it crosses, and from where. Rate for `spin up` running
one application; platform multipliers are the platform's. Deployment or manifest preconditions (a particular
`allowed_outbound_hosts` entry, an ingress that passes `Host`, a `self` or wildcard grant) do not lower the band:
CVE-2024-32980 needed three such conditions and was rated Critical 9.1.

- **Critical**: a component reaches something its manifest does not grant it: a host name, scheme or port outside
  `allowed_outbound_hosts` with no cooperation from an allowed peer (a redirect followed without a second check, a
  legacy interface that skips a check, a service-chaining target not granted, a self request that leaves this
  server); an address inside a configured `block_networks` range (through a DNS answer, an IP-literal URL, an
  IPv4-mapped IPv6 address or a pooled connection); a file outside its `files` mounts (on SpinKube the mount is the
  node's content cache); another component's or application's key-value store, database, variables or files
  (through store labels, `app_id` partitions or a shared backend). A dependency or middleware component reaching a
  host interface its `inherit` setting does not grant. A component running native code, corrupting host memory or
  otherwise escaping the Wasmtime sandbox, whether through host code in this repository, through a Spin-maintained
  fork or prebuilt artifact, or through guest input Spin hands to a dependency (SQL to the bundled SQLite, prompts to
  the local LLM, a URL to the MQTT client). Native code execution through a precompiled artifact or compile-cache
  entry that untrusted input can supply. Remote code execution on the host from an inbound request, a
  registry artifact, a plugin or a template.
- **High**: an `allowed_outbound_hosts` bypass that needs an unusual but plausible deployment (Host-based routing in
  front of Spin, an allowed host acting as a proxy); files written outside the intended directory when pulling an
  artifact, installing a plugin or a template, or copying `files` (path traversal, symbolic links, archive entries,
  a plugin or component name used as a path); a component id, `files` path or host requirement from a locked
  application or registry artifact that escapes `/assets/<component>/` or the cache; a plugin installed without its
  checksum being enforced; secrets (variables, runtime-config credentials, the host process environment: on SpinKube
  every application variable is a `SPIN_VARIABLE_*` environment variable) disclosed to a component not granted them,
  to another application, or in logs or error responses; HTTP request smuggling, desynchronisation or response
  splitting through the trigger; a request routed to the wrong component; a client-forged value in a host-provided
  request header (`spin-client-addr` and the other `spin-*` headers); a component writing, truncating, renaming or
  linking inside a read-only `files` mount; one request's body, stream, headers or variables delivered to another
  request in a reused WASIp3 instance; a pooled outbound connection carrying one component's TLS identity reused for
  another; a crash or unbounded allocation reachable from an unauthenticated inbound request with no component
  cooperation.
- **Medium**: a component crashing, hanging or exhausting the runtime beyond the limits in force (a panic in host
  code reachable from the guest, an unbounded allocation such as CVE-2026-27887 or a path the 128 MiB cap does not
  cover, a guest that keeps running after a configured deadline or timeout, host recursion over guest-controlled
  structure), resources leaked per request or per instance (open backend cursors, channels, sockets or handles that
  outlive the request), a registry-declared size that crashes a pull, and guest-set outbound header inconsistencies
  that do not reach a disallowed host; a process abort or native stack overflow reachable from a guest or a
  request; a runaway local LLM generation holding the application's engine lock. Findings in the deprecated Wagi
  executor are at most Medium. Note the baseline: `spin up` arms no execution deadline (`--request-timeout` is
  WASIp3-only and only expires the response; the guest keeps running) and sets no per-instance memory cap unless
  `--max-instance-memory` or runtime config gives one, so a guest that runs forever or grows to 4 GiB is expected
  behaviour, not a finding. A panic contained to one request is Low unless it leaks an instance or a permit; a
  `debug_assert!` that only fires in this dev-profile build is not a finding.
- **Low**: problems that need a malicious spin.toml, runtime-config.toml or plugin manifest that the person running
  `spin up` wrote or installed on purpose (`--url`, `--file`; not a locked application pulled from a registry or
  loaded by an embedder), or a hostile local user on the machine running the CLI; pathological components that make
  compilation or composition slow or large; a Spin default that leaves a Wasmtime proposal enabled which Spin guests
  cannot legitimately use; telemetry injection or flooding through `wasi:otel`; Wagi's `HTTP_*` environment (the
  `Proxy` header becomes `HTTP_PROXY`).

Not vulnerabilities: anything that needs control of spin.toml, runtime-config.toml, the mounted files, the
environment or the host's filesystem (the operator's own trust), except the locked-application content above;
`spin build` running the manifest's `command`; a component using a capability its manifest grants; an allowed host
name resolving to a private or cluster-internal address when `block_networks` is not configured; a
`spin_manifest_version = 1` manifest receiving `redis://*:*`, `mysql://*:*`, `postgres://*:*` and
`http://*:*`, `https://*:*`, `http://self` from the `allowed_http_hosts` compatibility conversion
(crates/manifest/src/compat.rs); service chaining reaching private routes at any path; state shared between
requests of one component under WASIp3 reuse (the guest's own responsibility; another component's state is
Critical); `/.well-known/spin/info` and `/.well-known/spin/health` being unauthenticated; the `SPIN_*` environment
knobs; raw sockets being authorised by IP literal or CIDR only; a component denying service to itself or its own
backend; timing, cache and Spectre-class side channels between components or tenants (Wasmtime's mitigations are
partial by design and `wasi:clocks` gives guests a fine timer; a Spin host-side cache keyed on another component's
data would be a finding, a timing difference would not); memory corruption confined to a component's own linear
memory, including in test components, examples and SDK code, except in the guest code Spin ships in this
repository (crates/componentize/adapters, crates/capabilities/deny_adapter.wasm) when it lets a guest confuse the
host; the operator's compile cache, precompiled artifacts and credential files being writable by the same local
user; compile-time slowness of Wasmtime, wasm-tools or wac on a pathological component (Low at most, and not fixed
upstream); findings in Wasmtime proper.

SECURITY.md describes the supported versions; scan `main`.

## Anything to leave alone

- Tests, the testing framework, examples and template content are not production code: a traversal or a crash
  there is not a finding (a template that grants `*://*:*` is at most a documentation note).
- The local LLM backend (crates/llm-local) loads model and tokenizer files the operator placed under the state
  directory's ai-models; a malformed file there is the operator's own. The inputs a component supplies are not (see
  Medium).
- crates/capabilities/deny_adapter.wasm and crates/componentize/adapters/*.wasm are checked-in build artifacts;
  their contents are in scope only where they let a guest confuse the host.
- Please do not report that `spin build`, `spin plugins`, `spin templates` and `spin doctor` run, fetch or install
  what the user asked for, that `spin up` without TLS serves plain HTTP, or that `spin up` listens on 127.0.0.1:3000
  by default (the SpinKube shim listens on 0.0.0.0:80 by design).

Reports: a reproducer as a Spin application (a spin.toml plus a small component, ideally in the style of
tests/test-components/components/ or tests/runtime-tests/tests/) with the `spin up` and `curl` commands, or a unit
test in the crate concerned. For WASIp3 findings, say whether the reproducer needs instance reuse
(`--max-instance-reuse-count`, `--max-instance-concurrent-reuse-count`) and whether a deadline changes the outcome.
Patches as a change against `main` with a test under tests/runtime-tests/tests/, in tests/integration.rs or in the
crate's own tests, formatted with `cargo fmt` and clean under `make lint`.
