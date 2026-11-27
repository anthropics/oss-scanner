# How we would like patches made

## Size and scope of a fix
- Fix the root cause where the check belongs: the queryset, serializer, permission class, access-control layer,
  query builder or shared helper. Do not patch only the reported call site.
- When sibling routes, `@action` methods, bulk paths or other services miss the same check, fix them in the same
  patch.
- Reuse the existing controls. Examples: `TeamAndOrgViewSetMixin` and its project-scoped querysets, explicit
  serializer fields with a project-scoped queryset, HogQL AST placeholders and `ast.Constant` for user values, the
  outbound request helpers in `posthog/egress/`, and `hmac.compare_digest` for secret comparison.
- Do not refactor, rename or reformat unrelated code. Do not add a dependency.
- Do not add a rate limit, a log line or a second validation layer as the fix when a missing check is the cause.
- When a fix changes a database schema, add the Django or ClickHouse migration and keep it safe for a large table
  with no downtime.

## Code style
- Follow the surrounding code and the guides in `AGENTS.md` and `.agents/`.
- Python: type hints, no new `# type: ignore`, formatted with `ruff format`, clean under `ruff check`.
- TypeScript: formatted with Oxfmt, clean under Oxlint, no `any`.
- Rust: formatted with `cargo fmt`, clean under `cargo clippy`.
- Add a comment only when the reason is not obvious from the code. Do not describe the vulnerability or the report
  in a comment.
- Do not add an author tag or an AI attribution to source files.

## Tests
- Add a regression test that fails before the fix and passes after it. Extend the nearest existing test file.
- Drive the public interface (the HTTP route, the query, the Hog program) and assert the result that a caller sees.
- For a tenant-isolation fix, create a second organization and project in the test and assert that the request
  fails and that the other project's data stays unchanged.
- Parameterize near-duplicate cases. Do not add sleeps or dates that are not pinned.

## Branch and commit message
- Against the `master` branch, one fix per patch.
- Conventional commit subject, lowercase, under 72 characters, for example `fix(insights): scope dashboard lookup
  to the project`.
- Keep the subject and body neutral. Do not put exploit details in the commit message.
