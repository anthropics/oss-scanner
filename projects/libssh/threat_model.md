# Threat model

## What this project does and where untrusted input enters

libssh is a multiplatform C library implementing the SSHv2 protocol on both client and server sides. It also provides SFTP client and server implementations, channel multiplexing, port and agent forwarding, and PKI/certificate verification.

Untrusted input enters via network packets from remote peers on both sides of the connection:

* **Pre-authentication peer traffic (highest risk):** Version banner exchanges, algorithm negotiation (`SSH2_MSG_KEXINIT`), Diffie-Hellman / ECDH key exchange, host key parsing, signature verification, and authentication requests (password, public key, keyboard-interactive, GSSAPI).
* **Post-authentication peer traffic:** Channel requests, PTY and environment requests, subsystem requests (SFTP), terminal settings, window/packet adjustments, and data transfers. Even after authentication, traffic from a verified peer or server must be treated as potentially malicious.
* **Client-side exposure:** A malicious or compromised SSH server sending crafted handshake packets, oversized banners, malicious SFTP directory traversals, or rogue channel requests to a libssh client.

Trusted inputs (not considered vulnerabilities if misconfigured):
* Local configuration files (`~/.ssh/config`, `/etc/ssh/ssh_config`).
* Local private keys, known_hosts files, and authorized_keys databases.
* API misuse contradicting documented function contracts (e.g. passing NULL to non-nullable parameters or operating on closed session pointers).

## Components that matter most / least

Most important:
* **Protocol and packet state machine (`src/packet.c`, `src/packet_cb.c`, `src/session.c`):** Packet framing, sequence numbers, decompression, rekeying, and state transitions (e.g. preventing authentication bypasses).
* **Authentication handling (`src/auth.c`, `src/server.c`, `src/bind.c`):** Client and server authentication mechanisms, credential validation, and privilege boundaries.
* **Key exchange and cryptography integration (`src/kex.c`, `src/dh.c`, `src/ecdh.c`, `src/pki*.c`, `src/libcrypto.c`):** Strict key exchange enforcement, public key and signature verification, and crypto backend wrappers.
* **Buffer and string parsing (`src/buffer.c`, `src/string.c`, `src/misc.c`):** Bounds checks, integer arithmetic, and binary packet decoding.
* **Channel multiplexing, teardown, and callback dispatch (`src/channels.c`):** Preventing use-after-free on closed or half-closed channels.
* **SFTP parser (`src/sftp.c`, `src/sftpserver.c`):** Message framing, attribute parsing, and path sanitization.

Least important / Out of scope:
* `src/scp.c`: Legacy SCP protocol (deprecated in favor of SFTP).
* `src/external/`: Third-party, fallback, and copylib implementations (e.g. bundled Ed25519 or bcrypt).
* `examples/`: Sample programs (e.g. `examples/samplesshd-cb.c`, `examples/sshnetcat.c`). They illustrate API usage and do not implement full production hardening; flaws in examples are not library bugs unless caused by a defect in `src/`.
* `tests/`: Test runners and harnesses themselves.

## How to exercise it

* **Build layout:** The source is located at `/src` and the pre-configured CMake/Ninja build directory is `/src/build`.
* **Running tests:**
  ```sh
  cd /src/build
  # Run all unit tests
  ctest --output-on-failure -j"$(nproc)"
  # Run a specific unit test
  ctest -R <test_name> --output-on-failure -V
  ```
* **Fuzzing harnesses:** Fuzz drivers for packet parsing, client, and server state machines are located in `tests/fuzz/` (built in `/src/build/tests/fuzz/`). They can be driven with corpora or reproducer files directly:
  ```sh
  /src/build/tests/fuzz/ssh_server_fuzzer <reproducer_or_corpus>
  /src/build/tests/fuzz/ssh_client_fuzzer <reproducer_or_corpus>
  ```

## How you rate severity

* **Critical:**
  * Pre-authentication Remote Code Execution (RCE) on the server.
  * Server-side authentication or authorization bypass (e.g. state machine flaw allowing unauthenticated access, or missing principal-to-user checks allowing arbitrary user impersonation).
  * Remote disclosure of server private host keys or cryptographic session secrets.
* **High:**
  * Pre-authentication memory corruption (buffer overflow, use-after-free, double free) reachable without credentials, even if RCE is not proven.
  * Client-side RCE or credential theft triggered by connecting to a malicious server.
  * Cryptographic flaws compromising handshake integrity or confidentiality (e.g. downgrade attacks or broken strict KEX).
* **Medium:**
  * Memory corruption triggerable only *after* successful authentication.
  * Information disclosure not exposing private keys or session secrets.
  * Denial of service via unbounded memory allocation or infinite CPU loops that impact the entire host or other concurrent sessions.
  * Cryptographic protocol flaws requiring an active Man-in-the-Middle (MitM) position with limited practical impact (e.g., Terrapin extension truncation).
* **Low:**
  * DoS affecting only a single connection or child process (standard libssh servers recommend a fork-per-connection model).
  * Memory leaks that do not allow unbounded remote memory exhaustion.
  * Flaws requiring non-default, test-only configuration or deprecated legacy algorithms.

## Anything to leave alone

* The `none` cipher suite (`none`, `none`-mac). It is strictly test-only and disabled by default in production builds.
* Bugs located solely in `src/external/` or `examples/`.
* Crashes caused by passing invalid arguments in violation of the public API documentation.
* Denial of service caused simply by closing or disrupting the attacker's own connection.
