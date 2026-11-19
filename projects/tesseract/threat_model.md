# Threat model

## What this project does and where untrusted input enters
- Tesseract is an OCR engine: it turns images of text into text. Its main product is `libtesseract`
  (the C++ core in `src/`), used by the `tesseract` CLI and by embedded clients through
  `include/tesseract/`. In production it processes scanned documents from arbitrary third parties
  (newspapers, books, forms), all of which must be treated as hostile input.
- Untrusted input enters through:
  - image files (TIFF, PNG, JPEG, ... via Leptonica) — the main attack surface;
  - trained models (`.traineddata`) and, less often, config files, read at `Init()` time.
- The build here has no network surface: libcurl is only used by the training tools to fetch remote
  training data, not by the OCR path.
- The JNI bindings in `java/` and the Java `ScrollView` viewer are not built in this image and are
  out of scope for this enrolment.

## Components that matter most / least
- Most important: the public API and the OCR pipeline reachable from an untrusted image —
  `src/api` (the C++ API `baseapi.cpp` and the C API `capi.cpp`), `src/textord` (page/line/word
  segmentation), `src/wordrec`, `src/lstm` (recognition), `src/classify`, `src/dict` (dictionaries
  and language models), and `src/ccstruct` / `src/ccutil` (core data structures).
- Important: the CLI (`src/tesseract.cpp`).
- Less important but in scope: the training tools (`src/training/`); they process user-supplied
  training material, although in practice they are used on trusted internal data.
- Out of scope: Leptonica itself (a system library, `libleptonica-dev`). The two git submodules —
  the `tesseract-ocr/test` regression corpus and the bundled GoogleTest — are not fetched into this
  image and are not available; do not expect them to be present.

## How to exercise it
- The engine is installed to /usr/local and works out of the box: `tesseract <image> <out> -l eng`,
  with the models in /opt/tessdata (TESSDATA_PREFIX is set).
- To get test input offline (there is no image corpus in the image), use the built training tool
  `text2image` to render arbitrary text into an image, then run it through `tesseract`. For example
  `text2image -F "DejaVu Serif" -s 30 /tmp/line "some hostile text"` writes `/tmp/line.tif`, which
  can be fed to `tesseract /tmp/line.tif stdout`. This exercises the real OCR path end to end with
  no network access. List the installed fonts with `text2image --list_available_fonts` and pick one
  that exists.
- `/src/unittest/fuzzers/fuzzer-api.cpp` is the OSS-Fuzz entry point (a small bit image driven
  through the public API) and a good starting point for crafting inputs; it can be compiled with
  AddressSanitizer against the built `libtesseract` to reproduce candidate issues. Note the bundled
  GoogleTest dependency is not fetched, so the gtest suite itself cannot be built in this image.
- The build tree is /src/build (RelWithDebInfo, -g -fno-omit-frame-pointer), so crashes give useful
  backtraces.

## How you rate severity
- A memory-safety bug (buffer overflow, use-after-free, double free, integer overflow leading to a
  bad allocation) reachable from an untrusted image or an untrusted `.traineddata` is high at a
  minimum; report it as critical only with a clear path to code execution.
- A crash or denial of service on malformed input is medium. Tesseract routinely processes hostile
  input, so robustness is part of its contract, but a crash by itself is not high.
- There is no network, no database and no authentication in the build; findings that require them
  do not apply. Do not report style, performance or portability issues, or issues that require a
  non-default build (OPENMP_BUILD, ENABLE_NATIVE, DISABLED_LEGACY_ENGINE, ...).

## Anything to leave alone
- Only Tesseract's own code: do not report issues in Leptonica or other third-party system
  libraries.
- The SIMD paths (`src/arch/dotproduct*.cpp`, `src/arch/intsimdmatrix*.cpp`) are correct on the
  target machine; do not report unaligned or architecture-specific access patterns as
  vulnerabilities.
- Training-tool misbehavior on corrupt training corpora is low priority.
