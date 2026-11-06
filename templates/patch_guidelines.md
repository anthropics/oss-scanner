<!-- Template: optional. Copy to your project or place a copy at projects/<name>/patch_guidelines.md, and replace the examples. Free text, at most 16 KiB. -->
# How we would like patches made

## Size and scope of a fix
- e.g. "as narrow as possible: change only the faulty function, no refactoring" or "fix the whole class of bug in a shared helper, not only the reported call site"

## Code style
- e.g. "few comments: only where the code is not obvious; format with the .clang-format at the root"

## Tests
- e.g. "add a regression test to the nearest existing file under test/"

## Branch and commit message
- e.g. "against the develop branch; subject line in the form 'component: what changed'"
