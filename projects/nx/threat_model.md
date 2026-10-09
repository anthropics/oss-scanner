# Threat model

## What this project does and where untrusted input enters

Nx is a build system and CLI for monorepos. Developers and CI run it inside their own workspace. It reads workspace configuration, builds a project graph, runs tasks, caches task outputs, and runs code generators.

Workspace configuration is code. `nx.json`, `project.json`, `package.json`, local plugins, generators and executors all run with the developer's privileges by design. An attacker who can edit them already has code execution, so "a malicious `project.json` runs a command" is not a vulnerability.

Untrusted input enters where Nx consumes data that the workspace owner did not write or review:

- **Values CI takes from pull requests.** Branch names, refs and SHAs passed to `nx affected` (`--base`, `--head`, `defaultBase`), commit messages and PR titles read by `nx release` changelog generation. Treat these as attacker-controlled strings.
- **Cache artifacts.** Outputs restored from a remote cache (Nx Cloud or a self-hosted remote cache over HTTP) are archives produced on another machine. Extraction must not write outside the workspace.
- **The local daemon.** `nx` starts a background daemon that listens on a Unix socket (named pipe on Windows). Another user on the same machine is untrusted and must not be able to drive it.
- **Downloaded code and metadata.** The Nx Cloud client bundle, package registry metadata read by `nx migrate`, `nx add` and `create-nx-workspace`, and migration definitions from third-party packages.
- **Local servers.** `nx graph` and related commands serve a web UI on localhost. Other origins in the user's browser are untrusted.

## Components that matter most / least

- Most: `packages/nx` (TypeScript CLI, daemon, task runner, cache, project graph, `nx release`, `nx migrate`) and its Rust native code in `packages/nx/src/native`.
- In scope: `packages/devkit`, `packages/js`, `packages/workspace`, `packages/create-nx-workspace`, and the framework plugins under `packages/*`.
- Out of scope: `nx-dev/`, `astro-docs/`, `e2e/`, `examples/`, `benchmarks/`, `tools/`, and `scripts/`. These are the docs site, tests and repo tooling, and none of them ship to users.
- Out of scope: the Nx Cloud service itself. It is a separate commercial product with its own reporting address. The Nx Cloud client code in this repository is in scope.

## How to exercise it

- Exercise a local release, the way users install Nx. The image publishes every public Nx package to a Verdaccio registry stored in `/src/dist/local-registry/storage`, as Nx's own e2e suite does. Start it from `/src` with `pnpm nx local-registry` (port 4873).
- `/src/dist/local-registry/proj-backup/` holds workspaces created from that release with `create-nx-workspace`, one per package manager and preset (`npm-apps.tar`, `pnpm-ts.tar`, and so on). Extract one into `/tmp` to get an installed workspace without the network.
- `pnpm nx test-native nx` runs the Rust tests. Run the TypeScript unit tests from `/src/packages/nx` with `env -u NX_NO_CLOUD npx vitest run`, because several specs assert Nx Cloud behavior and fail when `NX_NO_CLOUD` is set. Two specs fail in this image for environmental reasons. `run-state.spec.ts` expects a directory to be undeletable, but root can remove it. `pseudo-terminal.spec.ts` ("should subscribe to output") reads no output from a PTY in a headless container.

## How you rate severity

- **Critical:** code execution or arbitrary file write driven by input from a pull request, a remote cache artifact, another local user, or a web page. Examples include command injection through a branch name in `nx affected`, path traversal when extracting a cache artifact, and another user executing code through the daemon socket.
- **High:** reading or leaking secrets (environment variables, tokens, cache contents) to another user, origin or machine, and cache poisoning that changes a build's output without code execution.
- **Medium:** integrity problems that need an unusual but supported configuration, such as a documented environment variable set to a non-default value.
- **Low:** local denial of service, hangs or crashes of the CLI from malformed input.
- Not a vulnerability: arbitrary code execution that requires placing the command in a config file (`nx.json`, `project.json`, `package.json`, a plugin's options, or any other workspace configuration). Running configured commands is what Nx is for. The same goes for anything that requires editing plugins or installed `node_modules`, since those are trusted code.

## Anything to leave alone

- Outdated dependencies, or dependency CVEs that do not reach an Nx code path. Report only issues in Nx's own code.
- Commands that run arbitrary shell commands by design, such as `nx:run-commands` and `nx exec`, when the command comes from workspace configuration or the user's own command line.
- Generators writing files where the user told them to. Generator options come from the developer running them.

## How reports should look

Include the input an attacker controls, the exact command or code path that consumes it, and a reproduction that runs against the local release in a workspace extracted from `proj-backup`. A proposed patch is welcome. Reports should be plain text or Markdown.
