# How we would like patches made

## Size and scope of a fix
- Keep the fix as narrow as possible: change the faulty code path, no refactoring or unrelated
  cleanup. Narrow fixes are easier to review and to backport to release branches.
- Do not change consensus behaviour beyond what the fix requires. If the fix touches block or
  transaction validation, EVM execution or state transition, explain why the result still matches
  the Ethereum specification.
- Do not add dependencies or change `go.mod`.

## Tests
- Reproduce the bug as a failing test first, then fix it: the test must fail on the scanned commit
  and pass with the patch.
- Put the test next to the existing tests of the affected package (`*_test.go` in the same
  directory), and prefer extending an existing table-driven test over adding a new file.
- Never skip, disable or loosen an existing test to make a patch pass.
- Run the affected package's tests with `go test ./<package>/...` before proposing the patch.

## Code style
- Default to no new comments. Add one only for a non-obvious invariant or edge case, in one or two
  sentences, without dates, issue numbers or incident history.
- Format with `gofmt` and check the changed packages with `go vet`.
- Follow the error handling and logging style of the surrounding code.

## Branch and commit message
- Base the patch on `main`.
- Subject line: the changed package path(s), a colon, and what changed, in lower case, for example
  `p2p/discover: bound findnode response size`.
- Body: a short explanation of the defect and the fix. No sign-off or trailers.
