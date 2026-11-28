# Threat model

This follows webpack's published threat model,
<https://github.com/webpack/security-wg/blob/main/docs/threat-model.md>.

## What this project does and where untrusted input enters

enhanced-resolve turns a module request (`"lodash/fp"`, `"./a"`, `"#internal"`, `"../x.js?query#frag"`)
and a context directory into an absolute file path. It is webpack's resolver, and it is also used directly by
other bundlers, linters, test runners and tooling. It runs on a developer's machine or in CI with that user's
privileges, reads the file system (through `lib/CachedInputFileSystem.js` or a caller-supplied file system),
and returns a path or an error. It never reads the resolved module's contents or executes it. The resolver is
a pipeline of plugins on tapable hooks: `lib/ResolverFactory.js` wires the plugins, `lib/Resolver.js` runs
them, and `lib/index.js` is the public API.

**Under webpack's threat model, every input enhanced-resolve reads is trusted.** That covers:
- the resolver options (`alias`, `fallback`, `modules`, `roots`, `restrictions`, `conditionNames`,
  `mainFields`, `extensionAlias`, `plugins`, `fileSystem`, `pnpApi`, `tsconfig`, `packageMap`);
- the request strings, which come from the project's sources;
- `package.json` files (`exports`, `imports`, `browser`, `main`), `tsconfig.json` files and package maps, which
  come from the project and `node_modules`;
- the file system the resolver walks, including symlinks.

webpack trusts the developer's machine, configuration, project sources and installed packages, and says
reading any file reachable through configured resolve paths is expected (CWE-427). enhanced-resolve takes no
network input. So there is no known path for an attacker to reach it, and a finding that needs control of
any of these inputs is not a vulnerability.

Bugs are still worth reporting as robustness issues: a crash, hang or exponential slowdown on an input a real
project could contain. These are not security vulnerabilities under webpack's model; they are rated Low and
handled as normal bugs.

## Components that matter most / least

- Most, for robustness:
  - `lib/util/entrypoints.js` and the exports/imports plugins;
  - `lib/util/path.js`, `lib/util/identifier.js` and `lib/util/fileURLToPath.js`;
  - `lib/SymlinkPlugin.js`, `lib/TsconfigPathsPlugin.js` and `lib/util/packageMap.js`;
  - `lib/UnsafeCachePlugin.js` and `lib/CachedInputFileSystem.js`.
- In scope: all of `lib/`, plus `types.d.ts` and `types/` where the declared contract differs from the
  behavior.
- Out of scope: `test/`, `benchmark/`, `scripts/`, `.github/`. These are tests, benchmarks and repository
  tooling.
- Out of scope: other webpack-org repositories (`webpack`, `webpack-cli`, `webpack-dev-server`,
  `watchpack`, `tapable`, ...), and dependencies (`graceful-fs`, `tapable`).

## How to exercise it

- The image has the repository at `/src` with dependencies installed (`npm ci`); `/enhanced-resolve` is a
  symlink to `/src` because `test/simple.test.js` expects the checkout to carry the package name. There is no
  build step: `lib/` is plain CommonJS. `require("/src")` gives the public API.
- A reproducer is a small directory tree (a `node_modules/<pkg>/package.json`, a few files, maybe a symlink)
  plus a script that calls `require("/src").create.sync({ ... })(dir, request)` and prints the result or
  the time taken.
  - `test/fixtures/` holds ready-made trees.
  - `test/exportsField.test.js`, `test/importsField.test.js`, `test/symlink.test.js` and
    `test/tsconfig-paths.test.js` show how each feature is driven.
- `npm run test:only` runs the whole suite with the Node.js test runner (about 1,700 tests, seconds);
  `node --test test/<file>.test.js` runs one file. Avoid plain `npm test`, which runs the linters first.

## How you rate severity

- **Critical, High, Medium:** none expected, since no untrusted input reaches this package. A report at these
  levels must show a path by which network data reaches the resolver through webpack's dev tooling, with
  default or documented options. One example would be a dev server passing a request URL to the resolver.
- **Low:** robustness bugs that are not security vulnerabilities under webpack's model:
  - crashes, hangs, infinite recursion, exponential-time matching (including ReDoS) or memory exhaustion;
  - triggered by a request, `package.json`, `tsconfig.json` or directory layout that a real project could
    plausibly contain.
- Not a vulnerability:
  - anything that needs control of resolver options, plugins, the project's sources, `node_modules`
    contents, `tsconfig.json` or the file system;
  - encapsulation (`exports`) or `restrictions` bypasses by a package's own metadata (report as normal
    bugs);
  - resolving to any file reachable by the build;
  - absolute paths in error messages and logs;
  - behavior that differs from Node.js but matches documented webpack semantics;
  - Node.js or OS bugs.

## Anything to leave alone

- Dependency CVEs. Report those upstream.
- The legacy Node.js 10 to 16 test path (`test/_runner.js` with jest) and the Bun/Deno CI shims: they are
  test harness, not shipped code.
- Test fixtures under `test/fixtures/` contain deliberately malformed `package.json` files and odd paths.
- Issues that only exist on a Node.js version below `engines.node`, or only with a caller-supplied file
  system that violates the documented `FileSystem` interface.

## How reports should look

Give the input (request, `package.json`, `tsconfig.json`, directory tree), the resolver options in effect, and
a reproducer that builds the tree in a temporary directory, calls `require("/src")`, and shows the crash,
hang or slowdown next to a normal-sized input. Label it as a robustness bug unless you can show a path from
untrusted network input. A proposed patch against `lib/` is welcome, ideally with a test in the matching
`test/*.test.js` file. Plain text or Markdown.
