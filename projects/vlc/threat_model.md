# VLC 3.0.x threat model

This enrollment covers the maintained `3.0.x` branch, not VLC 4.0/master and
not older release tags.

VLC is a desktop media player and, through libVLC, a library embedded in other
applications. Nearly all of its input is processed by native code, often before
anything is displayed. Treat media bytes, container metadata, elementary
streams, subtitles, playlists, artwork, archives, URLs, protocol replies,
discovery packets, and control-interface requests as hostile whenever they can
come from outside the process.

## Trust boundaries and data flow

```text
access -> stream filter/extractor -> demux/probe -> packetizer
       -> decoder -> audio/video/subtitle filters -> output
```

Most stages are plugins under `modules/`. `src/` is libvlccore, `lib/` is the
public libVLC API, and `include/` holds their contracts. Plugins are probed,
opened, driven through function pointers, and closed; ownership and
asynchronous teardown across those steps are security-relevant.

Entry paths, roughly from most to least exposed:

- A file, URL, or stream the user opens. Probing, metadata preparsing,
  attachment extraction, and some decoding happen before playback, whatever
  the file extension.
- Playlists and media-library items, whose URLs can trigger later local-file
  or network access, redirects, credential forwarding, or protocol selection.
- External and embedded subtitles, fonts, images, album art, and attachments.
  Subtitles next to a media file load automatically by default.
- Lua scripts that run automatically: the playlist parsers in
  `share/lua/playlist/` on every matching URL, and the art fetchers in
  `share/lua/meta/art/` once metadata network access is allowed. Both parse
  hostile web replies through the C bindings in `modules/lua/libs/`.
- Hostile network peers reached through HTTP, RTP, MMS, SRT, RIST, SAT>IP,
  SMB/NFS/SFTP, VNC, UPnP, mDNS, or adaptive streaming. Use loopback servers
  inside the image; never contact third-party systems.
- Optional HTTP/Lua/RC/telnet control interfaces. An interface the operator
  enabled is not an authentication bypass by itself; look for crossing the
  configured authentication, origin, filesystem, or command boundary.
- Skins and extensions chosen by the user: lower reachability, but archive
  extraction, path containment, and parser memory safety still matter.
- Stream output, transcoding, capture devices, and hardware interfaces, which
  need explicit trusted configuration.

libVLC callers must pass valid pointers, lengths, lifetimes, and callbacks as
documented. A crash that needs the embedding application to break that
contract is API misuse; a hostile media item that makes VLC itself construct
the invalid state is in scope.

## Audit priorities

- `modules/demux/`, especially MP4, Matroska, AVI, Ogg, MPEG-TS/PS, ASF, image,
  subtitle, adaptive-streaming, and playlist parsers, including seeking,
  metadata, and attachments.
- `modules/packetizer/` and `modules/codec/`: channel and plane counts, coded
  versus visible dimensions, packet reassembly, codec configuration changes,
  drain/flush paths, and subtitle/caption state.
- `modules/access/`, `modules/access_output/`, `modules/stream_filter/`,
  `modules/stream_extractor/`, and `modules/services_discovery/`: short reads
  and writes, reconnect and redirect state, URL/header construction,
  credentials, teardown, and data sent back to a peer.
- `src/input/`, `src/network/`, `src/playlist/`, `src/misc/`, and
  `src/stream_output/`: shared allocation, picture/block ownership, URI and
  option parsing, callbacks, cancellation, and module lifetime. One core
  defect here often explains several apparent module crashes.
- `modules/lua/`: the C bindings in `libs/` receive strings, streams, XML,
  and variables derived from hostile replies; the playlist, meta, extension,
  and interface hosts in the same directory run the scripts.
- `modules/meta_engine/`, text rendering, `modules/gui/skins2/`, and the
  updater in `src/misc/`: metadata adapters cross library integer widths,
  skins unpack archives, and the update/signature path is an integrity
  boundary.

Code shared with the official Windows, macOS, iOS/tvOS, and Android builds is
in scope even when this Linux image cannot reach it: Direct3D, VideoToolbox,
Android, sandbox, installer, GPU, optical-disc, DVB-CAM, and other device
paths.

Lower priority: `test/`, `doc/`, `po/`, the third-party recipes and patches
under `contrib/`, and the build helpers under `extras/` other than the shipped
installer and packaging code in `extras/package/`. A crash confined to a test
harness or build helper is not a VLC vulnerability.

## Historical patterns and deduplication

The VLC 3.0 security bulletins (for example `VideoLAN-SB-VLC-3024`) show
recurring families: arithmetic in a narrower type before allocation or copy;
count, stride, channel, or plane mismatches between parser, core object, and
consumer; sizes and offsets trusted before a complete bounds check; stale
pointers after reallocation, callbacks, flush, seek, reconnect, or teardown;
partial I/O and error paths reusing stale state; uninitialized slack reaching
stream output or a peer; and names, URIs, playlist options, or protocol fields
crossing a filesystem or command boundary. Use `git log -S`, `git log -G`,
`NEWS`, and nearby regression tests to confirm a root cause is not already
fixed at the scanned head.

Inputs that reach the same bad arithmetic, ownership transition, or core helper
are one finding; a shared crash site with independent corrupting roots is not
a duplicate.

## Build and reproduction environment

The checkout with full git history is at `/src`; everything below works
offline. No build passes `--enable-debug`, so `assert()` is compiled out as in
release builds: an assertion would otherwise stop a run before the memory
error that shipped binaries reach.

- `/src/build`: release-like Clang build with debug information and frame
  pointers, enabling the media, network, Qt, and skins2 code, built with
  `--enable-run-as-root`. Use it to confirm behavior without sanitizer
  allocator effects.
- `/src/build-asan`: the same dynamic-plugin build, compiled with GCC and
  AddressSanitizer. The player is `/src/build-asan/vlc`; the deterministic
  demux drivers are `/src/build-asan/test/vlc-demux-run` and
  `/src/build-asan/test/vlc-demux-dec-run`.
- `/src/build-fuzz`: static ASan/libFuzzer build of VLC's own demux and
  demux-plus-decoder harnesses, limited to the explicit module list in
  `test/src/input/demux-run.c` and `test/Makefile.am`.
- `/src/fuzz-corpus/seeds/<target>` and `/src/fuzz-corpus/dictionaries/`: the
  public VideoLAN corpus, one directory per demux target. Use it for real
  inputs; most files under `test/samples/` are empty placeholders.

`/src/build-asan` also runs UBSan's bounds, shift, integer-divide-by-zero,
pointer-overflow, and VLA-bound checks; signed overflow is excluded because
timestamp arithmetic trips it constantly. A UBSan report prints once per
site and the run continues; ASan aborts on its first error. There is no MSan
or TSan tree. `ASAN_OPTIONS` makes oversized allocations return NULL instead
of reporting them, disables leak detection, and symbolizes traces; a failed
allocation must not corrupt memory. Neither sanitizer sees an overrun that
stays inside one allocation, such as the 32-byte padding around a
`block_Alloc` payload or a picture's planes sharing one buffer; `bounds`
covers fixed-size arrays only, so prove those from source and address
arithmetic.

The builds link distro libraries, which are not instrumented and differ from
the contrib versions in official packages. RealRTSP is disabled, the 3.0.x
default; the live555 RTSP client is not built because Debian trixie does not
ship it; the updater in `src/misc/` is Windows-only code, so review it by
reading.

Replay a file through one demuxer and its elementary-stream decoders:

```sh
VLC_TARGET=mp4 VLC_DEMUX_CONTROLS=1 \
  /src/build-asan/test/vlc-demux-dec-run /path/to/input
```

Omit `VLC_TARGET` to let VLC probe, set `V=1` for libvlc messages, and use
`vlc-demux-run` when decoder activity would obscure a demux root. The drivers
set their own build-tree plugin and data paths. A driver result proves that
harness path, not player reachability; confirm in the headless player:

```sh
timeout 30s /src/build-asan/vlc -I dummy --vout dummy --aout dummy \
  --no-video-title-show --play-and-exit /path/to/input
```

Bounded mutation of a built-in target:

```sh
mkdir -p /tmp/vlc-mp4-corpus
VLC_TARGET=mp4 /src/build-fuzz/test/vlc-demux-dec-libfuzzer \
  -fork=1 -ignore_ooms=1 -ignore_timeouts=1 \
  -max_total_time=300 -timeout=10 -rss_limit_mb=4096 \
  -dict=/src/fuzz-corpus/dictionaries/mp4.dict \
  /tmp/vlc-mp4-corpus /src/fuzz-corpus/seeds/mp4
```

Fork mode skips out-of-memory and timeout artifacts, which are resource
exhaustion, while a crash still stops the run and leaves a `crash-*` file.
`vlc-demux-libfuzzer` excludes decoders. A plugin missing from the static
harness is not unreachable: use the ASan replay driver, the player, or a small
libVLC API harness against `/src/build-asan`. The upstream suite is
`make -C /src/build check`, with focused tests under `test/`. `xvfb-run -a`
starts the Qt interface when a UI path must be exercised. Device and
external-network tests cannot run in this offline image; a skipped path is
not a safe one.

## Report format

Write the report as a VideoLAN triage write-up, in this order. No CVSS score:
severity is one label from the section below.

- **Summary**: one paragraph on what hostile input makes VLC do.
- **Mechanism**: the faulty code with `file:line` references at the scanned
  commit, and what the check, arithmetic, or ownership step gets wrong.
- **Input**: the fields the attacker controls, the minimal trigger values,
  and a negative control that differs minimally and stays clean.
- **Reach**: the path from the entry point to the fault, every option or
  default it depends on, what is not sufficient on its own, and anything this
  image lacks that the finding needs: a platform build or backend, a device,
  an external network, RealRTSP, live555, or the Windows-only updater.
- **Impact boundary**: what the evidence proves and what it does not. An
  out-of-bounds write, use-after-free, or corrupted pointer is not proof of
  code execution, and an out-of-bounds read is not a leak unless bytes reach
  an attacker-visible sink.
- **How to reproduce**: a short standard-library Python 3 script that writes
  the input deterministically, or the libFuzzer crash input minimized with
  `-minimize_crash=1`; the build directory and the exact offline command,
  with `VLC_TARGET` where a harness is used; and the control run.
- **Stack trace**: the complete AddressSanitizer report from
  `/src/build-asan`, verbatim from the `ERROR` line through `ABORTING`, with
  every frame, the allocation and free stacks, and the shadow bytes, plus any
  UBSan `runtime error` lines from the same run. When ASan is silent, a
  natural crash in `/src/build` captured under gdb with the full backtrace,
  or a Valgrind Memcheck run with `--track-origins=yes` that shows
  uninitialized data reaching a sink, each with its control run. A breakpoint
  showing a line can execute is not a crash.
- **Suggested fix**: a minimal patch against the scanned `3.0.x` code rather
  than master alone, in the surrounding style, reusing the branch's
  checked-arithmetic and allocation helpers, rejecting malformed data before
  mutating live state, and keeping the libVLC ABI and plugin behavior for
  valid inputs. Say whether it was built, whether the proof of concept stops
  reproducing, and what regression coverage it needs.

## Severity

Rate demonstrated standalone impact at realistic reachability, not the
strongest way a separate bug could use the primitive. An opt-in trusted
`--sout`, capture, device, or control configuration lowers reachability unless
an untrusted peer can then cross a boundary.

- **Critical**: demonstrated code execution from hostile content or an
  unauthenticated peer; compromise of the update/signature chain; or a
  comparably complete privilege-boundary break.
- **High**: demonstrated significant memory disclosure, credential or data
  exfiltration, authentication/origin bypass, arbitrary write outside an
  intended sandbox or extraction root, or strongly controlled memory
  corruption with a credible exploitation path on a default-reachable surface.
- **Medium**: confirmed OOB access, UAF, double free, uninitialized
  disclosure, or allocation overflow reached by hostile input without
  demonstrated high impact, especially when the user must open the item or
  enable the feature; also a persistent crash loop driven by remotely
  delivered library content, or a bug that blocks security updates. These
  still need prompt private triage.

There is no lower tier: anything below Medium falls under "Do not report".
VideoLAN decides the final label, embargo, advisory, and CVE handling; do not
promise them.

## Do not report

- an issue already fixed at the scanned `3.0.x` head, or a VLC 4.0/master-only
  code path;
- a NULL dereference, divide-by-zero, assertion failure, ordinary crash,
  bounded leak, hang, or other resource exhaustion, including libFuzzer
  out-of-memory and timeout artifacts and a NULL dereference after a failed
  or oversized allocation, with no memory corruption or other security
  boundary; the only exceptions are the crash-loop and update-blocking cases
  under Medium;
- a bug in a distro library merely because the image links it (`contrib/` holds
  VLC's recipes and patches, not upstream source), unless VLC's adapter,
  configuration, patch, or usage is the root;
- crashes that need impossible internal objects, invalid caller-owned lengths
  or lifetimes, a harness defect, or a static function called in a state
  production VLC cannot create;
- the documented operation of an explicitly configured RC, HTTP, telnet,
  stream output, capture, or renderer feature;
- harmless rejection, incorrect rendering, conformance differences, warnings,
  or sanitizer diagnostics with no release-build security consequence;
- RCE claims based only on heap adjacency, ASan redzones, a synthetic
  neighboring pointer, or chained unproven primitives.

Keep testing local and bounded: a minimal crash, disclosure, write primitive,
or boundary-crossing proof is enough. Do not build portable or weaponized
exploits.
