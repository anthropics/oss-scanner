# Foldera

Foldera is an MIT-licensed native Swift/AppKit file manager for macOS 14+.
It is experimental beta software. Its security relevance is handling untrusted
archives, filenames, Markdown and filesystem trees while possessing access to
the user's files. There is no claim of widespread adoption or production safety.

## Platform limitation: operator review required

The Linux image provides the full checkout at /src, Swift, libarchive and archive
utilities. It builds only the CArchive interoperability target and parses Swift
syntax. This does NOT build the Foldera application or run its regression suite.
AppKit, WebKit, Darwin APIs, macOS filesystem behavior and Apple frameworks are
not emulated. This enrollment is proposed for source review and limited portable
reproducers only, subject to explicit acceptance by the scanner operators.

Native verification requires macOS 14+ and Swift 6. Run `swift build` and
`./test.sh` there. Some file-coordination tests require a logged-in desktop;
see .github/workflows/test.yml. Linux libarchive behavior is not proof of the
behavior of the libarchive version shipped by macOS. Report all such limits.

## Attack surfaces

- Archive.swift and Unpack.swift: malicious archive entry names, traversal,
  absolute paths, symlinks/hardlinks, extraction outside the destination,
  archive browsing/preview caches, overwrite behavior and resource exhaustion.
- Transfer.swift, FileOps.swift, Undo.swift and BatchRename.swift: replacement,
  copy/move, cancellation and Undo/Redo integrity; symlink swaps, races, path
  identity, case-sensitive/case-insensitive filesystems and cross-volume moves.
- Sync.swift, SyncLibrary.swift and SyncScheduler.swift: adversarial directory
  trees, changed/unmounted roots, stale comparisons, symlink replacement,
  excluded items, saved profiles, scheduled operations and destructive changes
  exceeding the user's selected roots or confirmed intent.
- Markdown.swift and preview paths: untrusted Markdown/HTML, image paths,
  scripts, navigation and access to local files beyond the documented image
  policy. Trace what crosses into WebKit and external applications.
- Servers.swift and filesystem paths: untrusted names or network-share input
  reaching processes, URL handling or filesystem operations.

Assume files, archives and mounted shares can contain attacker-controlled data.
Distinguish a malicious document/archive from a local process already running
with the user's full filesystem rights. The latter is not automatically a new
privilege escalation. Apple sandbox/TCC or kernel bypasses are not provided by
this application. User-confirmed deletion within the selected scope is intended;
unconfirmed deletion or writes outside it are not.

## Reports and validation

Use disposable temporary fixtures, never real user files or credentials.
Prioritize arbitrary writes outside extraction/sync roots, unintended data loss,
code execution from untrusted content, and unauthorized local-file disclosure.
For races, show the operation order and the impact beyond the attacker's existing
access. State the macOS version, filesystem type, relevant permissions and user
interaction required. Bound resource-exhaustion demonstrations.

Provide the affected commit and lines, root cause, reproducer and a minimal patch
with a regression test. Separate source-level candidates from macOS-confirmed
findings, deduplicate by root cause, and avoid unsupported severity claims.
