# Patch format

Keep fixes focused on the demonstrated defect and follow the surrounding C++
style. Preserve public API and persisted-data compatibility where possible.
Explain any unavoidable compatibility change. Add deterministic regression tests
that fail before the fix and pass afterward, exercising the production path.
For shared validation rules, cover all affected callers and relevant activation
boundaries. Avoid unrelated refactoring and dependency updates. Include the
commands and results used to validate the patch; identify untested configurations.
