# Helium for Windows threat model

## What this repository is

Helium is a desktop web browser built on Chromium. This repository is its Windows platform layer: a quilt patch
series (`patches/series`) applied on top of Helium's shared patches, including the WinSparkle auto-updater
integration, the elevation service, and DRM support, plus the build script (`build.py`), the NSIS installer
(`installer/`), and packaging and signing scripts. The shared patches live in the `helium-chromium` submodule
(github.com/imputnet/helium), which is enrolled separately.

In the scanner image:

- `/src` is this repository, with the `helium-chromium` submodule checked out.
- `/chromium/src` is Chromium at the version in `helium-chromium/chromium_version.txt` with the shared patches and
  then this repository's patches applied (domain and name substitution are not applied, so URLs and `Chromium`
  identifiers are left as upstream has them). WinSparkle is unpacked at `/chromium/src/third_party/winsparkle`. To
  see which patch changed a file, use `grep -l <path> -r /src/patches /src/helium-chromium/patches`.

The image is Linux, so the Windows browser cannot be built or run here, and nothing in `/chromium/src` is compiled.
Findings have to be established by reading the code; say so in the report.

## Scope

Helium follows Chromium's threat model. Read `/chromium/src/docs/security/faq.md` and
`/chromium/src/docs/security/severity-guidelines.md` before reporting; where this file does not say otherwise, they
decide what is a vulnerability and how severe it is.

Look at what this repository changes or adds: the patches in `patches/` and the source they produce, and the
installer. Anything that lets an attacker get an update installed that Helium did not sign, or otherwise affects
what the updater fetches and runs, is critical, as is a way for an unprivileged process to make the installer,
updater or elevation service act with higher privileges. Bugs in the shared patches belong to the `helium`
enrollment, unless a Windows patch makes them reachable or worse. A bug that exists unchanged in upstream Chromium or
WinSparkle is out of scope on the same terms.

The attackers that matter are the ones Chromium considers: a malicious web page, a compromised renderer trying to
reach the browser process, a network attacker, and a malicious extension trying to exceed its permissions. For
Helium, add a malicious or compromised response from a Helium service, including the update feed.

## Out of scope

As in Chromium:

- Physically-local attacks and compromised machines: anything that needs the attacker to run code as the user,
  write to the profile directory or a user-writable install directory, set environment variables or command-line
  flags, or reach an open debugging port. Privilege escalation from another local user or an unprivileged process
  to SYSTEM or administrator, as above, stays in scope.
- Enterprise administrators and policy, which are privileged.
- Script run by the user themselves: `javascript:` URLs typed into the omnibox, bookmarklets, DevTools.

`build.py`, `package.py`, `signing.py`, `devutils/` and `.github/` are build tooling, and are out of scope unless a
bug lets a third party change what ends up in a build or a release.

## How you would like reports

Name the patch that introduces the bug (its path under `patches/`) or the installer file, and the patched source
file and line.
