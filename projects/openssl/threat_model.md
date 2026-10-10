# Threat model

This follows the OpenSSL security policy:
https://openssl-library.org/policies/general/security-policy/

## What OpenSSL is and where untrusted input enters

OpenSSL is a TLS/DTLS/QUIC toolkit (libssl) and general-purpose cryptography
library (libcrypto), with algorithm implementations in providers (default,
base, legacy, FIPS). It is embedded in operating systems, servers, clients and
devices, so the library is what matters; the `openssl` command line tool much
less so.

Untrusted input enters through:

* network peers: TLS, DTLS and QUIC handshake and record processing, on both
  client and server side (`ssl/`, `ssl/quic/`, `ssl/record/`, `ssl/statem/`);
* parsing and verification of data an application receives from others:
  DER/BER (ASN.1), PEM, X.509 certificates, CRLs and chain verification,
  PKCS#7, CMS, S/MIME, PKCS#12, OCSP, CT/SCT, CMP, ECH configurations, and
  the OSSL_DECODER/OSSL_STORE paths that read them (`crypto/`);
* public keys, signatures, ciphertexts, KEM encapsulations and other
  algorithm inputs supplied by a peer (RSA, EC, DH, ML-KEM, ML-DSA, SLH-DSA,
  LMS, etc.);
* the HTTP client (`crypto/http/`) used for OCSP, CMP and CRL fetching.

Treated as trusted (a bug needing attacker control of these is not a
vulnerability unless it also crosses a privilege boundary): configuration files
and `OPENSSL_CONF`, other environment variables, provider and engine modules,
the application's own private keys and parameters, and API misuse that
contradicts the documentation in `doc/man3`.

## Components that matter most / least

Most important:

* libssl: TLS 1.2/1.3 and QUIC state machines and record layers, then DTLS;
* certificate parsing and chain verification (`crypto/x509/`, `crypto/asn1/`);
* the default and FIPS providers (`providers/`), including constant-time
  behaviour observable over a network;
* PKCS#7/CMS/S/MIME/PKCS#12 parsing and verification.

Lower importance, still in scope: the legacy provider, rarely used protocols
and algorithms (enabled in this build with `enable-*` options), CMP, the HTTP
client.

Out of scope:

* the `openssl` command line tool (`apps/`): rate it LOW at most;
* `test/`, `fuzz/` harness code itself, `demos/`, `util/`, `doc/`, `dev/`,
  `Configurations/`, and anything under `external/` or a git submodule;
* code that is only compiled with `FUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION`;
* the attack classes excluded by our policy: same physical system side
  channels, CPU/hardware flaws, physical fault injection, and physical
  observation side channels (power, EM). Timing side channels observable
  remotely over the network remain in scope.

## How to exercise it

* `/src` is an in-tree debug build with ASan and UBSan, configured with
  `enable-fips` and the optional algorithms and protocols. Run the CLI with
  `/src/util/wrap.pl /src/apps/openssl ...` (it sets up library and provider
  paths). Rebuild with `make -j2`.
* The test suite: `cd /src && make test TESTS=test_<name>`
  (`make list-tests` lists them; `make test V=1` for verbose output). Unit tests
  are C programs in `test/`, driven by Perl recipes in `test/recipes/`. The
  TLS proxy tests (`test/recipes/70-*`, `util/perl/TLSProxy`) are the easiest
  way to send a crafted handshake message.
* The fuzz harnesses in `fuzz/` (`asn1`, `x509`, `cms`, `pkcs12`, `cmp`,
  `server`, `client`, `quic-server`, `dtlsserver`, ...) are built as
  `/src/fuzz/<name>-test`, which run the harness on input files:
  `/src/fuzz/<name>-test <file>`. The corpora are in `/src/fuzz/corpora/<name>/`.
  The TLS/QUIC/DTLS client and server harnesses depend on a deterministic RNG
  that only fuzzing builds have, so for handshake bugs prefer a TLSProxy test
  or a C program.

## How we rate severity

Use the categories from the policy: CRITICAL, HIGH, MODERATE (= medium), LOW.

* CRITICAL: affects common configurations and is likely exploitable, e.g.
  significant disclosure of server memory, easy remote compromise of server
  private keys, or remote code execution likely in common situations.
* HIGH: like critical but less common configurations or less likely to be
  exploitable, e.g. memory corruption reachable by a remote peer or by
  untrusted certificate/message input without a demonstrated exploit.
* MODERATE: crashes in client applications, flaws in less commonly used
  protocols (such as DTLS), and local flaws. Remotely triggerable crashes or
  excessive resource use in a server are usually MODERATE or LOW depending
  on how common the configuration is.
* LOW: issues that only affect the `openssl` command line tool, or that need
  unlikely configurations or non-default options.

State which configurations and which public API calls are needed to reach the
bug, and whether default builds and default settings are affected; that drives
our rating more than the bug class does.

## Anything to leave alone

* memory leaks, unless an unauthenticated peer can grow memory without bound;
* bugs only reachable by passing invalid arguments that the documentation
  forbids (NULL where not allowed, wrong buffer sizes, etc.);
* deprecated low-level APIs used outside their documented contract;
* known weak algorithms or protocol versions that are disabled by default,
  when the "vulnerability" is just their documented weakness.

## How we would like reports and patches to look

* A reproducer as a small C program against the public API, a `make test`
  recipe, or an input file for one of the `fuzz/` harnesses; plus the exact
  commit, configure options and the sanitizer output.
* The affected `openssl-3.*`/`openssl-4.*` release branches if known, since
  we fix all supported versions.
* Minimal patches against `master` following `STYLE.md`, ideally with a
  regression test under `test/`.
