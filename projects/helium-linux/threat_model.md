# Helium for Linux threat model

## What this repository is

Helium is a desktop web browser built on Chromium. This repository is its Linux platform layer: a quilt patch
series (`patches/series`) applied on top of Helium's shared patches, Linux build flags (`flags.linux.gn`), build
scripts (`scripts/`, `docker/`), and packaging (`package/`: the launcher wrappers, AppArmor profile, desktop entry,
and the deb, rpm and AppImage builds). The shared patches live in the `helium-chromium` submodule
(github.com/imputnet/helium), which is enrolled separately.

In the scanner image:

- `/src` is this repository, with the `helium-chromium` submodule checked out.
- `/chromium/src` is Chromium at the version in `helium-chromium/chromium_version.txt` with the shared patches and
  then this repository's patches applied (domain and name substitution are not applied, so URLs and `Chromium`
  identifiers are left as upstream has them). To see which patch changed a file, use
  `grep -l <path> -r /src/patches /src/helium-chromium/patches`.
- `/opt/helium/helium` (also `helium` on PATH) is the latest release. It may trail `main`, so check that a finding
  still applies to the patched source. It needs `--no-sandbox` when run as root and `--headless` because there is
  no display.

Nothing in `/chromium/src` is compiled: a Chromium build does not fit in the image's build budget.

## Scope

Helium follows Chromium's threat model. Read `/chromium/src/docs/security/faq.md` and
`/chromium/src/docs/security/severity-guidelines.md` before reporting; where this file does not say otherwise, they
decide what is a vulnerability and how severe it is.

Look at what this repository changes or adds: the patches in `patches/` and the source they produce, and the
packaging in `package/`, which decides how the browser is launched, sandboxed and installed. Bugs in the shared
patches belong to the `helium` enrollment, unless a Linux patch or the packaging makes them reachable or worse. A bug
that exists unchanged in upstream Chromium is out of scope on the same terms.

The attackers that matter are the ones Chromium considers: a malicious web page, a compromised renderer trying to
reach the browser process, a network attacker, and a malicious extension trying to exceed its permissions. For
Helium, add a malicious or compromised response from a Helium service.

## Out of scope

As in Chromium:

- Physically-local attacks and compromised machines: anything that needs the attacker to run code as the user,
  write to the profile directory or install directory, set environment variables or command-line flags, or reach an
  open debugging port.
- Enterprise administrators and policy, which are privileged.
- Script run by the user themselves: `javascript:` URLs typed into the omnibox, bookmarklets, DevTools.

`scripts/`, `docker/`, `devutils/` and `.github/` are build tooling, and are out of scope unless a bug lets a third
party change what ends up in a build or a release.

## How you would like reports

Name the patch that introduces the bug (its path under `patches/`) or the packaging file, and the patched source file
and line. Give a reproducer against the release binary where possible, and say when a finding was only confirmed by
reading code.
