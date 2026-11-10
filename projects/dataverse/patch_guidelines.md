# How we would like patches made

## Size and scope of a fix
Prefer a focused fix for the demonstrated root cause. Avoid unrelated
refactoring.

## Code style
Follow the conventions of the surrounding Java code and existing Dataverse
patterns. Keep comments limited to cases where the reasoning is not otherwise
clear.

## Tests
Add or update a regression test in the nearest appropriate test area. Run the
relevant tests where feasible, and report any tests that could not be run and
why.

## Branch and commit message
Target the Dataverse develop branch. Use a concise commit subject that
describes the component and change.
