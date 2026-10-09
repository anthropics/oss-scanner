# Threat model: libppuc

## What this project does and where untrusted input enters

libppuc is the host-side C++20 library of the PPUC (Pinball Power-Up Controller) stack. A PC or Raspberry Pi
inside a pinball cabinet runs the game and uses libppuc to configure and drive up to eight RP2040 IO boards
over one shared, half-duplex RS485 pair (115200 baud). Those boards switch the machine's coils, lamps and
general illumination, so a wrong output is a hardware-safety matter, not only a software one.

It is a library with no network code and no privileged operation. It has two inputs:

1. **The game configuration (YAML).** `PPUC::LoadConfiguration(path)` in `src/PPUC.cpp` parses a game's
   `io-boards.yaml` with yaml-cpp, validates it, and derives the dense bitmap mappings and the config frames
   sent to the boards. Game folders are downloaded and shared between machine owners, so treat this file as
   attacker-influenced: a hostile or merely malformed file must be rejected with an error, never crash the
   process, corrupt memory, or produce an out-of-range device, port or board index.
2. **Bytes arriving on the serial port.** `src/RS485Comm.cpp` decodes v2 frames (`0xA5` sync, 5-byte header,
   payload, CRC-16/CCITT-FALSE): config acks, switch-state replies, and admin replies (version report, stats
   report, firmware-update acks). The peer is normally our own firmware, but the bus is a long unshielded cable
   next to solenoids, any board can be faulty or run foreign firmware, and frames arrive truncated, corrupted
   or replayed. Every length, board number, switch number, bitmap size and sequence/epoch field taken from the
   wire is untrusted. A CRC only proves the frame was not damaged in transit, not that its contents are sane.

The caller (`ppuc-pinmame`, in `github.com/PPUC/ppuc`) is trusted. Arguments passed through the public API in
`src/PPUC.h` are not a trust boundary, with one exception: device numbers reach `SetSolenoidState`,
`SetLampState`, `SetGIState`, `SetSwitchState` and `TriggerEvent` from an emulated ROM and from Lua rules, so
an out-of-range number there must not index out of bounds.

## Components that matter most / least

- **Most:** frame receive and decode in `src/RS485Comm.cpp` (switch reply chain, config ack, admin channel and
  firmware-update transfer), and YAML loading, validation and mapping derivation in `src/PPUC.cpp`.
- **Also in scope:** the background update thread and its shared state (queues, runtime bitmaps, session
  epoch/resync) — data races and use-after-free around `Connect`/`Disconnect`/`StartUpdates`/`StopUpdates`.
- **Less important:** debug and log output, `tools/check-schema-drift.py` (a developer and CI script).
- **Out of scope:** everything under `external/` and `third-party/` — libserialport, yaml-cpp and doctest are
  upstream projects; please report bugs in them upstream. The files under `third-party/include/io-boards/` are
  staged from `github.com/PPUC/io-boards`, which owns the wire format; a flaw in the protocol *design* belongs
  there, but libppuc mishandling a frame is in scope here. `src/Adafruit_NeoPixel.h` only supplies constants.

## How to exercise it

- `build/` holds `libppuc.so`, `libppuc.a` and the doctest binary `ppuc_tests` (RelWithDebInfo).
  `build-asan/ppuc_tests` is the same suite under AddressSanitizer and UBSan. Run either directly or with
  `ctest --test-dir build` / `ctest --test-dir build-asan`.
- `tests/ConfigFixture.h` shows the cheapest harness for the YAML path: write a document to a temporary file
  and call `PPUC::LoadConfiguration()`. `tests/test_config_validation.cpp` has a minimal valid configuration
  to mutate.
- There is no hardware in the image and no ready-made harness for the transport. The serial device is whatever
  path is passed to `PPUC::SetSerial()` before `Connect()`, opened through libserialport, so a pseudo-terminal
  pair with a scripted board on the other end is the likely way in; this has not been tried by the maintainers.
  `tests/test_protocol_conformance.cpp` and `third-party/include/io-boards/PPUCProtocolV2.h` define the frames.
- To rebuild after a change: `cmake --build build` (dependencies are already staged; there is no network).

## How you rate severity

- **Critical:** memory corruption (out-of-bounds write, use-after-free, double free) reachable from bytes on
  the serial line or from a YAML file, where control of the corruption is plausible.
- **High:** any other memory-safety violation reachable from those two inputs (out-of-bounds read, an
  uncontrolled overflow). Also any input that makes the host energize an output it was not asked to, hold a
  coil on, or send a board a config or firmware image other than the intended one — this is a physical-safety
  issue even with no memory corruption.
- **Medium:** denial of service from those inputs — crash by uncaught exception, assertion or null
  dereference, an infinite loop, unbounded memory growth, a hang in the update thread or in `Disconnect()`.
  Data races with an observable wrong result.
- **Low:** issues that need the trusted caller to misuse the API, undefined behaviour with no demonstrated
  effect, and information exposure through debug output.

A sanitizer report alone is enough for a finding; a working exploit is not required. Please say which of the
two inputs reaches the bug and give the smallest YAML document or byte sequence that triggers it.

## Anything to leave alone

- The protocol has no authentication or encryption, does not validate sequence numbers, and does not
  acknowledge output frames. These gaps are known (see `docs/V2_PROTOCOL.md` section 12 in the `ppuc`
  repository), and anyone with physical access to the bus owns the machine anyway. Do not report their absence.
- Timing constants and bus throughput trade-offs are tuned against real hardware. Do not propose patches that
  add round trips, retries or delays to the runtime loop.
- A configuration that is valid but electrically unwise for a given machine (for example a long coil pulse)
  is the operator's responsibility, not a vulnerability.
- Proposed patches should follow `.clang-format` and come with a doctest case under `tests/`.
