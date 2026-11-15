# curl and libcurl threat model

## Scope and trust boundaries

Scan both libcurl (`lib/`, `include/curl/`) and the curl command line tool
(`src/`). curl is a transfer client, not a general-purpose network sandbox.
Applications choose URLs, protocols, credentials, callbacks and security
options; remote endpoints can be malicious even when those choices are valid.

Untrusted inputs include server and proxy responses, redirects, protocol
framing, compressed bodies, authentication challenges, DNS answers, TLS peer
data, cookies and other persisted state. Track what an attacker can actually
control and distinguish that from choices made by the application or operator.

Read the checkout's [known risks](https://github.com/curl/curl/blob/master/docs/KNOWN_RISKS.md)
and [libcurl security guidance](https://github.com/curl/curl/blob/master/docs/libcurl/libcurl-security.md)
before classifying behavior. Their local copies are `docs/KNOWN_RISKS.md` and
`docs/libcurl/libcurl-security.md`; consult the relevant option documentation
for the exact API contract.

Prioritize:

- Memory safety and integer handling in parsers, encoders, buffers, upload and
  download accounting, decompression, and protocol state transitions.
- Authentication and confidentiality boundaries: TLS and hostname verification,
  proxy authentication, credentials across redirects or reused connections,
  cookies, HSTS, Alt-Svc, and connection, session or DNS cache isolation.
- HTTP/1, HTTP/2 and HTTP/3 framing, multiplexing, stream cancellation,
  connection reuse, partial reads and writes, retry paths, and teardown.
- URL parsing and enforcement of explicitly selected protocol, redirect,
  address and transfer restrictions. Exercise non-HTTP protocols too.
- CLI processing of server-supplied filenames, output paths and transfer
  metadata within the documented behavior of the selected options.

## Intended behavior and application responsibilities

Arbitrary URLs can intentionally access local files, private hosts and
different protocols. Redirects and DNS can change the destination. These
capabilities are not by themselves curl SSRF vulnerabilities. Establish a
violation of an actual curl guarantee or configured safeguard, rather than an
application's missing URL or address validation. Different browser and curl
URL parsing rules alone do not establish such a violation.

Similarly, explicit insecure TLS settings, plaintext protocols, unrestricted
authentication forwarding, arbitrary custom headers, and verbose traces can
expose data as documented. Application-controlled CRLF in options that send
bytes as supplied is not automatically an injection vulnerability. Distinguish
these choices from a remote peer defeating protections that remain enabled.
Respect documented handle ownership, callback lifetimes and thread-safety
requirements when constructing API reproducers.

A failed transfer, rejected response or nonzero `CURLcode` is a valid outcome.
Do not assert that arbitrary input must complete successfully. Investigate
memory errors, forbidden side effects and security-boundary violations across
both success and failure paths, including cleanup.

## curl policy and severity

Follow the [curl vulnerability policy](https://curl.se/dev/vuln-disclosure.html),
also in `docs/VULN-DISCLOSURE-POLICY.md`. Judge impact and exploitability with
configuration, privileges, platform and protocol stated; sanitizer findings
alone do not determine severity. Critical requires easy unauthenticated remote
system compromise without user interaction in a common configuration. Prefer
the latest release plus master: unreleased-only defects are development bugs;
low/medium issues confined to releases over three years old are excluded.
API misuse is generally excluded, while ambiguous documentation merits review.
Exclude flaws confined to test infrastructure, debug-only code and
off-by-default experimental features; instrumented builds still exercise
production code. Small leaks, endless transfers, timeout-bounded busy loops
and server-triggered crash-only defects generally do not qualify. Large leaks,
sensitive-data exposure, defeated safeguards or other special circumstances
require assessment. Local attackers face a higher bar. Prove practical
reachability; synthetic lengths without feasible input are insufficient.

## Build layout and exercising the code

The Dockerfile prepares two CMake Debug builds with AddressSanitizer and
UndefinedBehaviorSanitizer, debug information and frame pointers:

- `/src/build/openssl`: OpenSSL TLS and the threaded DNS resolver.
- `/src/build/gnutls`: GnuTLS TLS, c-ares DNS, and HTTP/3 support.

Each build leaves its curl executable at `src/curl`, its shared and static
libcurl in `lib/`, its generated configuration at `lib/curl_config.h`, and test
executables at `tests/libtest/libtests`, `tests/unit/units` and
`tests/tunit/tunits`. Check each binary's
`--version` output and CMake cache to establish the actual available protocols,
features and dependency versions. These Linux builds do not validate other
platforms or every TLS backend.

The test corpus is `/src/tests/data`; libcurl API tests and internal unit tests
are in `/src/tests/`. Use the CMake targets so `tests/runtests.pl` receives the
correct build directory and binary paths. For example:

```sh
/src/build/openssl/src/curl --version
/src/build/gnutls/src/curl --version

# Run selected tests against each build; substitute relevant test numbers.
TFLAGS='-n -j2 1 2' cmake --build /src/build/openssl --target tests
TFLAGS='-n -j2 1 2' cmake --build /src/build/gnutls --target tests

# Run the available regression suite without Valgrind (sanitizers are enabled).
TFLAGS='-n -j2' cmake --build /src/build/openssl --target tests
TFLAGS='-n -j2' cmake --build /src/build/gnutls --target tests
```

Read `docs/runtests.md` and `docs/INSTALL-CMAKE.md` for test selection and build
targets. The scanner has no external network; use loopback peers and fixtures.
Test servers are attack simulators, not security targets. A skipped test does
not establish coverage of its protocol or feature. HTTP/3 is compiled in the
GnuTLS build; the installed nghttpx is not assumed to provide an HTTP/3 server.
The separate HTTP pytest suite and its dependencies are not prepared here.

Rebuild with `cmake --build /src/build/openssl --parallel 2` (or `gnutls`), and
rebuild test drivers with the `testdeps` target. For a direct test invocation,
run from the build's `tests/` directory, for example
`cd /src/build/openssl/tests && perl /src/tests/runtests.pl -a -p -n 1`.
Build-time smoke test output is kept in each build's `smoke-tests.log`.

`ENABLE_DEBUG=ON` enables test infrastructure and additional checks. Before
classifying a finding, verify it exists in production code and reproduces
with debug-only behavior disabled. Preserve sanitizers for memory diagnostics.

## Evidence expected for a finding

Provide a small self-contained reproducer, exact options or API calls, the
attacker-controlled transcript or fixture, the affected function, and the
observed security impact. Include the commit, build configuration, dependency
versions and required preconditions. Show the relevant stack trace or forbidden
network/file/credential behavior, rather than inferring exploitation from a
crash or warning alone.

State whether the latest released version is affected as well as master, and
check existing advisories and fixes before presenting a new vulnerability.
For a patch, add a focused regression that fails before the fix and passes
after it, including relevant failure and cleanup paths. Keep reports concise
and distinguish confirmed behavior from untested platform or backend claims.
