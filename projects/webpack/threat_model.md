# Threat model

## What this project does and where untrusted input enters

webpack is a module bundler. It runs on a developer's machine or in CI, with that user's privileges, reads a
project's source files, and writes a bundle that end users then execute in a browser, a web worker, Node.js,
Electron, Deno or Bun.

Configuration is code. `webpack.config.js`, loaders, plugins, `DefinePlugin`/`BannerPlugin`/`ProvidePlugin`
values, and everything installed in `node_modules` run with the developer's privileges by design. An attacker
who can edit any of them already has code execution, so "a malicious config/loader/plugin runs a command" is
not a vulnerability.

Untrusted input enters where webpack consumes data the developer did not write or review:

- **Source files being bundled.** webpack parses JavaScript (`lib/javascript`, with its own parser, printer
  and minifier described in `docs/syntax.md`), CSS (`lib/css`, including the built-in CSS parser and
  minifier), HTML (`lib/html`), JSON (`lib/json`), WebAssembly (`lib/wasm`, `lib/wasm-sync`), asset modules
  (`lib/asset`) and inline source maps. It also interprets strings inside those files: magic comments
  (`webpackChunkName`, `webpackInclude`, `webpackExports`, ...), `import()`/`require.context` arguments,
  `new URL(..., import.meta.url)`, `new Worker(...)` requests, and `//# sourceMappingURL`. Hosted playgrounds
  and build services feed webpack code their users wrote, and third-party packages are bundled unread, so
  treat source content as untrusted.
- **Strings from source that land in emitted output.** Module paths, chunk and asset names, filename
  template placeholders (`[name]`, `[file]`, `[query]`) and comments are copied into generated JavaScript, CSS
  and source maps that browsers execute. A source-controlled string breaking out of a comment, string literal
  or filename is injection.
- **The generated runtime.** Code under `lib/runtime`, `lib/web`, `lib/webworker`, `lib/node`, `lib/hmr`,
  `hot/`, `lib/container`, `lib/sharing`, `lib/library` and the CSS chunk-loading runtime executes in end
  users' browsers (`docs/runtime.md`). At run time it reads the page's DOM and URL (`publicPath: "auto"` uses
  `document.currentScript`), fetches chunks and `*.hot-update.json` manifests from `output.publicPath`,
  creates Trusted Types policies (`output.trustedTypes`), and, with Module Federation, loads remote containers
  and negotiates shared-module versions with them. Remotes are trusted by configuration, but the data they
  return is parsed.
- **The persistent cache.** With `cache.type: "filesystem"`, pack files under `node_modules/.cache/webpack`
  are deserialized on the next build (`lib/cache`, `lib/serialization`, `lib/util/serialization.js`). They are
  written by webpack with the developer's permissions, so another writer is an unusual threat, but
  deserialization should still not execute arbitrary code.
- **The file system.** Resolution follows symlinks (`resolve.symlinks`), `output.clean`
  (`lib/output/CleanPlugin.js`) deletes files, and asset emission writes to paths built from templates and
  source-controlled names. Nothing should be written or deleted outside `output.path`.

## Components that matter most / least

- Most: everything that generates code end users run (`lib/runtime`, `lib/web`, `lib/webworker`, `lib/hmr`,
  `hot/`, `lib/container`, `lib/sharing`, `lib/library`, `lib/css`), the places where source-controlled strings
  are turned into code (`lib/template`, `lib/dependencies`, `lib/javascript/JavascriptParser.js`, the
  minifiers in `lib/javascript`, `lib/css` and `lib/html`, `lib/wasm*`, `lib/json`, `lib/asset`), and
  `lib/serialization`, `lib/output/CleanPlugin.js`, `lib/util`.
- In scope: all of `lib/`, `bin/webpack.js`, `hot/`, `schemas/` (option validation) and `declarations/`.
- Out of scope: `test/`, `examples/`, `assembly/`, `tooling/`, `setup/`, `docs/`, `.github/`. These are
  tests, documentation and repository tooling. `docs/architecture.md`, `docs/syntax.md` and
  `docs/runtime.md` are the best introduction to the code.
- Out of scope: sibling projects published from their own repositories, including `webpack-cli`,
  `webpack-dev-server`, `webpack-dev-middleware`, every loader and plugin, and webpack's dependencies
  (`enhanced-resolve`, `watchpack`, `tapable`, `webpack-sources`, `loader-runner`, `acorn`, `browserslist`).
  A bug in one of them is in scope only when webpack's own code makes it reachable in a way the dependency
  does not already document.

## How to exercise it

- The image has the repository at `/src` with dependencies installed and webpack linked into its own
  `node_modules`, so `require("webpack")` and `node /src/bin/webpack.js` both work. A reproducer is a
  directory with a `webpack.config.js` and a few source files; build it with `node /src/bin/webpack.js
  --config <dir>/webpack.config.js`, then run or inspect `dist/`.
- `test/cases/` and `test/configCases/` hold hundreds of small projects, one directory each with an
  `index.js` and often a `webpack.config.js`, that are the best templates for a reproducer. `test/hotCases/`
  does the same for HMR and `test/watchCases/` for watch mode.
- `yarn test:basic` runs the quick suites; `yarn test:unit` the unit tests in `test/unitCases/`;
  `yarn test:integration` the full integration suite (`test/*.test.js` and `test/*.longtest.js`, slow).
  `yarn test:base <pattern>` runs a single file. Avoid plain `yarn test`, which runs the linters first.
- `yarn test:test262`, `yarn test:test262-parser`, `yarn test:html5lib` and `yarn test:css-parsing` run the
  spec conformance suites in `test/specCases/` against the corpora checked out under `test/external/`.
  `yarn test:minify-fuzz` fuzzes the JavaScript minifier. `yarn test:syntax-equivalence` and
  `yarn test:minify-corpora` need the `wpt`, `swc` and `oxc` corpora, which are not in the image.
- `examples/` builds with `yarn build:examples` and shows typical configurations.

## How you rate severity

- **Critical:** code execution or cross-site scripting in the emitted bundle or runtime, in an application
  built with default options, from input an attacker controls at run time (the page URL or DOM, or a
  response from an origin the attacker should not be able to influence); build-time code execution or a file
  write outside `output.path` triggered purely by the content of a source file being bundled, with no change
  to configuration or `node_modules`.
- **High:** a string from a source file reaching emitted JavaScript, CSS, HTML or a source map without the
  escaping webpack applies elsewhere (breaking out of a comment, string literal or template); path traversal
  through chunk names, asset names or filename placeholders derived from source content; `output.clean`
  deleting outside `output.path`; prototype pollution of the build process from source content; the HMR or
  Module Federation runtime letting one origin inject code into another where the documentation says they
  are isolated.
- **Medium:** code execution through persistent-cache deserialization (needs write access to
  `node_modules/.cache`); any of the above that needs a supported but non-default option; a crafted source
  file causing contents of files outside the project to be read into the bundle; a minifier or printer
  rewrite that can be steered from source content to make the output run code the input did not.
- **Low:** crashes, hangs, exponential-time parsing (including ReDoS) or memory exhaustion of the build from
  a crafted source file.
- Not a vulnerability: anything that requires editing configuration, a loader, a plugin or `node_modules`;
  `eval`-based devtools emitting `eval` (by design); `DefinePlugin`, `BannerPlugin` and `ProvidePlugin`
  emitting the strings they are given; absolute paths of the build machine appearing in development-mode
  output or in source maps the developer asked for; a minifier producing output that merely behaves
  differently from its input (a correctness bug, reported through the normal issue tracker).

## Anything to leave alone

- Dependency CVEs that do not reach a webpack code path. Report those upstream.
- `webpack-dev-server`, `webpack-dev-middleware` and `webpack-cli`. They have their own repositories and
  advisories, and the `test/WebpackDevServer.longtest.js` and `test/WebpackCli.longtest.js` suites only
  check that webpack works with them.
- The hash functions in `lib/util/hash` (md4, xxhash64, batched hashing) produce cache keys and content
  hashes for file names. They are not security primitives, and collisions are not vulnerabilities.
- Test fixtures under `test/` contain deliberately malformed code and configuration, and the corpora under
  `test/external/` are third-party.
- Compatibility shims for Node.js 10 to 18 and the Deno/Bun specific code under `lib/deno` and `lib/bun`
  when the issue only exists on a runtime webpack does not support.

## How reports should look

Name the input an attacker controls, the code path that consumes it, and give a reproducer that runs against
`/src/bin/webpack.js` with a minimal `webpack.config.js` and source files, modeled on a `test/configCases/`
directory. Show the emitted output or the runtime behavior that demonstrates the issue. A proposed patch
against `lib/` is welcome, ideally with a test case in `test/configCases/` or `test/cases/`. Plain text or
Markdown.
