# Threat model

This follows webpack's published threat model,
<https://github.com/webpack/security-wg/blob/main/docs/threat-model.md>.

## What this project does and where untrusted input enters

This repository publishes two npm packages from an npm workspaces monorepo:

- `webpack-cli` (`packages/webpack-cli`) is the command-line front end to webpack. It runs on a developer's
  machine or in CI, with that user's privileges. It parses argv, finds and loads a configuration file,
  turns flags into webpack options, and runs the `build`, `watch`, `serve`, `info`, `configtest`,
  `version`, `help` and `complete` commands.
  - Almost all of it lives in `packages/webpack-cli/src/webpack-cli.ts`.
  - The progress, bundle-analyzer and logging hooks are in `packages/webpack-cli/src/plugins/cli-plugin.ts`.
  - The entry point, including the "prefer the local installation" lookup, is
    `packages/webpack-cli/bin/cli.js`.
- `create-webpack-app` (`packages/create-webpack-app`) scaffolds a new project, loader or plugin. It asks
  questions with `@inquirer`, renders EJS templates from `packages/create-webpack-app/templates` through
  `node-plop`, writes the files (`packages/create-webpack-app/src/utils/generate-files.ts`), and runs the
  chosen package manager (`packages/create-webpack-app/src/utils/install-dependencies.ts`).

webpack trusts the developer and their machine, and everything they configure or install:
- the developer and their environment: the shell, the current directory and everything in it, environment
  variables (`WEBPACK_PACKAGE`, `WEBPACK_DEV_SERVER_PACKAGE`, `NODE_OPTIONS`, ...), and the answers given
  at `create-webpack-app`'s prompts;
- argv and `package.json` scripts;
- `webpack.config.*` in any format and anything it imports;
- loaders, plugins, external commands and everything in `node_modules`;
- the project's source files, assets, file names and lockfiles.

A finding that needs control of any of these is not a vulnerability. That covers most of what webpack-cli
reads.

What webpack does not trust is network data reaching dev tooling, and clients outside the developer's
intended environment. webpack-cli does not accept network input itself. Its part of that boundary is
`serve`: webpack-cli builds the options and starts `webpack-dev-server`, which owns the HTTP server, the
WebSocket, the `Host`/`Origin` checks and the proxy. In scope here is how webpack-cli derives those options
(ports, multiple compilers, `devServer` merging, flag-to-option mapping). A flag the developer did not pass
must not widen who can reach the server, for example by binding to all interfaces, setting
`allowedHosts: "all"` or turning off a check.

## Components that matter most / least

- Most: the `serve` command and how it builds dev server options in `packages/webpack-cli/src/webpack-cli.ts`.
- In scope: `packages/webpack-cli/src`, `packages/webpack-cli/bin/cli.js`, `packages/create-webpack-app/src`
  and `packages/create-webpack-app/bin/cli.js`, but only where code there affects what reaches the network.
- Least: config discovery and loading, `installPackage`, `#spawn`, `--json` output and the scaffolding
  templates. Their inputs are all trusted.
- Out of scope: `test/`, `smoketests/`, `scripts/`, `.github/`, `.changeset/`, `.devcontainer/`, `.husky/`,
  and the generated `OPTIONS.md` and `SERVE-OPTIONS-v*.md`. These are tests, release tooling and docs.
- Out of scope: webpack itself and the other webpack-org repositories (`webpack-dev-server`,
  `webpack-dev-middleware`, `webpack-bundle-analyzer`, every loader and plugin), and dependencies
  (`commander`, `interpret`, `rechoir`, `envinfo`, `@discoveryjs/json-ext`, `json5`, `js-yaml`, `toml`,
  `ejs`, `node-plop`, `cross-spawn`, `@inquirer/*`). A bug in one of them is in scope only when
  webpack-cli's own code makes it reachable from the network in a way the dependency does not already
  document.

## How to exercise it

- The image has the repository at `/src` with dependencies installed and both packages compiled into
  `packages/*/lib`. `node /src/packages/webpack-cli/bin/cli.js` is the CLI and `require("webpack-cli")` works
  from `/src`. A reproducer is a directory with a `webpack.config.js` and a few source files; run
  `node /src/packages/webpack-cli/bin/cli.js serve` with that directory as the current directory, then
  show which address the server listens on and which options it was given.
- `test/serve/` is the best template for a reproducer. `test/utils/test-utils.js` has the `run`/`runWatch`
  helpers the tests use.
- `npm run test:base -- --ci` runs the whole Jest suite; `npm run test:base -- --ci test/serve` runs one
  directory. Avoid plain `npm test`, which rebuilds and lints first.
- The scan runs offline:
  - The `test/create-webpack-app/` suites run `npm install` for the scaffolded project and fail without
    network.
  - Three `test/serve/` snapshots list the "On Your Network" addresses, which a container with no network
    interface cannot print. The servers themselves start and build.

## How you rate severity

These levels follow the advisories webpack has published for its dev tooling. They assume default or
documented options and no compromise of trusted elements.

- **Critical:** none expected; webpack-cli does not accept network input.
- **High:** `serve` disabling the dev server's host or origin checks without the developer asking for it,
  so that the High findings described in webpack-dev-server's threat model become reachable.
- **Medium:** `serve` binding the dev server beyond loopback, or otherwise widening who can reach it, when
  neither the configuration nor the flags asked for it.
- **Low:** `serve` printing a misleading address or exposure warning that leads a developer to expose the
  server without knowing it.
- Not a vulnerability:
  - anything that needs control of configuration, argv, `package.json` scripts, environment variables, a
    loader, a plugin, `node_modules`, or the files in the project directory (including file names, lockfiles
    and data-format config files);
  - `create-webpack-app` doing what the developer's answers ask;
  - `installPackage` installing the package it named after the developer answered yes;
  - the CLI preferring a project-local `webpack-cli` from `node_modules`;
  - terminal output from the build, which comes from trusted sources;
  - the dev server being exposed to the internet or used in production (an operational misconfiguration);
  - Node.js or OS bugs.

## Anything to leave alone

- Dependency CVEs that do not reach a webpack-cli code path. Report those upstream.
- webpack-dev-server's HTTP, WebSocket, proxy and static-file handling, and webpack's own parsing and code
  generation. Both have their own repositories, threat models and advisories.
- Test fixtures under `test/` contain deliberately broken configs, lockfile combinations and package
  layouts.
- `smoketests/` and `scripts/` only run in this repository's CI and release process.

## How reports should look

Name the configuration and flags in effect, and the dev server option webpack-cli produced that the
developer did not ask for. Give a reproducer that runs `node /src/packages/webpack-cli/bin/cli.js serve` in a
small directory modeled on a `test/serve/` case. Show the resulting options or listening address and a
request from outside the intended environment that the server answers. A proposed patch against
`packages/webpack-cli/src` is welcome, ideally with a Jest test in `test/serve/`. Plain text or Markdown.
