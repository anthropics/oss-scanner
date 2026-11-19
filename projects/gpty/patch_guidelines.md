# Patch format

One patch per finding, against the scanned branch. Keep it minimal: the fix and its test, nothing
else.

- Rust (`crates/`): `cargo fmt` and `cargo clippy --workspace --locked -- -D warnings` must pass.
  Add a regression test next to the code under test, named `test_<behaviour>`, with a
  Given/When/Then comment. No new dependencies, no version bumps, no refactors, no formatting-only
  hunks.
- GDScript (`godot/`): follow the surrounding style; add the test under `godot/tests/unit/` or
  `godot/tests/integration/` as `test_*.gd` (GUT does not recurse into subdirectories).
- Security checks stay fail-closed: do not weaken a permission, a peer check, a length bound or an
  allowlist to make a test pass.
- State the boundary the fix closes in the patch description, and name the test that proves it.
- Use a conventional subject: `fix(<scope>): <imperative summary>`, where scope is the crate or area
  (`core`, `ipc`, `gdext`, `terminal`, `concepts`, `media`, `vault`, `plugin`).
- Do not add a Signed-off-by, authorship claims or generated-by trailers; the patch is a proposal,
  not a contribution.
