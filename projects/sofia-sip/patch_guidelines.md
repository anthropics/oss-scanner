# How we would like patches made

## Size and scope of a fix
- As narrow as possible: change only the faulty function, no refactoring, no reformatting of nearby lines.
- If the same mistake is repeated in sibling header parsers, fix them in the same patch and say so.
- Keep exported API and ABI unchanged. Add a new function rather than change an existing one.

## Code style
- Match the surrounding code: two-space indentation, C89 (declarations at the top of a block), `/* */`
  comments only.
- Do not add a comment explaining the fix; the reasoning goes in the report.

## Tests
- Add a regression case to the nearest existing test program for the module (for example
  `msg/test_msg.c`, `sip/torture_sip.c`, `sdp/torture_sdp.c`, `url/torture_url.c`,
  `sresolv/torture_sresolv.c`), or a sample message under `sip/tests/` wired into `run_test_sip_msg`.
- Test comments describe the input and the expected outcome only.
- `make check` must pass.

## Commit message
- Against master. Subject in the form "Reject <input> <condition>" or "Fix <function> <behaviour>",
  in the imperative, without the words overflow, crash, exploit, vulnerability or CVE.
- A short body stating which input is now rejected or handled, nothing more.
