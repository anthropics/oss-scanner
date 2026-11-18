# ecCodes threat model

## What ecCodes does and where untrusted input enters

ecCodes is a C++ library (with a C API, `src/eccodes/eccodes.h`) and a set of command-line tools that decode and
encode the WMO formats GRIB edition 1 and 2 and BUFR edition 3 and 4, and read GTS bulletins, METAR and TAF.
Weather services, data portals and downstream libraries (Python cfgrib/eccodes-python, xarray, MetPy, MIR,
Magics, Fortran models) call it on files that they download from other centres, from the WMO Information System
and from public archives. **Treat every GRIB, BUFR, GTS, METAR and TAF message, and every byte of a file that
holds such messages, as attacker-controlled.**

Untrusted input reaches the code through:
- `codes_handle_new_from_file`, `codes_handle_new_from_message(_copy)`, `codes_any_new_from_file`,
  `codes_bufr_handle_new_from_file`, `codes_grib_handle_new_from_file` (with any `ProductKind`, also GTS/METAR/TAF)
  (but not `codes_*_new_from_samples`, see below);
- reading keys from such a handle: `codes_get_long/double/string/bytes(_array)`, `codes_get_size`,
  `codes_get_length`, the keys iterators, the BUFR `unpack` key (expansion of the data section), the GRIB
  geo-iterator (`codes_grib_iterator_new`), nearest-neighbour search (`codes_grib_nearest_*`), `codes_dump_content`;
- message scanning and splitting of files (`grib_count`, `codes_count_in_file`, multi-field GRIB2
  (`codes_grib_multi_support_on`), `codes_extract_offsets_malloc`, the index API `codes_index_*` and the
  fieldset API over untrusted files, and index files written by `grib_index_build`);
- the packing schemes when decoding values: simple, complex and spectral packing, second-order packing, JPEG 2000
  (via OpenJPEG), PNG, CCSDS/AEC, IEEE, run-length, etc.;
- re-encoding an untrusted message: setting keys on a handle created from an untrusted message, `codes_copy`,
  changing the edition, repacking, `codes_get_message`, writing it out;
- the command-line tools reading untrusted files: `grib_dump`, `grib_ls`, `grib_get`, `grib_get_data`,
  `grib_compare`, `grib_copy`, `grib_set`, `grib_to_netcdf`, `grib_filter`, `bufr_dump` (also with
  `-E c|fortran|python|filter`, which generates source code from the message), `bufr_ls`, `bufr_compare`,
  `bufr_copy`, `bufr_filter`, `gts_*`, `metar_*`, `taf_*`, `codes_info`, `codes_count`, `codes_split_file`.

Trusted (an attacker who controls them can already run code, so do not report bugs that need them to be
malicious):
- the definition files (`definitions/`, `ECCODES_DEFINITION_PATH`, `ECCODES_EXTRA_DEFINITION_PATH`) and the
  samples (`samples/`, `ifs_samples/`, `ECCODES_SAMPLES_PATH`). They are installed with the library. Bugs in the
  definition *parser* are only low severity. Note that the definitions are an interpreter driven by the message:
  a message may select any table, template, local section or concept that the definitions offer (for example
  through the centre, edition, templateNumber or localDefinitionNumber), and that path is in scope;
- `grib_filter`/`bufr_filter` rules files, command-line options and environment variables;
- values that the calling application itself passes to `codes_set_*` (except where the size of the buffer or
  array that the API promises to check is ignored).

## Components that matter most / least

Most important (decoding untrusted messages):
- `src/eccodes/accessor/` (the accessors that interpret sections, bitmaps, packed data, BUFR descriptors and
  data expansion), `src/eccodes/grib_bits*.cc`, `src/eccodes/grib_io.cc` (message scanning in files),
  `src/eccodes/grib_handle.cc`, `src/eccodes/grib_value.cc`, `src/eccodes/action/`, `src/eccodes/expression/`,
  `src/eccodes/geo/` (geo-iterators, nearest), the packing/unpacking accessors (`accessor/Data*Packing*`, e.g.
  `DataCcsdsPacking`, `DataJpeg2000Packing`, `DataPngPacking`, `DataComplexPacking`, `DataG2ComplexPacking`,
  `DataSecondOrder*`) with `grib_openjpeg_encoding.cc`/`grib_jasper_encoding.cc`, the BUFR code (`bufr_util.cc`,
  `accessor/ExpandedDescriptors`, `accessor/BufrDataArray`, `accessor/Bufr*`), the index and fieldset code, the dumpers (`src/eccodes/dumper/`).
- `tools/` (the command-line tools; `grib_to_netcdf` and `bufr_dump` are widely used in pipelines).

In scope but less important: the encoding paths, `grib_util_set_spec` (used by MIR/interpolation), the Fortran
and Python interfaces (thin wrappers).

Out of scope: `third_party/`, `deprecated/`, `examples/` and `tests/` (drivers only), the `rust/` crates (bindings),
`memfs.py` (build-time generator), the dependencies (OpenJPEG, JasPer, libaec, libpng, NetCDF, zlib). Report a
dependency bug only when ecCodes passes it invalid arguments.

## How to exercise it

The image has two build trees:
- `/src/build`: RelWithDebInfo, the regression test suite (`cd /src/build && ctest -LE download_data -j$(nproc)`,
  log in `/src/build/ctest.log`) and the downloaded test data in `/src/build/data/` (hundreds of real GRIB, BUFR,
  GTS and METAR files, including many from ECMWF bug reports).
- `/src/build-asan`: ASan + UBSan build of the library, tools (`/src/build-asan/bin/`) and tests. Run tools with
  `ECCODES_DEFINITION_PATH=/src/build-asan/share/eccodes/definitions`.

`ASAN_OPTIONS` disables leak detection: leaks are not security bugs here, except unbounded growth while
processing a single file.

Good reproducers are a small GRIB/BUFR file (hex dump or a Python script that writes it) plus the command line
of an ecCodes tool (`grib_dump`, `bufr_dump -j`, `grib_get_data`, ...) or a few lines of C against the public
API, with the sanitizer output from `/src/build-asan`.

## How we rate severity

- **Critical**: a memory-safety bug triggered by an untrusted message through the normal decoding API or a
  standard tool, with a controlled write (heap/stack overflow with attacker-chosen length or data, use-after-free
  with attacker-influenced reuse, double free) that plausibly leads to code execution.
- **High**: out-of-bounds write, use-after-free or double free reached by decoding an untrusted message, without
  a demonstrated path to code execution; out-of-bounds read that leaks heap memory into decoded values, the
  output of a tool or a re-encoded message; injection into generated code by `bufr_dump -E` or into output files
  of `grib_to_netcdf` that leads to code execution when the output is used as documented.
- **Medium**: out-of-bounds read (crash only), NULL dereference, integer overflow that leads to a wrong
  allocation size but no proven out-of-bounds access, assertion failures and `abort()` reached from untrusted
  input in library code (ecCodes is used in long-running services, so a crash is a denial of service), path
  traversal or writing outside the intended directory from message contents (for example `grib_filter`/`bufr_filter`
  file names built from keys, `grib_copy`/`bufr_copy` output templates `[key]`).
- **Low**: excessive memory or CPU use (huge allocations from size fields, quadratic or unbounded loops) from a
  small input, undefined behaviour without memory-safety impact (signed overflow, invalid shifts, misaligned
  access), crashes that need trusted input (definitions, samples, filter rules, API misuse by the caller),
  wrong decoded values without memory-safety impact.

A bug that needs a specific build option (`ENABLE_ECCODES_THREADS`, `ENABLE_MEMFS`, JPEG/PNG/AEC support) is
rated as if the option is on; these are on in most distributions.

## Anything to leave alone

- Bugs that need a modified definition or sample file, or malicious environment variables.
- Thread-safety bugs when the library is built without `ENABLE_ECCODES_THREADS`/`ENABLE_ECCODES_OMP_THREADS`
  (it is documented as not thread-safe then).
- Memory leaks on error paths (unless they make a single run grow without bound).
- Floating-point precision, rounding and decoding-accuracy issues.
- Issues only in `deprecated/`, `third_party/`, `examples/` or `tests/`.
- Messages that the WMO manuals forbid but that ecCodes decodes "too leniently", unless this causes one of the
  problems above.

Please group findings by root cause: the same missing length check in one accessor class, reached through several
keys or tools, is one finding. The same pattern in different accessor classes is separate findings.
