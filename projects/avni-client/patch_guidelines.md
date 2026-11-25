Patch guidelines

- Keep the fix narrow: change only what closes the reported issue. No refactoring, renaming or reformatting of
  surrounding code.
- Match the surrounding style and the formatter settings in the repository. Do not add comments; use clear names.
- Bind values as query parameters. Do not build SQL, shell commands or evaluated code by concatenating or formatting
  request or stored values into them.
- Add a regression test beside the existing tests of the affected module.
- Do not upgrade dependencies or the runtime as part of a fix unless the upgrade is the fix.
