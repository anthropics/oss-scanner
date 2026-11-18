# Threat model

## What this project does and where untrusted input enters

libipuz loads, edits and saves crossword and word puzzles in the
[ipuz](https://libipuz.org/ipuz-spec.html) format, a JSON-based format.
It is a C library built on GLib/GObject and json-glib, with parts of the
core (guesses, charsets, enumerations, cell coordinates) written in Rust
and exposed through a C FFI (`libipuz/rust/src/ffi.rs`).

Treat every puzzle file as untrusted. Puzzles are downloaded from the
internet and shared by email, and GNOME Crosswords' thumbnailer parses
`.ipuz` files automatically when a file manager shows a folder containing
them, with no user action beyond browsing to it.

The untrusted entry points are:

- `ipuz_puzzle_new_from_file()`, `ipuz_puzzle_new_from_stream()` and
  `ipuz_puzzle_new_from_data()`: the full puzzle parser, including every
  puzzle kind (crossword, cryptic, barred, arrowword, acrostic, filippine,
  nonogram, vocab, ...), clues, clue sets, styles and puzzle metadata.
- `ipuz_guesses_new_from_file()` and `ipuz_guesses_new_from_stream()`:
  saved player progress.
- The HTML-to-Pango-markup conversion in `libipuz/ipuz-misc.c`. Several
  text fields (titles, clues, notes, ...) may contain a subset of HTML,
  which is converted to Pango markup at parse time. Callers hand the
  result straight to Pango, so the output must always be well-formed,
  escaped markup.

## Components that matter most / least

- Most important: the parsers above, the HTML-to-markup conversion, and
  the Rust FFI boundary (lengths, NULL handling, string encoding, locking).
- In scope but lower priority: the editing API (`ipuz_*_set_*()`,
  `ipuz_*_fix_*()`), which callers drive with their own data.
- Out of scope: misuse of the C API by the caller (NULL or wrong-type
  arguments, use after unref). These are guarded with `g_return_if_fail()`
  by GLib convention and are caller bugs. Also out of scope: `docs/`,
  `po/`, `build-aux/`, `ci/` and the test programs themselves.

## How to exercise it

- `meson test -C /src/build` runs the C tests and the Rust unit tests.
- The test programs in `libipuz/tests/` load the `.ipuz` and `.guesses`
  files next to them; that corpus is a good starting point for malformed
  inputs.
- `/src/build-asan` has the same tests built with ASan and UBSan.

## How you rate severity

- Memory corruption (overflow, use-after-free, double free) reachable from
  a parsed file: high. Critical if it is plausibly controllable.
- Malformed markup out of the HTML conversion (unescaped `<`, `&`,
  unbalanced tags) that a caller would pass to Pango: medium.
- A file that crashes, aborts, asserts, deadlocks or hangs the parser: low
  to medium. It mostly hits the thumbnailer, which GNOME runs sandboxed.
- Excessive memory or CPU from a huge but well-formed puzzle: low.
- `g_critical()`/`g_warning()` output from bad input, with no crash: low.

## How we would like reports

- A minimal `.ipuz` (or `.guesses`) file that reproduces the problem, plus
  the test or command that triggers it.
- Patches that match the surrounding code; `cargo fmt` for Rust.

## Anything to leave alone

- Memory leaks on error paths are useful but not security issues; please
  report them separately and with low severity.
