# Threat model

## What this project does

GNU gettext is at the core of internationalization of programs and libraries in a typical GNU/Linux distribution. Thousands of packages rely on the concepts of PO files (message translation catalogs created by translators) and of MO files (message translation catalogs in binary format, read at runtime).

The package is structured as follows:
- `gettext-runtime/` - runtime libraries and programs
- `gettext-runtime/intl/` - runtime library for the C and C++ programming languages, mostly identical to the `glibc/intl/` directory of the GNU C Library,
- `gettext-runtime/intl-java/` - runtime library for the Java programming language
- `gettext-runtime/intl-csharp/` - runtime library for the C# programming language
- `gettext-runtime/intl-modula2/` - runtime library for the Modula-2 programming language
- `gettext-runtime/intl-d/` - runtime library for the D programming language
- `gettext-runtime/src/` - runtime programs for the POSIX shell programming language
- `gettext-runtime/libasprintf/` - an auxiliary library for safe `printf` in C++. Documentation available separately at <https://www.gnu.org/software/gettext/libasprintf/manual/index.html> .
- `libtextstyle/` - a library for styling textual output on terminal emulators via CSS files. Documentation available separately at <https://www.gnu.org/software/gettext/libtextstyle/manual/index.html> .
- `gettext-tools/` - tools and libraries for translators, programmers, and maintainers
- `gettext-tools/src/` - tools for creating or manipulating PO files or MO files
- `gettext-tools/libgettextpo/` - a library for PO file editors
- `gettext-tools/misc/` - a program for fetching the PO files of a package from a translation project
- `gettext-tools/tests/` - unit tests and integration test for the tools and the runtime libraries
- `gettext-tools/gnulib-lib/` - library source code pulled in from GNU gnulib
- `gettext-tools/libgrep/` - library source code pulled in from GNU gnulib
- `gettext-tools/gnulib-tests/` - unit tests for `gettext-tools/gnulib-lib/`
- `gettext-tools/tree-sitter-*/` - library source code for parsing programs in specific programming languages (Rust, TypeScript, Go, D, OCaml) via `xgettext`
- `gettext-tools/autotools/` - a program that integrates with the GNU Build System (`automake` in particular)
- `gettext-tools/wizard/` - another program for users of the GNU Build System
- `gettext-tools/its/` - XML-format specifications for how to handle XML inputs
- `gettext-tools/styles/` - ready-to-use CSS styles for styling textual output on terminal emulators
- `gettext-tools/examples/` - An internationalized "hello world" example in each of many programming languages.
- `gettext-tools/doc/` - Documentation of this package.

## Where untrusted input enters
- For `gettext-runtime/intl/`, untrusted input is in the arguments of the C API functions, in the environment variables, and in the `.mo` files on disk, that are opened by the code in `loadmsgcat.c`. Except that `.mo` files are assumed as having been produced by `msgfmt -c`, see the section "Security considerations" in `gettext-tools/doc/gettext.texi`.
- For the programs built in `gettext-runtime/src/`, untrusted input is in the command-line arguments and in the environment variables.
- For `libtextstyle/`, untrusted input is the CSS file passed to the top-level functions.
- For the `xgettext` program built in `gettext-tools/src/`, untrusted input is the command-line options and the set of argument files that contain program code to scan, possibly each in a different programming language.
- For the `msg*` programs built in `gettext-tools/src/`, untrusted input is the command-line options and the designated files. Except that `.mo` files are assumed as having been produced by `msgfmt -c`, see the section "Security considerations" in `gettext-tools/doc/gettext.texi`.
- For the `libgettextpo` library, untrusted input are the C API invocations. Except that the caller is supposed to respect the comments in the `gettext-tools/libgettextpo/gettext-po.in.h` file.

## Components that matter most / least
- The most important component is `gettext-runtime/intl/`, the runtime library.
- The next most important components are the programs in `gettext-runtime/src/`, since they are called by shell scripts.
- The next most important components are `msgmerge` and `msgfmt`, because they are used on the server side of translation projects.
- The next most important component is `xgettext`, because it processes source code provided by developers to the package maintainer.
- The next most important components are the other `msg*` programs.

## How to exercise it

Once built, the programs can be invoked via the command line.

The unit tests and integration tests in `gettext-tools/tests/` can be invoked individually through
```
make check TESTS=testname
```
or — for investigation of failures —
```
make check TESTS=testname KEEP=yes
```

For each of the programming languages, there is an integration test `lang-<language>`, that is a good starting point for exercising the facilities in that programming language. For instance, to exercise the facilities in the C++ programming language, start with one of `lang-c++`, `lang-c++20`, `lang-c++26`, `lang-c++-boost`.

## How you rate severity

We rate severity by considering how the possible attack scenarios could be realized in the real world. That is, what could a malicious translator do, what could a malicious programmer (who is not package maintainer) do, and so on.

When a program crashes (be it through an `abort()` call, a SIGSEGV, or a stack overflow (unless provoked by an unusually low `ulimit` command)), it is a bug worth reporting. Whether it is security relevant, is a different issue, to be evaluated through the attack scenarios (see above).

## Anything to leave alone

Don't report compiler warnings. Especially not those from `clang`, which has a higher verbosity by default.

## How to report a vulnerability

For each vulnerability or bug, we like to have a "how to reproduce". For the programs, that includes the command-line options and, if present, specific input files. For the libraries, that would be a piece of source code (in C for libintl and libgettextpo, in C++ for libasprintf, and so on) that exercises the particular API.

Don't bother proposing a patch, because we know how to code ourselves.
