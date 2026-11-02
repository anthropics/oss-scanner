# Threat model — pdf_oxide

## What this project does and where untrusted input enters
pdf_oxide is a Rust library (published on crates.io, with Python, WASM, C ABI and other language
bindings over the same core) that parses PDF files and extracts text, markdown, HTML, images and
structure, renders pages to raster images, edits and saves documents, fills forms, and creates and
verifies digital signatures.

**Every input PDF is untrusted.** Applications feed it documents from users, email, crawlers and
uploads. Untrusted bytes enter through `PdfDocument::open` / `from_bytes` and everything reachable
from it:
- the lexer and object parser, cross-reference tables and streams, object streams, and the
  recovery path that rebuilds a broken file;
- stream filters: Flate, LZW, ASCIIHex, ASCII85, RunLength, CCITTFax, DCT, JPX, JBIG2, predictors;
- encryption (RC4, AES-128/256, standard and public-key security handlers);
- fonts: Type 1, CFF, TrueType, Type 3, CMaps, ToUnicode, encodings;
- content streams, images and colour spaces (ICC, Lab, Indexed, Separation/DeviceN, functions),
  shadings and patterns, transparency groups and soft masks in the renderer;
- annotations, forms (AcroForm), the structure tree, outlines, name trees, actions, and
  signatures (CMS/PKCS#7 parsing and verification).

The editor and writer take the same untrusted documents as their starting point.

## Components that matter most / least
- Most important: everything in `src/` reachable from opening, extracting, rendering, editing and
  saving a document, and signature verification.
- In scope but lower priority: the document builder (`src/writer/`) when given trusted
  caller data, and the CLI (`pdf_oxide_cli/`) as a driver.
- Out of scope: language-binding glue outside `src/` (`python/`, `js/`, `go/`, `csharp/`, `java/`,
  etc.) unless the defect is in the shared Rust core; `benches/`, `examples/` and `scripts/`.

## How to exercise it
- `target/release/pdf-oxide` (from `pdf_oxide_cli`) runs extraction, conversion and rendering
  on a file; `pdf-oxide --help` lists the subcommands.
- `fuzz/` holds cargo-fuzz targets (`fuzz_parse`, `fuzz_render`, `fuzz_signatures`) and seeds;
  their dependencies are fetched in the image.
- `tests/` has ~1,200 integration tests, each building a small synthetic PDF in code; build one
  with `cargo test --features rendering --test <name>`.
- Never enable all features at once: `fips` and `legacy-crypto` are mutually exclusive.

## How you rate severity
- Critical: memory corruption reachable from a crafted PDF (the crate uses `unsafe` in only a few
  places, mostly the C ABI in `src/ffi.rs`), or a signature that verifies when it should not (a
  forged or altered document reported as validly signed).
- High: decryption or permission bypass (content of an encrypted document readable without the
  key), redaction that leaves the redacted content recoverable in the saved file, or an unbounded
  resource-consumption bug (hang, infinite loop, or memory/CPU exhaustion growing far beyond the
  file size) reachable from a small crafted file.
- Medium: a panic/abort on crafted input, a path traversal in an attachment or file name the
  library returns, or a resource-consumption bug bounded by a moderate factor of the file size.
- Low: incorrect output (wrong text, wrong pixels) with no security effect.

## Anything to leave alone
- Slow but bounded processing of genuinely huge documents is not a vulnerability.
- Behaviour that matches ISO 32000 and the reference readers (pdf.js, pdfium, MuPDF, poppler) is
  intended even when it surprises.
- Please send reports privately to the primary contact; fixes ship with a synthetic regression
  test, never the reporter's file.

## How we rate severity
- **Critical / high:** memory-safety violations (out-of-bounds read or write, use-after-free,
  or any bug in `unsafe` code or a codec/FFI dependency that corrupts memory) reachable from a
  crafted PDF; signature-verification bypass (an invalid or tampered signature reported as
  valid); remote code execution or arbitrary file read/write triggered by opening, extracting,
  rendering or editing a document.
- **Medium:** a crafted PDF that causes a panic, unbounded memory growth (decompression or
  object-count bombs that bypass the documented limits), an infinite loop or stack overflow in
  the library's default configuration; incorrect decryption or permission handling.
- **Low:** denial of service that needs an unusually large input or is already covered by the
  documented resource limits; wrong extraction or rendering output with no security impact;
  issues only reachable through non-default or caller-misused APIs.
- Without a demonstrated crash or reproducer, a suspected memory-safety issue is capped at medium.
- A report should include a minimal PDF (or a script that builds one) and the command that
  reproduces it. A patch with a regression test is welcome.
