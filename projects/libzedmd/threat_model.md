# Threat model: libzedmd

## What this project does and where untrusted input enters

libzedmd is the host-side communication library for ZeDMD, an open-hardware RGB LED dot-matrix display used in
real and virtual pinball machines. Applications such as Visual Pinball, libdmdutil and PPUC hand it frames;
it scales, splits them into zones, compresses them and streams them to the display over USB serial, WiFi or
SPI. Two command-line tools are built with it: `zedmd-client` (inspect and change a device's settings) and
`zedmd-test` (show test patterns). It is a C++ library with a C API (`src/ZeDMD.h`).

Inputs, from least to most trusted:

1. **The network, in WiFi mode** (`src/ZeDMDWiFi.cpp`). The library is always the client. `OpenWiFi(name)`
   resolves a host name (default `zedmd-wifi.local`) and talks to whatever answers: plain HTTP on port 80 for
   the handshake and settings (`/handshake`, `/get_*`, parsed by `ReceiveResponse`, `ReceiveIntegerPayload`,
   `ReceiveStringPayload` and the `|`-separated handshake parser), then TCP or UDP for frames. Anything on the
   local network that can answer for that name or address — a spoofed mDNS reply, a rogue device, a
   man-in-the-middle — controls every byte of those responses. Width, height, port, firmware version string,
   device type and delays all come from there and are used to size and index buffers afterwards.
2. **Bytes from the USB serial device** (`src/ZeDMDComm.cpp`). The library probes serial ports and reads a
   64-byte handshake plus acknowledgements. The peer is normally ZeDMD firmware, but any USB serial device that
   happens to be attached is probed too, and a compromised or faulty device can send anything. Panel width and
   height, the USB package size (`m_writeAtOnce`), and device type are taken from the handshake.
3. **SPI** (`src/ZeDMDSpi.cpp`, Raspberry Pi only, off by default via `SPI_SUPPORT`). Local hardware, trusted.
4. **The calling application — trusted.** Frames passed to `RenderRgb888()`/`RenderRgb565()` are assumed to
   match the size given to `SetFrameSize()`. Device paths, IP addresses, SSIDs and settings passed through the
   API or on the `zedmd-client` command line come from the operator.

The interesting failure is a mismatch between what the device or network peer *claims* (dimensions, package
size, zone layout) and what the application supplies, leading to an out-of-bounds read of the caller's frame
or an out-of-bounds write into the library's buffers.

## Components that matter most / least

- **Most:** the WiFi handshake and HTTP response parsing in `src/ZeDMDWiFi.cpp`; the serial handshake,
  acknowledgement handling and reconnect logic in `src/ZeDMDComm.cpp`; and the frame pipeline that those
  values feed — scaling, centring, zone splitting, compression and chunking in `src/ZeDMD.cpp` and
  `src/ZeDMDComm.cpp` (`QueueCommand`, the zone loop, `StreamBytes`, `SendChunks`).
- **Also in scope:** the worker thread and its queue (races and use-after-free around `Open`/`Close`/
  reconnect), fixed-size buffers for firmware version, SSID, device name and ID strings, and the C API wrappers.
- **Less important:** `src/client.cpp` and `src/test.cpp` argument handling (operator-supplied), logging,
  `Doxyfile`, the raw sample frames under `test/`.
- **Out of scope:** `external/` and `third-party/` — cargs, libserialport, sockpp, miniz and `FrameUtil.h` are
  other projects; a bug that lives entirely inside one of them should go there. The ZeDMD firmware is a
  separate repository. `src/ZeDMDSpi.cpp` is not compiled in this image.

## How to exercise it

- `/src/build/` has `libzedmd.so`, the static library, `zedmd-client` and `zedmd-test` with their runtime
  libraries copied beside them (RelWithDebInfo). `/src/build-san/` is the same under AddressSanitizer and
  UBSan. `zedmd-client --help` lists every option.
- **There is no automated test suite and no device in the image.** `zedmd-test` needs real hardware.
- The WiFi path needs no hardware: the scan container has a loopback interface, so a small fake device (a
  script serving HTTP on port 80 and accepting TCP or UDP on the port it advertises) is enough.
  `zedmd-client --ip-address 127.0.0.1 --info` then drives the handshake and settings parsers, and a few
  lines against the API with `OpenWiFi("127.0.0.1")` plus `RenderRgb888()` drive the frame path. The expected
  responses are whatever `ZeDMDWiFi::DoConnect()` parses; there is no separate protocol document here.
- The serial path can likely be driven the same way through a pseudo-terminal passed to `SetDevice()` (or
  `zedmd-client --port`); the maintainers have not tried this.
- `test/rgb565_*` and `test/rgb888_*` hold raw frames in the sizes the library handles.
- To rebuild after a change: `cmake --build build` (dependencies are staged; there is no network).

## How you rate severity

- **Critical:** memory corruption with plausible control (out-of-bounds write, use-after-free, double free)
  reachable from network responses in WiFi mode.
- **High:** any other memory-safety violation reachable from network responses; memory corruption reachable
  from serial-device bytes; an out-of-bounds read of the caller's frame buffer caused by peer-supplied
  dimensions.
- **Medium:** denial of service from either peer — crash, uncaught exception (the handshake uses `std::stoi`),
  hang, infinite reconnect loop, unbounded memory growth — and data races with an observable wrong result.
  Out-of-bounds reads reachable only from the serial device.
- **Low:** issues that need a hostile command line or a caller that breaks the documented API contract,
  undefined behaviour with no demonstrated effect, information exposure in logs.

A sanitizer report with a reproducing byte sequence or response is enough; a working exploit is not required.
Please say which transport reaches the bug.

## Anything to leave alone

- All three transports are unauthenticated and unencrypted, and the WiFi password is sent to the device over
  plain HTTP when the operator sets it. This is known and follows from what the firmware supports; do not
  report the absence of TLS or authentication. Bugs in how responses are handled are welcome.
- `RebootToBootloader`, `Reset`, `SaveSettings` and the settings setters change the device on request. That
  is their purpose.
- Timing constants, delays, keep-alive intervals and USB package sizes are tuned against real panels and
  firmware. Do not propose patches that change them or add round trips to the frame path.
- Proposed patches should follow `.clang-format` and must not change the wire format, which the firmware shares.
