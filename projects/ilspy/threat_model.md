# Threat model: ILSpy

## What this project does and where untrusted input enters

ILSpy is the open-source .NET assembly browser and decompiler: a cross-platform Avalonia desktop UI, the
`ilspycmd` CLI, and the `ICSharpCode.Decompiler` / `ICSharpCode.ILSpyX` libraries that Visual Studio, VS Code
and many other tools embed.

Everything ILSpy opens is untrusted. The primary scenario is a user opening a hostile file. Untrusted inputs:

- PE images and ECMA-335 metadata, IL method bodies, custom attributes, signatures
- embedded and linked resources: `.resources`, `.resx`, BAML (WPF), Avalonia resources, arbitrary blobs
- portable PDBs (embedded or on disk), source link and embedded source
- ReadyToRun images, single-file bundles (`ICSharpCode.ILSpyX` bundle reader), NuGet packages (`.nupkg`)
- names embedded in assemblies (type, resource, file and document names) that become file names and paths
  during whole-project export and resource extraction
- responses from NuGet feeds (ILSpyX NuGet feed browsing) and the update check

## Components that matter most / least

Most important (reachable from any input file):

- `ICSharpCode.Decompiler/`: metadata and IL readers, disassembler, type system, decompiler pipeline,
  `CSharp/ProjectDecompiler` (writes files and directories), `Metadata/` (PE/metadata parsing, `unsafe` code)
- `ICSharpCode.ILSpyX/`: assembly lists, package bundles, PDB loading, NuGet feed access
- `ICSharpCode.BamlDecompiler/`: BAML parsing
- `ILSpy.ReadyToRun/`: ReadyToRun parsing
- `ICSharpCode.ILSpyCmd/`: CLI entry point; writes output directories chosen by the user

Less important: UI chrome, docking, themes, settings and session persistence in `ILSpy/`.

Out of scope: `ILSpy-tests/` (test fixtures), `TestTools/`, `ILSpy.Installer/`, `ILSpy.AddIn*` (Visual Studio
add-ins, `net472`, not built in this image), third-party code vendored under `ICSharpCode.Decompiler/Humanizer`.

## How to exercise it

The image was built from `ILSpy.Desktop.slnf` in Debug configuration with the .NET 11 SDK; a .NET 10 runtime is
installed too, because the application projects target `net10.0` and the test projects `net11.0`.

- Tests (Microsoft.Testing.Platform, NUnit), run offline from `/src`:
  `dotnet test --project <project>.csproj --no-build -c Debug` for `ICSharpCode.Decompiler.Tests`,
  `ICSharpCode.ILSpyCmd.Tests`, `ILSpy.Tests` (headless Avalonia UI tests) and `ILSpy.BamlDecompiler.Tests`.
  Tests that need Windows, Mono or a 32-bit host self-exclude with `Assert.Ignore`.
- CLI reproducer: `dotnet ICSharpCode.ILSpyCmd/bin/Debug/net10.0/ilspycmd.dll <assembly> --disable-updatecheck`
  (`-p -o <dir>` exports a whole project, `--list`, `-t`, `-il`, `-d` select other outputs).
- `ICSharpCode.Decompiler.Tests/AGENTS.md` and the root `AGENTS.md` describe the test matrix and how fixtures are
  compiled; `ILSpy.Tests/` shows how to drive the UI headlessly.
- Rebuild after an edit with `dotnet build ILSpy.Desktop.slnf --no-restore -c Debug`; the NuGet cache in the image
  holds everything the solution needs. Do not require network downloads in a reproducer.

## How you rate severity

- Critical/high: code execution, or writing or reading outside the output directory the user chose, triggered by
  opening a crafted input (path traversal through embedded names during project export or resource extraction,
  deserialization of untrusted data, loading native code from an input).
- Medium: crashes from unchecked reads of malformed metadata in `unsafe` code, and other memory-safety issues
  in native interop. Plain managed exceptions on malformed input are robustness bugs, not vulnerabilities.
- Low/medium: unbounded CPU or memory from a crafted assembly, if trivially triggered by a small input;
  otherwise not a security issue.
- Network features (update check, NuGet feeds) are a concern only if a malicious server can make the client
  execute or write something it should not.

## Anything to leave alone

- Incorrect but harmless decompilation output (wrong C#, missing constructs) is a bug, not a finding.
- Stack overflows from extremely deep nesting in real-world assemblies are known; report only new, small inputs.
- Windows-only paths (GAC, process attach, `ILSpy.Tests.Windows`, `ILSpy.BamlDecompiler.Tests.Windows`) cannot be
  exercised in this image.
