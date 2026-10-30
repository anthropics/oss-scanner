# GNU Gatekeeper (GnuGK) – Threat Model

## 1. System overview

GnuGK is a long-running, multi-threaded H.323 gatekeeper. Depending on configuration it:

- terminates **RAS** (registration, admission, location) over UDP,
- routes or **proxies H.225 call signalling and H.245** over TCP (optionally TLS),
- **proxies RTP/RTCP media** and T.120, including NAT traversal (H.460.17/18/19/26, RTP multiplexing),
- exchanges LRQ/LCF with **neighbor and parent gatekeepers**,
- delegates **authentication, routing and accounting** to files, SQL, LDAP/H.350, HTTP, Lua, Redis, AMQP, syslog,
- exposes an **administrative status port** (telnet-style, optional SSH) and **SNMP**.

It typically runs on a public-facing host, frequently as root or with broad network privileges, and sits in front of PBXs, MCUs and PSTN gateways – so its compromise or misuse translates directly into toll fraud.

### 1.1 Port allocations

The H.323 protocol encapsulates port numbers inside the packets. Therefore the Docker image must publish each port under
the same number on the host as the GNU Gatekeeper uses inside the container; they can't be remapped as
with other protocols. In addition to that the GNU Gatekeeper must know the IP under which the clients see it,
because it will embed this IP in the packets to route the traffic through it. The provided configuration uses
STUN to find the public IP (which may fail in local lab networks).

Run the provided Docker container as:

```
sudo docker run -p 1719:1719/udp -p 1720:1720 -p 20000-20100:20000-20100 -p 30000-30500:30000-30500/udp -d gnugk
```

## 2. Assets

| ID | Asset | Why it matters |
|----|-------|----------------|
| A1 | Call routing / admission decisions | Unauthorized calls → toll fraud, PSTN abuse |
| A2 | Endpoint registration table (`RasTbl`) | Hijacking an alias redirects calls / intercepts users |
| A3 | Endpoint credentials (H.235 passwords, SQL/LDAP secrets) | Impersonation, lateral movement into backends |
| A4 | Media streams (RTP/RTCP) | Confidentiality of conversations |
| A5 | Status port control | Full administrative control: disconnect, unregister, reload config, route |
| A6 | Configuration file (`gatekeeper.ini`) and on-disk secrets | Contains all policy and backend credentials |
| A7 | CDRs / accounting data | Billing integrity, PII (caller/callee numbers, IPs) |
| A8 | Host process (code execution context) | Typically privileged; pivot point into the VoIP network |
| A9 | Service availability | Gatekeeper outage = no calls site-wide |

## 3. Actors and trust levels

| Actor | Trust | Notes |
|-------|-------|-------|
| T0 Anonymous Internet host | None | Can reach RAS (1719/udp, 1718 multicast), Q.931 (1720/tcp), TLS (1300/tcp), media ports |
| T1 Registered endpoint | Low | Authenticated only if an authenticator is configured; otherwise identity = claimed alias + source IP |
| T2 Neighbor / parent gatekeeper | Medium | Trust is configured per neighbor; LRQs may be accepted from IPs only |
| T3 Traversal client (H.460.17/18) | Low | Behind NAT, keep-alive based, source address changes are expected |
| T4 Backend services (SQL, LDAP, HTTP, Redis, AMQP) | Medium-high | Their responses drive auth and routing |
| T5 Status-port operator | High | Admin; authenticated via `[GkStatus::Auth]` (default rule `forbid`) |
| T6 Local OS users | Varies | Access to config, logs, trace files, CDR files |
| T7 Lua script author | High | Scripts run in-process |

## 4. Trust boundaries and entry points

```
            Internet / untrusted LAN
   ───────────────────────────────────────────────── TB1
     RAS UDP 1719 / 1718 mcast   (RasSrv.cxx, RasPDU.h)
     Q.931/H.225 TCP 1720        (ProxyChannel.cxx, sigmsg.cxx)
     TLS 1300                    (Toolkit TLS ctx, yasocket.cxx)
     H.245 TCP / multiplex 1722  (ProxyChannel.cxx)
     RTP/RTCP / multiplex 3000-1 (ProxyChannel.cxx)
     STUN 3478 (H.460.19 helper)
     LRQ/LCF from neighbors      (Neighbor.cxx)
   ───────────────────────────────────────────────── TB2  (admin plane)
     Status port 7000 (+SSH)     (GkStatus.cxx)
     SNMP agent                  (snmp.cxx)
   ───────────────────────────────────────────────── TB3  (backends, outbound)
     SQL drivers                 (gksql*.cxx, sqlauth.cxx, sqlacct.cxx)
     LDAP / H.350                (ldap.cxx, ptlib pldap)
     HTTP auth/policy/acct       (gkauth.cxx HttpPasswordAuth, Routing.cxx HttpPolicy, httpacct.cxx)
     Redis, AMQP, syslog, GeoIP
   ───────────────────────────────────────────────── TB4  (local host)
     gatekeeper.ini, CDR/trace files, Lua scripts, external commands (system())
```

Every byte crossing TB1 is attacker-controlled ASN.1 PER (RAS/H.245) or Q.931/H.225 with nested ASN.1, plus raw RTP. Values crossing TB1 later flow into TB3 (SQL, LDAP filters, HTTP URLs, Lua) and TB4 (shell commands, log/CDR files) – these second-order flows are where injection bugs live.

## 5. Threats (STRIDE)

Ratings: L = likelihood, I = impact (H/M/L). "Existing" lists mitigations known in the code base; "Gaps" are open items to verify or fix.

### 5.1 RAS (RasSrv.cxx, RasTbl.cxx, gkauth.cxx)

| # | Threat | STRIDE | L/I | Existing | Gaps |
|---|--------|--------|-----|----------|------|
| R1 | Unauthenticated RRQ registers another user's alias (alias hijack) | S | H/H | Auth modules (`SimplePasswordAuth`, `AliasAuth`, SQL/LDAP, `FileIPAuth`); `RasSrv::RRQFeatures` overwrite rules | Default config has no authenticator → any host may register any alias. Document a secure baseline config |
| R2 | Spoofed source IP in UDP RRQ/ARQ (RAS is UDP, unauthenticated by default) | S | H/H | IP-based checks, `RRQ check` | IP auth alone is spoofable on shared L2 or with asymmetric routing; recommend H.235 |
| R3 | Replay of H.235 CAT / MD5 / Procedure I tokens | S | M/H | Timestamp check in `gkh235.cxx` | Default `TimestampGracePeriod` ≈ 2 h – large replay window; no nonce/sequence-number cache |
| R4 | Weak H.235 algorithm (MD5 password hash) | I/S | M/H | – | Offline cracking of captured hashes |
| R5 | Malformed PER causes OOB read / crash in decoder | D/E | M/H | H323Plus PER decoder, size checks | Continuous fuzzing of RAS PDU decode + `RasPDU<>` handlers |
| R6 | Registration flood / table exhaustion (unbounded endpoints, aliases per endpoint) | D | H/M | TTL, `TimeToLive`, optional `MaxEndpoints` style limits | Per-source-IP rate limits; caps on alias count and alias length |
| R7 | Multicast GRQ/LRQ (1718) amplification / discovery | D/I | M/L | Can be disabled | Recommend disabled by default on public interfaces |
| R8 | Forged URQ/DRQ tears down others' registrations or calls | T/D | M/M | Endpoint ID + source checks | Verify all URQ/DRQ paths require matching endpoint ID **and** signal address |

### 5.2 Call signalling (Q.931/H.225, ProxyChannel.cxx, sigmsg.cxx)

| # | Threat | STRIDE | L/I | Existing | Gaps |
|---|--------|--------|-----|----------|------|
| S1 | Direct Setup from unregistered host bypasses admission (`AcceptUnregisteredCalls`) | E | H/H | Config switches, Setup authenticators | Misconfiguration is the #1 toll-fraud vector – flag in docs and startup log |
| S2 | Caller-ID / alias spoofing in Setup (`sourceAddress`, calling party number) | S | H/M | `clirw.cxx` CLI rewriting, `TwoAliasAuth`, `CapCtrlAuth` | No binding of presented CLI to authenticated identity unless explicitly configured |
| S3 | Malformed Q.931 IEs / nested UUIE / tunneled H.245 → memory corruption | E/D | M/H | Length checks in `sigmsg.cxx`, `ProxyChannel.t.cxx` tests | Fuzz Q.931 + UUIE + fastStart + tunneled H.245; ASan/UBSan CI |
| S4 | Slowloris / half-open TCP on 1720/1300, thread exhaustion | D | H/M | Listen queue, signalling timeouts | Per-IP connection limit; cap on concurrent pre-Setup sockets |
| S5 | TLS downgrade / weak cipher config on 1300 | I/T | M/M | OpenSSL context in Toolkit | Enforce TLS ≥ 1.2 by default, sane cipher list, verify peer cert option documented |
| S6 | Transfer/forwarding (`forwarding.cxx`, Facility, H.450) redirects call to attacker-chosen destination | T/E | M/H | Routing policies | Re-run admission/auth on redirected destination |
| S7 | Use-after-free on call teardown races (`callptr`, `CallSignalSocket`, `ProxyHandler` threads) | E/D | M/H | Ref-counted `callptr`, rwlocks | TSan runs on proxy/teardown paths |

### 5.3 H.245 / media proxy / NAT traversal

| # | Threat | STRIDE | L/I | Existing | Gaps |
|---|--------|--------|-----|----------|------|
| M1 | OLC/OLCAck rewrites point gatekeeper's RTP proxy at arbitrary host → reflection/DoS | T/D | M/M | `SetDestination` with `sourceIP` checks | Restrict media destinations to call participants' IPs |
| M2 | RTP injection / hijack via port guessing on proxied or multiplexed RTP (3000/3001) | T/I | M/M | Latching to first source, multiplex ID | Verify multiplex IDs are unpredictable and bound to call; consider SRTP/H.235.6 media where available |
| M3 | Media eavesdropping (cleartext RTP) | I | H/M | Optional H.235 media | Document that confidentiality requires H.235.6 / SRTP end-to-end |
| M4 | H.460.18 keep-alive / traversal client source-address takeover | S/T | M/H | Endpoint binding | Ensure address updates require authenticated keep-alive |
| M5 | H.460.26 RTP-over-signalling buffer abuse (`SendH46026RTP`) | D/E | M/M | – | Bound queue sizes and payload lengths |
| M6 | Port exhaustion of RTP range | D | M/M | Configurable range | Per-call/per-endpoint port caps |
| M7 | Port open/close notification runs `system()` with `%i`, `%n`, `%p`, `%t` substitution (`Toolkit.cxx`, `HAS_PORT_NOTIFICATION_EXEC`) | E | L/H | Values are formatted IP/int/enum, not raw strings | Keep it that way – any future placeholder from network data must be quoted; prefer `execve` without shell |

### 5.4 Neighbors / routing (Neighbor.cxx, Routing.cxx)

| # | Threat | STRIDE | L/I | Existing | Gaps |
|---|--------|--------|-----|----------|------|
| N1 | Rogue host sends LRQ as a "neighbor" to discover routes or obtain LCF to PSTN gateways | S/E | M/H | Neighbor list, `AcceptNeighborsCalls`, optional H.235 on LRQ | IP-only neighbor trust is spoofable over UDP |
| N2 | Forged LCF poisons routing (calls sent to attacker) | T/I | M/H | Sequence number match | Require auth on LCF; validate destination address families |
| N3 | LRQ forwarding loops / hop-count abuse | D | M/M | Hop count | Verify hop count enforced on every forward path |
| N4 | DNS/ENUM policy returns attacker-controlled destinations (`DNSPolicy`, `ENUMPolicy`, `URIServicePolicy`) | T | M/M | – | DNSSEC not validated; document trust assumption |
| N5 | `HttpPolicy` / `SqlPolicy` response tampering | T | L/H | Backend auth | Use HTTPS with cert validation; see 5.6 |

### 5.5 Admin plane (GkStatus.cxx, snmp.cxx)

| # | Threat | STRIDE | L/I | Existing | Gaps |
|---|--------|--------|-----|----------|------|
| P1 | Unauthorized status-port access → full control (disconnect, unregister, reload, route) | E | M/H | `[GkStatus::Auth]` rules (`forbid` default, `allow`, `explicit`, `regex`, `password`), SSH | `allow` rule and telnet are cleartext; bind to localhost by default |
| P2 | Brute force of status-port password | S | M/H | Retry counter, delay | Previously bypassable retry counter fixed – keep regression test |
| P3 | Sniffing credentials / CDR events on cleartext status port | I | H/M | SSH optional | Recommend SSH-only on non-loopback |
| P4 | Status-port output injection (aliases containing CR/LF or control chars confuse log parsers / scripts consuming the port) | T | M/M | – | Escape control characters in status output |
| P5 | SNMP v1/v2c community disclosure; SNMP writes | I/E | M/M | net-snmp agent | Recommend SNMPv3 or read-only, bound to management VLAN |

### 5.6 Backends (TB3)

| # | Threat | STRIDE | L/I | Existing | Gaps |
|---|--------|--------|-----|----------|------|
| B1 | SQL injection via alias, CLI, IP, call ID in `%{...}` placeholders (`sqlauth.cxx`, `sqlacct.cxx`, `SqlPolicy`) | T/E/I | M/H | `GkSQLConnection::EscapeString`, `EscapeAcctParam` | Audit every driver's `EscapeString` (esp. ODBC/Firebird/Oracle) and every template path; migrate to prepared statements |
| B2 | LDAP filter injection in `LDAPPasswordAuth`/`LDAPAliasAuth`/H.350 | T/E | M/H | Deprecated APIs replaced in `pldap.cxx` | RFC 4515 escaping of `* ( ) \ NUL` for every network-derived value |
| B3 | Redis command injection (`gksql_redis.cxx`) | T/E | M/H | – | Use argv-style command building, never string concatenation |
| B4 | HTTP auth/policy/acct over plain HTTP, URL parameter injection | I/T | M/M | – | URL-encode substituted values; HTTPS + cert verification |
| B5 | Backend slow/unavailable stalls RAS/signalling threads | D | H/M | Connection pools, timeouts per driver | Verify every backend call has a bounded timeout; define fail-open vs fail-closed per module |
| B6 | Lua scripts receive raw network values | E | L/H | Admin-authored scripts | Document that scripts must treat inputs as untrusted; no sandbox (`os`, `io` available) |
| B7 | Accounting injection into CDR files / syslog / AMQP (newline injection, CSV injection) | T | M/L | `EscapeAcctParam` | Strip CR/LF/control chars in `FileAcct`, `SyslogAcct` |

### 5.7 Local host (TB4)

| # | Threat | STRIDE | L/I | Existing | Gaps |
|---|--------|--------|-----|----------|------|
| H1 | Config file readable by other users → backend secrets | I | M/H | `EncryptAllPasswords` | Encryption is TEA keyed with a value stored in the same file (`KeyFilled`) – obfuscation only; rely on file permissions (0600) |
| H2 | Trace files at high levels log passwords, H.235 tokens, PII | I | M/M | Trace levels | Redact secrets regardless of trace level |
| H3 | Running as root | E | M/H | `-u user` drop privileges, initd scripts | Make non-root the documented default; capabilities for low ports |
| H4 | Config reload via status port loads attacker-modified file | E | L/H | Admin auth | Covered by P1 + H1 |

## 6. Cross-cutting: memory safety and concurrency

GnuGK is ~75 kLOC of C++ on top of ptlib and H323Plus, all parsing hostile ASN.1 and binary protocols on dozens of threads. The dominant technical risk class is memory corruption reachable pre-authentication (R5, S3, M5) and data races in call/endpoint lifetime (S7).

