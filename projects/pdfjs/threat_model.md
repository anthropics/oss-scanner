# Threat model

## What PDF.js is and where untrusted input enters

PDF.js parses and renders PDF files in JavaScript. It ships as:

* the built-in PDF viewer of Firefox (the `mozcentral` build, imported into mozilla-central under
  `toolkit/components/pdfjs`), which opens any PDF the user navigates to;
* the `pdfjs-dist` npm package (the library and the generic viewer in `web/`), embedded by many web sites, web
  applications and Electron apps, and used in Node.js for server-side text and image extraction.

The PDF file is entirely untrusted, and so is everything in it: the xref and object structure, streams and their
filters (Flate, LZW, ASCII85, ASCIIHex, RunLength, CCITTFax, DCT, JPX, JBIG2, Brotli), encryption, fonts
(TrueType/OpenType, CFF, Type1, Type3), images, color spaces and ICC profiles, shadings and functions (including
PostScript calculator functions), annotations and AcroForm fields, XFA forms, document JavaScript, outlines, link
destinations and URLs, attachments, XMP metadata and the structure tree.

The application embedding PDF.js, and the options it passes to `getDocument` and to the viewer components, are
trusted. In the generic viewer, the URL query and hash (`file=`, `#page=`, `#search=`, ...) are untrusted.

## Components that matter most and least

PDF.js is split in two halves:

* `src/core/` runs in a Web Worker (in Node.js, in the same process) and parses the PDF. It sends operator lists,
  font data, images, and annotation and form data to the main thread with `postMessage`.
* `src/display/` and `web/` run in the page (in Firefox, the `resource://pdf.js` viewer) and turn that data into
  canvas drawing and DOM.

Most important:

* anything that lets a PDF execute script in the page: the DOM built by `src/display/annotation_layer.js`,
  `src/display/xfa_layer.js` and `src/core/xfa/` (XFA to HTML), `src/display/text_layer.js`,
  `src/display/editor/`, font loading in `src/display/font_loader.js`, and the viewer in `web/` (links,
  attachments, document properties, outline, find, printing);
* the scripting sandbox: document JavaScript runs in QuickJS compiled to WebAssembly (`external/quickjs`,
  `src/pdf.sandbox.js`) in the generic viewer, and in a Gecko sandbox in Firefox. `src/scripting_api/` implements
  the Acrobat API inside it, and `web/pdf_scripting_manager.js` is the page side. Anything that lets document
  JavaScript reach the page beyond what that API allows is a sandbox escape;
* URL handling: `createValidAbsoluteUrl` (`src/shared/util.js`) and `web/pdf_link_service.js` must never produce a
  `javascript:` or other script-executing link, and the generic viewer must refuse a `file=` URL from another origin
  (`validateFileURL` in `web/app.js`);
* the worker to main thread boundary: data coming from `src/core/` must not be trusted by the main thread in a way
  that leads to script execution or prototype pollution.

Less important, but in scope: denial of service in `src/core/` (hangs, unbounded memory use), and rendering that
misleads the user about the document's content (for example a form field shown with a value different from the one
that is saved or printed).

Out of scope: `test/`, `examples/`, `gulpfile.mjs` and the rest of the build tooling, `l10n/`, and the debugging
tools only enabled by the `pdfBugEnabled` option (`web/debugger.mjs`). Bugs inside the third-party code in
`external/` (OpenJPEG, JBIG2, qcms and QuickJS, compiled to WebAssembly) belong upstream unless the way PDF.js uses
them makes them exploitable. The privileged Firefox side of the integration lives in mozilla-central, not here;
`web/firefoxcom.js` is the part of it that is in scope.

## How to exercise it

* Unit tests run in Node.js with jasmine: `npx gulp unittestcli` rebuilds `build/lib-legacy/` and runs the specs in
  `test/unit/` listed in `test/unit/clitests.json`.
* `test/pdfs/` holds the test corpus: around a thousand PDFs, many of them from past bug reports, plus the linked
  ones downloaded when the image was built.
* In Node.js, `build/generic-legacy/build/pdf.mjs` exports `getDocument`; `examples/node/getinfo.mjs` shows how to
  load a document and read its pages and metadata.
* `npx gulp server` serves the repository on http://localhost:8888. Open
  `/web/viewer.html?file=/test/pdfs/<name>.pdf` for the viewer from source, or
  `/build/generic/web/viewer.html?file=...` for the built one.
* A Firefox Nightly is installed for puppeteer in `$PUPPETEER_CACHE_DIR`, so a puppeteer script launched with
  `browser: "firefox"` can open the viewer headless and check whether a PDF executes script. The integration tests
  drive the viewer that way: `xvfb-run -a npx gulp integrationtest --noBrowserDownload --noChrome` (slow).

## How you rate severity

* Critical: script execution from a PDF in the Firefox built-in viewer, or an escape from the scripting sandbox
  there, with default preferences.
* High: script execution from a PDF in a page embedding `pdfjs-dist` with default options, a scripting sandbox
  escape in the generic viewer, or a bypass of the `file=` origin check.
* Medium: script execution that needs a non-default option, a link or form action that navigates to a dangerous URL
  after a user click, or spoofing of form field or signature contents.
* Low: denial of service. A PDF that hangs the worker, exhausts memory or crashes the tab is a regular bug for us.

## Anything to leave alone

* Exceptions, warnings or rendering differences on malformed PDFs, unless they lead to one of the issues above.
* Issues that need the embedding application to pass hostile options to the API.

Please include the PDF (or the script that generates it), how to reproduce the issue (a unit test, a Node.js script
or a viewer URL), and a patch against `src/` or `web/` with a test where possible.
