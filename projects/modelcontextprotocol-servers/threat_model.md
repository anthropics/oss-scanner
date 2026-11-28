<!--
Based on this repository's security policy, https://github.com/modelcontextprotocol/servers/blob/main/SECURITY.md, and
the MCP security policy, https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/SECURITY.md.
The rules that matter for a scan are copied here. Follow this file.
-->
# Threat model: MCP reference servers

## What this project does and where untrusted input enters

Seven reference servers for the Model Context Protocol. They are written to show MCP features, not as production products, but people run them. The operator's command line and environment are trusted. Tool arguments are untrusted: a language model that has read hostile content may choose them. So is the content a server handles: files and directories inside an allowed directory, a Git repository's working tree, `.git` directory and configuration, and fetched pages, redirects and `robots.txt`.

## Components that matter most / least

- `src/git`: confinement to `--repository`; never running a program that a repository's configuration, hooks, attributes or submodules name; flag-injection guards. Its README lists the protections it claims.
- `src/filesystem`: confinement to the allowed directories (symbolic links, races, renames), `--read-only`, `--read-only-dir` and `--confine-roots`. Its README lists the guarantees it claims.
- `src/fetch`: the private-address guard (every redirect hop, DNS rebinding, IPv6 forms), `robots.txt`, `--allowed-hosts`, the response-size limit, and the HTML simplifier.
- `src/everything`: a test server. Its gzip fetch guard and its HTTP transports' Origin check and loopback binding are in scope; the rest is low priority.
- `src/memory`, `src/sequentialthinking`, `src/time`: small; in scope.
- Out of scope: `scripts/`, `docs/`, `.github/` and the tests.

## In scope

A way around a boundary that a server's README or security policy claims to enforce, by someone who controls tool arguments or the content the server handles but not its command line. In particular:

- Reading, listing, writing or moving anything outside the allowed directories or the repository, or writing where the server is read-only.
- Running a program or command that the repository, a file or a page names.
- Reaching a private, loopback or link-local address through the default guards, or a host outside `--allowed-hosts`, or ignoring `robots.txt` where the server says it obeys it.
- For the Streamable HTTP and SSE modes: a web page in the user's browser driving a server that listens on loopback.
- A crash or unbounded resource use caused by a small file, page or repository, where the server documents a limit.

## Not a vulnerability: please do not report

- A server doing what its README documents: filesystem reads and writes inside its directories, git changes inside its repository, fetch reaching public addresses.
- `git` without `--repository` reaching any repository, or `fetch` with `--allow-private-ips` or a proxy reaching private addresses: both are documented.
- Anything that needs control of the command line, the environment, the user's global Git configuration or the server's own installation.
- One stdio peer crashing or hanging the other; prompt injection; a model calling a tool the user did not expect.
- A client's Roots replacing the command-line directories when `--confine-roots` is not set: documented.
- A shared thought history or knowledge graph among clients of one HTTP process: documented.
- Missing authentication on the HTTP modes when an operator binds a non-loopback address, which the READMEs warn about.
- Flaws in the MCP SDKs or other dependencies that these servers only inherit.
- `filesystem` on Windows: a parent directory swapped by another local process during an operation, which its README documents as not protected.
- Correctness bugs that cross no boundary.

## How we rate severity

- Critical: running a program with no unusual configuration, from hostile repository or file content or from tool arguments alone.
- High: running a program in an unusual but documented configuration; writing, or freely reading, outside a claimed boundary; a web page driving a server that listens on loopback.
- Medium: the same with a race; reading outside a boundary with limited control; reaching a private address, or a host outside `--allowed-hosts`, past the guard; getting past a documented size limit so that memory or CPU is exhausted.
- Low: ignoring `robots.txt`.
- Also low: leaking names or metadata across a boundary; denial of service of one server process.

Please report one root cause once, with a reproducer that runs the server itself. Several of these boundaries have had variants fixed recently (see the repository's published advisories), so check the history of the affected file first.

## How to exercise it

- TypeScript servers: `npm test` at the root, or in `src/<server>`; built code is in `src/<server>/dist`, for example `node src/filesystem/dist/index.js /tmp/dir`.
- Python servers: `cd src/<server> && uv run pytest`; to start one, `uv run mcp-server-git --repository /tmp/repo`.
- The branch scanned is `v2/main`, where development happens and pull requests go; `main` only receives releases.
- Expected failures in this image: two control tests in `src/git/tests/test_automatic_maintenance.py` (a newer Git runs a planted hook twice) and one long-file-name test in `src/filesystem/__tests__/pinned-directory.test.ts`.
