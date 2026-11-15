# FFmpeg threat model

FFmpeg is the multimedia framework behind most players, converters, browsers and
streaming services. Everything it reads is attacker controlled: media files and
streams, container metadata, elementary streams, subtitles, fonts, playlists,
URLs, protocol replies and network peers. Treat every byte of input as hostile.

## Trust boundaries

```text
protocol (libavformat/) -> demuxer -> parser / bitstream filter
  -> decoder (libavcodec/) -> filters (libavfilter/, libswscale/, libswresample/)
  -> encoder -> muxer -> protocol
```

Trusted: the command line, AVOptions, filter graphs and everything else the
operator or the calling application chooses, and the documented API contract
(valid pointers, ownership, threading rules). A crash that needs the caller to
break that contract is API misuse, not a vulnerability.

Untrusted: the input data at every stage, and anything derived from it. In
particular a playlist, an index or a manifest may reference other files and
URLs; opening those is governed by the `protocol_whitelist`, `safe` and
`allowed_extensions` options and their checks are a security boundary.

## Audit priorities

- `libavformat/`: demuxers (MOV/MP4, Matroska, AVI, MPEG-TS/PS, ASF, Ogg, FLV,
  RealMedia, the image and subtitle formats), the protocols (HTTP, HLS, DASH,
  RTSP/RTP, RTMP, TLS) and URL, header, redirect and seek handling.
- `libavcodec/`: decoders, parsers and bitstream filters. Dimension, channel,
  plane and bit depth changes, reference frame management, packet reassembly,
  slice and tile bounds, and the bit readers and entropy decoders they share.
- `libavfilter/`, `libswscale/`, `libswresample/`: frame geometry and format
  negotiation, and arithmetic on dimensions and sample counts.
- `libavutil/`: allocation size arithmetic, `AVBuffer` reference counting,
  `av_image_*` and `av_samples_*` layout helpers, parsing helpers.
- `fftools/`: handling of hostile input, not of hostile arguments.

Lower priority but in scope: encoders fed with hostile frames, muxers, devices.

Out of scope: external libraries (`--enable-lib*`), `doc/`, `tests/` and the
fuzzers in `tools/`. The hardware acceleration code is in
scope but cannot run here, as no hardware is present. The x86 assembly under
`*/x86/` is in scope; it runs only in the `build-asm` build below and is not
instrumented by the sanitizers.

## Severity

An out of bounds write, use after free or double free reachable from input is
high, critical when code execution is demonstrated. An out of bounds read or a
read of uninitialized memory is medium: either can be part of an ASLR bypass.
Assertion failures need reporting as well; the extra assertions are enabled so
that a violated invariant surfaces before the memory error it leads to. A null
pointer dereference or infinite loop is low. Leaks, timeouts, large allocations
and other denial of service are normal bugs, not security issues.

A finding is invalid if it needs a raised `max_alloc`, a build with
`--disable-safe-bitstream-reader`, or input buffers with less padding than the
API requires.

## Reporting

Do not provide unvalidated claims; reproduce and validate each finding. Be
concise. Clearly separate the issues you replicated from what you inferred.
Before reporting, check that no pull request already fixes the issue: if
present, `refs/pull/*/head` holds the head of every pull request, open and
closed, and `git log --glob='refs/pull/*' ^master -- <file>` lists their
commits touching a file.

A report contains:

- A reproducible test case, ideally something to copy and paste directly, such
  as an ffmpeg command line together with an attached multimedia input file.
  Give attached files unique names.
- An unambiguous source identifier (git commit hash). If you think it
  replicates with other versions, add that information.
- Stack traces with line numbers.
- An analysis of the issue, only if you understand and have validated it.
  Distinguish the root cause from symptoms or workarounds.
- The commit that introduced the vulnerability, if known.
- A script generating the input, if available.
- A fully tested and reviewed fix in the style of `doc/developer.texi`, with
  test cases that anchor every aspect of it: if the fix adds, removes or
  changes a specific part of the code, a test case should break if that change
  is not done. Fixes are minimal, easy to review and backportable. A fix must
  not break anything; verify it with `make fate`.

## Build layout and how to exercise it

Three builds share the checkout, all with `clang-19`, AddressSanitizer,
UndefinedBehaviorSanitizer fatal except for its pointer overflow check, `-O1 -g3`
and `--assert_level=2`; `$CONFIGURE_FLAGS` holds their common configure flags
and `$LIBRARY_FLAGS` the external libraries.

- `/src` is the in tree build of the tools and libraries without the assembly,
  so that every C implementation is the one exercised. `/src/ffmpeg` and
  `/src/ffprobe` are the tools. `/src/fate-suite` holds the FATE samples, if
  present; `make fate-list` names the tests, `make fate-<name>` runs one,
  `make fate` runs all of them, and `tests/data/fate/<name>.err` keeps the
  stderr of a failed test.
- `/src/build-asm` is the same build with the assembly enabled, as shipped on
  x86-64. Use it to reproduce in or around the assembly and to confirm that a
  finding is reachable with it; `make fate-checkasm` there compares every
  assembly function against its C version, and
  `tests/checkasm/checkasm --test=<name>` runs one group.
- `/src/build-fuzz` is an `--enable-ossfuzz` build without the assembly and
  with libFuzzer instrumentation. `tools/target_dem_fuzzer`, `target_io_dem_fuzzer`,
  `target_sws_fuzzer` and `target_swr_fuzzer` are prebuilt there. A target for
  one component is built on demand, named after the lower case component name
  in `config_components.h`, for example:

```sh
cd /src/build-fuzz
make tools/target_dec_h264_fuzzer
make tools/target_dem_mov_fuzzer
make tools/target_bsf_h264_mp4toannexb_fuzzer
make tools/target_enc_mpeg4_fuzzer
tools/target_dec_h264_fuzzer -max_len=1000000 ../fate-suite/h264-conformance/
```

After changing code run `make -j$(nproc)` in whichever of the three directories you use.
The scanner has no network; the protocols are exercised with loopback peers
only.
