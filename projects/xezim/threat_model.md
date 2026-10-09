# Threat model: xezim

## What this project does and where untrusted input enters
xezim is an IEEE 1800 SystemVerilog simulator (CLI binary `xezim`). It parses,
elaborates and simulates designs and testbenches. Untrusted input enters as:
- SystemVerilog/Verilog source files, include files, macros and `-f` argument
  files given on the command line (the main attack surface: lexer,
  preprocessor, parser, elaborator, constant evaluation, the bytecode compiler
  and the Cranelift JIT that compile the design);
- data files read by the design at run time (`$readmemh`/`$readmemb`,
  `$fscanf`, `$fgets`, plusargs);
- the `-xezim_env` and `-fst_scope_file` option files;
- UPF files (`--upf`).

Treat a design as untrusted *data*: simulating a malicious source file should
never corrupt memory, execute native code outside the language's semantics,
or crash the simulator with a memory-safety bug.

## Components that matter most / least
- Most: everything reachable from a source file: preprocessor, parser and
  elaborator (xezim-core git dependency), constant evaluation, the bytecode
  compiler and interpreter, the Cranelift JIT and the native/AOT code paths,
  and any `unsafe` code (JIT memory, packed-value storage, FFI glue).
- Also in scope: the FST/VCD waveform writers, `$readmem*`/`$writemem*`, and
  the option-file parsers.
- Less: the VPI and DPI interfaces. `--dpi-lib`, `-pli` and VPI load native
  shared libraries chosen by the user; they run native code by design and are
  trusted. Bugs in xezim's own glue for them still count.
- Out of scope: `$system` and file-access system tasks doing what IEEE 1800
  says they do (a design may legitimately run commands and read or write any
  path the user can); vendored third-party UVM sources.

## How to exercise it
- `target/release/xezim -s <top> file.sv` simulates a design; `--fst out.fst`
  also writes waveforms. `target/debug/xezim` has overflow checks and debug
  assertions on.
- `tests/` holds the regression corpus: Rust test files with embedded
  SystemVerilog sources; `cargo test --release --test <group>` runs a group
  (`misc`, `classes`, `scheduling`, `types`, `collections`, `strings`, `lrm`,
  ...).

## How you rate severity
- Critical: memory corruption or native code execution caused by a source or
  data file (JIT/unsafe/FFI bugs), on the default command line.
- High: memory-safety bugs needing an unusual option, or out-of-bounds reads
  leaking host memory into simulation output.
- Medium: a panic, hang or unbounded memory growth from a small malicious
  input (denial of service of a local tool).
- Low: wrong simulation results that are not security-relevant are bugs, not
  vulnerabilities; please don't report them here.

## Anything to leave alone
- Do not report that `$system`, DPI, VPI or `-pli` can run arbitrary code;
  that is their purpose.
- Do not report resource exhaustion from designs that legitimately need large
  memory or long run times.
