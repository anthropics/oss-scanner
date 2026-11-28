# Threat model: sofia-sip

## What this project does

sofia-sip is a C library implementing a SIP (RFC 3261) user agent stack: message parsing, transports,
transactions, dialogs, SDP offer/answer and DNS resolution for SIP. Its main consumer is FreeSWITCH
(`mod_sofia`), which runs it as an Internet-facing SIP server, registrar, gateway and WebRTC endpoint,
usually on public UDP/TCP/TLS/WS/WSS ports. One sofia-sip process typically carries many unrelated calls,
so a crash takes down every call on the server.

The library parses every incoming message before the application sees it. Authentication happens later,
in the application. Treat all parser and transport code as reachable by an unauthenticated remote peer.

## Where untrusted input enters

- **SIP messages** from any network peer over UDP, TCP, TLS, WebSocket and secure WebSocket
  (`tport/`, including the WebSocket framing and HTTP upgrade handshake in `tport/ws.c` and
  `tport/tport_type_ws.c`). Stream transports deliver partial, pipelined and oversized messages.
- **Message parsing**: the generic parser and header framework in `msg/` (including MIME and multipart
  bodies in `msg/msg_mime.c`), SIP headers in `sip/`, URLs in `url/`, the token and host grammar in `bnf/`.
- **SDP bodies** in `sdp/` (parser and printer), and SDP negotiation in `soa/`.
- **DNS responses** in `sresolv/` (NAPTR, SRV, A, AAAA, CNAME). Destinations often come from
  attacker-supplied URIs (Request-URI, Contact, Route, 3xx redirects, REFER), so an attacker can make the
  library query a domain whose authoritative server they control.
- **Digest challenges and credentials** in `iptsec/` (`WWW-Authenticate`, `Proxy-Authenticate`,
  `Authorization`), including challenges from upstream servers that the library answers as a client.
- **Transaction and dialog state** in `nta/` and `nua/`: out-of-order, duplicated, cancelled and
  forked transactions, PRACK, session timers, REFER and SUBSCRIBE/NOTIFY (`nea/`), driven by the peer.
- **HTTP** parsing in `http/` and the HTTP client/server in `nth/`. Built by default, but FreeSWITCH does
  not use them.

## Components that matter most / least

Most important, in order: `msg/`, `sip/`, `tport/` (with `ws.c`), `sdp/`, `url/`, `bnf/`, `sresolv/`,
`nta/`, `nua/`, `soa/`, `iptsec/`, `nea/`, and the `su/` helpers they call (allocation, strings, base64).

Lower priority but in scope: `http/`, `nth/`, `features/`, `tport` HEP capture output (`tport_logging.c`).

Out of scope: `libsofia-sip-ua-glib/`, `win32/`, `open_c/`, `packages/`, `docs/`, `s2check/`, `tests/`,
the test and `torture_*` programs, `utils/` command-line tools, and code that `configure.gnu` does not
build: STUN (`stun/`, `--disable-stun`), NTLM, SCTP and SigComp.

## Build and how to exercise it

The image is configured with `./configure.gnu`, as FreeSWITCH builds it (`--with-pic --with-glib=no
--disable-shared --without-doxygen --disable-stun`), and built in-tree at `/src` with
`-g -O1 -fno-omit-frame-pointer -fsanitize=address,undefined`. The static library is also installed to
`/usr/local` (`pkg-config --cflags --libs --static sofia-sip-ua`); a standalone harness must be built with
the same `-fsanitize` flags. `ASAN_OPTIONS` sets `detect_leaks=0` because the test programs leak on
exit by design; set `detect_leaks=1` to confirm a leak.

`assert()` is enabled in this and the FreeSWITCH builds (`--enable-ndebug` is off), so a reachable
assertion is a remote abort.

- `libsofia-sip-ua/sip/test_sip_msg` parses one SIP message from stdin (`-t` for stream framing);
  `sip/tests/*.txt` hold sample messages.
- `libsofia-sip-ua/sdp/test_sdp` parses one SDP body from stdin or a file; samples in `sdp/tests/`.
- `libsofia-sip-ua/msg/test_msg`, `sip/torture_sip`, `url/torture_url`, `sdp/torture_sdp`,
  `sresolv/torture_sresolv`, `iptsec/test_auth_digest`, `tport/test_tport`, `soa/test_soa`: per-module
  unit tests to copy from.
- `tests/check_sofia` and `nua/check_nua` run end-to-end NUA call scenarios over loopback.
- `utils/sip-options` sends OPTIONS; a loopback UDP or TCP socket in Python works as a remote peer.

`make check` runs the whole suite; `make-check.log` at `/src` and each test's `.log` hold the results from
image build time. The nta test programs (`check_nta`, `test_nta`, `test_nta_api`) do not link on master,
and `tests/check_dlopen_sofia` needs a shared library, which this static build does not produce.

## How we rate severity

- **Critical**: memory corruption (out-of-bounds write, use-after-free, double free) that an
  unauthenticated remote peer reaches with SIP, SDP, WebSocket or DNS input in the default configuration
  and controls well enough to plausibly gain code execution.
- **High**: any other memory corruption reachable from network input; a crash, abort or assertion
  failure that one unauthenticated peer triggers with a small number of messages ("packet of death");
  an out-of-bounds read that crashes or sends heap memory back to the peer.
- **Medium**: an out-of-bounds read that neither crashes nor discloses memory; CPU or memory exhaustion
  from a single peer that an application cannot bound through the library's settings; a crash that needs
  an established dialog with the attacker as a participant; a crash from a crafted DNS response.
- **Low**: anything reachable only through the C API with arguments the application controls (NULL
  pointers, malformed tag lists, out-of-range parameters), crashes only in out-of-scope code, and
  leaks bounded by one transaction.

Lower a rating by one level when the bug needs a non-default build option or a transport the
application must explicitly enable, and say which.

## Anything to leave alone

- Leaks reported at process exit by the test programs.
- Integer overflow on buffer sizes above what the transport can deliver (UDP datagram limit, configured
  message size limit), unless the report shows it reachable.
- UBSan reports for unaligned access or signed shifts without a demonstrated memory-safety or behavioural
  consequence. In particular: misaligned access through `url_string_t`, because passing a `char *` where the
  API takes `url_string_t const *` is the intended calling convention (`URL_STRING_MAKE()`); and "member
  access within null pointer" where the code only takes a member's address (`&p->m`, an embedded struct
  or array) without loading from it.
- Defects in third-party code (OpenSSL, libc).
