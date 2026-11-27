# Threat model

This follows webpack's published threat model,
<https://github.com/webpack/security-wg/blob/main/docs/threat-model.md>.

## What this project does and where untrusted input enters

tapable is the small plugin/hook library at the core of webpack. A library author creates hooks
(`new SyncHook(["compilation", "params"])`, `AsyncSeriesHook`, `SyncWaterfallHook`, `HookMap`,
`MultiHook`, ...), plugins register callbacks with `hook.tap`, `tapAsync` and `tapPromise`, and the author
fires the hook with `call`, `callAsync` or `promise`. webpack, webpack-dev-server, enhanced-resolve and many
other tools call it in-process, with the developer's privileges, on every build.

On the first call after the taps or interceptors change, `lib/HookCodeFactory.js` (with the per-hook
factories in `lib/Sync*Hook.js` and `lib/Async*Hook.js`) builds the source of a dispatcher function and
compiles it with `new Function`. Tap functions, tap objects and interceptors are referenced by array index.
The hook's argument names are spliced into the generated source verbatim.

**Under webpack's threat model, every input tapable handles is trusted.** That covers:
- hooks and their argument names;
- taps and tap options (`name`, `stage`, `before`);
- interceptors;
- `HookMap` keys;
- the values passed to `call`.

They all come from webpack, plugins, loaders, configuration or the project, which webpack trusts. tapable
takes no network input of its own. A finding that needs control of any of these is not a vulnerability.

The one case that could matter is a webpack dev tool passing untrusted network data straight into a hook
call or a `HookMap` key, where tapable then mishandles it: generated code interpreting a value as code, or a
key polluting `Object.prototype`. A report must show such a path concretely.

Bugs are still worth reporting as robustness issues: dispatch control flow that skips a tap, calls a
callback twice, or loops, with ordinary plugin code. These are not security vulnerabilities under webpack's
model; they are rated Low and handled as normal bugs.

## Components that matter most / least

- Most: `lib/HookCodeFactory.js` (code generation and the series/looping/parallel control flow) and the
  `content` implementations in the `lib/Sync*Hook.js` and `lib/Async*Hook.js` files; then `lib/Hook.js`
  (tap registration, `_insert` ordering, interceptors) and `lib/HookMap.js`.
- In scope: all of `lib/` and the published typings in `tapable.d.ts`.
- Out of scope: `test/`, `benchmark/`, `.changeset/`, `.github/`, and the repository tooling. These are
  tests, benchmarks and release tooling.
- Out of scope: other webpack-organization repositories and tapable's dev dependencies. A bug in a consumer
  is in scope here only when it is caused by tapable doing something its documentation (`README.md`) does
  not describe.

## How to exercise it

- The image has the repository at `/src` with all dependencies installed by `npm ci`. There is no build
  step: `require("/src/lib")` is the package as published.
- `npm test -- --ci` (Jest, about 140 tests) runs everything, offline, in well under a minute.
  `npx jest test/HookCodeFactory.test.js` runs a single file. `test/HookCodeFactory.test.js` and the
  snapshots in `test/__snapshots__/` show the exact generated source for each hook type, and
  `test/HookTester.test.js` drives every hook type through the same scenarios.
- A reproducer is a short Node.js script that requires `/src/lib`, builds a hook, taps it and calls it, and
  prints the outcome. To inspect the generated dispatcher, call the hook once and print
  `hook.call.toString()`.

## How you rate severity

- **Critical:** a value from untrusted network data, passed by a webpack dev tool with default or documented
  options to `call`/`callAsync`/`promise` or as a `HookMap` key, reaching the source compiled by
  `new Function`.
- **High:** prototype pollution of the host process from such network data.
- **Medium:** none expected.
- **Low:** robustness bugs that are not security vulnerabilities under webpack's model:
  - generated control flow that skips taps, runs a tap twice, invokes a callback twice or reports success
    after an error, with ordinary plugin code;
  - crashes, stack overflows or quadratic behavior from many taps.
- Not a vulnerability:
  - anything that needs control of a plugin, an interceptor, tap options, a hook's argument names, or the
    values webpack derives from configuration, sources or `node_modules`;
  - `new Function` itself (it is the design);
  - a `SyncLoopHook`/`AsyncSeriesLoopHook` looping forever because a tap keeps returning a value
    (documented behavior);
  - incompatibility with a Content Security Policy that forbids `unsafe-eval`;
  - Node.js or OS bugs.

## Anything to leave alone

- Vulnerabilities in consumers (webpack, dev-server, loaders, plugins) that only use tapable to dispatch.
  Report those to the consumer.
- CVEs in dev dependencies. None of them ship in the published package, whose `files` are `lib` and
  `tapable.d.ts` and which has no runtime dependencies.
- Performance regressions measured by `benchmark/`.
- Compatibility with Node.js versions older than the ones in `.github/workflows/test.yml`.

## How reports should look

Give a standalone reproducer that runs with `node` against `/src/lib` and show its output, including the
generated source from `hook.call.toString()` when code generation is involved. For anything above Low, also
name the webpack dev tool and the network request that delivers the value to tapable. Otherwise label it as
a robustness bug. A proposed patch against `lib/` is welcome, ideally with a test in the matching
`test/*.test.js` file and updated snapshots (`npx jest -u`). Plain text or Markdown.
