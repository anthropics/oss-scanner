# ZXC threat model

## What this project does and where untrusted input enters

ZXC is a lossless compression codec: a C17 library (`src/lib`, public headers in `include/`) and a command-line tool (`src/cli/main.c`). The on-disk format is specified in `docs/FORMAT.md`, and version 9 is frozen. The decoder is built for speed: its main loop runs without per-copy bounds checks and uses speculative wild copies, so its safety rests on validation done up front and on the end-of-buffer safe zone.

Treat all of the following as attacker-controlled:

- **Archives**, passed to any decoding or inspection entry point: `zxc_decompress`, `zxc_decompress_dctx`, `zxc_decompress_inplace`, `zxc_decompress_inplace_dctx`, `zxc_decompress_inplace_bound`, `zxc_decompress_block`, `zxc_decompress_block_safe`, `zxc_stream_decompress`, `zxc_dstream_decompress`, `zxc_seekable_open*`, `zxc_seekable_decompress_range`, `zxc_seekable_decompress_range_mt`, `zxc_get_decompressed_size`, `zxc_get_frame_info`, `zxc_get_last_frame_info` and their `zxc_stream_get_*` forms.
- **Dictionary files** (`.zxd`), passed to `zxc_dict_load` and `zxc_dict_read_id`, including the Huffman table they carry.
- **Data to compress**, passed to the compression, streaming and dictionary-training APIs. The content can be chosen by an attacker; it must not cause memory errors or an output larger than the documented bounds.
- **Files given to the `zxc` CLI**, in every mode that reads them (`-d`, `-t`, `-l`, `-D`, `-b`).

The application calling the library is trusted. Its arguments are expected to respect the contracts in `docs/API.md`.

## Components that matter most and least

Highest priority:

1. Block decoders in `zxc_decompress.c` and `zxc_huffman.c`: every SIMD variant, the wild-copy paths, overlapping matches, the transition into the safe zone, and the strict decoder behind `zxc_decompress_block_safe`.
2. In-place decoding: the guarantee that the write cursor never overtakes unread input, and the bound computation.
3. Frame, block-header, footer and seek-table parsing in `zxc_dispatch.c`, `zxc_common.c` and `zxc_seekable.c`, including integer overflow in size arithmetic.
4. Static contexts: workspace sizing and carving, since they serve kernel and heapless targets.
5. Push streaming in `zxc_pstream.c`: state across arbitrary input and output splits.
6. `.zxd` parsing and dictionary binding in `zxc_dict.c`.

Also in scope: the encoders in `zxc_compress.c`, the multi-threaded driver in `zxc_driver.c` (races, lifetime, error paths), and the CLI.

Lower priority: `contrib/` (kernel ports). It is not built in this image; report a defect there only when it is specific to that code and can be shown from reading it.

Out of scope: `bindings/` (do not analyse, build or test the language bindings), `site/`, `docs/`, `tests/`, CI configuration, and defects in the vendored `src/lib/vendors/rapidhash.h` that do not come from how ZXC uses it.

## How to exercise it

The checkout is at `/src`.

- `/src/build`: release-style build with debug info. `zxc` is the CLI, `zxc_test` the unit tests (`--exact <name>` runs one).
- `/src/build-asan`: the same targets under ASan and UBSan. `ctest --test-dir /src/build-asan` runs the unit, conformance and golden tests.
- `/src/build-fuzz/zxc_fuzzer_<target>`: libFuzzer targets under ASan and UBSan, with sources in `tests/fuzz/`. Targets are `decompress`, `roundtrip`, `roundtrip_scalar`, `seekable`, `pstream`, `dict`, `stream`, `inplace`, `block` and `variants`. To replay one input, pass its path as the argument.
- `tests/conformance/v9/{valid,invalid}` holds archives that make good seeds, and `tests/conformance/invalid_cases.h` shows how malformed ones are built.
- `tests/cli/test_cli.sh <path to zxc>` runs the CLI suite. It writes to `./test_tmp`.

OSS-Fuzz and ClusterFuzzLite already run these harnesses, so shallow malformed-input crashes are unlikely. The most useful work is what they reach poorly. In the fuzz builds the dispatcher uses the `_default` variant only, so the AVX2, AVX-512 and NEON decoders are reached only through `zxc_fuzzer_variants` and the CMake builds. Other good targets are bugs that need a valid checksum or a consistent multi-field forgery, multi-frame archives, large block sizes, multi-threaded paths, and static contexts.

## How we rate severity

- **Critical**: an out-of-bounds write reachable from a crafted archive or `.zxd` through a documented API, where the attacker influences the written data and its location or length.
- **High**: any other out-of-bounds write, use-after-free or double free reachable from untrusted input; an out-of-bounds read or uninitialized memory whose content reaches the decoded output; compressor output exceeding `zxc_compress_bound`; a memory error caused by the content of data being compressed; input that compresses without error and then decodes without error to different bytes.
- **Medium**: an out-of-bounds read that can only crash; a data race on a supported multi-threaded path with a demonstrated effect; undefined behaviour with a demonstrated effect on a release build; an infinite loop; CPU or memory use far out of proportion to the input and output sizes.
- **Low**: a NULL dereference or an assertion failure limited to a crash in an uncommon configuration; undefined behaviour reported by a sanitizer with no demonstrated effect; a malformed archive accepted in violation of a MUST in `docs/FORMAT.md`, with no memory-safety impact.

State whether a finding needs a non-default option, such as checksum verification, a dictionary, a static context or a specific CPU feature. A demonstrated memory error should come with a reproducer through a public API.

## What is not a vulnerability

- Violating a documented caller contract: a `dst_capacity` larger than the real buffer, overlapping `src` and `dst` outside the in-place API, or sharing a context or seekable handle between threads against `docs/API.md` section 13.
- A `read_at` callback that is not thread-safe when used with the multi-threaded seekable API.
- Writes past the returned decompressed size but inside `dst_capacity`, and any content of `dst` after a failed call.
- Loads inside the output buffer whose bytes a shuffle never selects (see `ZXC_MSAN_UNPOISON` in `zxc_decompress.c`).
- A high compression ratio by itself. Output size proportional to what the archive legitimately declares is expected.
- Checksum weaknesses. Checksums detect accidents and rapidhash is not cryptographic, so forged checksums and hash collisions are not findings. Archives are not authenticated.
- Corrupted data decoding to wrong bytes when checksum verification is off, which is the default of `zxc_decompress`.
- A seek table rewritten consistently so that a range read returns another well-formed block of the same on-disk size. `docs/FORMAT.md` documents this limitation.
- CLI paths given on the command line reaching any file the invoking user can access. The format stores no path. If an archive could influence an output path, that would be a finding.
