# TinySSH threat model

## Project and trust boundaries

TinySSH is a minimal SSHv2 server written in C. It provides public-key
authentication, remote shell and command execution, PTYs, and explicitly
configured subsystems. It supports Ed25519, ChaCha20-Poly1305, Curve25519, and
hybrid sntrup761/X25519 key exchange. It does not implement password
authentication, compression, or port, agent, or X11 forwarding.

The server normally receives an accepted connection on standard input/output
from a supervisor such as inetd, tcpserver, or systemd. Treat all client bytes
as untrusted, both before and after authentication: identification strings,
packet lengths and payloads, algorithm lists, key-exchange values, usernames,
public keys and signatures, channel requests, terminal settings, and channel
data. Account databases, administrator-selected command-line options, and
properly protected host keys are trusted configuration.

An unauthenticated client must not gain execution, access protected data, or
authenticate as another user. Authenticated commands must run with the selected
account's UID, GID, and supplementary groups. Authentication as one account
does not authorize access to another account or to the server's private keys.
Normal command execution within the authenticated account's permissions is
an intended feature, not a vulnerability. A configured forced command (`-e`)
must not be bypassed by client requests or environment manipulation.

`tinysshnoneauthd` intentionally permits authentication without a key, but only
for accounts whose UID matches the daemon's effective UID. Review that boundary
and forced-command enforcement; do not report the documented absence of key
authentication in this separate mode as an authentication bypass.

## Review priorities

- Packet framing, parsing, buffer bounds, integer arithmetic, state transitions,
  and resource consumption in `packet*.c`, `buf.c`, and `stringparser.c`.
- Algorithm negotiation, strict key exchange, rekeying, session identifiers,
  sequence numbers, and authenticated encryption in `packet_kex*.c`,
  `packet_auth.c`, and `sshcrypto*.c`.
- Signature verification and authorized-key lookup in `subprocess_auth.c`,
  including ownership and permission checks, symlink/path resolution, races,
  and failure handling. An unprivileged user must not be able to authorize a
  key for another account by manipulating files or directories they control.
- Privilege transitions, subprocess communication, descriptor lifetime, host
  key handling, and signing in `channel*.c`, `dropuidgid.c`,
  `subprocess_sign.c`, and `main_tinysshd*.c`.
- Command/subsystem selection, PTYs, environment construction, and channel flow
  control. Client `env` channel requests are deliberately rejected; the terminal
  type in a PTY request is still accepted and should be treated as untrusted.
- Cryptographic backends and their integration in `crypto*.c`, `cryptoint/`,
  `fe*.c`, `ge25519.c`, `sc25519.c`, `randombytes.c`, and `cleanup.c`:
  correctness, randomness, secret lifetime, and secret-dependent timing.

Focus on code reachable from the current top-level build. Tests and test-only
authentication shortcuts are useful audit tools; distinguish them from
production entry points. The Debian Trixie image installs `lib1305-dev`,
`lib25519-dev`, `libntruprime-dev`, and `librandombytes-dev`.
The build detects these libraries and uses the corresponding external backends;
bundled implementations remain fallbacks. Inspect the generated `haslib*.h`
headers and `libs` files in `/src` and `/src/tests` to confirm the selected
backends. Exercising the bundled alternatives requires a separate build without
the corresponding development libraries.

## Build and tests

The checkout and production binaries are in `/src`; test executables and
expected outputs are in `/src/tests`. Debug information and frame pointers are
enabled, and the Makefiles retain their normal optimization and `-fwrapv` flags.
All dependencies are installed during the image build. Tests use local pipes
and OpenSSH ProxyCommand and do not require Internet access or a listening SSH
service.

From the scanner's root shell, run:

```sh
cd /src
make
make -C tests
chown -R scanner-test:scanner-test /src
runuser -u scanner-test -- make test
runuser -u scanner-test -- make test-ssh
```

Run SSH integration tests as `scanner-test`, whose login shell is Bash; those
tests reject execution as root. `make test` exercises cryptography and protocol
regressions; `make test-ssh` exercises forced-command/environment handling and
session identifiers across rekeying using the installed OpenSSH client.
Tests compare `tests/*.out` with `tests/*.exp`; inspect failures even if the
Docker build succeeded. The current `test-subprocess-auth.sh` explicitly skips
authorized-key handling, so a passing suite does not validate that boundary.

For new reproducers, generate disposable host keys with
`/src/tinysshd-makekey <new-directory>`. Use temporary accounts and files for
privileged authentication and session tests, and describe their setup in the
report. Test helpers in `tests/_tinysshd-test-*.c` can drive malformed protocol
messages and state transitions.

## Severity and useful reports

Prioritize demonstrated impact and state the attacker's prerequisites:

- Unauthenticated remote code execution, authentication bypass granting an
  unauthorized session, or recovery of server private keys are top priority.
- Cross-account access, privilege escalation, and forced-command bypasses are
  high priority; distinguish restricted accounts from ordinary shell accounts.
- Memory corruption is high priority. Establish reachability and attacker
  control, and distinguish a crash from demonstrated code execution.
- For denial of service, distinguish termination of the attacker's own
  per-connection process from exhaustion or disruption affecting other users.
- For cryptographic or timing findings, explain the attacker model, observable
  signal, affected secrets, and practical impact.

Include the tested commit and build configuration, affected entry point,
required privileges, a minimal reproducer, expected and actual behavior, and
a proposed focused patch and regression test where feasible. Distinguish
production findings from test-harness behavior and generic hardening advice.
