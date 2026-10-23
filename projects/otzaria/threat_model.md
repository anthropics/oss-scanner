# Threat model

## What this project does and where untrusted input enters
Otzaria is an offline reader and search tool for a large library of Jewish texts (Windows, Linux, macOS, Android, iOS), written in Flutter with Rust native libraries for full-text search and OpenType shaping. Untrusted input enters through:
- **Plugins** (`lib/plugins/`): third-party HTML/JS packages, installed from the plugin store or as local archives, run in a WebView and reach the app through a permission-gated bridge (file system, books, downloads, deep links, printing). A plugin escaping its declared permissions, reading files outside its granted folders, or running code in the host is the most important class of bug.
- **External URIs and command-line activation** (`lib/core/external_uri_router.dart`, `external_activation_*`, `cli_command.dart`): `otzaria://` links and arguments passed by other processes or web pages.
- **Downloaded content**: app updates (`lib/update/`), library updates and delta patches (`lib/library_update/`), plugin archives, and catalog/metadata fetched over HTTP. A network attacker or a compromised mirror must not get code execution, path traversal out of the data folder, or a silently corrupted library.
- **User-imported files** (`lib/user_content_import/`, `pdf_book/`): PDFs, text, DOCX and archives the user opens; treat their content as untrusted.
- **Library databases** (SQLite) and search indexes are produced by our pipeline and are trusted for integrity, but SQL built from user search queries or book references must not be injectable.

## Components that matter most / least
- Most: the plugin bridge and its permission checks, archive extraction (zip/zstd), update and patch application, external URI handling, the Rust search engine's query parsing.
- Least: UI layout, themes, the tour, `tool/` scripts that only run in CI. Third-party Dart/Rust packages are out of scope unless our use of them is what is wrong.

## How to exercise it
- `flutter test --no-pub test/<area>` runs the unit and widget tests (e.g. `test/plugins`, `test/core`, `test/library_update`, `test/update`); most of the app's logic is reachable from them.
- The image has no desktop build: the Linux build needs a patched WPE WebKit SDK.

## How you rate severity
- Critical: code execution in the host process, or a plugin or web page escaping its sandbox to read or write arbitrary user files.
- High: path traversal or arbitrary file write through an archive, update or plugin; bypass of a plugin permission prompt; SQL injection.
- Medium: denial of service from a crafted file, query or plugin (crash, hang, unbounded memory); information disclosure limited to app data.
- Low: issues that need a local attacker who already controls the user's account.

## Anything to leave alone
- Do not report that the user can install a plugin or open a file they chose; report only what such content can do beyond its granted permissions.
