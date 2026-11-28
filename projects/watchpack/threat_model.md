# Threat model

This follows webpack's published threat model,
<https://github.com/webpack/security-wg/blob/main/docs/threat-model.md>.

## What this project does and where untrusted input enters

watchpack is the file system watcher behind webpack's watch mode, and through it `webpack --watch`,
webpack-dev-server and webpack-dev-middleware. It runs on a developer's machine or in CI, with that user's
privileges. A caller hands it lists of files, directories and missing paths to watch (`lib/index.js`), and
watchpack reports `change`, `remove` and `aggregated` events plus time info entries that webpack uses to
decide which modules to rebuild. It only reads file system metadata. It calls `fs.watch`, `fs.readdir`,
`fs.lstat`, `fs.stat`, `fs.readlink` and `fs.realpath`, and never opens, writes or deletes files.

**Under webpack's threat model, every input watchpack reads is trusted.** That covers:
- its options (`ignored`, `poll`, `followSymlinks`, `aggregateTimeout`) and the `WATCHPACK_*` environment
  variables;
- the paths it is asked to watch;
- the contents of the watched trees (entry names, symlinks, and the file system events they cause).

All of these come from the developer, their configuration, their project or their installed packages, on
infrastructure webpack assumes is already secured. watchpack takes no network input. So there is no known
path for an attacker to reach it, and a finding that needs control of any of these inputs is not a
vulnerability.

Bugs are still worth reporting as robustness issues: a crash, hang, leaked watcher or runaway CPU use from a
file tree a real project could contain. These are not security vulnerabilities under webpack's model; they
are rated Low and handled as normal bugs.

## Components that matter most / least

- Most, for robustness:
  - `lib/LinkResolver.js` and the symlink handling in `lib/DirectoryWatcher.js` (symlink loops, unbounded
    recursion);
  - `lib/util/globToRegExp.js` and the `ignored` handling in `lib/index.js`;
  - `lib/watchEventSource.js` with `lib/reducePlan.js` (watcher accounting, leaked handles).
- In scope: all of `lib/` and the published type declarations in `types/`.
- Out of scope: `test/`, `benchmark/`, `playground/`, `.changeset/`, `.github/`. These are tests,
  benchmarks and repository tooling.
- Out of scope: other webpack-org repositories, `graceful-fs`, and Node.js `fs.watch` itself.

## How to exercise it

- The image has the repository at `/src` with dependencies installed, so `require("/src")` gives the
  `Watchpack` class. There is no build step.
- A reproducer is a small Node.js script:
  1. Create a temporary directory and lay out the entries.
  2. Run `new Watchpack({ aggregateTimeout: 100, followSymlinks: true })` and call
     `wp.watch({ files, directories, missing, startTime: Date.now() - 10000 })`.
  3. Print the events, `wp.getTimeInfoEntries()` and
     `require("/src/lib/watchEventSource").getNumberOfWatchers()`, then call `wp.close()`.

  `playground/watch-folder.js` is a minimal example of the API.
- `test/Watchpack.test.js`, `test/DirectoryWatcher.test.js` and `test/LinkResolver.test.js` are the best
  templates; `test/helpers/TestHelper.js` creates and tears down a temporary `fixtures` directory.
- `npx jest --runInBand <file>` runs one suite. `npm run test:only` runs all of them offline (about seven
  minutes). Avoid plain `npm test`, which runs `lint:declarations` (a `git diff`).
- The image runs Linux, where `fs.watch` is not recursive. The macOS and Windows recursive watcher paths in
  `lib/watchEventSource.js` cannot be exercised directly here.

## How you rate severity

- **Critical, High, Medium:** none expected, since no untrusted input reaches this package. A report at these
  levels must show a path by which network data reaches watchpack through webpack's dev tooling, with default
  or documented options.
- **Low:** robustness bugs that are not security vulnerabilities under webpack's model:
  - uncaught exceptions, or stack overflow from symlink loops in `LinkResolver`;
  - hangs, infinite rescans, unbounded `DirectoryWatcher` creation or leaked `fs.watch` handles;
  - CPU or memory exhaustion, or ReDoS in a regexp built from an ordinary `ignored` glob;
  - in each case, triggered by a tree a real project could plausibly contain.
- Not a vulnerability:
  - anything that needs control of watchpack's options, the watched path lists, the `WATCHPACK_*`
    environment variables, the project, `node_modules` or the file system;
  - missed or duplicated events caused by OS watcher limits, network or virtual file systems, timestamp
    accuracy or clock skew (correctness bugs);
  - file paths and timestamps appearing in events, which is the API's purpose;
  - Node.js or OS bugs.

## Anything to leave alone

- Dependency CVEs (including `graceful-fs`). Report those upstream.
- Timing-related flakiness in the test suite, and anything that only reproduces on Node.js versions that
  `engines` and the CI matrix no longer cover.
- How webpack, webpack-dev-server or webpack-dev-middleware use watchpack's events.
- Test fixtures under `test/` and the benchmark cases under `benchmark/`.

## How reports should look

Give the tree layout or sequence of file system operations, the options in effect, and a self-contained
Node.js reproducer that `require`s `/src`, builds the tree in a temporary directory and shows the crash,
hang, watcher count or wrong events. State which platform the issue applies to. Label it as a robustness bug
unless you can show a path from untrusted network input. A proposed patch against `lib/` is welcome, ideally
with a Jest test modeled on `test/Watchpack.test.js` or `test/LinkResolver.test.js`. Plain text or Markdown.
