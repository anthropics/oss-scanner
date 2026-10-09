# Botan: threat model and severity guide for the scanner

Botan is a C++20 cryptography and TLS library (BSD-2-Clause, https://botan.randombit.net), used in open source
projects such as KeepassXC, Mozilla Thunderbird, strongSwan, and softHSM. It is certified by Germany's BSI
(Federal Office for Information Security) for use in security sensitive applications.

This file condenses the project's own documents for a scan. The originals are in the image and are
worth reading before starting:

- `/src/doc/threat_model.rst`: the side-channel threat model (summarised below)
- `/src/doc/side_channels.rst`: which countermeasures exist, per algorithm, and which code is knowingly not constant-time
- `/src/doc/goals.rst`: project goals ("the library should never crash, or invoke undefined behavior, regardless of
  circumstances")
- `/src/doc/security.rst`: every past advisory, with the reasoning behind its severity. This is the best calibration
  data there is: before rating a finding, look for the closest precedent there.
- `/src/news.rst`: what changed in the current release cycle. New code has had the least review.

## What Botan does and where untrusted input enters

Botan is a library. The application decides what reaches it, so "untrusted" means: data a remote party or a file from
an untrusted source can supply through a public API. In practice these are the entry points, roughly in order of
exposure:

- **TLS and DTLS, client and server** (`src/lib/tls`, 1.2 and 1.3): records, handshake messages, extensions, session
  tickets, peer certificates, alerts, and the timing of all of these. The attacker is the peer or a network MITM.
- **X.509** (`src/lib/x509`): certificate, CRL and OCSP response parsing; path validation (`x509_path_validate`);
  name constraints; hostname and IP matching; trust-anchor selection; the OCSP HTTP client. PKCS #10 requests and
  PKCS #12 files (`src/lib/pkcs12`).
- **ASN.1/BER/DER** (`src/lib/asn1`): under everything above and under every key format. Also the PEM and
  base64/base32/base58/hex codecs (`src/lib/codec`, `src/lib/pubkey/pem`).
- **Public key material from others** (`src/lib/pubkey`, `src/lib/math`): SubjectPublicKeyInfo and PKCS #8 (plain and
  PBES2-encrypted, where the KDF parameters, including scrypt and Argon2 work factors, come from the file); ECC point
  and explicit-curve decoding; RSA/DSA/DH parameter handling; the post-quantum schemes (ML-KEM, ML-DSA, SLH-DSA,
  FrodoKEM, Classic McEliece, HSS/LMS, XMSS) and their key, ciphertext and signature decoders; BLS12-381 (new).
- **Operations on attacker-chosen inputs with our secret key**: RSA/SM2/ECIES/ElGamal/DLIES decryption, KEM
  decapsulation, ECDH/X25519/X448 with a peer's public value, signature verification with attacker keys and
  signatures, AEAD decryption with attacker ciphertext and tags.
- **RNG** (`src/lib/rng`, `src/lib/entropy`): `AutoSeeded_RNG`, `HMAC_DRBG`, `ChaCha_RNG`, `System_RNG`,
  `Processor_RNG`, entropy sources and reseeding logic. Nothing here parses attacker data, but predictability is the
  worst outcome the library can have.
- **Smaller parsers**: URIs, IPv4 addresses and subnets, DNS names and wildcards, HTTP responses (`src/lib/utils`,
  `src/lib/x509`), Roughtime (`src/lib/misc/roughtime`), SRP6, SPAKE2+, PSK databases, algorithm-specifier strings
  (`SCAN_Name`), the zfec forward error correction codec, the `compression` wrappers around zlib/bzip2/lzma.
- **The C FFI** (`src/lib/ffi`, header `botan/ffi.h`) and the **Python binding** (`src/python/botan3.py`). Pointer and
  length arguments are the caller's promise, but everything the FFI computes from them (integer conversions, NUL
  handling, object lifetimes, error codes) is ours.

The public API is the set of headers installed as `botan/*.h` (every `src/lib/**/*.h` that is not included as
`botan/internal/...`), plus `botan/ffi.h` and the Python module. Internal headers (`#include <botan/internal/...>`) are
not API: their preconditions are enforced by their callers, and calling one with arguments that violate its
documented or asserted preconditions is not a bug. The test suite links against them through `BOTAN_TEST_API`, so a
function being reachable from `botan-test` does not make it public.

## What matters most, and what is out of scope

Most important, in order: TLS, X.509 path validation and OCSP, the ASN.1 decoder and every key/certificate decoder
built on it, public-key decryption and verification paths, the RNGs, and the constant-time property of anything that
touches secret keys or plaintext. Memory safety everywhere in `src/lib`.

In scope but a lower priority:

- The `botan` command-line tool (`src/cli`). Its arguments and the files it is told to read are the operator's and are
  trusted. What it receives from the network (`tls_client`, `tls_server`, `tls_proxy`, `tls_http_server`,
  `ocsp_check`, `http_get`, `roughtime`) is not: an advisory in 2026 covered `ocsp_check` accepting unauthenticated
  responses.
- Experimental modules (`--enable-experimental-features`, for example `ffi_tls`): built here, not built by default,
  not covered by SemVer. Bugs in them are still wanted; say in the report that the module is experimental and off
  by default, so the reader can weigh exposure.
- Deprecated algorithms (listed by `configure.py` and in `doc/deprecated.rst`): memory safety still matters, their
  cryptographic weakness does not (see below).

Out of scope, or not what we mean by security:

- The test suite (`src/tests`), fuzzers (`src/fuzzer`), build system (`configure.py`, `src/build-data`, `src/scripts`)
  and examples assume their inputs are public and trusted. A buffer overflow in a test is just a bug.
- zlib, bzip2, lzma, sqlite3 and boost are system libraries. Our wrappers around them are in scope; they are not. A
  decompression bomb is not a finding; bounding decompressed output is the application's job.
- Hardware and provider backends not built in this image: PKCS #11 (`src/lib/prov/pkcs11`, built but with no module
  to talk to), TPM 1.2/2.0, CommonCrypto.
- Speculative execution attacks (Spectre and family), ALU-contention side channels, power analysis, EM side channels
  and fault attacks. These need hardware support and a system-wide view; see `doc/threat_model.rst`.

## The image: two builds, and how to exercise them

The checkout is `/src`; `git -C /src rev-parse HEAD` names the commit under scan. Everything runs offline.

`/src/build-asan` is clang with ASan, UBSan (`-fno-sanitize-recover`) and libstdc++ debug iterators, `-O1 -g`,
`--with-debug-asserts` and `--unsafe-terminate-on-asserts`:

- `./build-asan/botan-test` runs the suite (`--list-tests` lists suites, `./build-asan/botan-test x509_path_rsa_pss
  tls_messages` runs some; `--run-long-tests` and `--run-memory-intensive-tests` add the slow ones; run it from
  `/src` so it finds `src/tests/data`).
- `./build-asan/botan` is the CLI (`botan help`).
- `./build-asan/build/fuzzer/<name>` are the harnesses from `src/fuzzer/<name>.cpp`, one per attack surface
  (`asn1`, `cert`, `crl`, `ocsp`, `pkcs8`, `x509_dn`, `x509_path`, `tls_client`, `tls_server`,
  `tls_client_hello`, `tls_13_handshake_layer`, `oaep`, `pkcs1`, `mode_padding`, `os2ecp`, `ec_scalar`, `ecc_*`,
  `mp_*`, `pow_mod`, `invert`, `uri`, `ipv4`, ...; `ls build-asan/build/fuzzer` for the full list). Each reads the files named on its command line
  (or stdin when given none) and feeds them to `LLVMFuzzerTestOneInput`, so `./build-asan/build/fuzzer/cert
  some.der` is a complete reproducer. `/src/fuzzer_corpus/<name>/` holds real seed corpora for the parsers (`asn1`,
  `cert`, `crl`, `ocsp`, `os2ecp`, `pkcs1`, `pkcs8`, `tls_client`, `tls_server`, `tls_13_handshake_layer`, `x509_dn`,
  `x509_path`); the arithmetic harnesses have none. `python3 src/scripts/test_fuzzers.py fuzzer_corpus
  build-asan/build/fuzzer` runs every harness over its corpus, or over random inputs where there is none
  (`--one-at-a-time --gdb` gives backtraces).
- A failed `BOTAN_ASSERT` aborts in this tree with an "Assertion ... failed" message. The same input makes a normal
  build throw `Botan::Internal_Error` instead. Rate it as described under "It's just a bug" below, not as a crash.
- `locking_allocator` is disabled in both trees so that `secure_vector` memory comes from malloc and ASan sees each
  allocation. Production builds may serve it from a single mlock()ed pool, which changes nothing about whether an
  overflow is a bug.

`/src/build-dbg` is clang `-O3 -g -fno-omit-frame-pointer`, no sanitizers, built with `--with-valgrind` and installed
to `/usr/local` (`libbotan-3.so`, headers in `/usr/local/include/botan-3`, `botan` on the path):

- Realistic performance for quadratic-behaviour and timing investigations; `./build-dbg/botan speed` and
  `./build-dbg/botan timing_test` exist.
- Side channels: secrets are marked with `CT::poison` and valgrind's uninitialised-value tracking reports any
  conditional jump or memory index that depends on them. `python3 src/scripts/run_tests_under_valgrind.py
  --verbose --test-binary=build-dbg/botan-test <suite...>` runs test suites this way (a few seconds per small suite,
  and silent without `--verbose`);
  `python3 src/ct_selftest/ct_selftest.py --build-config-path=build-dbg/build/build_config.json
  build-dbg/botan_ct_selftest` checks that the mechanism itself works in this build. A report of "Conditional jump
  or move depends on uninitialised value(s)" inside a poisoned region is a real side-channel finding; one in a test
  harness or on public data is not.
- Python: `PYTHONPATH=/src/src/python python3 -c 'import botan3; print(botan3.version_string())'`;
  `python3 src/scripts/test_python.py` runs the binding's tests from `/src`.
- CLI tests: `python3 src/scripts/test_cli.py build-dbg/botan` and `python3 src/scripts/test_cli_crypt.py
  build-dbg/botan`. `test_cli.py` starts `tls_server`/`tls_proxy` on localhost, which works offline.
- Writing your own program: `clang++ -std=c++20 -g repro.cpp $(botan config cflags) $(botan config libs)`, or link
  against `build-asan/libbotan-3.a` with the same sanitizer flags for an instrumented reproducer.

Not available offline: the BoGo TLS interoperability suite (needs Go and BoringSSL), the online tests
(`--run-online-tests`), Wycheproof and Limbo vectors beyond those already in `src/tests/data`.

Where novel bugs are most likely: the byte-level parsers (`asn1`, `cert`, `crl`, TLS messages) have been
fuzzed continuously in OSS-Fuzz for years, so a shallow crash there is unlikely. Better odds lie in logic
(what path validation accepts, how the TLS state machine and policy respond to unusual message sequences,
name-constraint and hostname decisions), arithmetic edge cases (`src/lib/math`, `pcurves`, `bls12_381`),
resource bounds on attacker-chosen parameters, side channels on new code, and whatever `news.rst` says landed
recently.

## How we rate severity

Adapted from the project's internal calibration rubric. All CVEs are Botan's unless stated; `doc/security.rst` has
the write-up of each.

### High or Critical

**Predictable RNG output.** Any bug that makes RNG output predictable, excluding an application that deliberately
configures an RNG with no entropy sources and a predictable seed. For a recent case see the 2026
`AutoSeeded_RNG::clear()` reseeding advisory in `doc/security.rst`.

**Memory writes in a context exposed to adversarial input, plausibly leading to code execution.** For example in the
TLS handshake, while parsing a public key or X.509 certificate, or while decrypting an RSA ciphertext. Examples:
CVE-2016-2196 (one-word overwrite in P-521 reduction), CVE-2016-2195 (heap overflow during ECC point decoding),
and the 2026 scrypt 32-bit heap overflow advisory.

**TLS protocol guarantee violations.** A core guarantee of the protocol fails: authentication bypass, downgrade, key
or plaintext exposure. Examples: CVE-2026-34582 (TLS 1.3 client authentication bypass), OpenSSL's CVE-2014-0224 (CCS
injection) as the kind of thing meant.

**X.509 or OCSP accepts something invalid, broadly.** An unprivileged attacker can forge more or less at will: a chain
for a name they do not control, or an OCSP response that makes a revoked certificate look good. Examples:
CVE-2026-34580 (trust anchor confusion), CVE-2026-32883 (OCSP response signature check omitted), CVE-2022-43705
(OCSP responder's embedded certificate not checked).

### Medium

**Arithmetic errors in public-key cryptography** that a remote party can trigger. Potentially High if information about
long-term secret key material leaks as a result.

**X.509 or OCSP accepts something invalid, with mitigating factors.** CVE-2018-9127 and CVE-2015-7826 accepted wildcard
certificates for names they should not have matched, but only within the issued wildcard domain. CVE-2024-39312: with
both permitted and excluded name-constraint subtrees present, only the permitted ones were checked; rare configuration,
and the permitted set already limited the damage.

**Side channels likely to be remotely exploitable that can leak long-lived keys or plaintext** (Bleichenbacher-style
oracles). Examples: CVE-2018-12435 and CVE-2016-2849 (ECDSA signing not constant-time, enough to expose the key),
CVE-2021-24115 (table-based base64 decoding, demonstrated key extraction from SGX), CVE-2015-7827 (PKCS #1 v1.5
decoding not constant-time). Variable time on entirely public data is not a bug, even inside a sensitive operation:
RSA decryption first checks that the ciphertext has the right length and is in range and throws if not, and that
early return depends only on the ciphertext and the public modulus.

**Read-only memory errors** that do not obviously disclose data. A Heartbleed-style bug that returns raw memory to the
attacker may be High depending on context. Examples: CVE-2018-9860 (over-read in TLS CBC decryption), CVE-2026-32877
(heap over-read during SM2 decryption) both of which crashed without disclosing information.

**Denial of service.** Quadratic behaviour, allocation of unbounded memory, arbitrarily large computation, an infinite
loop, a null dereference, or a crash that seems unlikely to lead to code execution. Not included: inefficiency that is
linear in the input (an unnecessary copy of N bytes is a cleanup, not a security issue). Examples: CVE-2026-44378
(quadratic CPU in BER decoding), CVE-2024-34702 (excessive name constraints), CVE-2024-34703 (oversized elliptic curve
parameters), CVE-2015-7825 (infinite loop in path validation), CVE-2015-5727 (excess allocation in BER decoder),
CVE-2015-5726 (null dereference in BER decoder), CVE-2016-2194 (infinite loop in modular square root).

### Low

**Policy enforcement failure.** The application asked for a policy and we did not enforce all of it. CVE-2016-2850: a
malicious TLS server could ignore client preferences and, for example, use a curve the client had not offered.

**Side channels with limited leakage**, because keys are ephemeral or the channel is narrow. CVE-2018-20187 leaked the
bit length of the scalar during ECC key generation (rare for ECDSA, ephemeral for ECDH, and the bit length gives only a
small speedup to Pollard rho). The 2020-03-24 advisory: CBC padding was not constant-time, leaking only the plaintext
length, with no obvious oracle. The mere existence of a documented side channel is not a bug: the baseline
implementations of some algorithms use table lookups and `doc/side_channels.rst` says so; a constant-time variant exists
where practical (hardware AES, SIMD) but not on every platform. Making a baseline implementation constant-time is
hardening, not a fix.

**Failure to zeroize, marginally.** Zeroization is a lost cause in a high-level language; values on the stack are not
our concern and adding zeroization calls is hygiene. The exception, as in the 2017-07-16 advisory, is code that
promises to zeroize and does not (a `secure_vector` that only cleared part of its buffer).

### "It's just a bug"

Report these, with Low severity or as a non-security bug, and do not dress them up:

- Any input or sequence of calls that makes a `BOTAN_ASSERT` fail. These express invariants that should already have
  been checked, so a failure is a bug, but the result in a normal build is a `Botan::Internal_Error` exception, not a
  crash (the ASan tree here aborts instead; see above). If the triggering input is one a remote peer can send and the
  consequence goes beyond the exception, say so and rate on the consequence.
- API misuse that the library fails to catch. Ideally a contract violation raises an error; when it does not, that is
  a bug, not a security issue. Recent examples: an unkeyed OFB cipher object could encrypt a short message
  (commit e657f7c11), GMAC would authenticate without a nonce having been set (commit 959c343ff8aaa).
- An outright incorrect computation, depending on context. SIV mode with a gap in the associated-data indices produced
  a ciphertext that disagreed with the standard but was still secure (commit 7cc17f5838f68).
- Incomplete validation of an input where accepting it is benign in practice, recent examples would be OCSP
  responses containing UTCTime where RFC 6960 requires GeneralizedTime (commit fd52f32b6ea), or NULL versus empty
  AlgorithmIdentifier parameters not always enforced as the specific RFC demands (commit b7dd7290a02).

### "It's not even a bug"

- The application violates an API contract in a way the library has no viable way to detect. The FFI takes pointers and
  lengths; an invalid pointer is the caller's problem.
- Exploiting the issue needs trusted access, and an attacker with that access could already do something worse.
  Example: Botan stops reading an OCSP response at the first `SingleResponse` matching the certificate, so a responder
  could put "good" before "revoked" for the same certificate. An attacker who can sign OCSP responses can simply sign a
  response that says "good". There is no patch against an attacker with those privileges, so this is not a finding.
- Parsing or processing an invalid input ends in an exception that reasonably describes why the input is invalid. That
  is the designed behaviour. Botan signals bad input by throwing (`Decoding_Error`, `Invalid_Argument`,
  `TLS::TLS_Exception`, ...); only uncaught `std::bad_alloc` from unbounded allocation, crashes, undefined behaviour,
  hangs, or wrong answers delivered without an exception are interesting.
- An algorithm being cryptographically broken. Botan implements several, some deprecated and some not. Their existence
  is not a security issue (documentation failing to warn that one is broken would be a bug).
- Variable-time behaviour whose inputs are entirely public (see Medium side channels above).

### Out of scope

Power analysis, EM, fault injection and speculative-execution attacks, as in `doc/threat_model.rst`.

## The side-channel model, in short

From `doc/threat_model.rst`: the attacker in scope can run code on the same CPU (via SMT) and observe cache, TLB and
branch-predictor state; in the stronger SGX setting they can single-step and measure every conditional jump and memory
access; the weaker LAN attacker only measures operation timing. Code touching secret data is meant to be constant-time
in the "program counter security model": no conditional jumps and no memory addresses derived from secrets. `CT::poison`
annotations plus valgrind verify this in CI on GCC and Clang, x86-64 and aarch64, at several optimisation levels, and
several algorithms also blind their inputs as defence in depth (ECDSA blinds the inversion of k, the scalar
multiplication and the recombination). A side channel is ultimately a property of a compiled binary on specific
hardware, so a finding should name the binary and the leaking instruction, not just the source.

## Things to leave alone

- 32-bit `size_t` overflows: this image is x86-64 only. We do care about them (the 2026 scrypt bug was 32-bit only);
  report them from analysis, say clearly that they were not reproduced here, and do not claim a 64-bit impact.
- Known and documented table-lookup implementations (`doc/side_channels.rst` lists them).
- Deprecated or weak algorithms being available.
- Zeroization hygiene, unless a documented promise to zeroize is broken.
- Style, naming, "missing const", unused includes, and other cleanups. The project runs clang-tidy and clang-format.
- `BOTAN_TEST_API` functions and `botan/internal/*.h` called with arguments their callers never pass.
- Compiler or sanitizer diagnostics in system headers (boost, libstdc++).

## How we would like reports and patches to look

- One finding per report, with the commit (`git -C /src rev-parse HEAD`), the build tree used, and the exact
  command. Prefer a reproducer that is one of: a fuzzer binary plus input file, a short C++ program against the public
  API (give the compile line), a `botan` CLI invocation, or a `botan-test` case. Include the sanitizer, valgrind or
  gdb output.
- State who controls the input and through which public API it arrives (a TLS peer? a certificate in a chain being
  validated? a file the application chose to decrypt?), what the attacker gains, and which rubric category above you
  are applying. A reachability argument matters more to us than a sanitizer trace: a report that is only "this
  internal function lacks a bounds check" without an input that reaches it will be set aside.
- Patches: a minimal diff against master in the surrounding style (`src/configs/clang-format`); validate arguments
  with `BOTAN_ARG_CHECK` or throw the existing exception types; no new dependencies; keep public signatures unless the
  fix requires otherwise; add a regression test under `src/tests` (test vectors go in `src/tests/data`, usually `.vec`
  files) or a corpus file for the relevant fuzzer. Note where a fix changes behaviour that an application might rely on.
- If a finding matches a precedent in `doc/security.rst`, cite it and rate alike. If it is a near-miss on something fixed
  in `news.rst` for the current cycle, say so: it may be a regression or an incomplete fix, which we treat as urgent.
