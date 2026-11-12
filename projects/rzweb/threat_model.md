# RzWeb threat model

## What RzWeb does and where untrusted input enters

RzWeb is a browser UI for the Rizin reverse engineering framework. Rizin is compiled to WebAssembly by rzwasi and
runs inside a Web Worker, one worker per tab. A user drops a binary into the page and gets disassembly, decompiler
output, cross-references, graphs, hex, strings, imports, exports and a Rizin terminal. The promise to users is that
analysis stays on their machine: file bytes live only in WebAssembly memory and IndexedDB and are never uploaded.

The repo also has a local MCP server (`mcp/`) that loads the same rizin.wasm in Node and keeps contexts on disk, and
a Cloudflare Worker sketch (`hosted/`) that is not deployed.

Treat these as attacker controlled:
- The binary itself and everything Rizin derives from it: section and symbol names, strings, imports, exports,
  comments, flags, type and debug info, function names, graph labels and any JSON that Rizin returns.
- `RZWEBPRJ` project bundles (`src/lib/rizin/projectBundle.ts`) and bare `.rzdb` files that a user opens, including
  ones received from someone else.
- Output of Rizin commands as it is parsed in the worker and rendered by the React views, the xterm terminal and the
  cytoscape graph.
- For the MCP server: tool arguments sent by the MCP client (which may be driven by text taken from a hostile
  binary), including context ids, hashes, offsets and command strings, and the HTTP requests in `--http` mode.

Trusted: the user typing in the Rizin terminal, the user's own JavaScript in the Scripts panel, the operator's
command line flags and environment variables for the MCP server, and the published rizin.js and rizin.wasm.

## Components that matter most / least

Most important:
- `src/lib/rizin/` (worker, RPC protocol, session, project bundle decoding, context store in IndexedDB, analysis
  cache, xrefs and graph builders).
- Every view that renders Rizin output in `src/components/` and `src/pages/AnalysisPage.tsx`.
- `mcp/src/` (server tools, the `--allow-write` and `--allow-raw` gates, the on-disk store under
  `RZWEB_CONTEXT_DIR`, and the HTTP transport).

Also in scope: `public/_headers` (COOP/COEP), the service worker setup, write mode and patch saving.

Lower priority: `hosted/` is a sketch that is not deployed. Report issues there, but rate them one level lower.

Out of scope here: bugs inside Rizin's C code belong to rizinorg/rizin. The rzwasi source is in `/opt/rzwasi-src`
for reading. A bug in its `rzweb_*` session API is welcome, but say that the fix belongs in rzwasi.

## How to exercise it

- The image has the frontend built in `/src/dist` with the WASM pair served from `/rzwasi`. Serve it offline with
  `npx vite preview --port 4173 --strictPort` from `/src` and drive it with Playwright (Chromium is installed,
  `NODE_PATH` points at the global `playwright` package).
- Unit tests: `npm test` (Vitest, Node). Vitest cannot load rizin.wasm, so wasm paths need the browser or the MCP
  server.
- MCP server: `node /src/mcp/dist/index.js` (stdio) or `--http 8788`. `RZWEB_WASM_DIR` and `RZWEB_CONTEXT_DIR` are
  already set in the image.
- Lint and typecheck: `npm run lint`, `npm run typecheck`.

## How I rate severity

- Critical: a binary, project bundle or `.rzdb` that runs script in the RzWeb origin, or sends file bytes or
  analysis data off the device, with no action beyond opening it. For the MCP server: tool input that leads to
  command execution on the host or writing files outside the context directory.
- High: reading or changing another context's data from a crafted file. Reading files outside the context
  directory through the MCP server. Getting around `--allow-write` or `--allow-raw`. Write-mode patches landing in
  the saved file when write mode is off.
- Medium: a small crafted input that freezes the tab or the MCP server well beyond normal `aaa` time, or that
  corrupts stored contexts so they no longer open. Problems in the unauthenticated `--http` mode that need network
  access to the machine.
- Low: anything in `hosted/`, issues that need the user to paste a hostile script into the Scripts panel, and
  issues that need a non-default flag plus a malicious MCP client.

## Anything to leave alone

- The Scripts panel runs the user's own JavaScript with `new Function` inside the worker. That is the feature.
- Long `aaa` runs on large binaries and the fact that cancel only works between stages are known limits.
- No `ptrace` in the browser. Debugger features are not expected to work.
- Outdated dependencies with no reachable path in RzWeb.

## Reports and patches

Give the commit, the input file or tool call, the entry point and what happened. Keep patches small, in TypeScript,
in the style of the file you touch, with a Vitest test next to the code when it can run without rizin.wasm. CI wants
zero lint warnings and no `any`.
