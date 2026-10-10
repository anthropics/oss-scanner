# radare2

radare2 is a reverse engineering framework and a set of command-line tools used
to inspect executables, firmware, memory dumps and malicious files. It also
provides C libraries embedded by other applications. File contents, metadata,
lengths, offsets, counts and instruction bytes must be treated as untrusted.

## Scope and trust boundaries

- Prioritize binary parsers in `libr/bin`, architecture decoders in `libr/arch`,
  analysis in `libr/anal`, filesystem and archive readers in `libr/fs`, and the
  buffer, string and decompression helpers used by these paths.
- Look for out-of-bounds access, integer overflow affecting sizes or offsets,
  use-after-free, double free, unbounded recursion, infinite loops and excessive
  resource consumption reachable while inspecting crafted inputs.
- Input-derived names and metadata must not unexpectedly become radare2 commands,
  shell commands or output paths. Command injection and extraction path traversal
  are relevant when the attacker controls data rather than the user's commands.
- Network protocols and HTTP services are in scope when explicitly enabled;
  document the configuration, authentication and attacker access required.
- radare2 intentionally supports shell commands, scripts, native plugins,
  debugging and writes to files. Explicitly requesting those operations is not
  itself a vulnerability. Distinguish these capabilities from unintended execution
  caused by parsing a file, and evaluate sandbox bypasses against the documented
  restrictions of the selected mode.
- Include bundled dependencies when a finding is reachable through radare2;
  identify the upstream component and avoid duplicating an existing report.

## Build and exercise

The checkout is at `/src`; the tools and libraries are installed in `/usr/local`.
The build retains debug information, frame pointers and downloaded subprojects.
The regression corpus is already in `/src/test/bins`, and Python r2pipe is
available in the environment. Do not execute sample binaries from the corpus.

From `/src`, run targeted regression tests with `r2r -C test db/formats/elf`
or select another existing file under `test/db`. Run the normal suite with
`r2r -C test`; see `test/README.md` for optional suites and requirements.
Unit tests can be built and run with `make -C test unit-tests`.

Useful entry points include `rabin2 -I sample`, `rabin2 -S sample`, and
`r2 -N -q -c 'aaa;q' sample`. Keep the filename last. Do not use `-n` to
exercise binary parsers: it disables binary loading.

For an offline sanitizer rebuild, run `make clean`, then configure with
`CFLAGS='-O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined'` and
`LDFLAGS='-fsanitize=address,undefined'`, retaining `--prefix=/usr/local` and
`--without-syscapstone`. Run `make -j2 && make install && ldconfig` afterward.
Avoid `make mrproper` and `sys/sanitize.sh` offline: they remove downloaded
dependencies. See `DEVELOPERS.md` for further error-diagnosis guidance.

## Reports and fixes

Report the exact revision, build flags, invocation, minimized input, sanitizer
trace or timeout, root cause and attacker-controlled fields. Separate demonstrated
impact from possible exploitability: a crash alone does not establish code
execution, and a local parsing bug is not automatically a remote vulnerability.
For denial of service, include input size and observed time or memory consumption.
Group multiple manifestations of the same root cause into one report.

Prefer small fixes using existing radare2 APIs and focused `r2r` regressions.
Follow `AGENTS.md` and `DEVELOPERS.md`; binary fixtures belong in the separate
radare2-testbins repository. Check related parser paths for the same missing
validation. Avoid unrelated refactors or blanket suppression of malformed inputs.

The project's `SECURITY.md` describes its disclosure policy and security contact.
Scanner reports can be sent to the primary contact configured in `project.yaml`.
