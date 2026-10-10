# Threat model

## What simplexmq is and where untrusted input enters

simplexmq implements the SimpleX network: the SMP message routers (`smp-server`), the XFTP file routers
(`xftp-server`), the push notification server (`ntf-server`), the `xftp` command-line client, and the SMP agent
library that clients (including simplex-chat) use to create queues, establish duplex connections with double
ratchet end-to-end encryption, and send files.

The protocol specifications and the full threat model are in `protocol/`, in particular `protocol/security.md`,
`protocol/overview-tjr.md`, `protocol/simplex-messaging.md`, `protocol/xftp.md`, `protocol/agent-protocol.md`,
`protocol/push-notifications.md` and `protocol/xrcp.md`.

Untrusted input enters from:

* any network client of a router: routers are public and accept connections from anyone, before and after
  the TLS handshake, the transport handshake and command authorization;
* the routers themselves, from the agent's point of view: a router may be malicious and send any response,
  message or error to a client;
* contacts: everything a peer sends inside a connection, including confirmation and handshake messages,
  ratchet headers, encrypted envelopes and their decrypted content;
* connection links, short links, file descriptions and invitation data, which users receive out of band;
* proxied traffic: an SMP router forwarding messages for clients to another router (`PFWD`/`RFWD`).

The local user, the local database and the host operating system are trusted.

## Components that matter most and least

Most important:

* `src/Simplex/Messaging/Server*` and `src/Simplex/FileTransfer/Server*`: command parsing and authorization,
  queue and message stores (memory, journal and PostgreSQL), store logs, proxying;
* `src/Simplex/Messaging/Transport*`: TLS setup, transport handshake, block framing, HTTP/2 used by XFTP and
  notifications;
* `src/Simplex/Messaging/Protocol.hs`, `Encoding*`, `Parsers.hs`, `src/Simplex/FileTransfer/Protocol.hs`:
  binary encodings that parse attacker-controlled data;
* `src/Simplex/Messaging/Crypto*` and `cbits/sntrup761.c`: the double ratchet with post-quantum KEM, signatures,
  key agreement, short-link encryption, file encryption;
* `src/Simplex/Messaging/Agent*`: connection establishment, message integrity checks, ratchet state handling,
  queue rotation, and what a malicious router or contact can make the agent do;
* `src/Simplex/Messaging/Notifications/*` and `src/Simplex/RemoteControl/*`.

Lower priority:

* `xftp-web/` (the TypeScript XFTP web client) and `scripts/resolver/` (the Python names resolver service);
* `apps/`: thin `main` wrappers around the library;
* `scripts/` other than the resolver: deployment helpers.

Out of scope:

* third-party code in `cbits/blst` and `cbits/libbbs`, except where a flaw is reachable through simplexmq;
* `tests/`, including the keys and certificates in `tests/fixtures`, which are intentionally public.

## How to exercise it

The image is built with `cabal.project.local` enabling tests and the `server_postgres` flag, so `cabal build`
and `cabal test` work offline without rebuilding dependencies.

* Binaries: `$(cabal list-bin smp-server)`, `xftp-server`, `ntf-server`, `xftp`. `smp-server init` creates a
  configuration and keys under `/etc/opt/simplex`.
* Tests: `$(cabal list-bin simplexmq-test) -m "<describe path>"`, for example `-m "Core tests"` or
  `-m "SMP server via TLS"`. Tests run from `/src` and use `tests/tmp`.
* PostgreSQL tests need the server: run `service postgresql start` first. It accepts passwordless connections
  as `postgres` on localhost, as in CI.

## How we rate severity

We use the levels in https://github.com/simplex-chat/simplex-chat/blob/stable/docs/SECURITY.md:

* Critical: affects common configurations, low or medium difficulty. For example, disclosure of users' messages or
  files via routers or communication channels, or remote compromise of client or router private keys.
* High: as critical but in less common configurations or with high difficulty. Also any remote code execution, any
  way to bypass queue or command authorization, any way for a router to undetectably add, corrupt or reorder messages,
  and any way for a single unauthenticated client to crash or stall a router.
* Medium: crashes of clients caused by received messages or files, flaws in rarely used protocols, local flaws.
* Low: issues that only affect the CLI app, unlikely configurations, or medium issues that are very hard to exploit.

A report should state which adversary from `protocol/security.md` can exploit the issue, and what it gains
beyond what that document says the adversary can already do.

## Anything to leave alone

* Anything `protocol/security.md` lists under what an adversary *can* do, for example a router learning
  when a recipient is online, a router dropping all messages to a queue, or traffic correlation by a passive
  observer of both parties.
* CPU and hardware flaws, physical side channels (power, EM), and access to data on the user's device with
  the user's or root privileges, including the database and its key if stored on the device.
* Weaknesses that require the cryptographic primitives themselves to be broken.
