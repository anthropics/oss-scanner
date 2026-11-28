# How we would like patches made

## Size and scope of a fix
- Fix the root cause once, in the shared code that every caller goes through, not only at the reported call site.
- No refactoring, renames or unrelated cleanups in the same patch.

## Code style
- Format with gofumpt and goimports (the repository's `.golangci.yml` is the reference).
- New `.go` files start with the MPL-2.0 header used across the repository.
- Comments only where the code cannot say why: ordering, ownership or safety contracts. Do not describe what the code does.

## Tests
- Add a regression test next to the fixed code that fails without the fix.
- Do not add or grow `export_test.go`. If a test needs unexported logic, that logic belongs in an `internal/<name>` package with exported functions.
- Controllers are tested by asserting the resources they emit, following the existing controller tests.

## Branch and commit message
- Against `main`, as one commit.
- Conventional commit header, lowercase, imperative, at most 89 characters, no trailing period: e.g. `fix: reject reader role on etcd snapshot`.
- A body is required: explain the mechanism and why the change fixes it, wrapped at 72 columns.
- Leave the DCO `Signed-off-by` to the maintainer who applies the patch.
