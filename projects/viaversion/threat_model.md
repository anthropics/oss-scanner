# Threat model

## What this project does and where untrusted input enters

ViaVersion translates the Minecraft network protocol between versions, so that newer clients
(and with ViaBackwards, older ones) can join a server on another version. It runs on Paper servers
(`bukkit/`, `bukkit-legacy/`) and Velocity proxies (`velocity/`), and other projects embed it as a
library. Every packet goes through `UserConnectionImpl.transform`, one protocol per version step.

**In scope: serverbound (client to server) packets.** Anyone who can open a TCP connection
controls every byte of them, starting with the handshake that picks the protocol path. Status and
login come before authentication, and offline-mode servers let anyone reach play state.
ViaVersion handles these packets before the server's own validation. The platform's frame decoder
caps the size of one packet, so measure amplification against that cap.

**Out of scope: clientbound packets**, even when ViaVersion runs client-side (ViaFabricPlus,
ViaProxy) against a third-party server. Also trusted: `config.yml`, the mapping data under
`common/src/main/resources/assets/viaversion/data/`, plugins calling the API, and the platform's
own pipeline.

## Components that matter most / least

The issues that matter most:

- **Massive allocations from a small packet:** a client-supplied length or count that sizes an
  array, collection or buffer before the bytes behind it are checked (see
  `ArrayType.checkLength`).
- **Getting past the packet limiter** (`UserConnectionImpl.checkServerboundPacket`,
  `PacketTracker`): one client packet that ViaVersion turns into many serverbound packets or a lot
  of work, for example through `PacketWrapper.sendToServer`, `scheduleSendToServer` or
  passthrough packets, which the limiter does not see.
- **Stalling on massively complex data:** deeply nested or huge NBT, text components, item data
  components, book pages, recipes or command data, parsed or converted without the limits that
  newer versions apply. This runs on the event loop or server thread, so seconds of CPU per
  packet are server-wide. `TagType` applies ViaNBT's `TagLimiter`; check what happens after it,
  in item and component rewriting (`rewriter/`, the 1.20.5+ structured components), text
  conversion (mcstructs `text`) and hashing (`codec/hash/`).
- **Unbounded caches that a client can fill:** per-connection storages (`StorableObject`s,
  trackers in each protocol's `storage/` package) and static maps without a cap or eviction.

ViaNBT (`com.viaversion:nbt`) and the mcstructs `text` fork (`com.viaversion.mcstructs`, from
ViaVersion/mcstructs-viafier) are maintained by the same team. Bugs in them that serverbound
packets reach through ViaVersion are in scope; report them here and name the library.

Out of scope: test code, `build-logic/`, commands, the dump upload and the update checker.
`.github/` matters only where untrusted input runs with a token that can write or read secrets.

The older the server version, the less it matters. Exploits that stem from the server's own
protocol (e.g. pre-1.21.5 container clicks and item handling) are the server's problem. Some
packets go through larger loops in ViaVersion, but the server's own checks kick the client right
after ViaVersion's handlers. Those only matter if the work ViaVersion does before the kick is
itself a stall or a large allocation. Creative-mode set slot packets matter less than clients
without special permissions, and creating arbitrary items there is allowed by vanilla.

## How to exercise it

Gradle runs offline in the image, and the tests have already passed there. Run one with
`./gradlew :viaversion-common:test --tests '<class>'`.

- Type level: `Types.ITEM1_13_2.read(Unpooled.wrappedBuffer(bytes))`, as in
  `common/src/test/.../type/ItemTypeTest.java`.
- Protocol level: extend `PlatformTestBase` (it loads every protocol and its mappings), create a
  connection with `ViaChannelInitializer.createUserConnection(new EmbeddedChannel(), false)`, set
  its versions and state in `getProtocolInfo()`, add the protocols from
  `ProtocolManager.getProtocolPath(clientVersion, serverVersion)` to its pipeline, and pass the
  crafted packet (VarInt id, then the fields) to `transformServerbound`.
- Show the cost in numbers: bytes sent against bytes allocated or retained, or time per packet
  against the packet limiter's default of 800 packets per second.

## How you rate severity

Rate what one client can do to the server with the default `config.yml`.

- Critical: code execution, or reading or acting on another player's connection. Making the whole
  server unavailable (out of memory, or the server thread or a shared event loop stalled for
  seconds) with a few packets before login, where no account is needed.
- High: the same server-wide impact from a player in play state.
- Medium: large but bounded amplification, growth that is freed on disconnect but matters with
  many connections, kicking other players, and creative-only paths.
- Low: hardening without a demonstrated impact.

## Reports and patches

Include a reproducer: a unit test, or the packet bytes with the client and server versions. Patch
against the default branch, for Java 17 and only the Netty 4.0 API (old platforms ship Netty
4.0.x). Keep the `api/` module compatible, add no dependencies, and follow the surrounding style.
Fix the code that applies the mapping data, not the data files. Where practical, add a small test
under `common/src/test/`.

## Anything to leave alone

- Clientbound-only paths.
- A malformed packet that throws and disconnects only its sender. That is the intended error
  handling.
- Wrong translation without a security impact (visual glitches, lost data, desyncs).
- What the vanilla server of the same version or the platform (Paper, Velocity, ...) does without
  ViaVersion, unless ViaVersion adds the cost or lets data past a limit that vanilla enforces.
- Configuration that turns protections off. `packet-size-limiter` is off by default by choice.
