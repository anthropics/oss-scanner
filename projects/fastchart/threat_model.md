# Threat model

## What this project does and where untrusted input enters
- fastchart is a PHP extension that builds charts (38 classes under `FastChart\`, from `LineChart` and `StockChart` to `SankeyChart` and `WordCloud`) and symbols (`Code128`, `QrCode`), renders them to SVG, then rasterizes to PNG, JPEG, or WebP, or writes PDF. Rendering is plutosvg (SVG parse) plus plutovg (rasterize), both vendored; encoding uses system libpng, libjpeg-turbo, and libwebp; text uses FreeType or the vendored stb_truetype; PDF uses pdfio.
- Assume an application passes user-controlled data into the public API. Untrusted input enters through:
  - Data setters: series, OHLCV rows, slices, points, boxes, bubbles, tasks, nodes/links, matrices, and similar nested PHP arrays, which are parsed into typed C arrays. Lengths, nesting, mixed types, NaN/Inf, huge or negative values, and duplicate or missing keys are all attacker-chosen.
  - Strings: titles, category and axis labels, legend text, annotations, number/label format strings, colors, barcode and QR payloads. These reach SVG text escaping, text measurement, and layout.
  - `svgToPng()`, `svgToJpeg()`, `svgToWebp()`: an arbitrary SVG document from the caller goes straight to the plutosvg parser, including `data:image/png|jpeg;base64,` images decoded by the vendored stb_image.
  - File paths and file contents: `setBackgroundImage()`, `addIconAt()`, `setFontPath()`, and `renderToFile()`. Image and font file contents may be user uploads; paths go through `php_check_open_basedir`.
  - Dimensions and quality arguments that feed buffer sizing (`width x height x 4`, bounded by `fastchart.max_render_pixels`).

## Components that matter most / least
- Most: the PHP-array-to-C parsers and the SVG generation in `fastchart.c`, `fastchart_target.c`, `fastchart_svg.c`, `fastchart_axis.c`, and the per-chart `fastchart_<type>.c` files; the raster and encode pipeline (`fastchart_rasterize.c`, `fastchart_encoder.c`, `fastchart_pdf.c`); text handling (`fastchart_text.c`); symbols (`fastchart_code128.c`, `fastchart_qrcode.c`, `fastchart_symbol.c`).
- Vendored code under `vendor/` (plutosvg, plutovg including its stb_image and stb_truetype copies, qrcodegen) is in scope only when the bug is reachable through fastchart's PHP API. A plutosvg parser bug reachable via `svgToPng()` counts; one only reachable from a plutovg function fastchart never calls does not.
- Out of scope: bugs inside FreeType, libpng, libjpeg-turbo, libwebp, zlib, pdfio, or PHP itself (report upstream). A fastchart misuse of their APIs (wrong buffer size, missing error check, longjmp across Zend state) is in scope.
- Out of scope: `bench/`, `docs/`, `scripts/` (dev tooling), `tests/`, and Windows-only code paths in `config.w32`.

## How to exercise it
- The module is at `/src/modules/fastchart.so` and installed, so `php -d extension=fastchart` loads it. It is built `--with-pdfio`, so `renderPdf()` works. gd and simplexml are loaded for test-side image and SVG checks. Fonts: `/usr/share/fonts/truetype/lato/Lato-Regular.ttf` and DejaVu.
- `run-phpt` runs the PHPT suite (416 tests); pass paths or `run-tests.php` flags to narrow it. Tests using strace fault injection need ptrace and skip without it.
- `docs/examples/*.php` are small runnable charts, and `fastchart.stub.php` lists every method and its parameters.
- Minimal driver: `php -d extension=fastchart -r 'echo strlen(FastChart\Chart::svgToPng(file_get_contents($argv[1])));' input.svg`.
- For memory errors, run under valgrind with `USE_ZEND_ALLOC=0`.

## How you rate severity
- Critical: memory corruption with a controlled write (attacker-chosen offset or contents) reachable from chart data, labels, SVG passed to `svgTo*()`, or an image or font file the application loads.
- High: any other out-of-bounds write, use-after-free, or double free reachable from those inputs.
- Medium to high: out-of-bounds read or information leak (uninitialized or heap bytes in rendered output, SVG text, or returned strings).
- Medium: crash, NULL dereference, assertion, or division by zero on malformed data, SVG, or image input; a path that writes or reads outside the `open_basedir` the operator configured when the path itself comes from user data.
- Low to medium: resource exhaustion (CPU, memory outside `memory_limit`) from small input that bypasses or precedes the `fastchart.max_render_pixels` / `fastchart.max_image_cache_bytes` caps. Rendering near the documented caps is expected cost, not a finding.
- Low or out of scope: anything that needs attacker-controlled PHP code or INI settings, such as calling internal methods in odd orders from hostile code or raising the caps. Silent dropping of malformed entries in non-strict mode (`setStrict(false)`) is documented behavior.

## Anything to leave alone
- Do not report rendering differences, anti-aliasing, or layout aesthetics.
- Do not report SVG/PNG output size or speed unless it is a resource-exhaustion bug as defined above.
- Optional codecs missing at build time are a supported configuration; "missing codec" errors are not bugs.
