# Threat model

The project's security policy is `.github/SECURITY.md`; it supports the latest major and minor release and routes
private reports through Tidelift.

## What pipdeptree does and where untrusted input enters

pipdeptree discovers installed Python distributions and renders their dependency graph. It can resolve requirements
against a package index or read a PEP 751 lock file, then emit text, JSON, CycloneDX, Mermaid, Graphviz source or
Graphviz-rendered output. Most parsing and graph construction lives in the PyO3 Rust extension under `rust/src/`;
`src/pipdeptree/_runner.py` connects it to Python streams and the desktop opener.

Like SBOM scanners, pipdeptree should inspect package metadata without importing or executing the installed package.
Code execution caused by metadata inspection is a security boundary even though installing the package already ran its
code. Incorrect dependency data from a malicious package is not: pipdeptree reports the metadata it receives.

Treat these inputs as hostile:

- `METADATA`, `direct_url.json`, `RECORD`, `entry_points.txt`, egg-link files and names beneath a scanned
  `site-packages` directory;
- package names, versions, requirements, extras, markers, licenses, URLs and editable or VCS metadata;
- PEP 751 lock files and requirements files supplied to resolver subcommands;
- package-index responses and artifacts processed during resolution;
- interpreter paths and the response returned by an interpreter queried with `--python`;
- labels and links sent to JSON, CycloneDX, Mermaid and Graphviz renderers;
- Graphviz output bytes, terminal dimensions, encodings and Python streams.

An interpreter selected with `--python`, the selected package index, a Graphviz executable on trusted `PATH` and the
desktop opener are operator choices. Reports must separate pipdeptree's use of them from their own behavior.

## Components to prioritize

Review `rust/src/metadata.rs` and `rust/src/metadata/` for parsing and directory traversal. `direct_url.json`,
editable-install records and VCS metadata must remain data. Package-size calculation and path discovery must not follow
symlinks out of the selected environment or loop through a hostile tree.

Inspect `rust/src/graph/`, `lock.rs`, `index.rs`, `environment.rs` and `process.rs` for cycle handling, marker
evaluation, interpreter probing and resolver subprocess arguments. Bound allocations and recursion for long fields, many
packages, duplicate records and deep cyclic graphs. A relative interpreter request must not select an executable from
the working directory ahead of the documented search order.

Review each renderer under `rust/src/render/`. JSON and CycloneDX require valid structured output; Mermaid and Graphviz
require context-specific escaping of package-controlled labels, URLs and license text. Graphviz invocation must use a
fixed argv boundary. `_runner.py` may write binary output to a temporary file and open it on the desktop, so check its
suffix, permissions, cleanup and treatment of attacker-controlled bytes.

At the Rust/Python boundary, malformed input should become an ordinary error, not an uncaught panic, invalid lifetime or
memory-safety defect. A dependency defect belongs here only when pipdeptree misuses the dependency or exposes a new
reachable impact.

## How to exercise the image

The image contains the source at `/src`, the built Rust extension, pipdeptree in `/opt/venv`, a wheel under
`/opt/wheels` and Graphviz. Run `python -m pytest tests`.

Create a temporary directory containing handcrafted `.dist-info` trees and invoke `pipdeptree --path <path>`. Use local
requirements and lock files for resolver cases. Test every output format with the same hostile names. For interpreter
probing, provide an executable fixture that prints controlled output and record the argv. The scan has no network, so
index cases need a local fixture or mocked process response.

## Severity

- Critical: inspecting metadata, a lock file or an SBOM-style input executes code from that input without invoking an
  selected interpreter or renderer.
- High: parsing or rendering attacker-controlled data writes or reads outside the requested input and output roots, or
  triggers memory corruption across the Rust/Python boundary.
- Medium: crafted labels or paths make Graphviz or the desktop opener process an unintended local file or option; a
  small input causes sustained resource exhaustion; or a temporary output exposes sensitive content to another local
  user.
- Low: a bounded crash, malformed graph, false dependency result or resource use proportional to a large environment.

## Reports and exclusions

Include the pipdeptree commit, command, complete metadata or lock fixture, interpreter, output format, platform, spawned
argv and resulting files. Prefer a reproducer that does not install or import attacker code.

Do not report:

- code execution by an interpreter selected with `--python` or by a Graphviz binary already replaced on trusted `PATH`;
- malicious behavior during package installation;
- dependency data that pipdeptree reproduces from metadata or the selected index;
- false positives, false negatives or dependency conflicts without a separate security impact;
- a vulnerability in Graphviz, an index client or the operating system's desktop opener that reproduces without
  pipdeptree.
