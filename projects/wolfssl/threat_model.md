# Threat model

This follows the wolfSSL security policy and vulnerability report template, `SECURITY-POLICY.md` and
`SECURITY-REPORT-TEMPLATE.md` in the repository. Where this file and the policy differ, the policy wins.

## What wolfSSL is and where untrusted input enters

wolfSSL is a TLS 1.2/1.3, DTLS 1.2/1.3 and QUIC library (`src/`) built on the wolfCrypt cryptography library
(`wolfcrypt/src/`), written in C90 for targets from bare-metal microcontrollers and RTOSes to servers. Features are
chosen at compile time, with `./configure` options or a `user_settings.h`, so one source tree compiles into very
different libraries. The library is what matters; the example programs and the tests are not.

Untrusted input enters through:

* TLS and DTLS records from the network, on both the client and the server side: record decryption and padding
  removal, the handshake dispatchers (`DoHandShakeMsgType` in `src/internal.c`, `DoTls13HandShakeMsgType` in
  `src/tls13.c`), extension parsing in `src/tls.c` (key shares, PSK identities and binders, ALPN, SNI, ECH, cookies,
  early data), alerts and application data. DTLS adds fragment reassembly, epochs, connection IDs and the cookie
  exchange (`src/dtls.c`, `src/dtls13.c`); QUIC adds `src/quic.c`.
* Resumption input: session IDs, session tickets, PSK identities and binders, and whatever the application's external
  session cache callbacks return (`src/ssl_sess.c`).
* Peer certificates and revocation data: chains, OCSP responses and stapling, CRLs, and the AIA and CRL distribution
  point URLs that wolfIO fetches (`src/internal.c` `ProcessPeerCerts`, `src/ssl_certman.c`, `src/ocsp.c`,
  `src/crl.c`, `src/wolfio.c`, and the ASN.1 parser in `wolfcrypt/src/asn.c`).
* Data an application receives from others and hands to the parsing APIs: DER/BER/PEM certificates, keys, CRLs, CSRs,
  PKCS#7/CMS, PKCS#8, PKCS#12 and OCSP structures (`wolfcrypt/src/asn.c`, `pkcs7.c`, `pkcs12.c`, `src/x509.c`,
  `src/pk.c`, `src/ssl_load.c`).
* Public keys, signatures, ciphertexts and KEM encapsulations from a peer, passed to the `wc_*` APIs (RSA, ECC, DH,
  Curve25519/448, Ed25519/448, ML-KEM, ML-DSA, LMS, XMSS, SLH-DSA, ...).
* The OpenSSL compatibility layer (`src/ssl.c` and the `src/ssl_*.c` files it includes, `src/pk.c`, `src/x509*.c`,
  `wolfcrypt/src/evp.c`), which receives lengths, strings and objects that applications such as nginx, curl,
  OpenVPN, stunnel, HAProxy and OpenSSH often take from remote parties (BIO, EVP, d2i/i2d, X509 and ASN1 printing).
* Passive traffic fed to the sniffer (`src/sniffer.c`): every captured byte is attacker-controlled.
* State restored from outside the process: `wolfSSL_restore_session_cache`, `wolfSSL_memrestore_session_cache`,
  `wolfSSL_CTX_restore_cert_cache` and `wolfSSL_CTX_memrestore_cert_cache`.

The attacker is one of:

* a remote, unauthenticated TLS, DTLS or QUIC peer, in either the client or the server role;
* an on-path network attacker who can inject, drop, reorder and replay records;
* a peer or certificate issuer who controls certificate, CRL and OCSP contents, including the URLs in them;
* a party who supplies keys, signatures, ciphertexts or ASN.1 structures that an application passes to wolfCrypt;
* an attacker who measures timing or cache behaviour, over the network or from software on the same device (which
  matters most on embedded targets);
* an attacker who can predict or influence a platform's entropy source;
* a local user who can write the cache files or certificate directories the application loads.

Trusted. The attacker does not control these, so a defect that needs attacker control of one is API hardening, unless
a second, named defect hands that control over:

* The build: configure options, `user_settings.h` and integrator-defined macros. A defect that exists only in a
  supported build configuration is still in scope: name the configuration (see below).
* The application's own private keys, certificates and parameters, loaded with the `wolfSSL_CTX_use_*` and
  `wolfSSL_use_*` calls, or imported through `wc_*` functions when they are the application's own.
* Settings the application chooses: cipher suite lists, protocol version limits, verify mode, depth and callback,
  timeouts, and algorithm and key-size choices when it creates a key or context.
* The size the application declares for an output buffer it passes in: declaring more than it allocated breaks the
  API contract. Input lengths are not trusted.
* Callbacks and hooks the application registers (I/O, allocator, logging, verify, crypto callbacks, heap hints, device
  IDs) and their context pointers. The bytes an I/O callback delivers are network input, the session cache callbacks
  are an entry point above, and entropy sources are not trusted.

## What must be protected

* Private and symmetric keys, handshake and session secrets (pre-master and master secrets, TLS 1.3 traffic secrets,
  PSKs, session tickets and their keys), and the DRBG state and its seed. Secret intermediates must be wiped with
  `ForceZero` after use.
* Peer-authentication state: the verified peer certificate chain, hostname and IP checks, revocation decisions, and
  the verify policy in force for the connection.
* Integrity and confidentiality of the record layer, including the uniqueness of AEAD nonces on every path
  (synchronous, threaded and asynchronous record encryption).
* Memory safety of the process that links wolfSSL.
* Availability of TLS and DTLS endpoints against protocol-level attacks.

## Components that matter most / least

Most important:

* the TLS 1.3 and TLS 1.2 state machines and record layer (`src/internal.c`, `src/tls13.c`, `src/tls.c`,
  `src/keys.c`), then DTLS 1.2/1.3 and QUIC;
* certificate parsing and chain verification (`wolfcrypt/src/asn.c`, `src/ssl_certman.c`, `src/x509.c`,
  `src/x509_str.c`), OCSP and CRL;
* the wolfCrypt code the handshake reaches: RSA (including PKCS#1 v1.5 padding checks), ECC, DH, Curve25519,
  Ed25519, ML-KEM, ML-DSA, AES-GCM, ChaCha20-Poly1305, the hashes, HMAC/HKDF and the TLS PRF, the DRBG
  (`wolfcrypt/src/random.c`), and SP math (`wolfcrypt/src/sp_int.c`, `sp_c32.c`, `sp_c64.c`);
* PKCS#7/CMS and PKCS#12 parsing;
* the OpenSSL compatibility layer.

Lower importance, still in scope:

* the sniffer, DTLS multicast, ECH, early data, the external session cache and the persisted caches;
* rarely used algorithms (ARIA, Camellia, SM2/SM3/SM4, SRP, ...) and the post-quantum signatures other than ML-DSA
  (SLH-DSA, LMS, XMSS). Features that need `--enable-experimental` (Falcon, FrodoKEM, dual-algorithm certificates,
  ...) are not in these builds and matter least;
* the hardware and platform ports in `wolfcrypt/src/port/`, and the kernel-module glue in `linuxkm/` and `bsdkm/`.
  They cannot be run in this image: report only what a code trace makes clear, and treat their reach as narrow;
* the architecture-specific SP files (`sp_x86_64.c`, `sp_arm32.c`, `sp_arm64.c`, `sp_armthumb.c`, `sp_cortexm.c`,
  `sp_dsp32.c`, `sp_sm2_*.c`) and much of the assembly (`wolfcrypt/src/*_asm.S` and `*.asm`, and the `*-asm.S` and
  `*-asm_c.c` files under `wolfcrypt/src/port/`). These are mostly generated by wolfSSL's own generator scripts,
  which are not in this repository, so describe a defect there precisely; a patch to the generated file is welcome
  as an illustration of the fix;
* the language bindings in `wrapper/`.

Out of scope (non-library code, per the policy):

* `examples/`, `tests/`, `testsuite/`, `wolfcrypt/test/`, `wolfcrypt/benchmark/`, `scripts/`, `IDE/`, `Docker/`,
  `doc/`, and build tooling;
* `certs/`: test certificates and keys, weak or expired on purpose;
* the attack classes the policy excludes: physical access, power and EM side channels, and fault injection (including
  missing verify-after-sign style countermeasures). Timing and cache side channels that software can observe, on the
  same device or over the network, remain in scope.

## Build configurations in scope besides the default build

Many real defects live only under a build option. Each of these is in scope: review the code it adds, removes or
changes as its own variant, and name the macro in any finding that only it exposes.

* `WOLFSSL_STATIC_MEMORY` (`--enable-staticmemory`): static pools, where a block must be freed with the heap hint it
  was allocated from;
* `WOLFSSL_SMALL_STACK` (`--enable-smallstack`): heap instead of stack buffers, with different error paths;
* `WOLFSSL_SNIFFER` (`--enable-sniffer`);
* `WOLFSSL_ASYNC_CRYPT` (`--enable-asynccrypt-sw` builds the software simulator) and `WOLFSSL_THREADED_CRYPT`, whose
  record paths must build the same nonce, sequence number and explicit IV as the synchronous path;
* `WOLFSSL_DTLS13`, `WOLFSSL_DTLS_CID`, `WOLFSSL_MULTICAST`, `HAVE_ECH`, `WOLFSSL_EARLY_DATA`, `HAVE_SESSION_TICKET`,
  `HAVE_EXT_CACHE` and `PERSIST_SESSION_CACHE`;
* `OPENSSL_EXTRA` and `OPENSSL_ALL` (`--enable-opensslextra`, `--enable-opensslall`);
* the math back ends: SP math with and without assembly (`--disable-asm`, `--enable-sp-math`, small-limb
  `SP_WORD_SIZE` 8, 16 or 32), and `USE_INTEGER_HEAP_MATH` (`--enable-heapmath`), where fixed buffers such as
  `ENCRYPT_LEN` can be smaller than runtime-configurable key-size maxima;
* `WC_NO_CACHE_RESISTANT`, `CURVE25519_SMALL` and `CURVE448_SMALL`;
* `WOLFSSL_NO_ASM`, `WOLF_C89` (where `XSNPRINTF` falls back to `sprintf`) and non-GNU compilers, where barrier and
  `ForceZero` fallbacks differ;
* each platform arm of `wc_GenerateSeed`, and `CUSTOM_RAND_GENERATE_SEED`.

## How to exercise it

The image holds two builds of the same commit, both made with clang, AddressSanitizer and
UndefinedBehaviorSanitizer. `$SAN_FLAGS` holds the compiler flags. UBSan's `-fsanitize=function` is off because
wolfSSL deliberately calls free functions through `void (*)(void*)` casts.

* `/src` is an in-tree debug build, `./configure --enable-all --enable-sniffer --enable-debug --enable-mldsa
  --enable-slhdsa --enable-lms --enable-xmss` (`--enable-all` leaves those four signature schemes out), installed to
  `/usr/local`. After a change, rebuild with `cd /src && make -j2 && make install && ldconfig`. Because it defines
  `DEBUG_WOLFSSL`, the example programs log every step to stderr.
* `/opt/wolfssl-default/src` is the default `./configure` build, installed to `/opt/wolfssl-default`. Use it to
  check whether a defect is reachable in a default build, which the policy weighs heavily. It has ML-KEM but none of
  the post-quantum signatures. A change made in `/src` must be applied here too before it shows up in this build.

Run things from `/src`, because the examples and tests load `./certs/`:

* Server and client: `./examples/server/server -i -x -v d -d -p 11111` keeps accepting connections, keeps going after
  errors, accepts any protocol version up to TLS 1.3 and does not ask for a client certificate. Connect with
  `./examples/client/client -p 11111 -v 4` (TLS 1.3) or `-v 3` (TLS 1.2); without `-v`, both programs default to
  TLS 1.2. `-u` selects DTLS on both sides, and `-?` lists every option.
* Crafted records and handshakes from the network: tlslite-ng and tlsfuzzer are installed in `/opt/tlsfuzzer`. For
  example `tlsfuzzer-python /opt/tlsfuzzer/tlsfuzzer/scripts/test-tls13-conversation.py -h localhost -p 11111`
  against the server above. The scripts in that directory are a library of malformed-message tests to adapt. Some of
  them expect behaviour that wolfSSL does not share, so a failing script is a lead, not a finding.
* In-memory handshakes in C: `tests/utils.c` has the `test_memio_*` helpers (`test_memio_setup`,
  `test_memio_do_handshake`, `test_memio_inject_message`, `test_memio_modify_message_len`, ...) that `tests/api/` uses
  to run a client and a server in one process and alter the records between them. This is the quickest way to write
  a reproducer for a handshake bug, and the form we want for regression tests.
* Unit tests: `./tests/unit.test --api -<test_name>` runs one API test, `-~<substring>` runs those whose names
  contain a string, `--list` and `--groups` list them, and `--group <name>` runs a group. The whole
  `./tests/unit.test` takes a few minutes here. The API tests are in `tests/api.c` and `tests/api/test_*.c`.
* `./wolfcrypt/test/testwolfcrypt` is the wolfCrypt self-test, and `./testsuite/testsuite.test` a TLS smoke test.
* Sniffer: `./sslSniffer/sslSnifferTest/snifftest -pcap <file> -key <key> -server <ip> -port <port>`. Sample
  captures are `scripts/sniffer-*.pcap`, and `scripts/sniffer-testsuite.test` shows the arguments for each.
* A standalone reproducer against the public API: include `<wolfssl/options.h>` before any other wolfSSL header, and
  build it with the sanitizers too, either `clang $SAN_FLAGS poc.c -o poc -lwolfssl` (the `--enable-all` build) or
  `clang $SAN_FLAGS -I/opt/wolfssl-default/include poc.c -o poc -L/opt/wolfssl-default/lib
  -Wl,-rpath,/opt/wolfssl-default/lib -lwolfssl` (the default build).
* Another configuration, offline: `git -C /src worktree add --detach /tmp/variant && cd /tmp/variant &&
  ./autogen.sh && ./configure <options> CFLAGS="$SAN_FLAGS" LDFLAGS="-fsanitize=address,undefined" && make -j2`.
  `./configure --help` lists the options, and `configure.ac` shows the macros each one defines. Add a macro that
  has no option with `CFLAGS="$SAN_FLAGS -DMACRO"`.
* ASan runs with `detect_leaks=0`. Set `ASAN_OPTIONS=detect_leaks=1` when a leak is the point (see below).

## How we rate severity

Use the policy's four levels: Critical, High, Medium and Low. wolfSSL makes the final call, so give the facts that
drive it.

Start from the consequence on a system that has the affected code:

* Critical: code execution, disclosure of secrets (keys, session secrets, plaintext, process memory), authentication
  bypass (a forged signature or MAC accepted, a certificate chain accepted without correct verification, a hostname or
  revocation check that can be skipped, a downgrade), or memory corruption whose target or contents the attacker
  influences.
* High: a crash or hang of a TLS or DTLS endpoint that a peer causes through protocol processing, or data corruption
  across a security boundary. Memory corruption the attacker cannot steer is rated by what it demonstrably causes,
  usually this.
* Medium: limited disclosure, or weakened security (for example a timing difference that leaks a little per query).
* Low: minor consequences.

Then lower it:

* by one level when triggering it needs more than routine use or direct attacker input (extra access, user
  interaction, an established race), and by two when it needs several unusual runtime conditions;
* by one level when the code is only built with an optional feature, or only on a particular architecture or back
  end, and by two when it needs a specific chip, platform port, or an unusual combination of options. Widely enabled
  options (the OpenSSL compatibility layer, session tickets, OCSP stapling, DTLS) count as optional features, so say
  which well-known integrations turn them on. Count a build restriction here once, not again as trigger difficulty;
* never below Low for a real defect.

A finding that needs a second, hypothetical defect to give the attacker control of a trusted input is Low at most;
name that prerequisite. Where a fact cannot be established, say so instead of guessing.

The policy does not treat these as vulnerabilities: misuse of an API against its documentation, attacks that need
capabilities that already grant the outcome, availability impact outside protocol-facing paths (for example a crash
on a file or a parameter the application itself chose), and anything without a working reproducer. Report them as
hardening at Low, or not at all.

## Anything to leave alone

* Memory leaks, unless a remote peer can grow memory without bound.
* NULL dereferences and other failures reachable only by passing a public API arguments its documentation forbids.
* The example programs, the tests and the test certificates (see out of scope above).
* Weak or legacy algorithms and protocol versions that are off by default (SSLv3, TLS 1.0/1.1, MD5, DES, RC4,
  static RSA and anonymous cipher suites) when the finding is only their documented weakness.
* Function-pointer type casts that UBSan's `-fsanitize=function` would flag.
* Fault-injection hardening and physical side channels.

## How we would like reports and patches to look

Reports are triaged against `SECURITY-REPORT-TEMPLATE.md`, so please cover what it asks for:

* the build configuration: whether the defect is reachable in a default `./configure` build and, if not, every option
  and macro it needs;
* the file, function and line numbers of the defect, its class, and two to four sentences on what goes wrong;
* the integration that routes attacker bytes there (the TLS/DTLS stack, peer certificate validation, OCSP/CRL, the
  OpenSSL compatibility layer as a named application uses it, PKCS#7/CMS, PKCS#12, ...), and a byte-flow trace from
  the public API to the defect with a file:line for each step;
* the attacker position, the prerequisites, and what the attacker can do afterwards that they could not before;
* a working reproducer (a C program against the public API, a `tests/api` test using the memio helpers, a
  tlsfuzzer script, or an input file) with exact build and run commands and the sanitizer output;
* whether the API use that triggers it is documented and supported;
* any recent commits in `git log` that touch the same function.

Patches should be against master and follow the existing style: C90 (declarations at the start of a block, `/* */`
comments), 4-space indentation, plain ASCII, the X* wrappers (`XMEMCPY`, `XMALLOC`/`XFREE` with the heap hint,
`XSTRLEN`, ...), `ForceZero` for secrets, `ConstantCompare` when comparing secret data, negative wolfSSL error codes
(`BUFFER_E`, `BAD_FUNC_ARG`, `ASN_PARSE_E`, ...), and every `#ifdef` variant still compiling. Include a regression
test in `tests/api/` (or `wolfcrypt/test/test.c` for a wolfCrypt-only defect). Security fixes go to the current and
the previous stable release, so name the affected `vX.Y.Z-stable` tags when you can tell.
