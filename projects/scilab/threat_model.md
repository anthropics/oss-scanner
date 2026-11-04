# Scilab threat model

Scilab (https://www.scilab.org) is an open-source numerical computation package: a dynamic
language interpreter for scientific computing, with ~30 modules under `modules/`, each mixing
Scilab macros (`.sci`), native C/C++ (and some Fortran) primitives, and Java. The GUI and help
browser are Java (Swing + JCEF/Chromium); Xcos (the dynamic-systems model editor and simulator)
is C++ + Java; graphics are C++.

## What this project does and where untrusted input enters

Scilab is a desktop application, not a network service. The user is trusted; the files and data
they open are not. Untrusted input enters through the C/C++ and Java code that parses, all
reachable from the command line or a one-line script:

- Binary scientific data formats: HDF5 (`.sod` saves, `load`/`save`), MAT-Files
  (`loadmatfile`), Parquet and Arrow (`parquetRead`), Excel workbooks (`xlsxRead`,
  `readtable`), CSV (`csvRead`), WAV/audio (`wavread`/`loadwave`), images.
- Xcos diagram files (`.xcos`/`.zcos` XML, `.ssp` SSP packages) and the simulation code that
  the editor runs from them.
- The macro/language layer itself: PCRE2 regexes, the parser and bytecode interpreter in
  `modules/`, XML help pages (libxml2), gettext catalogs.
- Network-facing code that a user can switch on: the HTTP/WebSocket server and client
  bindings (cppserver/curl), and the ATOMS module manager that downloads and installs
  third-party toolboxes over HTTPS.

Anything in the prebuilt prerequisites (see "out of scope" below) is linked in, so a bug in
our glue code around those libraries is in scope even when the library itself is not.

## Components that matter most / least

- Most: the native (C/C++/Fortran) code that parses data files and diagrams without any
  scripting — `modules/hdf5`, `modules/spreadsheet`, `modules/xcos` and its simulator,
  `modules/sound`, `modules/matio`, `modules/fileio`, and the interpreter core
  (`modules/core`, `modules/ast`, `modules/io`).
- Less, but in scope: the Java GUI and help browser, the graphics stack, the HTTP/WebSocket
  bindings.
- Least: demos, packaging scripts, ATOMS repository metadata.

## How to exercise it

- Build artifacts sit in the checkout after the build: run the interpreter from
  `/src/scilab` as `./bin/scilab-cli -nwni -l en_US -quit -e "<code>"` (text-only, no GUI,
  fastest) or `./bin/scilab -nw` under `xvfb-run` when graphics are needed.
- One test per feature: `test_run("<module>")` from a Scilab session runs
  `modules/<module>/tests/unit_tests/` and `tests/nonreg_tests/`, each `<name>.tst` checked
  against its sibling `<name>.dia.ref`.
- Untrusted input is easiest to exercise by writing a crafted file and loading it with the
  documented function (`load`, `loadmatfile`, `xlsxRead`, `csvRead`, `readtable`, `wavread`,
  Xcos `load`/`xcos_simulate`...), e.g. from a small `.sce` script run in `-nwni` mode.

## How you rate severity

- Any memory-safety bug (buffer overflow, use-after-free, double free, unchecked
  format string) reachable from parsing a data file or diagram is **high** at minimum; if it
  can plausibly yield code execution from just opening a crafted file, it is **critical**.
- The same class of bug reachable only by running a malicious `.sci`/`.sce` script is
  **medium** at most: a script is arbitrary code by design (documented `system`, file I/O,
  `dynamic_link`), so only the memory corruption itself counts, not the code it runs.
- DoS from a malformed file (crash, hang, exhaustion) is **medium**; a hang inside a script
  the user wrote is not a vulnerability.
- Java GUI issues are rated one step lower than their native equivalent (XSS/UI spoofing is
  **low**, RCE stays **critical**).

## Anything to leave alone

- Do not report the interpreter's unrestricted power (no sandbox, scripts can execute
  commands) as a vulnerability: it is the documented design, not a bug.
- Do not report the `modules/dynamic_link` machinery as a protection bypass: `link`,
  `call`, `addinter` and `ilib_build` exist precisely to compile and load arbitrary
  C/C++/Fortran libraries into the Scilab process at runtime. There is no boundary to
  cross and nothing to protect; findings that depend on this feature (arbitrary code
  execution, memory corruption in a user-supplied library, hijacking of the compiler
  or the loaded `.so`) are out of scope. Only bugs in the feature itself that corrupt
  memory while using documented, legitimate inputs are in scope.
- Do not report issues in the prebuilt third-party artifacts the build downloads
  (`lib/thirdparty/`, `thirdparty/` jars, `java/jre`, the bundled JCEF/Chromium): they are
  binaries, not built from this repository's sources — we forward those upstream. The
  binding/glue code in `modules/` around them stays in scope.
- Do not report compiler warnings, deprecations, or unaligned-access pedantry on x86.

## Reports and patches

Please write reports and reproducers as a short `.sci`/`.sce` script using documented
functions only, runnable in `-nwni` mode. Patches should follow the existing module style
(C++ through the api_scilab headers, `_("...")` for user-facing strings) and add a nonreg test
`<name>.tst` with its `.dia.ref` when the fix is testable.
