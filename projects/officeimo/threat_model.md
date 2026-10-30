# OfficeIMO security audit

## Project and trust boundaries

OfficeIMO is an MIT-licensed .NET document toolkit. Its own libraries read,
create, edit, convert, render, and extract Office documents, PDF, email,
archives, OneNote, markup, and other structured formats. Applications may use
these libraries in upload processing, document conversion, and extraction
pipelines. Assume that input files and their contents are attacker controlled.

The repository's SECURITY.md describes the maintained security boundaries.
Treat package parts, archive entries, metadata, embedded objects, relationships,
links, image data, markup, and OfficeIMO.Tool MCP arguments as untrusted.
Filenames and URLs embedded in documents are data, not permission to read local
files, make network requests, or execute content.

## Priorities

- Parsers, decompressors, container readers, and format detection: malformed
  lengths, offsets, dimensions, record chains, recursion, expansion, and
  allocations. Check configured input, entry, nesting, and output limits.
- Archive extraction and package relationships: traversal, rooted paths,
  filesystem escapes, and unexpected external resource access.
- OfficeIMO.Security and document integration: encryption, password handling,
  integrity validation, signatures, and inert treatment of active content.
  Use generated software keys and synthetic certificates for reproductions.
- Conversion, rendering, and generated HTML: escaping and sanitization across
  trust boundaries, unsafe resource loading, and active-content policies.
- OfficeIMO.Tool and workflow entry points: configured allowed filesystem
  roots, MCP argument validation, and unintended file or process access.
- Email and compound-document readers: hostile attachments, nested containers,
  record references, decompression, and caller-visible resource exhaustion.

All first-party source in this repository is in scope, including shared
components and host integration. The Linux environment provides executable
coverage for the managed document engines. Native Apple and Windows-only UI
hosts may be inspected, but cannot be executed in this Linux image.

## Environment and useful entry points

The checkout is /src. The Dockerfile restores and builds OfficeIMO.sln in
Release, retains NuGet packages and fixtures, and runs the security suite on
.NET 10. Both .NET 8 and .NET 10 SDKs/runtimes are installed. Restore is an online
setup step; during an audit use --no-restore.

Useful offline commands from /src include:

```sh
dotnet test OfficeIMO.Security.Tests/OfficeIMO.Security.Tests.csproj -c Release -f net10.0 --no-build --no-restore --filter 'Category!=Performance'
dotnet test OfficeIMO.Reader.Tests/OfficeIMO.Reader.Tests.csproj -c Release -f net10.0 --no-build --no-restore --filter 'Category!=Performance'
dotnet test OfficeIMO.Tool.Tests/OfficeIMO.Tool.Tests.csproj -c Release -f net10.0 --no-build --no-restore --filter 'Category!=Performance'
```

Format-specific suites such as OfficeIMO.Excel.Tests, OfficeIMO.Pdf.Tests,
OfficeIMO.Email.Tests, and OfficeIMO.Word.Tests provide additional drivers and
fixtures. Check the relevant project before choosing a framework or test filter.
Some integration, browser, visual, cloud, and independent-producer checks need
external tools or services that are not supplied by this container. Do not
treat unavailable optional integrations as vulnerabilities. Use focused parser
and security tests for bounded audit iterations; performance evidence is opt-in.

## Intended behavior and scope limits

- Preserve macro or script bytes as inert document data where supported.
  Preservation does not authorize execution. Do not execute embedded content.
- Check the actual public API and its configured limits. A caller explicitly
  opting into trusted raw markup or external resource access is a different
  boundary from an untrusted document bypassing a restrictive default.
- OfficeIMO.Reader.Web uses a caller-owned HttpClient. Its documented URI checks
  do not validate resolved addresses or redirects before connection; callers
  accepting untrusted URLs must enforce those network rules in their handler.
  Distinguish this documented contract from a bypass of an enforced policy.
- Report vulnerabilities in OfficeIMO code. A flaw solely in an upstream
  dependency belongs to that dependency; report a first-party integration flaw
  when OfficeIMO's use or configuration creates the vulnerability.
- Third-party comparison tools, benchmark baselines, fixtures, and intentionally
  malformed test data are evidence, not separately enrolled audit targets.
- Do not contact production services, use real customer documents, access
  persistent signing stores, or include secrets in a reproducer.

## Findings and severity

Include a minimal synthetic input, the affected public API and package, exact
reproduction command, observed impact, and the trust boundary crossed. Demonstrate
the reachable production path rather than only an isolated internal helper.

Classify by demonstrated impact and realistic deployment: unauthorized execution,
arbitrary file access/write, secret exposure, or authentication/integrity bypass
may be high or critical. Resource exhaustion from small untrusted input or a
bypass of configured bounds is meaningful; explain the input size, limits,
runtime, and memory needed. A normal parse rejection or exception alone is not
a vulnerability. Group reports sharing a root cause and list affected sibling
formats or entry points. A minimal patch with a regression test is preferred.
