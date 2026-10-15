# Threat model: Terraform Module Releaser

## What this project does and where untrusted input enters

Terraform Module Releaser is a GitHub Action (TypeScript, Node 24, bundled to `dist/index.js` with ncc) for Terraform
monorepos. It runs on `pull_request` events with a `GITHUB_TOKEN` that typically has `contents: write` and
`pull-requests: write`.

- **PR opened or synchronized:** discovers module directories (any directory with `.tf` files), maps the PR's commits to
  modules, computes the next SemVer per module, and posts or updates a "release plan" PR comment.
- **PR merged:** for each changed module, copies the module's files to a temp directory, commits and tags them, pushes
  with `git` (`execFileSync`), and creates a GitHub release with a changelog. It then posts a summary comment, deletes
  orphaned tags and releases of removed modules (opt-in), and regenerates the repository wiki using `terraform-docs`.

Untrusted input comes from anyone who can open a pull request, including from a fork:

- Commit messages, which go through `conventional-commits-parser` and keyword matching, then into changelogs, release
  bodies, PR comments, and wiki pages.
- PR title, body, and branch names from the event payload (`GITHUB_EVENT_PATH`).
- File and directory names in the PR. Module paths become tag names, release names, wiki page names, git arguments, and
  filesystem paths.
- File contents in module directories, including `.tf` files read by `terraform-docs`, and symlinks or other special
  files inside a module that the release copy step may follow.
- Existing tags, releases, release bodies, and PR comments in the repository. These carry hidden markers that the
  action uses to prove it created a release (see `docs/state-management.md`), so forged or edited markers count as
  untrusted input.

The action inputs in the workflow file, such as `module-path-ignore`, `wiki-usage-template`, and the exclude patterns,
are set by the repository owner. Treat them as trusted.

## Components that matter most / least

Most important (`src/`):

- `releases.ts`, `tags.ts`, and `utils/github.ts`: git commands, token handling through an `http.extraheader`
  credential, copying `.git` into release temp directories, and tag/release creation and deletion.
- `wiki.ts` and `terraform-docs.ts`: wiki clone and push, page filename generation, and running the `terraform-docs`
  binary on PR-controlled module content.
- `parser.ts`, `terraform-module.ts`, and `utils/file.ts`: module discovery, path handling, and tag/module association.
- `commit-analyzer.ts`, `changelog.ts`, `pull-request.ts`, and `utils/markers.ts`: commit parsing, markdown assembly,
  and marker parsing and validation.
- `config.ts` and `context.ts`: input and event-payload parsing.

Less important or out of scope:

- `dist/` is generated from `src/` by release automation. Report against `src/`.
- `__tests__/`, `__mocks__/`, `scripts/`, `tf-modules/` (test fixture modules), `.github/workflows/`, and
  `.devcontainer/` are development and CI tooling only.
- Bugs inside third-party dependencies, unless the action's own code makes them reachable with real impact.

## How to exercise it

- `npm test` runs the Vitest suite. Octokit and `child_process` are mocked in most unit tests, so they run offline.
  Expected failures in the scan environment (about 800 other tests pass):
  - The "real API" suites in `pull-request`, `releases`, `tags`, `utils/github`, and `wiki` (`generateWikiFiles()`)
    need `GITHUB_TOKEN` and fail in setup without it.
  - The "real system installation" tests in `terraform-docs.test.ts` download terraform-docs and need network access.
- `__tests__/helpers/` has helpers for building config, context, and Octokit mocks. `scripts/event.pull-request.json` is
  an example event payload.
- `terraform-docs` (the default version from `action.yml`) is installed at `/usr/local/bin/terraform-docs` in the image.
- `tf-modules/` contains example Terraform modules for module discovery and wiki generation.

## How you rate severity

The main attacker is a PR author **without** write access, such as a fork contributor. Rate by what that author can do:

- **Critical:** running commands on the runner, or exposing `GITHUB_TOKEN` or other workflow secrets, from PR-controlled
  input (commit messages, file or directory names, `.tf` contents, branch names).
- **High:**
  - The token ends up anywhere it can be read: logs, PR comments, release bodies, wiki pages, or pushed git objects or
    config (for example, through the `.git` copied into release temp directories).
  - PR-controlled input makes the action push, delete, or overwrite tags, releases, or wiki pages it should not touch.
    This includes path traversal into another module's tag namespace and forged provenance markers that cause a release
    or tag to be adopted or deleted.
  - Reading or writing files outside the workspace and temp directories, including through symlinks in module
    directories.
- **Medium:**
  - Markdown or HTML injection in PR comments, release notes, or wiki pages that misleads reviewers, such as spoofing the
    release plan or hiding content. GitHub sanitizes rendered HTML, so script execution is not expected.
  - Input that stalls the action for a long time, such as super-linear regex backtracking on commit messages. These are
    bounded by the job timeout.
- **Low:** problems that need repository write access or a malicious maintainer, and anything that needs the workflow
  author to misconfigure the action (for example, `pull_request_target` combined with checking out the PR head).

## Anything to leave alone

- Do not report that the action needs `contents: write` and `pull-requests: write`. These permissions are documented and
  required.
- Do not report that the action downloads `terraform-docs` at runtime from `terraform-docs.io` over HTTPS. This is
  documented behavior.
- Super-linear regexes inside `conventional-commits-parser` are already known to us. Report them only with a realistic
  commit message that causes a practical stall, along with a mitigation in our code.
- Reports about the content of `tf-modules/`, which are intentionally simple fixtures.
