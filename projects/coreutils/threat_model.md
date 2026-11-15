# Threat model

## Project summary

coreutils is the reference C implementation of the standard Linux command line utilities.
There will be 100 or so binaries built in the src/ directory.

## Project specific details

### Interaction

To run a test in isolation:
  make check TESTS=test/foo/bar.sh SUBDIRS=. VERBOSE=yes RUN\_EXPENSIVE\_TESTS=yes

To run a test directory in isolation:
  make check SUBDIRS=tests/misc VERBOSE=yes

It's important that any changes pass higher level checks, performed with:
  make syntax-check

### Directory Structure
- `src/` - Main source code for all coreutils programs
- `lib/` - Core utility library generated from gnulib
- `gl/` - coreutils libs, which may be copied to gnulib in future
- `gnulib/` - Gnulib submodule (external dependency)
- `tests/` - test suite in perl and shell, with a preference for shell
- `doc/` - Documentation and man page sources
- `man/` - Generated man pages
- `build-aux/` - Build system scripts and utilities

Note the gnulib/ directory is a separate project which will be analyzed independently,
so only report issues there that directly affects the coreutils project.

### Code Style
- **Indentation**: 2 spaces (no tabs) in all files except Makefiles
- **Braces**: Required for multi-line blocks, optional for single-line blocks
- **Line Length**: 72 characters for commit messages, keep code <= 80 characters
- **Comparison Operators**: Prefer `<` and `<=` over `>` and `>=`
- **Whitespace**: Avoid trailing whitespace
- **Types**: Prefer idx\_t to size\_t or int

### Commit Message Format
```
program_name: brief description (the why)

Detailed explanation if needed. (the what)
* file1 (function1): Description of change.
* file2 (function2): Another change.
```

## Security sensitive aspects

These utilities do not access the network, nor do they run as persistent services.
Utilities need to be resistant to TOCTOU races, symlink attacks, memory corruption.
Some utilities parse input are: cksum --check, basenc, date, od.

## How to act on a vulnerability

Ideally a simple command line reproducer should be given in the summary.
Also if proposing a patch, ideally a test would be provided
as that can more robustly and concisely detail the issue.
