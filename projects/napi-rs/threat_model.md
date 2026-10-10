# napi-rs threat model

## Purpose and trust boundaries

napi-rs implements Rust bindings to Node-API and generates the glue, native addon
loaders and TypeScript declarations used by JavaScript applications. Its Rust
crates, procedural macros, CLI and JavaScript/WASI runtime are in scope. The
primary concern is whether safe Rust APIs and generated bindings remain memory
safe when called with adversarial JavaScript values and under garbage collection,
reentrancy, worker teardown and asynchronous completion.

Untrusted input can include JavaScript values, strings, buffers, typed arrays,
objects with getters/proxies, callbacks, promises and data originating from a
downstream application's network or file inputs. Track the application's real
input path: napi-rs itself is not a network service. A local JavaScript caller
often already has Node.js process privileges; demonstrate how a defect crosses
an actual trust boundary instead of assuming every JavaScript API is remotely
exposed.

Addon source code, build scripts, dependencies and native libraries intentionally
execute with the developer's privileges. Compiling an attacker-controlled Rust
project or loading an attacker-controlled native addon is not a sandbox escape.
CLI filenames, configuration, generated loader paths and package metadata still
deserve review wherever less-trusted data reaches filesystem writes, dynamic
loading or shell commands. Distinguish those paths from deliberate user commands.

## Priorities

- `crates/napi` and `crates/sys`: ownership, rooting and lifetimes across the
  Rust/Node-API boundary; buffers and typed arrays (including detachment and
  external memory); type validation, finalizers, references, closures, exceptions,
  threadsafe functions, async tasks and environment shutdown.
- `crates/macro` and `crates/backend`: generated validation, conversions, lifetime
  assumptions and unsafe glue reachable through ordinary safe addon code.
- `crates/async-runtime`, `async-runtime` and `wasm-runtime`: cancellation,
  resource cleanup, host protocol validation, worker lifecycle and shared memory.
- `cli` and `crates/build`: loader generation, binary selection and build/package
  operations, including path handling and injection where input is not already
  explicitly trusted executable code.
- `examples` and test fixtures provide reproducers and regression harnesses.
  Demonstrate library defects through them; example-only deliberate unsafe misuse
  is not automatically a vulnerability of the library's safe API.

Node.js, V8, Rust, emnapi and other dependencies are separate upstream projects.
Report flaws in napi-rs's use of them here; clearly attribute dependency-only
issues. CI credentials and publishing services are not provided in this image.
Do not contact external systems to demonstrate a finding.

## Build and offline tests

The image contains the full checkout at `/src`, Node.js 24, stable Rust, the
repository-pinned Yarn, native GNU/Linux addons, JavaScript build outputs, Cargo
debug symbols with frame pointers, and package caches. Cargo.lock is generated
during image creation because the project does not commit one; keep it when
rebuilding the same image. Run from `/src` with networking disabled:

```sh
yarn build
yarn workspace @examples/napi build
yarn workspace @examples/compat-mode build
yarn workspace @examples/custom-async-runtime build
yarn workspace @examples/shared-async-runtime build
cargo test --offline --workspace
cargo test --offline -p napi --features tokio_rt,async-runtime
cargo test --offline -p napi --features async-runtime
yarn workspace @napi-rs/async-runtime test
yarn workspace @napi-rs/wasm-runtime test
yarn workspace @examples/compat-mode test
yarn workspace @examples/custom-async-runtime test
yarn workspace @examples/napi exec node --import @oxc-node/core/register ../../node_modules/ava/entrypoints/cli.js --concurrency=2 '__tests__/**/*.spec.{ts,cts,js,cjs,mjs}' '!__tests__/async-exit.spec.ts'
yarn workspace @napi-rs/cli exec node --import @oxc-node/core/register ../node_modules/ava/entrypoints/cli.js --concurrency=2 'src/**/__tests__/**/*.spec.ts' '!src/api/__tests__/new.spec.ts' '!src/api/__tests__/create-npm-dirs.spec.ts'
yarn workspace @napi-rs/cli exec node --import @oxc-node/core/register ../node_modules/ava/entrypoints/cli.js --concurrency=2 src/api/__tests__/new.spec.ts --match='should fail*' --match='dry run should not create any files' --match='generated WASI binding pattern matches every generated artifact name'
yarn workspace @napi-rs/cli exec node --import @oxc-node/core/register ../node_modules/ava/entrypoints/cli.js --concurrency=2 src/api/__tests__/create-npm-dirs.spec.ts --match='!should *WASM targets*' --match='!should intersect mixed node engine ranges with the WASI minimum'
```

The native addon is at `examples/napi/example.linux-x64-gnu.node`, with its
generated loader at `examples/napi/index.cjs`; compatibility examples are in
`examples/napi-compat-mode`. Rust outputs are in `target/debug`.

This environment exercises native Linux x86-64. It does not claim the full
upstream platform matrix: Electron, Bun, browser tests, other CPU/OS targets,
WASI execution and nightly sanitizers need additional runtimes/toolchains.
The native `async-exit.spec.ts` test fetches GitHub and is explicitly excluded
offline. CLI `e2e/cli.spec.ts` installs packages into fresh temporary projects via
the npm registry and is excluded from the offline CLI commands. Two CLI source
files run separately with narrower selection: `new.spec.ts` includes its seven
offline validation/dry-run tests but excludes thirteen template clone/fetch
tests; `create-npm-dirs.spec.ts` includes nine tests (including local registry
fixtures) but excludes six tests matching `should *WASM targets*` and the
`should intersect mixed node engine ranges with the WASI minimum` test; all seven
fetch live npm metadata. All other CLI source tests remain included. The suites
retain upstream skips, including macOS ARM64-only GC tests and WASI tests when
WASI binaries are absent. These are execution exclusions, not exclusions from
code review or from reporting defects with an applicable reproducer.

## Assessing and reporting findings

Explain attacker control, reachable API, deployment assumptions and impact.
Memory corruption, use-after-free, double free or data races through safe APIs
are high priority; provide a minimal Node.js/Rust reproducer and evidence of the
invalid access. Rate critical only when demonstrated exploitability and realistic
exposure justify it, rather than from an unsafe block alone. Separate process
crashes, hangs and resource exhaustion from code execution, and assess severity
according to reachability and impact. A normal type error or documented panic
from violated unsafe preconditions is not itself a safe-API security defect.

Include exact versions, features, build commands and reproduction commands.
Prefer small regression tests and fixes that preserve Node-API compatibility,
cross-platform behavior and public API semantics. Record required preconditions,
failed reproduction attempts and uncertainty rather than overstating impact.
