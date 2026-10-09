# Threat model: iroh

## What this project does and where untrusted input enters

iroh lets applications dial other endpoints by public key instead of by IP address. An `EndpointId` is an Ed25519 public key. iroh finds a path to it, hole-punches a direct UDP path where it can, and otherwise falls back to a relay server. Connections are QUIC, built on noq (n0's QUIC stack with multipath and a NAT traversal extension, maintained by the same team in a separate repository). The scanned branch is `main`, which is the 1.x release line. The workspace has five crates:

- `iroh`: the `Endpoint`. It owns the UDP sockets and the relay connections (`src/socket/`), NAT traversal and path selection, address lookup (`src/address_lookup/`: DNS, pkarr, in-memory), network probing (`src/net_report*`), the TLS setup (`src/tls/`), the `Router` that dispatches incoming connections by ALPN (`src/protocol.rs`) and the connection hooks (`src/endpoint/hooks.rs`).
- `iroh-base`: `PublicKey`/`SecretKey`/`EndpointId`, `EndpointAddr`/`TransportAddr`/`CustomAddr` and `RelayUrl`, with their string and serde forms. Applications parse these from tickets and user input.
- `iroh-relay`: the relay protocol, the relay client, the relay server (as a library and as the `iroh-relay` binary) and QUIC address discovery (QAD).
- `iroh-dns`: pkarr `SignedPacket`, the `_iroh` TXT record format for endpoint info, and the `DnsResolver`.
- `iroh-dns-server`: a pkarr relay over HTTP plus an authoritative DNS server for endpoint records (the `iroh-dns-server` binary), with an optional mainline DHT fallback.

The security model rests on one rule: the `EndpointId` is authenticated by TLS 1.3 with raw Ed25519 public keys (RFC 7250), and nothing else is trusted for authenticity. A dialer puts the expected key in the server name (`<id>.iroh.invalid`, never sent because SNI is off) and accepts only that key. An acceptor learns the remote id from the client's key. IP addresses, relay URLs, DNS answers, pkarr records, QAD reports and relay servers are all untrusted. A relay forwards encrypted QUIC packets by endpoint id. It must not be able to read, change or inject application data, or make one endpoint appear to be another. Which peers may connect is the application's decision, made through hooks, `IncomingFilter` and the ALPNs it registers.

Treat all of the following as attacker-controlled.

**Against an endpoint:**

- Every UDP datagram that reaches its sockets, from anyone, before any handshake.
- Everything a connected remote sends after the handshake. This includes streams and datagrams, and also QUIC frames for multipath and NAT traversal, such as the candidate addresses a remote advertises.
- Everything a relay server sends. A relay may be malicious. This covers the handshake challenge, datagram and datagram-batch frames (including the segment size), `EndpointGone`, `Status`, `Ping` and `Restarting`.
- Relay URLs and IP addresses learned from remotes or from address lookup. An endpoint dials relays a remote advertises.
- DNS responses, pkarr relay responses and pkarr packets.
- The responses to network probes: the captive-portal check, HTTPS latency probes, QAD observed addresses, and UPnP/PCP/NAT-PMP replies from the LAN.
- Strings and bytes that applications parse into `EndpointId`, `EndpointAddr`, `CustomAddr` or `RelayUrl`, through `FromStr` or serde (postcard and JSON). This includes tickets.

**Against a relay server:**

- Every TCP connection to its HTTP(S) port. This covers the HTTP request, the websocket upgrade headers, the `Sec-WebSocket-Protocol` version negotiation, the `x-iroh-relay-client-auth-v1` header and the challenge-response handshake.
- After the handshake, every frame from the client. Any keypair can authenticate, and the default access policy allows everyone.
- The `/generate_204` captive-portal endpoint and its `X-Iroh-Challenge` header.
- QUIC connections to the QAD port (7842 by default).

**Against `iroh-dns-server`:**

- DNS queries over UDP and TCP.
- DNS-over-HTTPS (`GET`/`POST /dns-query`).
- `PUT /pkarr/{z32-key}` with a signed packet from anyone, and `GET /pkarr/{z32-key}`.
- When the DHT fallback is enabled, mainline DHT responses.

## Components that matter most / least

Most important, in this order:

1. **The relay server.** It is publicly reachable and multi-tenant, so one client affecting another matters as much as a crash. The code is in:
   - `iroh-relay/src/server/`: `http_server.rs` (accept, upgrade, timeouts), `client.rs` (per-client actor), `clients.rs` (registry and forwarding) and `streams.rs` (rate limiting).
   - `iroh-relay/src/protos/`: `relay.rs` (frame codec), `handshake.rs` and `common.rs`.
   - `iroh-relay/src/quic.rs` (the QAD server).
   - The binary's config and access control in `iroh-relay/src/main.rs`: `AccessConfig`, allowlist, denylist, `shared_token` and `http`.
2. **The endpoint's networking core.** This is the code that receives packets and decides where to send them:
   - `iroh/src/socket.rs` and `iroh/src/socket/**`: the transports, the relay actor, `remote_map/remote_state.rs` (NAT traversal), path state and mapped addresses.
   - `iroh/src/endpoint.rs` and `iroh/src/endpoint/connection.rs`.
   - `iroh/src/tls/`: the certificate verifiers, resolver and server-name encoding. A flaw here can break identity.
3. **Parsers of data from peers or applications:**
   - `iroh-base/src/key.rs`, `endpoint_addr.rs` and `relay_url.rs`.
   - `iroh-dns/src/pkarr.rs`, `endpoint_info.rs` and `attrs.rs`.
   - The relay client side in `iroh-relay/src/client.rs` and `iroh-relay/src/client/`.
4. **`iroh-dns-server`:**
   - `src/http/`: the pkarr routes, DoH and `rate_limiting.rs`.
   - `src/dns.rs` and `src/dns/node_zone_handler.rs`.
   - `src/store.rs`, `src/store/signed_packets.rs` and `src/util.rs`.
5. **Supporting endpoint code:** address lookup (`iroh/src/address_lookup/**`), `net_report`, the `Router` and the hooks.

Several dependencies are maintained by the same team in other repositories: noq, noq-proto and noq-udp (QUIC), n0-dns-resolver, portmapper, netwatch, iroh-metrics and n0-mainline. Their sources are in the cargo registry in this image. A flaw in one of them that an attacker can reach through iroh is in scope. Show the path from iroh's API and name the crate the fix belongs in.

rustls, ring, aws-lc, ed25519-dalek, hickory, simple-dns, tokio, hyper, axum and tokio-websockets have their own security processes. A flaw that lies wholly inside one of them belongs there. Report it here only when iroh's use of it makes it reachable, and show how.

Out of scope:

- `iroh/bench`, `iroh/examples`, and the examples and benches of `iroh-dns-server`.
- Test code, the `test_utils` and `server::testing` modules, and everything gated on the `test-utils` feature (including `CaTlsConfig::insecure_skip_verify` and `make_dangerous_client_config`).
- `docker/`, `.github/`, the release tooling and the docs.

The WebAssembly (browser) build and the Windows, Apple (`fast-apple-datapath`) and Android code paths are in scope for review, but this image can only run Linux code.

## How to exercise it

The image is a checkout of `main` in `/src`. The workspace is built with `--all-features` in the dev profile, which keeps debug assertions and overflow checks on. The binaries, examples and test binaries are under `/src/target/debug`. Every crate in `Cargo.lock` is fetched and `CARGO_NET_OFFLINE=true` is set, so rebuilding with other features or cfgs (for example `RUSTFLAGS="--cfg iroh_loom"`) works without a network. cargo-nextest, rustfmt and clippy are installed. `dig` and `curl` are available for poking at servers.

**Tests**

- `cargo nextest run --workspace --all-features` runs the suite the way CI does. The repository's `.config/nextest.toml` stops any test after 30 s.
- Offline, two tests fail because they need n0's public DNS and relay servers: `iroh defaults::tests::test_dns_lookup_ipv4_ipv6` and `iroh::integration simple_endpoint_id_based_connection_transfer`. Everything else passes.
- The relay codec has property tests that decode arbitrary and mutated bytes: `cargo nextest run --workspace --all-features proptests`.
- Keep `--workspace --all-features` when selecting tests. Narrowing with `-p <crate>` resolves features differently and triggers a rebuild. Filter by test name instead.

**In-process building blocks for new tests**, all behind the `test-utils` feature:

- `iroh::test_utils::run_relay_server()`, `run_relay_server_with(quic)` and `run_relay_server_with_access(quic, access)` start a relay on 127.0.0.1 with a self-signed certificate and, optionally, QAD. Clients need `CaTlsConfig::insecure_skip_verify()`. See `endpoint_connect_close` in `iroh/src/endpoint.rs` for two endpoints talking through such a relay with `RelayMode::Custom`.
- `iroh::test_utils::DnsPkarrServer` runs a local DNS server and pkarr relay. Its `preset()` wires an endpoint to them.
- `iroh::test_utils::test_transport::TestNetwork` is an in-memory custom transport. It also needs `unstable-custom-transports`.
- `iroh-relay/tests/relay_axum.rs` and `relay_hyper.rs` embed the relay service in another HTTP server. They show how to drive the server side of the relay protocol directly from a test.

**Servers to attack**

- **Relay.** `target/debug/iroh-relay --dev` serves the relay over plain HTTP on `[::]:3340`, at `http://localhost:3340/relay`, with metrics on port 9090.
  - For HTTPS and QAD, use `/opt/iroh-local/relay.toml`: `target/debug/iroh-relay -c /opt/iroh-local/relay.toml`.
    - It serves the relay at `https://localhost:3443/relay` and QAD on UDP 127.0.0.1:7842, with a self-signed certificate for `localhost` (`/opt/iroh-local/relay.crt`).
    - In this mode, plain HTTP on 127.0.0.1:3340 serves only the captive-portal check.
    - `curl --cacert /opt/iroh-local/relay.crt https://localhost:3443/healthz` checks that it is up. iroh clients need that certificate as an extra root, or `CaTlsConfig::insecure_skip_verify()`.
  - Edit a copy of that file to try access control (`access.allowlist`, `access.shared_token`) or rate limits (`[limits.client.rx] bytes_per_second`, `max_burst_bytes`).
- **DNS server.** `IROH_DNS_DATA_DIR=/tmp/iroh-dns target/debug/iroh-dns-server` runs the default configuration, with the mainline fallback off:
  - HTTP on port 8080: `PUT`/`GET /pkarr/{z32-key}` and `/dns-query`.
  - HTTPS on port 8443, self-signed for `localhost`.
  - DNS over UDP and TCP on port 5300, for the origin `irohdns.example`.
  - Example query: `dig @127.0.0.1 -p 5300 TXT _iroh.<z32-key>.irohdns.example`. `target/debug/examples/convert endpoint-to-pkarr <endpoint-id>` prints the z32 form of an endpoint id.
  - Do not enable `[mainline]`: it needs the Internet.
- **Two endpoints.** With both servers above running, start a provider with `target/debug/examples/transfer provide --env dev`. In another shell, run `target/debug/examples/transfer fetch <ENDPOINT_ID> --env dev`.
  - The provider publishes its address through the local pkarr relay. The fetcher resolves it through the local DNS server and connects through the local relay, or directly over loopback.
  - `--relay-only` forces the relayed path. `--no-relay` with `--remote-direct-address` forces a direct one.

**NAT traversal labs.** `cargo nextest run --workspace --all-features --test patchbay --profile patchbay` builds virtual NATs, routers and lossy links in Linux user namespaces (`iroh/tests/patchbay/`, `iroh-dns-server/tests/patchbay.rs`). It runs real hole punching and relay fallback with an in-lab relay. There are 74 labs, covering NAT types, uplink switches and degraded links. Add a test there to reproduce a finding that needs a NAT or a second network. The labs need permission to create user namespaces, which a privileged container has.

## How you rate severity

A finding counts when an attacker in one of the positions above makes iroh misbehave through its documented API and default configuration. Say which position the attacker holds: a remote endpoint, a relay, an on-path or off-path network attacker, a DNS or pkarr source, a relay client, or a client of the DNS server. Findings against the defaults weigh more than ones that need a non-default option.

- **Critical**
  - Connecting to, or being accepted as, an `EndpointId` without its secret key. This includes any case where `Connection::remote_id()` reports a key the peer does not hold.
  - A relay or network attacker reading, modifying or injecting application data in an iroh connection.
  - Memory corruption or code execution in any crate.
- **High**
  - A remote endpoint, a relay or an unauthenticated network attacker crashing an `Endpoint` or its `Router` (a panic that ends it, an abort, a stack overflow), hanging it, or growing its memory or CPU without bound with cheap input.
  - A relay server crashed by a client or by an unauthenticated connection.
  - A relay client that disconnects, disrupts, impersonates or receives the traffic of another client.
  - A bypass of the relay's configured access control, or of a configured rate limit.
  - `iroh-dns-server` crashed, or made to serve or store a record that is not validly signed by the key it is published under.
  - `iroh-dns-server` storage or memory growing without bound from unauthenticated input.
  - An endpoint or relay made to send substantially more traffic to a third-party address than the attacker sent (reflection or amplification).
- **Medium**
  - Denial of service that needs a connection the victim application accepted and stays bounded to that connection.
  - A panic confined to one connection or task that does not end the endpoint or server.
  - Steering an endpoint onto a worse path (relay instead of direct, or a path the attacker chose) without breaking confidentiality.
  - Leaking an endpoint's addresses or id to parties the documentation says do not learn them.
  - Secret keys or access tokens written to logs at info level or above.
- **Low**
  - Problems that need a non-default option meant for trusted setups: the `test-utils` feature, `--dev`, `dangerous_http_only`, `SSLKEYLOGFILE` or keylogging.
  - Problems that need a malicious local config file or environment variable.
  - Panics caused by invalid arguments from the embedding application.
  - Secrets written to logs at debug or trace level.

A bug with no security consequence, such as a wrong metric, a stale doc or a test flake, is not a vulnerability. Do not report it.

## How to report

- Give a reproducer that runs in this image, offline. It can be a Rust test in the affected crate that uses the helpers above, or commands against `iroh-relay`, `iroh-dns-server` or the `transfer` example. Include the exact bytes or frames sent and what was observed. For resource exhaustion, give the measured memory, CPU or time and the input that caused it.
- Name the attacker position and any configuration that differs from the default.
- Propose a minimal patch against `main` with a regression test. Keep unrelated refactoring out of it, and run `cargo fmt`.
- Report one root cause once. If the same flaw is reachable over the relay and over a direct path, that is one finding that lists both paths.
- If the root cause is in noq or another n0 crate listed above, say so, and write the patch against that crate.

## Anything to leave alone

- 0-RTT data can be replayed. This is documented on `Connecting::into_0rtt` and `Accepting::into_0rtt`.
- Relays see client IP addresses, endpoint ids, and which endpoints exchange packets. Published pkarr and DNS records are public. Both are by design.
- Plain DNS TXT answers are not authenticated. Identity rests on TLS, so a forged address is a failure to connect, not an impersonation. Only bypassing pkarr signature checks matters.
- QAD observed-address reports are hints and are documented as untrusted.
- Any endpoint may connect to an endpoint that registers an ALPN. Deciding who is allowed is the application's job.
- That an endpoint dials a relay URL a remote advertised is not a finding by itself.
- The metrics endpoints of the relay and the DNS server have no authentication. They are meant for trusted networks.
- The relay ships with no rate limit and allows everyone unless configured. Flooding an unconfigured relay with traffic is not a finding. Getting past a configured limit or access policy is.
- `Limits::accept_conn_limit` and `accept_conn_burst` are documented as not implemented.
