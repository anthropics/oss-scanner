# Waybar: threat model and severity guide

Waybar is a status bar for Wayland compositors (Sway, Hyprland, niri, river, dwl, wayfire, mango and
other wlroots-based ones), written in C++20 on GTK3/gtkmm. It runs as the desktop user, for the whole
session, and renders data coming from the compositor, D-Bus services, system daemons, the kernel and
user scripts. Many of those strings originate from other programs or from remote parties (window
titles set by web pages, media metadata, Wi-Fi SSIDs, Bluetooth device names), and most are rendered
as Pango markup.

## What this project does and where untrusted input enters

The user's configuration (`config.jsonc`, `style.css`, and the files it `include`s) is **trusted**:
it can run arbitrary shell commands by design (`exec`, `on-click`, `custom/*` modules). Everything
below is in scope.

- **Strings from other clients, rendered as Pango markup**: window titles and app ids
  (`src/modules/sway/window.cpp`, `src/modules/hyprland/window.cpp`, `src/modules/niri/`,
  `src/modules/wlr/taskbar.cpp`, `src/modules/river/`, `src/modules/dwl/`), MPRIS metadata
  (`src/modules/mpris/`), MPD tags (`src/modules/mpd/`), tray items (see below), and remote names
  such as Wi-Fi SSIDs (`src/modules/network.cpp`, `src/util/netlink.cpp`) and Bluetooth device
  aliases (`src/modules/bluetooth.cpp`). Escaping before markup, format-string handling (`fmt`/`format`
  replacement) and the `rewrite` regex rules are the key paths. A web page controls its tab title and
  therefore the browser window title; a nearby access point or Bluetooth device controls its name.
- **System tray (StatusNotifierItem / dbusmenu)**: `src/modules/sni/` talks to any process on the
  session bus. Icon pixmaps (width, height, raw ARGB bytes), icon names and theme paths, tooltips,
  titles and the dbusmenu layout are all attacker-controlled by a local unprivileged app.
- **Compositor IPC**: Sway IPC (`src/modules/sway/ipc/`), Hyprland socket events
  (`src/modules/hyprland/backend.cpp`), niri (`src/modules/niri/backend.cpp`), and Wayland
  protocol events (`src/modules/wlr/`, `src/modules/ext/`, `src/modules/river/`,
  `src/modules/dwl/`). Message framing, lengths, JSON parsing and the event-string splitting are in
  scope; the compositor itself is trusted, but the data it relays (titles, workspace names, class
  names) is not.
- **Other D-Bus services**: UPower, power-profiles-daemon, logind, systemd, gamemode, ModemManager
  (`wwan`), privacy (PipeWire nodes). Replies are parsed with GVariant; type confusion and missing
  type checks are in scope.
- **Kernel and sysfs/procfs**: `src/modules/battery.cpp`, `backlight*.cpp`, `temperature.cpp`,
  `cpu*`, `memory/`, `disk.cpp`, netlink in `network.cpp` and `src/util/netlink.cpp`. Parsing
  errors are lower priority since these sources are mostly trusted, except netlink scan results
  carrying SSIDs.
- **Custom module output**: `src/modules/custom.cpp` and `custom_graph.cpp` parse the stdout of user
  scripts (text or JSON with `text`, `tooltip`, `class`, `percentage`). The script is trusted, but
  it often relays untrusted data, so crashes on malformed or huge output are in scope.
- **Process handling**: `include/util/command.hpp` (fork/exec, pipes, signal handling), and
  `src/main.cpp` / `src/client.cpp` (signals, reload, output hotplug). File-descriptor leaks into
  child processes and races at teardown are in scope.

## Components that matter most / least

- Most important: markup escaping and format handling for externally controlled strings, the tray
  (`sni/`), the compositor IPC parsers, `custom.cpp`, and object lifetime on reload, output
  hotplug and exit (`bar.cpp`, `client.cpp`, `AModule.cpp`, the module destructors). Waybar has a
  history of use-after-free and crash-on-exit bugs in these teardown paths.
- Lower priority: `test/`, `man/`, `resources/`, `package/`, `nix/`, `Dockerfiles/`.
- Out of scope: the Meson subprojects in `subprojects/` (libcava, fmt, spdlog, date, catch2,
  gtk-layer-shell, jsoncpp) and system libraries, except for Waybar-specific misuse of them.

## How to exercise it

Two builds are prepared, both with every optional module enabled:

- `/src/build`: gcc, debugoptimized. Unit tests (Catch2): `meson test -C /src/build --suite waybar
  --print-errorlogs`. They cover config parsing and `include`s (`test/config.cpp`), utilities
  (`test/utils/`) and the Hyprland backend (`test/hyprland/`).
- `/src/build-asan`: ASan + UBSan + `_GLIBCXX_ASSERTIONS`. Use
  `LSAN_OPTIONS=suppressions=/src/asan.supp` to silence known leaks in GTK, Pango and fontconfig.
- End to end: `test/smoke/` runs the real binary in a headless sway (`WLR_BACKENDS=headless`,
  `WLR_RENDERER=pixman`). For example:

  ```
  export WAYBAR_BIN=/src/build-asan/waybar
  ./test/smoke/run.sh test/smoke/config.jsonc test/smoke/style.css /tmp/bar.png
  ./test/smoke/fuzz.sh        # custom module fed empty / invalid JSON / huge / non-UTF8 output
  ./test/smoke/lifecycle.sh   # SIGINT, output hotplug, reload churn
  ```

  `test/smoke/lib.sh` shows how to start the compositor and assert on sanitizer reports. A
  `custom/*` module with `exec` pointing to a script is the easiest way to feed arbitrary strings
  through the formatting and markup paths. For the tray, a small program registering a
  StatusNotifierItem on a `dbus-run-session` bus is enough.

## How we rate severity

- **Critical**: memory corruption or code execution triggered by remote input with no user action,
  for example a crafted SSID or Bluetooth name, or a web page title, reaching a write out of bounds
  or a use-after-free.
- **High**: memory corruption, use-after-free or double free reachable from a local unprivileged
  client (tray item, window title, MPRIS player, compositor-relayed data); injection of arguments or
  shell syntax into a command Waybar executes when the injected text comes from an untrusted source.
- **Medium**: crash or hang of the bar (denial of service) from untrusted strings or D-Bus/IPC
  messages; Pango markup injection that changes what the bar displays (spoofing) without memory
  corruption; unbounded memory growth from repeated events.
- **Low**: crashes that need a malformed user configuration, malformed sysfs/procfs content, or a
  misbehaving compositor; leaks at exit; issues in tests, docs or packaging.

## Please avoid reporting

- Anything that requires control of the user's config or style files, including commands run by
  `exec`, `on-click` and similar options; this is intended behavior.
- Leaks reported only at process exit, and leaks inside GTK, Pango, fontconfig or GLib
  (see `asan.supp`).
- Bugs in subprojects or system libraries that are not caused by how Waybar calls them.
- Style, build warnings, missing tests or missing documentation.

## Patches and reproducers

- Include the exact config (`config.jsonc`, and `style.css` when relevant), the command or script
  that produces the input, and the full ASan/UBSan output from `/src/build-asan/waybar`.
- Keep patches minimal and in the existing style (`.clang-format`, C++20, gtkmm). Add a Catch2 test
  under `test/` when the bug is in a pure function, or a case in `test/smoke/` when it needs the
  running bar.
- Run `meson test -C /src/build --suite waybar` before proposing a patch.
