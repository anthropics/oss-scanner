# Threat Model

## What NSS is and where untrusted input enters

Network Security Services (NSS) is the TLS and PKI library used by Firefox and Thunderbird, and by other
applications through its public C API. It implements TLS and DTLS (1.0 through 1.3), X.509 certificate parsing
and path validation, OCSP and CRLs, PKCS #7 / CMS and S/MIME, PKCS #12, PKCS #5 and PKCS #8 key handling, and a
PKCS #11 cryptographic module (softoken) built on the freebl primitives.

Untrusted data reaches NSS from:

* the remote (D)TLS peer, whether NSS is the client or the server: every handshake message, record, extension
  and certificate chain;
* certificates, CRLs and OCSP responses, however they arrive (TLS, files, the certificate store);
* PKCS #7 / CMS, S/MIME and PKCS #12 blobs supplied by the application (for example an email attachment or an
  imported key file);
* any DER / BER that reaches the ASN.1 decoders in `lib/util` (QuickDER and the generic SEC_ASN1 decoder).

The application calling NSS is trusted; the data it passes in is not.

## Components that matter most and least

Most important:

* `lib/ssl` (TLS and DTLS state machines, record layer, extensions, ECH), `lib/freebl` (cryptographic
  primitives, including the constant-time code), `lib/softoken` and `lib/pk11wrap` (the PKCS #11 module and the
  wrapper everything else goes through);
* `lib/util` (ASN.1 decoders, SECItem handling), `lib/certdb`, `lib/certhigh` and `lib/mozpkix` (certificate
  parsing and path validation), `lib/cryptohi` (signature verification);
* `lib/pkcs12`, `lib/pkcs7`, `lib/smime` (parsers for application-supplied blobs).

Lower priority or out of scope:

* `cmd/` (command-line tools; useful for reproducing, not a security boundary), `gtests/`, `fuzz/`, `cpputil/`,
  `tests/` and the test certificates and private keys they contain, which are intentionally public;
* bundled third-party code: the copies of sqlite and zlib under `lib/`, and googletest under `gtests/`;
* `lib/dbm` (legacy database) and `lib/libpkix` (legacy path validation): both are disabled in this build and
  not used by Firefox;
* NSPR (at `/nspr`): in scope only where a bug is reachable through NSS with attacker-controlled data;
* code that is disabled by default and already known to be insecure, such as deprecated cipher suites.

FIPS mode is a non-default configuration (`./build.sh --enable-fips`; this image is built without it). Issues
that are reachable only in FIPS mode are in scope but typically lower severity than the same issue in the
default configuration.

## How to exercise it

* The build in this image is a debug build with AddressSanitizer and UndefinedBehaviorSanitizer
  (`./build.sh --asan --ubsan`, as NSS CI's `linux-x64-asan/debug` job), at `/dist/Debug`. Libraries are in
  `/dist/Debug/lib` (set `LD_LIBRARY_PATH` to run anything), tools and test binaries in `/dist/Debug/bin`.
  `ASAN_OPTIONS`, `UBSAN_OPTIONS`, `NSS_DISABLE_ARENA_FREE_LIST` and `NSS_DISABLE_UNLOAD` are set as in CI.
* Useful tools in `/dist/Debug/bin`: `tstclnt` and `selfserv` (TLS client and server), `certutil`, `pk12util`,
  `vfychain`, `p7verify`, `derdump`, `pp`.
* The gtest binaries (`ssl_gtest`, `pk11_gtest`, `der_gtest`, `smime_gtest`, `softoken_gtest`, ...) are the
  easiest place to add a reproducer. `ssl_gtest` needs its certificate database: `-d` pointing at the
  `ssl_gtests` directory the smoke test created under `/tests_results/security/localhost.*/`, or a fresh one from
  `tests/ssl_gtests/ssl_gtest_db.sh`. A single test can be run with `--gtest_filter`.
* The full test harness is `tests/all.sh`, driven by `NSS_TESTS` (suite names) and `NSS_CYCLES`; `HOST`,
  `DOMSUF` and `DIST` are already set. The image only ran `*/TlsConnectGeneric.Connect/*` from `ssl_gtests`.
* `fuzz/targets` holds libFuzzer targets (TLS client and server, ASN.1, QuickDER, certificate DN, PKCS #7,
  PKCS #8, PKCS #12, S/MIME, ECH, EC derivation). They are not built in this image. `./build.sh --fuzz` builds
  them from the sources already here, with no downloads; use a separate output directory
  (`./build.sh --dist=/dist-fuzz --fuzz`) because the fuzzing build changes the libraries, and `/dist` holds
  the sanitizer build.

## How we rate severity

### Critical or high

These are typically high severity and high priority. Memory corruption that an attacker controls and that may
lead to code execution is critical; so is a bypass of authentication or confidentiality of a TLS session.

* Memory safety or undefined behaviour issues.
* Cryptographic vulnerabilities: e.g. padding oracles, missing point or curve validation, nonce misuse,
  downgrade, key or algorithm confusion, and certificate-validation bypasses (chain building, signature
  verification, name constraints).
* Issues which can be triggered by a (D)TLS peer, whether client or server.
* Issues which compromise the security of a (D)TLS session, whether authentication or confidentiality.
* Issues arising from processing untrusted input (S/MIME, PKCS #12, PKCS #7 / CMS, certificates, OCSP, ...).
* Issues reachable with attacker-controlled data through the API surface an application like Firefox or
  Thunderbird uses.
* Asserts which correspond to a memory or correctness safety invariant being broken.
* Race conditions which can be triggered remotely.

### Low

These should still be reported, but are low priority and typically low severity:

* Denial of service, timeouts, and operations which should succeed but instead fail safely. A clean crash
  (NULL dereference, abort) without memory corruption is a denial of service, not a memory-safety issue.
* Issues which require a malicious PKCS #11 token to be loaded into NSS.
* Issues which require a malicious application calling into NSS, or API misuse.
* Issues which cannot be reached from the public interface of NSS.
* Issues in code which is disabled by default and already known to be insecure (e.g. deprecated cipher suites).
* Issues reachable only in FIPS mode (see above).
* Issues which require unlikely user interactions.
* Race conditions which cannot be triggered in practical situations.
* Cryptographic side channels (e.g. timing) in freebl or the TLS layer. (NSS uses ephemeral keys)

### Notes on sanitizer output

This build uses UBSan with `undefined,local-bounds`. A UBSan report (for example signed overflow or a misaligned
load) in code with no demonstrated security consequence is low; one on an attacker-controlled path, or that
ASan confirms as an out-of-bounds access, is rated as a memory-safety issue above.

## How we would like reports and patches to look

* A reproducer, ideally as a gtest case (for `ssl_gtest` or the relevant `*_gtest`) or as a `tstclnt` /
  `selfserv` / `certutil` invocation against the sanitizer build, with the sanitizer report attached.
* A patch against the default branch of https://github.com/mozilla/nss, formatted with `./mach clang-format`.
