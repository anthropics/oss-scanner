# How we would like patches made

## Size and scope of a fix
- Fix the check at the enforcement point that is wrong, as narrowly as possible. No refactoring.
- If the fix changes JSON-RPC access logic (`rbac.AccessController`, claim handling), apply the same rule to the
  explorer visibility layer (`GetBatchVisibility`, `GetBatchEventAccess`), and the other way round. The two must
  agree for every viewer and address.
- Fail closed: on an error or missing data, deny.

## Code style
- Idiomatic Go with explicit error handling, formatted with `gofmt`.
- Never return raw error text (`err.Error()`) in an HTTP response; `tools/check-err-leak.sh` checks this.
- A changed HTTP endpoint keeps its swaggo annotation block in step; regenerate with `make api-spec`.
- Database changes are additive migrations under `internal/db/migrations/`. Never write to `rbac_audit_log` or other
  hash-chained audit tables from a migration.

## Tests
- Add a table-driven regression test next to the changed code that fails without the fix.
- For an access-control fix that applies to both layers, extend `TestExplorerRedactorWiring_FullStack`
  (`internal/server/explorer_redactor_wiring_integration_test.go`), which runs without Docker. Note in the patch that
  `TestAccessVisibilitySymmetry` (`e2e/access_visibility_symmetry_test.go`) should be extended too; it needs the e2e
  stack and runs in CI.

## Docs and commits
- When the fix changes behavior an operator relies on, update the matching page under `site/src/app/docs/`.
- Commits need a DCO sign-off (`git commit -s`).
