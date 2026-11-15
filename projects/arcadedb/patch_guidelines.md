# How we would like patches made

## Size and scope of a fix
- Fix the root cause, not only the reported call site. If the same check is missing on sibling paths (batch, async,
  import, other wire protocols, replication), fix those too in the same patch, ideally through one shared helper.
- Reuse existing components (security checks in `ServerSecurity`, `SecurityDatabaseUser`, the existing path and input
  validation utilities) rather than adding parallel ones.
- No unrelated refactoring, renaming or reformatting.
- Do not add new dependencies. If one is unavoidable it must be Apache 2.0 compatible (Apache 2.0, MIT, BSD, EPL, ...).
- Keep performance in mind: no extra allocations or locking on hot paths (page access, record serialization, query
  execution loops) unless the fix requires it.

## Code style
- Java 21. Match the surrounding code.
- Import classes and use the simple name; do not use fully qualified names in code.
- Use `final` on local variables and parameters where possible.
- An `if` with a single child statement does not need braces.
- Few comments: only where the reason for the code is not obvious.
- For JSON use `com.arcadedb.serializer.json.JSONObject` and `JSONArray`, with the getters that take a default value.
- No `System.out` or debug logging left in the patch.
- Do not add an author tag or any AI attribution to source files.

## Tests
- Every fix comes with a regression test that fails before the fix and passes after it, in the module that contains
  the fix, under `src/test/java`.
- Use JUnit 5 and AssertJ, in the form `assertThat(value).isTrue();`.
- Server tests start servers through the existing fixtures (`BaseGraphServerTest`, `StaticBaseServerTest`) and read the
  bound port back with `getServerHttpPort(...)` or `getServerHttpUrl(...)`; never hard-code a port such as 2480.
- Never assert on raw wall-clock elapsed time; use `StallAwareStopwatch` from the engine test-jar if timing matters.
- Run the affected tests with `-am` so the working tree is used, for example `./mvnw -o -pl server -am test -Dtest=...`.

## Branch and commit message
- Against the `main` branch.
- Commit subject in the form `fix(<module>): <what changed>`, for example `fix(server): enforce type ACL on batch endpoint`.
