# Threat model

## What this project does and where untrusted input enters
ntopng is a network traffic monitoring and analysis tool (C++ core with an embedded Lua/Mongoose web layer). Untrusted input arrives from:
- network traffic captured from packet interfaces (pcap, PF_RING) or received from flow exporters (NetFlow, sFlow, IPFIX over ZMQ/UDP) — packet and flow parsing, nDPI protocol dissection, and anything stored from them (host names, certificates, DNS and HTTP fields) that is later rendered in the web UI;
- the HTTP server: URL parameters, POST bodies, cookies and headers handled in `src/HTTPserver.cpp` and the Lua scripts under `scripts/lua/` (REST API in `scripts/lua/rest/`);
- authenticated users (including lower-privileged ones) of the web UI and REST API.

## Components that matter most / least
Most: packet/flow parsing in `src/`, the HTTP server and authentication/session code (`HTTPserver.cpp`, `Ntop.cpp`), the C++ to Lua bindings (`LuaEngine*.cpp`), and the Lua REST endpoints.
Least / out of scope: `third-party/` (bundled libraries; report upstream), the `pro/` directory is not part of this repository.

## How to exercise it
Run `ntopng -i none` or feed a pcap with `-i file.pcap`, then request the web UI and `/lua/rest/` endpoints. Redis is required (`redis-server`).

## How you rate severity
- Memory corruption reachable from network traffic or an unauthenticated HTTP request: high at a minimum; critical if it may lead to remote code execution.
- Authentication or authorization bypass, or privilege escalation from a non-admin to an admin user: high or critical.
- Stored or reflected XSS, CSRF and SQL injection in the web UI or REST API: medium to high depending on required privileges.
- Denial of service from crafted traffic: medium.

## Anything to leave alone
- Issues that need an administrator to configure something unsafe on purpose.
- Findings only in code under `third-party/`.
