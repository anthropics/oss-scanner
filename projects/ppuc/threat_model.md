# Threat model: ppuc

## What this project does and where untrusted input enters

ppuc holds the host applications of the PPUC (Pinball Power-Up Controller) stack. A PC or Raspberry Pi inside
a pinball cabinet runs the original game ROM under PinMAME (or a ROM-less script engine) and acts as the
machine's CPU, driving RP2040 IO boards over RS485 through `libppuc`. Three executables are built:

- `ppuc-pinmame` — the game runtime (`src/ppuc.cpp` and most of `src/`).
- `ppuc-menu` — an SDL3 launcher that starts a game from a menu file (`src/menu.cpp`).
- `ppuc-backbox` — a standalone display client for a second computer in the backbox (`src/backbox.cpp`).

The machine is an appliance: it usually runs unattended as a normal user on a home or arcade network, and the
operator installs game folders obtained from other people. Inputs, from least to most trusted:

1. **The network, `ppuc-backbox` only.** It starts a libdmdutil `DMDServer` on a TCP port (default 6789) and
   renders the frames it receives. Anything on the local network can connect. `ppuc-pinmame` is the client end
   (`--backbox-address`, `[Backbox]` in the INI). There is no other listening socket in this repository.
2. **The game folder** passed as `--game <dir>`. One folder per game, shared between owners and exported by
   the config tool, so treat every file in it as attacker-influenced data:
   - `io-boards.yaml` — hardware configuration; parsed by libppuc and again here for the GameCore sections
     (`src/game/GameConfigYaml.cpp`).
   - `rules/*.lua` — game rules, run by `src/LuaRulesEngine.cpp`. Rules are code, but they are meant to be
     confined: only the base, table, string and math libraries are opened and `dofile`/`loadfile` are removed,
     leaving the `ppuc.*` API (`src/LuaGameApi.cpp`). A rules file reaching the file system, starting a process,
     or corrupting memory through that API is a sandbox escape and is in scope.
   - attract slides and their YAML (`src/AttractSlidesLoader.cpp`), translite images, music files, and the
     per-game `ppuc.ini`.
   - `pinmame/roms`, `pinmame/nvram`, `pinmame/cfg` — consumed by PinMAME, and NVRAM contents are read back by
     `src/PinmameNvramTracking.cpp` using the JSON maps loaded by `src/PinmameNvramMapLoader.cpp`.
   - PUP packs, `.directb2s`, AltSound and AltColor/Serum files — consumed by third-party plugins and libraries.
3. **Firmware images.** `--firmware-path` names a directory of `.uf2` files; `src/Uf2Image.cpp` parses them and,
   only with `--allow-firmware-update`, the image is sent to a board. A crafted `.uf2` must not corrupt memory,
   and file-name parsing must not make the host flash an image onto the wrong board type.
4. **IO boards on the serial line.** Handled in libppuc (enrolled separately). In scope here is how ppuc uses
   what libppuc reports: switch numbers, board versions, types and statistics.
5. **Command line, the top-level INI, and the menu file — trusted.** These are written by the operator.
   `ppuc-menu` executing the `command` of a menu entry, and `ppuc-pinmame` running `poweroff` on request, are
   features.

## Components that matter most / least

- **Most:** `src/LuaRulesEngine.cpp`, `src/LuaGameApi.cpp`, `src/LuaArg.h`, `src/ScriptEngine.cpp`,
  `src/ScriptObject.cpp` (the Lua boundary); `src/game/` and `src/AttractSlidesLoader.cpp` (YAML from the game
  folder); `src/Uf2Image.cpp` and the firmware-update path in `src/ppuc.cpp`; `src/PinmameNvramTracking.cpp`,
  `src/PinmameNvramMapLoader.cpp`, `src/SegmentDigitDecode.cpp`; `src/backbox.cpp`.
- **Also in scope:** INI and game-folder path resolution in `src/ppuc.cpp` (path traversal out of the game
  folder), `src/PluginBus.cpp`, `src/PluginEngine.cpp`, `src/MediaPluginHost.cpp` (how data from plugins is
  handled on our side), audio (`src/AudioOutput.cpp`, `src/AudioMixer.cpp`, `src/AudioLanes.cpp`), `src/dmd/`,
  and thread-safety between the engine, rules, plugin and display threads.
- **Less important:** bench-test modes, speech front-ends (`src/*SpeechService*`), `tools/`, `platforms/`
  build and autostart scripts, `examples/`.
- **Out of scope:** everything under `external/`, `third-party/` and the packaged `ppuc/` directory. PinMAME,
  the vpinball plugins (PUP, B2S, AltSound, PinMAME), libdmdutil and its `DMDServer`, libzedmd, libserum, SDL3
  and its satellites, FFmpeg, Lua, yaml-cpp, flite and espeak-ng are other projects; a bug that lives entirely
  inside one of them should go to that project. It is in scope when ppuc hands such a library a wrong length,
  a dangling pointer or an unchecked value. `libppuc` and `libsdldmd` are ours but are separate repositories;
  `tests/` is test code.

## How to exercise it

- `/src/ppuc/` is the packaged release build: the three executables next to their runtime libraries,
  `plugins/` and `pinmame-nvram-maps/`. Binaries are linked with an `$ORIGIN` rpath and only run from there.
- `/src/build-debug/` is PPUC's own code rebuilt RelWithDebInfo with frame pointers, including the tests.
  Its three executables do not sit next to their libraries, so start them with
  `LD_LIBRARY_PATH=/src/ppuc`, for example `LD_LIBRARY_PATH=/src/ppuc build-debug/ppuc-pinmame --help`.
  Run `ctest --test-dir /src/build-debug`, or the doctest binary `build-debug/ppuc_tests` directly.
  `ppuc_plugin_smoke` drives `PluginBus` and `MediaPluginHost` headlessly against `tests/fakectl`; the image
  builds it best-effort, so check the binary exists before relying on it.
  `ppuc_tmwrp_coldstart` skips itself: it needs a ROM, and no ROMs or game folders are in the image.
- For a sanitizer build of the tests: `cmake -S /src -B /src/build-asan -DPLATFORM=linux
  -DARCH="$(cat /etc/ppuc-arch)" -DCMAKE_BUILD_TYPE=Debug -DENABLE_SANITIZERS=ON -DPPUC_BUILD_TESTS=ON
  -DPPUC_BUILD_MENU=OFF -DPPUC_BUILD_BACKBOX=OFF`, then build the `ppuc_tests` target. Dependencies are already
  staged, so this works offline.
- `tests/RulesFixture.h` and `tests/GameFixture.h` are the cheapest harnesses for Lua rules and GameCore
  YAML, and `tests/test_uf2_image.cpp` for firmware images.
- `examples/` has a rules file, an INI, a menu file and a game YAML. `ppuc-pinmame --help` lists every option;
  `-n` (no serial) runs without boards. There is no display or audio device in the image, so SDL needs
  `SDL_VIDEODRIVER=dummy` / `SDL_AUDIODRIVER=dummy`; full runs of `ppuc-menu` and `ppuc-backbox` may still not
  be possible there.
- `README.md`, `HANDBOOK.md` and `docs/` (start with `docs/STACK.md`) describe intended behaviour.

## How you rate severity

- **Critical:** memory corruption with plausible control, or code execution, reachable over the network in
  `ppuc-backbox`; a Lua rules file or any other game-folder data file achieving code execution outside the
  sandbox or writing files outside the game folder.
- **High:** any other memory-safety violation (out-of-bounds read or write, use-after-free, double free)
  reachable from game-folder files, a `.uf2` image, or data reported by a board. Any input that makes the host
  fire or hold a coil the ROM and rules did not ask for, or flash a board with an image not meant for its
  type — a physical-safety issue even without memory corruption. Reading files outside the game folder.
- **Medium:** denial of service from those inputs — crash, uncaught exception, hang, unbounded memory or CPU
  — and data races with an observable wrong result. Remote crash of `ppuc-backbox`.
- **Low:** issues that need a hostile command line, top-level INI or menu file; undefined behaviour with no
  demonstrated effect; information exposure in logs.

A sanitizer report with a reproducing input is enough; a working exploit is not required. Please name the
input class from the list above and attach the smallest file or byte sequence that triggers the problem.

## Anything to leave alone

- Lua rules can pulse coils, suppress switches and change game behaviour through `ppuc.*`. That is the purpose
  of the rules engine and not a finding; only escaping the confinement described above is.
- `ppuc-menu` running the commands in its menu file, and the `poweroff` call, are intended.
- The backbox link and the RS485 bus are unauthenticated and unencrypted by design; do not report the absence
  of authentication or TLS. Bugs in how received data is handled are welcome.
- The move onto the VPX plugin bus (`docs/PLUGIN_MIGRATION.md`) is in progress, so `src/PluginEngine.cpp` and
  `src/MediaPluginHost.cpp` change often; findings there are welcome but should name the commit they apply to.
- Proposed patches should follow `.clang-format`, add a doctest case under `tests/` where possible, and update
  `HANDBOOK.md` if they change anything an operator sees.
