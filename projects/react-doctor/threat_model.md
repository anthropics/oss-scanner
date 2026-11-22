# Threat model

## What this project does and where untrusted input enters

React Doctor is a static analyzer for React codebases. It ships as the `react-doctor` CLI, the `oxlint-plugin-react-doctor` and `eslint-plugin-react-doctor` lint plugins, a programmatic API (`@react-doctor/api`), and a GitHub Action (`action.yml`). People run it on code they did not write: AI agent output, pull requests from forks, and third-party repositories they clone to audit.

Untrusted input enters in these places:

- **Scanned source files**: every `.js`, `.jsx`, `.ts` and `.tsx` file in the scanned tree, parsed by the rules in `packages/oxlint-plugin-react-doctor` and the checks in `packages/core/src/checks`. File contents, file names and directory names are all attacker controlled.
- **Project metadata**: `package.json`, lockfiles, `tsconfig.json`, `.gitignore`, `.gitattributes`, and the Babel, Vite, Next.js, Rsbuild, Rspack and Expo config files that `packages/core/src/project-info` reads to detect frameworks and the React Compiler. React Doctor reads these statically with the TypeScript and oxc parsers and must never execute them.
- **Git data**: branch names, refs, paths and diffs that `packages/core/src/services/git.ts` and the Action's changed file logic (`scripts/normalize-changed-files.mjs`) pass to `git`.
- **The GitHub Action on pull requests**: the Action scans the PR's code, renders the results with `scripts/render-github-action-comment.mjs`, and posts a sticky PR comment, inline review comments and a commit status with the workflow's `GITHUB_TOKEN`. Diagnostic messages, file paths and code snippets in those comments come from the PR.
- **Network responses**: the supply chain check (`packages/core/src/check-supply-chain.ts`) fetches package scores from Socket and caches them on disk, and the CLI posts diagnostics to the score API (`packages/core/src/request-score.ts`). Both responses are untrusted.

Trusted: the user who runs the CLI and their flags, the workflow author's Action inputs, and the project's own `doctor.config.*` file. React Doctor loads `doctor.config.ts`, `.js`, `.mjs`, `.cjs`, `.mts` and `.cts` with jiti (`packages/core/src/load-config.ts`), which runs the file's code by design, the same way ESLint runs `eslint.config.js`.

## Components that matter most and least

Most important:

- anything that makes a scan execute code from the scanned tree other than `doctor.config.*`, such as a path where the React Compiler config evaluator (`packages/core/src/project-info/react-compiler-config-evaluator.ts`) or project analysis (`packages/core/src/project-analysis`) imports or `require`s a project file;
- command or argument injection through file names, refs or config values into `git`, the oxlint binary (`packages/core/src/runners/oxlint/spawn-oxlint.ts`) or the Node resolver (`packages/core/src/resolve-compatible-node.ts`);
- file reads or writes outside the scanned project, for example through symlinks, `..` paths, or cache paths (`REACT_DOCTOR_CACHE_DIR`) derived from scanned content;
- the GitHub Action: injection into `$GITHUB_OUTPUT` or `$GITHUB_ENV`, shell injection in the composite steps, markdown or link injection in PR comments that impersonates the bot or hides content, and anything that leaks the token;
- sending source code or secrets from the scanned tree to the score API or to Socket beyond the diagnostic and dependency data those features need.

Less important, but in scope: crashes and hangs on crafted source files (one file that stalls a CI run), cache poisoning that makes a later scan report wrong results, and false negatives in the security rules (`packages/core/src/checks/security-scan`) caused by a bug rather than a known rule limit.

Out of scope: `packages/evals` (internal evaluation runner), `scripts/performance`, `scripts/fn-mining`, `scripts/delta-audit`, the test suites under `**/tests`, `docs/`, and bugs that live entirely in oxlint, jiti, TypeScript or other dependencies unless React Doctor's own code makes them reachable.

## How to exercise it

- After the Docker build, every package is built in place under `packages/*/dist`. Run the CLI with `node packages/react-doctor/bin/react-doctor.js <dir>`. Add `--json` for a machine-readable report. Add `--no-score --no-supply-chain` to skip the network calls, which fail offline anyway.
- Unit tests: `pnpm test` (vitest through turbo). Tests live in `packages/*/tests`, and many of them write a small project to a temporary directory and scan it, which is a good template for a reproducer.
- `packages/fuzz` is an adversarial fuzzing harness for the lint rules (`pnpm fuzz`).
- To exercise the GitHub Action offline, run `scripts/render-github-action-comment.mjs` and `scripts/normalize-changed-files.mjs` directly on a crafted JSON report or a crafted list of changed files.

## How you rate severity

- Critical: code execution on the machine running a scan, triggered by a scanned file or project metadata with default options, other than through `doctor.config.*`. Also critical: leaking the Action's `GITHUB_TOKEN` or writing to the repository from a fork pull request.
- High: command or argument injection into a subprocess, reads or writes outside the scanned tree, injection into `$GITHUB_OUTPUT` or `$GITHUB_ENV` from PR content, or sending source code or secrets off the machine.
- Medium: markdown or link injection in PR comments that misleads reviewers, cache poisoning that hides findings, or a bug that makes a security rule miss the case it documents.
- Low: crashes, hangs and memory exhaustion on crafted input. These are regular bugs for us.

## Anything to leave alone

- Do not report that `doctor.config.ts` or `doctor.config.js` runs code. That is the documented config format.
- Do not report that the Action runs an installed `react-doctor` from the project's `node_modules`. The workflow author chose to install the project's dependencies.
- Do not report rule false positives or style disagreements.

Please include a minimal project (or a test in `packages/*/tests`) that reproduces the issue against the built packages in this image, and a patch against `packages/` or `scripts/` where possible.
