# How we would like patches made

## Size and scope of a fix
as narrow as possible: change only the faulty function, no refactoring

## Code style
format with the .clang-format in /src

## Tests
add a regression test in a new file under the per-component tests/ for those that have one, or create one for those that do not

## Branch and commit message
against the main branch; subject line in the form 'component: what changed'; include a Signed-off-by: line per the DCO; see /src/CONTRIBUTING.md
