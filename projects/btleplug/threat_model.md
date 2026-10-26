# Threat model

## What this project does and where untrusted input enters

btleplug is a cross-platform Rust Bluetooth Low Energy (BLE) GATT central library. One async
API (`src/api/`) covers scanning, connecting, service and characteristic discovery,
reads, writes and notifications, with a backend per platform: BlueZ over D-Bus on Linux
(`src/bluez/`), CoreBluetooth on macOS/iOS (`src/corebluetooth/`), WinRT on Windows
(`src/winrtble/`), and JNI into Java on Android (`src/droidplug/`). Applications such as the
Buttplug intimate hardware library use it to talk to whatever devices happen to be nearby.

Untrusted input enters in these places:

- **Anything a BLE peripheral sends.** Any device in radio range is untrusted, before and after
  connection. That covers advertisement data (local name, manufacturer data, service data,
  service UUIDs, TX power, RSSI), the GATT database it reports during discovery (services,
  included services, characteristics, descriptors, properties, handles), characteristic and
  descriptor values from reads, notification and indication payloads, MTU and connection
  parameter values, and disconnects at arbitrary points mid-operation. Treat all of it as
  hostile. The platform stack (BlueZ, CoreBluetooth, WinRT, Android) delivers it, but btleplug
  converts and stores it (`src/advertisement.rs`, `src/common/`, each backend's `peripheral.rs`
  and `adapter.rs`, `src/bluez/` conversion of D-Bus properties via bluez-async).
- **FFI boundaries.** `src/corebluetooth/` (objc2 delegate callbacks, `ffi.rs`, `utils/`) and
  `src/droidplug/` (`jni/`, `jni_utils/`) contain `unsafe` code that marshals device-controlled
  data (byte arrays, strings, UUIDs) between the platform runtime and Rust, and moves callbacks
  across threads. Memory safety, lifetime, and thread safety problems there are the most
  important class of bug in this project.
- **Application calls.** The calling application is trusted, but the public API must not allow
  undefined behaviour from safe Rust, whatever the arguments or call ordering (for example
  operations racing a disconnect, or concurrent discovery and reads on the same peripheral).

## Components that matter most / least

- Most important: `src/droidplug/` and `src/corebluetooth/` (unsafe FFI handling device data),
  advertisement and GATT value handling in every backend, `src/common/adapter_manager.rs` and
  the event stream plumbing that every backend shares.
- Also in scope: `src/bluez/` and `src/winrtble/` conversion of platform types, `src/api/`
  (BDAddr and UUID parsing), `src/serde.rs`.
- Less important: logging and `Debug` implementations, examples.
- Out of scope: `test-peripheral/` (Zephyr firmware for the hardware test rig), `tests/android/`,
  `scripts/`, the Java sources under `src/droidplug/java/` except where Rust relies on their
  behaviour, and third-party crates (bluez-async, dbus, jni, objc2, windows) unless btleplug uses
  them unsafely.

## How to exercise it

- This is a Linux image with no Bluetooth adapter and no BlueZ daemon, so only the Linux code
  paths compile, and nothing can reach a real device. CoreBluetooth and WinRT code can only be
  reviewed, not run.
- Debug builds are in `/src/target/debug`. Rebuild offline with `cargo build --offline --locked`
  (add `--all-features` for serde and JNI host tests).
- Unit tests: `cargo test --offline --locked`.
- JNI host tests: `./scripts/run-jni-tests.sh` compiles the plain-Java support classes with the
  installed JDK and runs `src/droidplug/jni_utils` tests against a host JVM
  (`cargo test --features jni-host-tests -- --test-threads=1`). This is the way to exercise the
  Android JNI marshalling code here.
- The integration tests in `tests/` (one binary per test, all `#[ignore]`) need the Zephyr test
  peripheral in `test-peripheral/` and cannot run in this image. Their bodies in
  `tests/common/test_cases.rs` document what the peripheral sends.

## How you rate severity

- **Critical:** memory corruption or code execution in the host process triggered by a BLE
  peripheral, connected or merely advertising.
- **High:** undefined behaviour reachable from safe Rust through the public API; a peripheral
  causing data or events to be attributed to a different peripheral, characteristic or
  application subscription.
- **Medium:** panics, deadlocks, or unbounded memory growth triggered by a peripheral (for
  example oversized or malformed advertisement data, a hostile GATT database, notification
  floods, or disconnects mid-operation).
- **Low:** the same issues reachable only through unusual application call patterns; log
  injection from device names.

## Anything to leave alone

- BLE devices can claim any name, address or service UUIDs; btleplug does not authenticate
  peripherals, and pairing and link-layer security are the platform stack's responsibility. Do
  not report device spoofing on its own.
- Do not report bugs inside BlueZ, CoreBluetooth, WinRT or the Android Bluetooth stack.
