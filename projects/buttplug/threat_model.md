# Threat model

## What this project does and where untrusted input enters

Buttplug is a Rust framework for controlling intimate hardware (vibrators, strokers, e-stim, etc.).
A **Server** manages **Hardware Managers** (Bluetooth LE via btleplug, serial, Lovense HID/serial
dongles, SDL gamepads, the Lovense Connect app, and a WebSocket device bridge), matches discovered
hardware to one of ~150 vendor **Protocols**, and translates abstract commands from a **Client**
into device-specific byte sequences. `intiface_engine` wraps the server into a runnable service
with WebSocket, REST, repeater and mDNS front ends. The library is also embedded in-process by
apps such as Intiface Central. `CONTEXT.md` in the repository defines the vocabulary used here.

Untrusted input enters in these places:

- **Client connections.** The Buttplug JSON protocol (spec versions v0 through v4, see
  `crates/buttplug_core/src/message/` and `crates/buttplug_server/src/message/`) arrives over the
  WebSocket server in `crates/buttplug_transport_websocket_tungstenite` and
  `crates/intiface_engine`. By default it listens on 127.0.0.1, but
  `--websocket-use-all-interfaces` exposes it to the LAN. There is deliberately no authentication
  and no Origin check: browser-based apps connect to it directly. Treat every message, including
  the handshake and messages in older spec versions that go through the downgrade/upgrade
  conversion code, as hostile. Panics, unbounded allocation, out-of-range feature/device indices,
  integer overflow in value scaling, and anything that lets a client send a device bytes outside
  what the protocol implementation intends are in scope.
- **Devices.** Hardware is untrusted. A BLE peripheral in radio range can advertise any name,
  service UUID or manufacturer data and so be identified as any supported protocol. Everything a
  device sends back (notifications, reads, battery and sensor input, Lovense dongle serial/HID
  frames, serial port responses) is parsed in `crates/buttplug_server/src/device/protocol_impl/`
  and the `crates/buttplug_server_hwmgr_*` crates and must be treated as hostile.
- **Lovense Connect** (`crates/buttplug_server_hwmgr_lovense_connect`, off by default). It polls
  `https://api.lovense.com/api/lan/getToys`, then makes plain HTTP requests to whatever LAN host
  and port that response names. Responses from both the Lovense API and the LAN host are
  untrusted. Being steered into requests to arbitrary hosts, and parsing problems in either
  response, are in scope.
- **Device WebSocket server** (`crates/buttplug_server_hwmgr_websocket`, off by default). Lets
  devices or device emulators connect inbound and identify themselves. The connecting peer is
  untrusted.
- **REST API** (`crates/intiface_engine/src/rest_server.rs`, opt in, bound to 127.0.0.1) and the
  **repeater** (`repeater.rs`), which forwards WebSocket traffic. Same expectations as client
  connections.
- **Configuration.** The built-in device configuration in `crates/buttplug_server_device_config`
  is trusted. The user device configuration file is semi-trusted: frontends write it, but it is
  also edited by hand and shared between users, so crashes or memory issues from parsing a
  malformed file are in scope at a lower severity. Command-line arguments are trusted.

## Components that matter most / least

- Most important: message parsing, validation and spec-version conversion in `buttplug_core` and
  `buttplug_server` (`server.rs`, `server_message_conversion.rs`, `message/`); the device manager
  and per-device command handling in `buttplug_server/src/device/`; the protocol implementations
  that parse device input; the WebSocket transport; `intiface_engine` network front ends.
- Also in scope: the hardware managers (especially the `unsafe` code in
  `buttplug_server_hwmgr_lovense_dongle` and `buttplug_server_hwmgr_sdl_gamepad`), user device
  configuration parsing, `buttplug_client` handling of server responses (a client connecting to
  a malicious server must not crash or misbehave beyond returning errors).
- Less important: the in-process client connector, mDNS advertisement, logging.
- Out of scope: `crates/buttplug_wasm` and `crates/buttplug_server_hwmgr_webbluetooth` (wasm32
  only, not built in this image), `wasm/`, `examples/`, `crates/buttplug_tests` (test harness),
  `docs/`, `plans/`, `scripts/`, and third-party crates unless Buttplug uses them unsafely.

## How to exercise it

- Everything is pre-built in `/src/target/debug`, including the `intiface-engine` binary. Rebuild
  offline with `cargo build --offline --locked`.
- There is no Bluetooth or USB hardware in the container. Use **Simulated Devices** (configured
  in the user device configuration file) or the test device harness in
  `crates/buttplug_tests/tests/util/device_test/` to drive protocol implementations, including
  feeding them crafted device input.
- Start an engine with a WebSocket server, for example
  `./target/debug/intiface-engine --websocket-port 12345 --log debug`, and connect with any
  WebSocket client to send raw Buttplug JSON. `--help` lists the hardware manager and front end
  switches.
- Tests: `cargo test --offline --locked`. `crates/buttplug_tests/tests/` covers the client,
  message downgrades, device protocols and the device configuration.

## How you rate severity

- **Critical:** memory corruption or code execution reachable by a network peer (a WebSocket
  client when listening on all interfaces, the device WebSocket server, Lovense Connect
  responses) or by an unpaired BLE device in radio range.
- **High:** the same reachable only from localhost or from a user device configuration file; a
  client or device causing commands to be sent to a device other than the one targeted, or
  values outside the range the protocol implementation and user configuration allow (for example
  bypassing a user's configured output limits); Lovense Connect being steered into requests
  against arbitrary hosts.
- **Medium:** panics, hangs or unbounded memory growth triggered by a client message or device
  input (these take down the whole engine, and all connected devices with it); information leaks
  to a client beyond the device list it is entitled to.
- **Low:** the same issues reachable only through trusted configuration or command-line options;
  log injection.

## Anything to leave alone

- Lack of authentication, TLS or Origin checking on the client WebSocket server is by design.
  Any local process or web page can connect and control devices. Do not report this on its own.
- Do not report that a BLE device can impersonate another device model; identification is based
  on advertisement data by design. Do report what a malicious device can do once identified.
- Do not report panics in code that only runs in tests or examples.
