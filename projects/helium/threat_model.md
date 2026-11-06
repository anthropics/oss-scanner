# Helium threat model

## What Helium is

Helium is a desktop web browser built on Chromium. This repository does not contain a browser source tree. It holds
a quilt patch series (`patches/series`, applied in order), resources, build flags (`flags.gn`) and the Python tooling
that turns a Chromium source tarball into Helium's source. The platform repositories (helium-linux, helium-macos,
helium-windows) add their own patches and package the result; they are out of scope here.

In the scanner image:

- `/src` is this repository.
- `/chromium/src` is Chromium at the version in `chromium_version.txt` with every patch in `patches/series` applied
  (domain and name substitution are not applied, so URLs and `Chromium` identifiers are left as upstream has them).
  To see what Helium changed in a file, find the patch with `grep -l <path> /src/patches -r`.
- `/opt/helium/helium` (also `helium` on PATH) is the latest Linux release. It may trail `main` by a Chromium
  milestone, so check that a finding still applies to the patched source. It needs `--no-sandbox` when run as root
  and `--headless` because there is no display.

Nothing in `/chromium/src` is compiled: a Chromium build does not fit in the image's build budget.

## Scope

Helium follows Chromium's threat model. Read `/chromium/src/docs/security/faq.md` and
`/chromium/src/docs/security/severity-guidelines.md` before reporting; where this file does not say otherwise, they
decide what is a vulnerability and how severe it is.

Look at what Helium changes or adds: the code in `patches/` and the source it produces. Helium removes or replaces
several Google services with its own (sync, extension and component downloads, updates, search, onboarding), so new
code that talks to Helium's services, parses their responses, or exposes new browser-process functionality to web
content, WebUI or extensions deserves the closest look. A bug that exists unchanged in upstream Chromium is out of
scope, unless a Helium patch makes it reachable or worse.

The attackers that matter are the ones Chromium considers: a malicious web page, a compromised renderer trying to
reach the browser process, a network attacker, and a malicious extension trying to exceed its permissions. For
Helium, add a malicious or compromised response from a Helium service or sync server.

## Out of scope

As in Chromium:

- Physically-local attacks and compromised machines: anything that needs the attacker to run code as the user,
  write to the profile directory or install directory, set environment variables or command-line flags, or reach an
  open debugging port.
- Enterprise administrators and policy, which are privileged.
- Script run by the user themselves: `javascript:` URLs typed into the omnibox, bookmarklets, DevTools.

In this repository, `devutils/`, `utils/`, `i18n/` and `resources/` are build-time tooling and data, and are out of
scope unless a bug lets a third party change what ends up in a build.

## How you would like reports

Name the Helium patch that introduces the bug (its path under `patches/`) and the patched source file and line.
Give a reproducer against the release binary where possible, and say when a finding was only confirmed by reading
code.
