# How we would like patches made

## Size and scope
- As narrow as the bug: fix the faulty function, do not refactor around it. If the same
  mistake appears in several places, fix the reported one and name the others in the
  report instead of changing them all.
- Keep the fix on the same side of the boundary as the bug. Validate a bad header where
  it is parsed, not in the caller that happens to notice.
- Reject bad input by returning an error (a negative errno for a FUSE operation, `false`
  or a negative result elsewhere) and logging with the `S3FS_PRN_*` macros. The project
  builds with `-fno-exceptions`: do not add a `throw`, and do not rely on one.
- No behaviour changes beyond the fix. In particular, do not add or rename a mount
  option unless the bug cannot be fixed without one; if it cannot, say so in the report.

## Code style
- C++17, four spaces, no tabs. Follow the surrounding code closely: `if(cond){` with no
  space after the keyword, `}else if(cond){` on one line, `}` on its own line.
- Prefer what the codebase already uses: `std::string`, `std::optional`,
  `std::string_view`, `std::unique_ptr` with the `unique_ptr_*` deleters in
  `src/types.h`, and `std::scoped_lock` or `std::lock_guard` for the mutexes. No new raw
  `malloc`/`free` or owning raw pointers.
- Few comments. Where the reason for the fix is not obvious from the code, use the
  project's form:

      // [NOTE]
      // why this is here, in prose
      //

- Never log a secret: pass credentials and signing material through
  `mask_sensitive_string()`.
- A patch must keep `make cppcheck`, `make clang-tidy` and `make shellcheck` clean.

## Tests
- Add a regression test. If the bug is reachable from a parser or from arithmetic, add a
  case to the matching `src/test_*.cpp` (`test_s3objlist`, `test_metaheader`,
  `test_curl_util`, `test_string_util`, `test_cache_node`, `test_page_list`): these run
  without a mount and are the form we most want.
- If it can only be shown through the mounted file system, add a function to
  `test/integration-test-main.sh` next to the closest existing test and register it with
  `add_tests`, following the style of its neighbours. Avoid `sleep`; wait for a
  condition instead.
- A test that fails before the fix and passes after it. Say in the report which it is.

## Branch and commit message
- Against `master`.
- Subject: one imperative sentence, capitalised, no trailing period, no component prefix
  — "Do not trust the Content-Length of a HEAD reply", in the style of the existing
  history. A body only if the reason is not obvious from the subject and the diff.
