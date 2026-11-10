# ClamUI threat model for OSS Scanner

## Product and security goals

ClamUI is an MIT-licensed Linux desktop interface and CLI for ClamAV, written
in Python with PyGObject, GTK4 and libadwaita. It provides file scanning,
quarantine, scheduled scans, configuration management, removable-device
scanning, logs, and optional VirusTotal integration. Packages include Flatpak,
AppImage and Debian builds. All formats use the host ClamAV installation;
ClamUI does not ship the antivirus engine or its production signature database.

Treat files selected for scanning, their names and directory trees as hostile.
A normal scan or quarantine operation must not execute their contents, let
their names become commands, modify unrelated files, disclose unrelated data,
or cross from the desktop account into root privileges without authorization.
An operation that fails or skips content must not be represented as a clean scan.
VirusTotal integration is opt-in, and file transmission must follow the user's
consent and configured behavior. API keys and private file information matter.

This model describes intended properties and review priorities, not a claim
that every property is already enforced by the implementation.

## Attacker capabilities and trust boundaries

An attacker may supply downloaded files, archives or removable-media contents,
including unusual filenames, symlinks, hardlinks and trees changed during an
operation. A local lower-privileged process may race filesystem operations.
Imported profiles, externally supplied paths/URIs, scan output, JSON, log text,
tray IPC and HTTP response data should be checked at their relevant boundary.
For each finding, explain how the attacker obtains control of that input.

The main UI and CLI normally run as the user's unprivileged desktop account.
ClamAV execution, clamd communication, Flatpak-to-host commands, scheduled
execution and the polkit-elevated configuration helper form distinct boundaries.
Existing root control or arbitrary code execution as the victim is not, by
itself, a new vulnerability. Such capabilities can still be relevant if they
cross into a more privileged account or violate an independent file boundary.

Flatpak intentionally grants broad host filesystem access and uses
`flatpak-spawn --host`. These grants alone are not a finding. Injection into
host commands or unintended operations made possible by ClamUI are in scope.

## Highest-priority code

1. **Privileged configuration and helper installation.** Review
   `src/cli/apply_preferences.py`, `src/cli/install_helper.py`,
   `src/cli/resources/io.github.linx_systems.ClamUI.policy`,
   `src/core/privileged_paths.py`, `src/core/clamav_config.py`,
   `src/core/privileged_helper.py`, and `debian/build-privileged-helper-deb.sh`.
   Investigate caller identity, source ownership/mode, destination allowlists,
   read-mode restrictions, symlink/race handling and root-owned module loading.
   The download/install path also needs signature, package identity, version,
   size and digest validation across the privilege transition. Use local
   fixtures and mocked HTTP responses rather than downloading live releases.
2. **Quarantine.** Review `src/core/quarantine/`, especially `file_handler.py`,
   `manager.py` and `database.py`. Check containment, integrity verification,
   restore/delete destinations, replacement races, safe permissions, unexpected
   file types, concurrent operations and database-controlled path metadata.
   A symlink check before a later path-based operation is not sufficient proof
   of race resistance. Describe whether corruption is attacker-reachable.
3. **Command execution and scheduling.** Review `src/core/scanner.py`,
   `scanner_base.py`, `daemon_scanner.py`, `scheduler.py`, `flatpak.py`,
   `updater.py`, `src/cli/scheduled_scan.py`, and the CLI routers. Check argv and
   option boundaries, quoting at shell/systemd/cron boundaries, control
   characters, host path translation, daemon errors and cancellation. Include
   device-auto-scan and file-manager entry points when tracing attacker input.
4. **Privacy and remote data.** Review `src/core/virustotal.py`,
   `keyring_manager.py`, `settings_manager.py`, the VirusTotal UI and privileged
   helper download handling. Look for unintended uploads, credential leakage,
   unsafe fallback behavior, unbounded responses and unsafe trust in URLs or
   redirects. Network responses can be exercised offline with mocks.
5. **Profiles, logs, UI and IPC.** Review `src/profiles/`,
   `src/core/path_validation.py`, `sanitize.py`, log/export code, and
   `src/ui/tray_manager.py`/`tray_service.py`. Check imported profile validation,
   parser ambiguity, log/markup injection, IPC validation and security-relevant
   misrepresentation of scan results. Purely cosmetic issues have low priority.

The active scan interface is `src/ui/scan_view.py`. The separate components
under `src/ui/scan/` are not wired into the running scan screen at the reviewed
revision; explain reachability before attributing user-visible impact to them.

## Scope and severity guidance

Prioritize vulnerabilities in ClamUI's own code and packaging. ClamAV engine
parsing bugs, detection quality, signature false positives/negatives, and
dependency advisories without a ClamUI-specific exploit path belong upstream.
ClamUI's unsafe use of a dependency or subprocess remains in scope. The
marketing/documentation website is outside this application scan's focus.

Suggested triage guidance, subject to maintainer review:

- **Critical:** demonstrated reliable arbitrary root code execution or a similarly
  severe privilege-boundary compromise reachable from realistic hostile input.
- **High:** arbitrary code execution as the desktop user through a routine
  operation, a demonstrated privilege escalation, impactful arbitrary file
  modification/deletion, or substantial unintended data/credential disclosure.
- **Medium:** realistically exploitable denial of service, meaningful scan
  bypass/misreporting, or a constrained confidentiality/integrity violation.
- **Low:** limited log/UI deception or hardening gaps with demonstrated but small
  security impact. Label speculative concerns as such.

Do not upgrade severity solely because this is antivirus software. Describe
attacker access, victim action, affected account, default configuration and
impact. An authorized restoration to a path the user deliberately selected or
deliberately enabled plaintext fallback is not automatically an exploit.

## Build and offline exercise

The Dockerfile keeps the complete checkout at `/src`, Python in `/src/.venv`,
and all Python runtime/test dependencies installed before network isolation.
The source is editable by `clamui-test` (UID 10001) for local reproductions.
The image builds a wheel and the real privileged-helper Debian package in
`/opt/clamui-artifacts/`. The package is an inspection artifact, not installed.

Run `clamui-tests -q` from the scanner shell. This runs the existing suite as
`clamui-test` under a temporary D-Bus session and Xvfb, excluding `tests/e2e`
as in the project's primary CI job. It invokes the installed Python directly;
it does not sync packages. To focus on security-relevant behavior:

```sh
clamui-tests -q tests/core/test_quarantine_security.py \
  tests/core/test_privileged_paths.py tests/core/test_path_validation.py \
  tests/core/test_sanitize.py tests/core/test_flatpak.py \
  tests/cli/test_apply_preferences_security.py
```

The image records a build-time test attempt in
`/opt/clamui-validation/pytest.log` and `pytest.exit-code`. Nonzero status,
including timeout 124, must be examined; successful image creation does not
mean the suite passed. Build/dependency/package failures abort the image build.

ClamAV binaries are installed for inspection, but no production definitions,
live clamd, systemd user session, real Secret Service backend, or Flatpak host
is configured. Existing scanner integration tests mock ClamAV. Use local
synthetic fixtures/mocks for these interfaces. Real desktop/e2e behavior needs
an appropriate environment and must not be inferred from mocked test passes.
Do not contact VirusTotal, upload files, update signatures, or require credentials.

The scanner shell is root for analysis tools. Show an unprivileged starting
point when reporting an escalation, for example with
`runuser -u clamui-test -- /src/.venv/bin/python /src/reproducer.py`.
Use the root shell only to stage a controlled helper fixture or inspect its
privileged half. The container is not evidence of a real polkit/desktop exploit.
The normal test command skips tests explicitly marked as requiring root. In
an isolated environment that permits changing file ownership, exercise the
existing root-only UID-mismatch case separately from the root shell:

```sh
/src/.venv/bin/python -m pytest -q \
  tests/cli/test_apply_preferences_security.py::TestSourceUidMismatchRejected
```

Do not run the entire helper-security file as root: several other cases use
the current account as their simulated nonzero polkit caller.

## Useful reports and patches

Report privately to `clamui@rooki.xyz`, which is the project's published
security contact. Include affected revision and functions, entry point,
attacker prerequisites, a small deterministic reproducer, expected/actual
behavior, impact and suggested severity. Use temporary files, fake credentials,
and local services/fixtures. Do not access unrelated user data.

Prefer a focused patch that fixes the boundary where the problem originates,
with a regression test that fails before the fix. Preserve host-ClamAV support,
the user-consent model, relative production imports and the declared GTK and
libadwaita compatibility. Group duplicates by common root cause and distinguish
new findings from an already-fixed historical issue with similar symptoms.
