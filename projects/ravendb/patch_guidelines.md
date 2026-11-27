# How we would like patches made

## Size and scope
- Fix the root cause once, in shared code when several callers are affected. No unrelated refactoring.
- Keep existing error handling and validation in any code you move.

## Code style
- Follow the surrounding code. Comment only where the reason is not obvious from the code.

## Tests
- Add a regression test under `test/SlowTests.Issues/Issues` (or the nearest existing test file) that fails before the fix.
- Use `[RavenFact(RavenTestCategory.X)]` or `[RavenTheory(RavenTestCategory.X)]`, never plain `[Fact]`/`[Theory]`;
  categories are listed in `test/Tests.Infrastructure/RavenTestCategory.cs`.
- Inherit from `RavenTestBase`, `ClusterTestBase` or `ReplicationTestBase`.

## Branch
- Against the branch that was scanned.
