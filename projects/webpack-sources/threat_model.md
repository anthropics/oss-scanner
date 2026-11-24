# Threat model

This follows webpack's published threat model,
<https://github.com/webpack/security-wg/blob/main/docs/threat-model.md>.

## What this project does and where untrusted input enters

webpack-sources is the library webpack, its loaders and its plugins use to represent generated code. A
`Source` holds code as a string or Buffer and can be asked for its text, size, hash and source map. The
classes in `lib/` compose:
- `RawSource` and `OriginalSource` wrap code.
- `SourceMapSource` wraps code plus a source map, optionally with an inner map to combine with it.
- `ConcatSource`, `PrefixSource` and `ReplaceSource` build new code out of other sources.
- `CachedSource` memoizes results.
- `CompatSource` adapts source-like objects, and `SizeOnlySource` only knows a size.

The library runs inside the build process, with the developer's privileges, and has no network, file system
or process access of its own.

**Under webpack's threat model, every input webpack-sources handles is trusted:**
- the calling code (webpack, loaders, plugins, configuration);
- source text and source maps, which come from the project's sources, loaders and `node_modules`;
- `CachedSource` data, which webpack writes to its own persistent cache.

webpack trusts all of these. webpack-sources takes no network input. So there is no known path for an
attacker to reach it, and a finding that needs control of any of these inputs is not a vulnerability.

Bugs are still worth reporting as robustness issues, as long as a real build could contain the input:
- a crash, hang or super-linear slowdown on source text or a source map;
- output code that differs from what the caller asked for;
- an output map that is malformed or points at the wrong source.

These are not security vulnerabilities under webpack's model; they are rated Low and handled as normal
bugs.

## Components that matter most / least

- Most:
  - map parsing and combining: `lib/SourceMapSource.js`, `lib/helpers/readMappings.js`,
    `lib/helpers/streamChunksOfSourceMap.js`, `lib/helpers/streamChunksOfCombinedSourceMap.js`;
  - map writing: `lib/helpers/createMappingsSerializer.js`;
  - the code that splices text: `lib/ReplaceSource.js`, `lib/PrefixSource.js`, `lib/ConcatSource.js`.
- In scope: all of `lib/`. `types/` and `types.d.ts` are generated declarations.
- Out of scope: `test/`, `benchmark/`, `.changeset/`, `.github/` and the lint/format configuration.
- Out of scope: other webpack-org repositories and devDependencies; the published package has no runtime
  dependencies.

## How to exercise it

- The image has the repository at `/src` with `npm ci` done and no build step: `require("/src")` loads the
  library directly. A reproducer is a single `node repro.js` script that builds sources from crafted
  strings or maps and prints `source()`, `map()` or `sourceAndMap()`; the `source-map` package in
  `/src/node_modules` (`SourceMapConsumer`) is handy for showing where an output mapping points.
- `node --require ./test/helpers/validate-mappings.js --test --test-reporter=dot "test/*.js"` runs the full
  suite (about 90,000 tests, a few minutes); pass a single file such as `test/SourceMapSource.js` for one
  class. Avoid plain `npm test`, which runs eslint and tsc first.
- `test/Fuzzy.js` composes every source class at random and is the best template for a differential
  reproducer. `npm run benchmark` is useful to show a super-linear slowdown against a normal-sized input.

## How you rate severity

- **Critical, High, Medium:** none expected, since no untrusted input reaches this package. A report at these
  levels must show a path by which network data reaches webpack-sources through webpack's dev tooling, with
  default or documented options.
- **Low:** robustness bugs that are not security vulnerabilities under webpack's model, on source text or a
  source map a real build could contain:
  - crashes (uncaught exceptions other than a clear error on malformed input), hangs, super-linear time
    (including ReDoS) or memory exhaustion out of proportion to input size;
  - `source()`, `buffer()` or the output map not matching what the caller's operations describe.
- Not a vulnerability:
  - anything that needs control of the calling code, configuration, a loader, a plugin, `node_modules`, the
    project's sources and their source maps, or the persistent cache;
  - source text appearing verbatim in the output, which is its purpose;
  - input map strings copied into the output map;
  - hash collisions in `updateHash` output (not a security primitive);
  - Node.js or OS bugs.

## Anything to leave alone

- Dependency and devDependency CVEs. Report those upstream.
- webpack's own use of the library, which is covered by webpack's threat model.
- The test shims and snapshot files under `test/`, and the benchmark harness in `benchmark/`.
- Compatibility code for Node.js versions that Node.js itself no longer supports.

## How reports should look

Give a self-contained `node repro.js` that requires `/src` and prints the output showing the issue: the
emitted code, the output map, a `SourceMapConsumer` lookup, or timings next to a normal-sized input. Label it
as a robustness bug unless you can show a path from untrusted network input. A proposed patch against `lib/`
is welcome, ideally with a test in the matching `test/<Class>.js` file. Plain text or Markdown.
