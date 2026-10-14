# Threat model: gopacket

## What this project does and where untrusted input enters

gopacket is a Go library that decodes network packets. Callers hand it raw bytes
read from a capture file, a live interface or any other source, and it turns them
into typed protocol layers (Ethernet, IPv4/IPv6, TCP, UDP, DNS, GTP, SCTP, and
about 150 others). It also reassembles TCP streams and defragments IPv4 and IPv6.

Every byte that reaches a decoder is untrusted. The typical caller is a packet
sniffer, an intrusion detection system or a network monitor that reads traffic
from the wire or from a user-supplied pcap file. An attacker on the network, or
one who can get a capture file opened, controls the input completely.

The library is expected to handle hostile input by returning an error or marking
the layer as a decode failure. It must never panic, loop forever, read out of
bounds or allocate an amount of memory that the attacker controls.

## Components that matter most

In order of importance:

1. `layers/`: the protocol decoders. This is where almost all parsing happens and
   where almost all historical bugs have been. Variable-length fields, option
   lists, nested TLVs and length fields taken from the packet are the usual
   suspects.
2. `reassembly/` and `tcpassembly/`: TCP stream reassembly. State is kept per
   flow, so an attacker who can open many flows or send out-of-order segments can
   try to exhaust memory or CPU. Buffer limits exist but are off by default, so
   a caller that does not set them is exposed.
3. `ip4defrag/` and `ip6defrag/`: IP fragment reassembly. Same concerns as above,
   plus overlapping and oversized fragments.
4. `pcapgo/`: pure-Go readers and writers for pcap and pcapng files. File headers
   and per-record lengths come from the file.
5. `pcap/` and `afpacket/`: cgo and raw-socket capture backends. Bugs here can
   cross the Go/C boundary. These need a privileged process and a live interface
   to exercise, so a reproducer that only works with root is still in scope but
   harder to demonstrate.

Out of scope or low priority:

- `examples/` and `dumpcommand/`: demo programs, not library code.
- `pfring/`: needs the PF_RING userspace library and is not built in this image.
- `bsdbpf/`: BSD only, not built on Linux.
- Anything that requires the caller to pass its own malformed data structures
  rather than malformed packet bytes.

## How to exercise it

- `go test ./...` runs the suite. The decoders are table-driven: most tests in
  `layers/` take a byte slice and compare the decoded layers.
- The quickest way to reach a decoder with arbitrary bytes is
  `gopacket.NewPacket(data, layers.LayerTypeEthernet, gopacket.Default)`, or the
  specific `LayerType` for the protocol under test. `gopacket.Default` recovers
  panics into a decode failure layer; pass `gopacket.DecodeOptions{SkipDecodeRecovery: true}`
  to make a panic visible.
- `gopacket.NewDecodingLayerParser` is the zero-allocation path. It recovers
  panics into an error by default; set `IgnorePanic` on the parser to see them.
- The DNS and sFlow decoders already have Go fuzz targets. Adding a fuzz
  harness around a decoder you suspect is a good way to produce a reproducer.
- Reassembly can be driven with `tcpassembly.NewAssembler` fed by synthetic
  TCP layers; no network is needed.

## How we rate severity

- Out-of-bounds read or write, use-after-free or memory corruption in cgo code
  reachable from packet bytes: **high**. **Critical** if it is shown to be
  controllable.
- A panic (index out of range, nil dereference, slice bounds) in a decoder:
  **medium**. Both decode paths recover panics by default, so the caller keeps
  running, but a decoder that panics instead of returning an error is a bug and
  we want the report. Raise to **high** if the panic escapes recovery or if it
  takes down a long-running capture process in the default configuration.
- Unbounded allocation or an infinite loop driven by a length field in one
  packet: **medium**. **High** if the amplification is large (kilobytes of
  input to gigabytes of memory) or if it also affects the default decode path.
- Resource exhaustion in reassembly that needs many packets or many flows from
  the attacker: **medium** by default. **Low** if the caller has set the
  assembler's buffer limits and the report only shows the cap being reached.
- Incorrect decoding that silently produces wrong field values: **low** unless
  it lets an attacker hide traffic from a security tool, in which case
  **medium**.
- Anything that needs the caller to misuse the API (wrong layer type, unsafe
  reuse of a buffer after the documentation says not to): **informational**.

## What a good report looks like

- A Go test, or a short `main` package, that feeds a byte slice into a public
  API and shows the panic, the hang or the memory growth. Hex bytes inline are
  fine.
- Name the package and the function where the fault happens.
- A patch is welcome. Keep it to the decoder at fault: add a length check and
  return an error, do not restructure the decoder.
- Please do not change exported function signatures in a proposed patch. The
  library has many downstream users and we do not accept breaking changes.

## Things to leave alone

- Deliberately permissive decoding: many decoders accept truncated trailing
  data and mark the layer as truncated rather than rejecting the packet. That
  is intended.
- Checksum verification is opt-in and off by default. A packet with a wrong
  checksum decoding successfully is not a bug.
- The zero-copy and `NoCopy` options document that the caller must not modify
  the input buffer. Reports that rely on violating that contract are not bugs.
- Race conditions in test helpers or examples.
