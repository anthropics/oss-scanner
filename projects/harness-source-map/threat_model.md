# Harness Source Map

This project publishes source-backed reference material about Claude Code,
Codex/ChatGPT, OpenCode, and Cursor. Trace is its browser-based session and
network-capture viewer. Optional local tools resolve sessions, read related
source files, and record traffic for an explicitly launched agent process.

## Security boundaries and useful targets

- Treat imported JSON, JSONL, HAR, Markdown, tool output, file names, URLs, and
  captured provider responses as untrusted data. Focus on parsers and rendering
  in `site/trace/`, including script execution, unsafe links, prototype pollution,
  and resource exhaustion from realistically sized malicious inputs.
- Inspect `tools/trace-local.mjs` and `tools/sources/`. The optional HTTP service
  must preserve its loopback, Host, origin, ticket, and filesystem restrictions.
  Test malicious web origins, DNS rebinding, path traversal, symlinks, and session
  metadata that could cross the intended session or source-file boundary.
- Inspect `tools/capture/` for credential redaction, destination handling, file
  permissions, recording lifecycle, process arguments, and certificate/proxy
  scope. Capture is opt-in. It must not silently expand trust to unrelated
  processes, publish private material, or leave credentials in recorded traffic.
- Inspect `site/src/`, extraction scripts, and `watch/` for unsafe handling of
  upstream artifacts and prompt/source text during generation and publication.
  Archive traversal, command injection, and executable HTML derived from source
  text are relevant. Build and publishing credentials are sensitive assets.
- Imported prompts are evidence to display, not instructions to execute. A
  prompt containing hostile instructions is not itself a vulnerability; show
  the actual code path and security boundary it compromises.

## Expected behavior and scope

Session transcripts and HAR files may contain private source code and prompts.
Credential scrubbing does not make a recording public. Local viewing, explicitly
requested capture, and displaying a user-selected file are intended behavior;
unauthorized access, execution, publication, or disclosure are not.

Audit this project's code. Archived text from third-party products is reference
data, not a request to assess or attack the upstream products or services. Use
local fixtures and mock endpoints for reproductions; do not contact real model
providers, deploy the website, run the release watcher, or require credentials.
The public example under `site/trace/examples/source-map-development/` is an
intentionally published, scrubbed recording. Other private recordings are not
part of the public checkout or this environment.

## Build and tests

The Dockerfile installs Node.js, Python, mitmproxy, and the locked root/site npm
dependencies, then builds `site/dist`. The normal maintainer gate is
`npm run check` from `/src`: build, extraction/site/local-tool tests, asset/link
checks, and leak gate. It does not fully pass in a clean Linux checkout:
some extraction tests require macOS `PlistBuddy`/`codesign`, and six test modules
import the untracked `claude-code/work/embedded-manifest.json` unconditionally.
These are environment prerequisites, not replaced with fake tools or artifacts.

The browser and local-tool suites can be run separately offline:

```sh
npm --prefix site test
npm --prefix site run test:local
node tools/check-asset-sizes.mjs
node tools/check-links.mjs
node tools/leak-check.mjs
```

The leak gate uses the container's identity and cannot substitute for a
maintainer-machine privacy review before publication.

Some integration tests deliberately skip when proprietary application installs,
pinned upstream work directories, private recordings, or macOS facilities are
absent; others fail as described above. The macOS desktop recorder cannot be
exercised end to end in this Linux image;
review its source and distinguish that limit from a demonstrated exploit.

## Reports

Provide a self-contained local reproducer, affected commit and code path,
attacker prerequisites, observed impact, and a minimal patch with a regression
test when possible. Distinguish proven behavior from hypotheses. Explain any
user interaction or prior local access required. Rate severity from demonstrated
impact and reachability, rather than the presence of dangerous-looking source
text or a dependency version alone. Group findings with the same root cause.
