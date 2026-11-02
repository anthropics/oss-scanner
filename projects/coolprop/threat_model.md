# Threat model

## What this project does and where untrusted input enters

CoolProp is a C++17 library of thermophysical properties: equations of state for pure fluids and
mixtures (Helmholtz-energy, cubic, PC-SAFT, GERG, IF97), humid air, incompressible fluids, transport
properties, and tabular / SVD-SBTL interpolation backends. It is called from engineering software and
from services: the Python package; the C API shared library, which the Excel, Julia, Rust, Fortran and
LabVIEW wrappers call; SWIG wrappers; and a WebAssembly build that runs in browsers. Online property
calculators can pass user-typed fluid names and state values straight through.

Untrusted input, most important first:

1. **Fluid strings, parameter names and numeric state values** passed to `PropsSI`, `Props1SI`,
   `PhaseSI`, `HAPropsSI`, `AbstractState::factory` / `AbstractState_factory`, `update`, and
   `keyed_output`. Treat all of these as attacker-controlled: any byte string, any double (NaN, inf,
   denormals, huge or negative). Fluid strings have a grammar of their own:
   `BACKEND::Name1[x1]&Name2[x2]`, the `BICUBIC&HEOS::` / `SVDSBTL&HEOS::` families, INCOMP
   concentrations (`INCOMP::MEG-20%`), legacy `REFPROP-MIX:` prefixes, and a factory-options suffix
   `?{json}` or `?@<path>` (`src/CoolProp.cpp` `extract_backend` / `extract_fractions`,
   `src/DataStructures.cpp`, `src/FactoryOptions.cpp`, `src/AbstractState.cpp`). Factory-options JSON
   that arrives inside a fluid string is item-1 input, not item 3.
2. **The C API boundary** (`src/CoolPropLib.cpp`, `include/CoolProp/CoolPropLib.h`): caller-supplied
   output buffers with length arguments, input/output arrays with lengths, integer handles, and integer
   parameter / input-pair indices. No C++ exception may escape this boundary.
3. **JSON or text supplied at runtime as fluid data**: `add_fluids_as_JSON` (HEOS, SRK/PR, PCSAFT,
   INCOMP), `set_interaction_parameters`, `set_departure_functions` (JSON or REFPROP HMX.BNC text), and
   the transport-property expression language those fluid files may carry (`src/expression/`).
   Applications sometimes accept user-uploaded fluid files. Parsed with nlohmann::json; some paths are
   also schema-validated with valijson, others are not.
4. **Cache files on disk**, written by CoolProp and read back on later runs: tabular tables under
   `~/.CoolProp/Tables` (`ALTERNATIVE_TABLES_DIRECTORY`) and SVD-SBTL surfaces under
   `~/.CoolProp/SVDTables` (`ALTERNATIVE_SVDTABLES_DIRECTORY`), both zlib-compressed msgpack
   (`src/Backends/Tabular/`, `src/SBTL/SVDSurfaceSerializer.cpp`), plus the uncompressed binary
   critical-patch sidecar next to the SVD surfaces (`src/Backends/SVDSBTL/SVDSBTLBackend.cpp`). A crafted
   cache file needs write access to the user's cache directory, or a shared/networked home or table
   directory.

Trusted (not an attack surface): the fluid library compiled into the binary; configuration set by the
embedding application, whether through `set_config_string`, `set_config_as_json_string` or environment
variables (`ALTERNATIVE_*` paths, `COOLPROP_REFPROP_ROOT`, ...); and the REFPROP shared library CoolProp
loads when the application asks for the REFPROP backend. Which library is `dlopen`ed is the
application's decision by design.

**The `?@<path>` suffix is a feature for trusted callers.** It makes CoolProp read a JSON options file
named in the fluid string. That a fluid string can name a file to open is by design and is not, by
itself, a finding; services that forward user-typed fluid strings are expected to reject `?`. What is
in scope: memory-safety bugs on that path, and any way the *contents* of the named file come back to
the caller (in an error message, an output value, or a side channel). See the severity rules below.

## Components that matter most and least

- Matters most: the string parsing in item 1; `src/CoolPropLib.cpp`; `src/Backends/Helmholtz/`
  (HEOS, mixtures, flash routines, `MixtureParameters.cpp`), `src/HumidAirProp.cpp`,
  `src/Backends/Incompressible/`, `src/Backends/Cubics/`; the IF97 backend, including the CoolProp-owned
  `IF97.h` that CPM fetches from github.com/CoolProp/IF97; the JSON loaders; the expression parser.
- Medium: the table/surface deserializers (item 4); `src/Backends/Tabular/`, `src/Backends/SVDSBTL/`,
  `src/SBTL/`, `src/SVD/`, `src/Region/`.
- Lower: `src/Backends/REFPROP/` (only reachable when a licensed REFPROP is installed; its
  fixed-length Fortran string buffers are still in scope); `src/nanobind_interface.cxx` (the Python
  module, not built in this image), `src/emscripten_interface.cxx`, `src/CoolProp.i`.
- Out of scope: `externals/` and the third-party code CPM fetches (Eigen, nlohmann_json, valijson,
  msgpack-c, fmt, Catch2, boost-headers) except where CoolProp misuses it; `wrappers/` other than the C
  API they call; `dev/` (fitting and table-generation scripts, CI); `Web/` and `doc/`; `src/Tests/`.

## How to exercise it

- `/usr/local/bin/coolprop-driver` reads one command per line on stdin and calls the C API of the
  AddressSanitizer build of `libCoolProp.so`. It prints one line per command: a number, `ok`, or an
  error line carrying CoolProp's message.
  - `props D T 300 P 101325 Water`
  - `props Q P 101325 H 2e5 HEOS::Methane[0.5]&Ethane[0.5]`
  - `haprops W T 300 P 101325 R 0.5`
  - `state HEOS Water PT_INPUTS 101325 300 Dmolar`
  - `json HEOS /tmp/fluid.json`, `config ALTERNATIVE_TABLES_DIRECTORY /tmp/t`

  Arguments are split on whitespace, so an argument cannot contain a space or be empty, and lines over
  1 MiB are rejected. For JSON with spaces, or anything else the driver cannot express, write C or C++
  against `/src/include/CoolProp/CoolPropLib.h` (source of the driver: `/opt/coolprop-driver/driver.c`)
  or `AbstractState.h`, and link `-L/src/build-asan -lCoolProp -Wl,-rpath,/src/build-asan` with
  `-fsanitize=address`.
- `/src/build-asan/CatchTestRunner` runs the Catch2 suite (also ASan). Select by tag, e.g.
  `"[FactoryOptions]"`, `"[json]"`, `"[expression]"`, `"[flash]"`. The everyday scope `"~[slow]"` takes
  an hour or more under ASan; prefer a narrow tag. `[slow]` and `[SVDSBTL]` tests build large SVD tables
  and take many minutes each; avoid them unless the finding is in that code. `[REFPROP]` / `[refprop]`
  tests skip: REFPROP is not in the image. `[!benchmark]` tests are hidden by default, but a positive tag
  filter pulls them back in; add `~[!benchmark]` (their timing assertions are meaningless under ASan).
- Example fluid JSON lives in `dev/fluids/*.json`, mixture parameters in `dev/mixtures/`, and
  incompressibles in `dev/incompressible_liquids/`.
- `ASAN_OPTIONS=detect_odr_violation=1` is set in the image, as in CoolProp's CI: at -O2 the vendored
  `externals/miniz-3.1.1/miniz.c` has two identical internal-linkage arrays merged onto one address,
  which the default level-2 ODR check misreports.

## How we rate severity

"Item 1", "item 3" and "item 4" refer to the input classes above.

- Out-of-bounds write, use-after-free or double free reachable from item-1 input, or from a C API
  call whose arguments are within the documented contract: **critical**.
- Out-of-bounds read reachable the same way: **high**.
- The contents of a file named by `?@<path>` (or any other file) returned to the caller of an item-1
  function, in an error message, output or otherwise: **medium**. Merely opening the file: not a finding.
- A C API function that fails to reject an argument it could check, and then corrupts or reads memory
  out of bounds: **high**. "Could check" means a negative or zero length, an out-of-range parameter or
  input-pair index, or a handle that was freed or never issued. A declared buffer length larger than the
  real buffer cannot be detected by any callee and is not a finding.
- A C++ exception escaping the C API, or a null dereference / abort, from item-1 input: **medium**.
- The same bugs reachable only through item-3 input: one level lower. Only through a crafted cache file
  (item 4): two levels lower, minimum **low**.
- An infinite loop, unbounded recursion (stack exhaustion) or unbounded allocation (decompression bomb,
  a size field driving `resize`) from item-1 input: **medium**; from item 3: **low**; from item 4:
  **low**. Slow but terminating solves: out of scope.
- Wrong property values, NaN or huge-value results, non-convergence, or a thrown `CoolProp::ValueError`
  / `SolutionError` for nonsensical input: **not security issues**. That is the documented way CoolProp
  reports bad input.

## Anything to leave alone

- Numerical accuracy, thermodynamic consistency and solver robustness are not security findings; we track
  them in our own tests.
- Floating-point exceptions (division by zero, overflow to inf, invalid to NaN) are expected inside the
  solvers and are caught or propagated as NaN.
- Behaviour that needs the attacker to control configuration, environment variables, or the REFPROP
  library path is trusted-caller territory (see above), unless it can be reached from item-1 input.
- Issues in Eigen, nlohmann_json, valijson, msgpack-c or miniz themselves belong upstream; report them
  only if CoolProp's use of the library is what makes them reachable.
- Reports: please include a reproducer as `coolprop-driver` input or a short C/C++ program, the ASan
  trace, and a minimal patch against `master` in CoolProp's style (clang-format config in the repo).
