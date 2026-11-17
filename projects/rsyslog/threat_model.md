# rsyslog threat model (OSS Scanner entry point)

## Authoritative model: read these first

rsyslog keeps its threat model in the repository. It is the source of truth;
this file only adds what is specific to the scanner image. Where the two
differ, the repository files win.

1. `/src/doc/security/project-threat-model.md`: trust boundaries (TB-NET-IN,
   TB-LOCAL-IN, TB-CONFIG, TB-PRIV, TB-PIPELINE, TB-STORAGE, TB-OUTBOUND,
   TB-EXEC, TB-MODULE, TB-CI), security invariants (SI-*), assumptions and
   exclusions, attacker stories and severity calibration (section 4).
2. `/src/doc/security/threat-model-components.json`: maps repository paths to
   those boundaries and invariants. Components with `"requires_lead": true`
   hold remote-input parsing, transport security, privilege, storage,
   execution and release authority; prioritise them.
3. `/src/SECURITY.md`: scope, triage, and how optional/contrib modules and
   configuration preconditions affect rating.
4. `/src/doc/ai/security_triage_rubric.md`: evidence standard (confirmed vs
   potential vs hardening) and wording rules.

## Where to spend effort

Follow the priority order of section 3 of the project threat model. In short:
remote input (framing, decompression, TLS handshake, protocol state and
message data in the network inputs and the core parsers), then configured peer
identity and access controls, then the message pipeline, queues, storage,
outputs and external helpers. Local inputs (TB-LOCAL-IN) are in scope with
lower exposure. Configuration is administrator authority (TB-CONFIG): a
finding there needs a realistic path for a lower-privileged actor.

State which `compatibility.defaults.secure` mode a finding assumes (the
default is `warn`, see section 1 of the project threat model).

## How to exercise it in this image

- One in-tree ASan + UBSan build in `/src` (autotools). `tools/rsyslogd` is
  the daemon; modules are in `plugins/*/.libs`, `contrib/*/.libs` and
  `runtime/.libs`. Run it from the tree with
  `-M/src/runtime/.libs:/src/plugins/<mod>/.libs:...` and `-f <config>`;
  `-N1` validates a configuration without starting.
- Testbench in `tests/`: run single tests with
  `make check TESTS="imtcp-basic.sh"`. Most tests start rsyslogd with a small
  configuration via `tests/diag.sh` and feed it with `tests/tcpflood`
  (TCP, UDP, TLS, RELP). Existing tests are the best reproducer templates.
  `RSYSLOG_TESTBENCH_SKIP_SERVICE_RELEVANCE=1` is set so that tests are not
  skipped by the PR-CI relevance gate.
- libFuzzer targets: `tools/fuzz_rsyslog_message` (PRI, RFC 3164, RFC 5424
  parsers) and `tools/fuzz_imtcp_session` (imtcp framing, multiline,
  zlib/zstd). See `tests/fuzz/README.md`.
- ASan leak detection is off by default (`ASAN_OPTIONS=detect_leaks=0`)
  because shutdown paths are not leak-clean. Enable it when needed; for
  memory-growth claims show that memory grows with attacker input.

## Things to leave alone

These follow from the assumptions and exclusions in the project threat model:

- Plain syslog sender spoofing without a configured authentication boundary.
- `imdiag`, `omtesting`, `tests/` and other test-only code as a production
  surface (they remain in scope only where they can affect a released
  artifact).
- Defects inside third-party libraries (report upstream); rsyslog's use of
  their APIs stays in scope.
- Best-effort statistics counters (impstats) being racy or inexact.
- One-time leaks at shutdown or on configuration load.
- UBSan reports of unsigned integer wrap-around without a resulting memory or
  logic error (this image does not enable that check).
