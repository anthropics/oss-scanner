# Helium for macOS threat model

## What this repository is

Helium is a desktop web browser built on Chromium. This repository is its macOS platform layer: a quilt patch
series (`patches/series`) applied on top of Helium's shared patches, including the Sparkle auto-updater integration,
plus build, signing and packaging scripts. The shared patches live in the `helium-chromium` submodule
(github.com/imputnet/helium), which is enrolled separately.

In the scanner image:

- `/src` is this repository, with the `helium-chromium` submodule checked out.
- `/chromium/src` is Chromium at the version in `helium-chromium/chromium_version.txt` with the shared patches and
  then this repository's patches applied (domain and name substitution are not applied, so URLs and `Chromium`
  identifiers are left as upstream has them). Sparkle is unpacked at `/chromium/src/third_party/sparkle`. To see
  which patch changed a file, use `grep -l <path> -r /src/patches /src/helium-chromium/patches`.

The image is Linux, so the macOS browser cannot be built or run here, and nothing in `/chromium/src` is compiled.
Findings have to be established by reading the code; say so in the report.

## Scope

Helium follows Chromium's threat model. Read `/chromium/src/docs/security/faq.md` and
`/chromium/src/docs/security/severity-guidelines.md` before reporting; where this file does not say otherwise, they
decide what is a vulnerability and how severe it is.

Look at what this repository changes or adds: the patches in `patches/` and the source they produce. Anything that
lets an attacker get an update installed that Helium did not sign, or otherwise affects what the updater fetches and
runs, is critical. Bugs in the shared patches belong to the `helium` enrollment, unless a macOS patch makes them
reachable or worse. A bug that exists unchanged in upstream Chromium or Sparkle is out of scope on the same terms.

The attackers that matter are the ones Chromium considers: a malicious web page, a compromised renderer trying to
reach the browser process, a network attacker, and a malicious extension trying to exceed its permissions. For
Helium, add a malicious or compromised response from a Helium service, including the update feed.

## Out of scope

As in Chromium:

- Physically-local attacks and compromised machines: anything that needs the attacker to run code as the user,
  write to the profile directory or app bundle, set environment variables or command-line flags, send Apple events
  to the browser, or reach an open debugging port.
- Enterprise administrators and policy, which are privileged.
- Script run by the user themselves: `javascript:` URLs typed into the omnibox, bookmarklets, DevTools.

The build, signing and packaging scripts, `devutils/` and `.github/` are build tooling, and are out of scope unless a
bug lets a third party change what ends up in a build or a release.

## How you would like reports

Name the patch that introduces the bug (its path under `patches/`) and the patched source file and line.
