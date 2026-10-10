# Threat model — MetasequoiaIME (水杉输入法, MSIME)

## What this project does and where untrusted input enters

MSIME is a cross-platform Chinese input method. Its native hosts (`platforms/<os>`) are loaded by the operating system into, or alongside, every application the user types into; they all link one Rust core through a versioned C ABI (`crates/host-api`). Layering is described in `ARCHITECTURE.md`.

Treat these as untrusted:

- **Keystrokes and editor context** delivered by the OS input framework (IBus, Fcitx5, TSF, IMK, Android/iOS/HarmonyOS keyboards), including surrounding text and application names reported by arbitrary client applications.
- **Files the user imports or downloads**: dictionary packs and user word lists, skins/themes, extension packs (sound, music, command table, effect; `.zip` or folders — see `crates/client-core` `plugins` and `crates/pack-tool`), snapshots and backups.
- **Network responses**: cloud candidates, translation, voice/AI endpoints, account sync, cloud clipboard, resource and update downloads (list in `PRIVACY.md`). Assume a hostile or compromised server.
- **Cross-process messages**: the Windows TSF DLL ↔ Server IPC (`shared/contracts/`), Android JNI, HarmonyOS NAPI, and MCP stdio input to `crates/mcp-server`.
- **Paths and environment** on multi-user systems (`crates/path-trust`).

## Components that matter most / least

- Most: `crates/host-api` (C ABI and FFI bounds), `crates/input-runtime`, `crates/engine`, `crates/client-core` (resource install, archive extraction, config parsing), the Linux hosts under `platforms/linux`, and IPC/protocol parsing in `shared/contracts` and `platforms/windows`.
- In scope but lower: `crates/mcp-server`, `crates/pack-tool`, `crates/dict-builder` (developer/author tooling that still parses untrusted files).
- Out of scope: vendored third-party code (e.g. `platforms/windows/third_party/`), `.agents/`, docs, and build/release scripts under `scripts/` and `.github/`.

## How to exercise it

- `cargo test --locked` runs the Rust workspace tests (built in the image under `/src/target`).
- The Linux native host is built under `/src/build/linux`; `ctest --test-dir /src/build/linux` runs its unit tests.
- `target/debug/msime-pack validate <pack>` exercises extension-pack import; `target/debug/msime-mcp` speaks MCP over stdio.

## How we rate severity

- Critical: remote code execution, or exfiltration of what the user types (passwords, typed text, clipboard, audio) without user action — including via a malicious network response.
- High: memory corruption in the FFI/C++ hosts reachable from keystrokes, IPC or an imported file; path traversal or arbitrary file write from an archive/pack/download; privilege boundary crossings between processes or users; crashes reachable from ordinary typing in any app (an input-method crash takes input away from every application on that system).
- Medium: denial of service from imported files or server responses that needs user action; information leaks to local logs; sending data off-device on a path not listed in `PRIVACY.md`.
- Low: issues needing an already-compromised local account, or affecting only developer tooling.

## Anything to leave alone

- Known failing tests listed in `scripts/known-failures.txt` are not vulnerabilities.
- Synthetic test credentials and fixture addresses in the repository are intentional.
- Please send reports and proposed patches against the `develop` branch.
