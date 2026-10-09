# Threat model: py1815

## What this project does and where untrusted input enters

py1815 is a pure-Python implementation of DNP3 (IEEE 1815) for distributed energy resources (solar inverters, battery storage, EV chargers). It has three parts:

- An outstation library (`src/py1815/`): the device side that a SCADA master connects to. It reports measurements and accepts controls that operate real equipment.
- A DER profile (`src/py1815/profile/`): the IEEE 1815.2 point map, a builder that turns a map and a binding into an outstation, and a simulated DER.
- A master (`src/py1815/master/`): polls outstations, issues controls, and serves a JSON API and a browser console.

Untrusted input enters at these points:

1. Outstation TCP listener (`server.py`). Every octet a peer sends is untrusted. With a TLS context, the peer certificate is checked against an allow-list (`server.authorize`) before any DNP3 data reaches the session. Without TLS there is no authentication and every parser is reachable by anyone who can open the socket. Both deployments are supported and both are in scope.
2. Master TCP client (`master/association.py`, `master/requests.py`). Responses and unsolicited messages from an outstation are untrusted. An outstation can be compromised or spoofed.
3. Master HTTP API and console (`master/api.py`, `master/service.py`, `master/console/`). The API requires a bearer token when bound beyond localhost. The console page itself needs no token. Values received from outstations are rendered in the console.
4. Configuration and profile files (`master/config.py`, `profile/config.py`, `profile/load.py`, `profile/xlsx.py`). These are written by the operator and are lower priority, but a parser crash or path traversal from a crafted file is still worth reporting.

## Components that matter most / least

Most important, in order:

1. Control handling: `control.py`, `application.parse_object_blocks`, the select-before-operate state machine in `session.py`, and the boundary where a control reaches the caller's `ControlProvider`. Any defect that lets a control operate the wrong point, operate without a matching select, reuse an expired select, or reuse a select granted on a previous connection.
2. Admission and association handling in `server.py`: the TLS allow-list, and the rule that an unauthorized peer cannot displace or disturb an established master.
3. Parsers: `link.py` (FT3 framing, CRC), `transport.py` (reassembly), `application.py` (function codes, object headers, qualifiers and ranges), `objects.py`, `decode.py`.
4. Resource limits reachable from one connection: event buffers (bounded by configured capacity), fragment reassembly (bounded by `max_fragment`), and the idle timeout.
5. Master API authentication, and cross-site scripting or injection in the console through values an outstation reports.

Out of scope:

- `interop/` (interoperability test peers in Rust and C++), `scripts/`, `tools/`, `docs/`, `tests/`.
- The IEEE 1815.2 point tables and the DNP Users Group schema. They cannot be redistributed and are not in the image.

## How to exercise it

- Run the suite: `pytest -q`. Tests that need the IEEE point tables or the Device Profile schema skip.
- `py1815-der run` needs the IEEE point tables, which are not in the image. Build an outstation from the library directly instead, as `tests/test_server.py` and `tests/test_session*.py` do.
- `py1815.master.loopback` connects a master to an outstation session in one process with no socket. It is the fastest way to drive both sides.
- `py1815-master console --outstation lab=127.0.0.1:20000` serves the console on localhost, where no token is required, against an outstation you start yourself. `--demo` needs the IEEE point tables and does not work in the image.
- Useful starting points for new harnesses: `tests/test_control_parsing.py`, `tests/test_session_controls.py`, `tests/test_session_fragmentation_invariants.py`, `tests/test_master_service.py`, `tests/test_master_console.py`.

## How you rate severity

State whether the finding needs a TLS listener with an allow-list or a plaintext listener.

- Critical: an unauthenticated or unauthorized peer causes a control to reach a `ControlProvider`; a TLS listener admits a certificate the allow-list should refuse; remote code execution.
- High: a control reaches a different point, function, or value than the master sent; a select is spent by a non-matching operate, after expiry, or on a later connection; an unauthorized peer displaces or alters an established association; a single connection crashes or hangs the outstation process, or causes unbounded memory growth; one association's data leaks into another's responses; bypass of the master API token.
- Medium: denial of service that requires an authorized peer; a malicious outstation that crashes the master or corrupts its stored values; cross-site scripting in the console from outstation-reported values.
- Low: wrong responses to malformed but harmless requests; information in logs; issues that need operator-controlled configuration files.

## Anything to leave alone

- Plaintext operation when no TLS context is configured. DNP3 over plain TCP is normal on isolated OT networks. Unencrypted traffic, or controls accepted on a plaintext listener, is not a finding. TLS not applied when configured is a finding.
- Controls accepted from an authorized master for a point its provider owns. That is the intended behavior.
- Missing DNP3 Secure Authentication (SAv5). It is not implemented.
- The master console with no token: on localhost by default, or beyond it with `--no-token`. Both are documented operator choices. A token requirement that is skipped when one is configured is a finding.
- Event buffers that survive a reconnect. This is by design: a returning master expects its unread events.
- Floating-point variations and device attributes, which are not implemented.

## Report format

Include a minimal reproducer as a pytest test or a short script using the library API, the listener mode tested (TLS or plaintext), and a proposed patch with a regression test in `tests/`.
