# Threat model: DPDK

Policy: doc/guides/contributing/vulnerability.rst
Coding and patch rules: AGENTS.md, doc/guides/contributing/

## What DPDK is

DPDK is a set of libraries and poll mode drivers for user space packet
processing. Applications (routers, firewalls, load balancers, vSwitches,
packet brokers) link it and run a busy-polling data path on dedicated
cores. The process usually runs as root or with CAP_NET_ADMIN/CAP_IPC_LOCK,
owns the NIC through VFIO, and maps hugepage memory shared with the device
and with secondary processes. A crash or hang of a data path core takes
down the service.

## Trust boundaries

Untrusted:

* Packet contents received from the network. Any software that parses,
  reassembles, merges, splits, classifies, encrypts or decrypts packet data
  must handle arbitrary bytes. This includes:
  - lib/net (ptype parsing, header length, checksum helpers)
  - lib/ip_frag (IPv4/IPv6 reassembly, fragment tables)
  - lib/gro, lib/gso
  - lib/ipsec (inbound ESP, anti-replay), lib/pdcp, lib/security
  - lib/node graph nodes that parse headers
  - lib/pdump, lib/pcapng, lib/bpf when run on packet data
  - lib/hash, lib/acl, lib/lpm, lib/fib, lib/rib, lib/member when keys come
    from packet headers (the tables themselves are trusted)
  - software parsing on the Rx side of drivers/net (virtual PMDs, tunnel
    and ptype parsing done in software)
  - cryptodev and compressdev input data: ciphertext, AAD, digests,
    compressed streams (drivers/crypto/{openssl,ipsec_mb,null,scheduler},
    drivers/compress/{isal,zlib})
* The guest side of vhost (lib/vhost, drivers/net/vhost, drivers/vdpa,
  examples/vhost*). The virtio driver in a VM or container controls the
  vrings, descriptor chains, indirect tables, guest physical addresses,
  lengths, the virtio-net header, control queue commands and vhost-crypto
  requests. A guest must not be able to read or write host memory outside
  the regions it was given, crash or hang the vhost process, or leak mbufs.
* vhost-user and VDUSE protocol messages from the front-end
  (lib/vhost/vhost_user.c, lib/vhost/vduse.c). The front-end may be a
  compromised QEMU or an unprivileged container. DPDK has issued CVEs for
  vhost-user message handling in the past.
* VF to PF mailbox messages when DPDK runs as the PF host
  (drivers/net/intel/ixgbe/ixgbe_pf.c, drivers/net/intel/i40e/i40e_pf.c,
  ice DCF, bnx2x vfpf). The VF may be owned by a hostile guest.
* The memif client, when DPDK is the memif server (drivers/net/memif,
  role=server). The client controls the shared regions, rings,
  descriptors, region index, offset and length. A client must not be able
  to make the server read or write outside the shared regions, return an
  invalid mbuf, or crash or hang the server process.

Trusted:

* Hardware: NIC, crypto, compress, DMA, event and baseband devices and
  their firmware. Values the device writes (descriptor lengths, completion
  entries, admin queue replies, parse results, RSS hash) are trusted.
  A bug that needs a malicious device is not a vulnerability.
* The hypervisor when DPDK is the guest: virtio (drivers/net/virtio,
  drivers/crypto/virtio), vmxnet3, netvsc/vmbus, Hyper-V, and the virtio-net
  header supplied by the host. Confidential computing (TDX, SEV-SNP) where
  the host is the adversary is out of scope.
* The kernel: tap, af_packet, af_xdp metadata, VFIO, uio, hugetlbfs.
* The memif server, when DPDK is the memif client (role=client, the
  default). The client has to trust the server. Missing validation of
  what the server writes is a bug, not a vulnerability.
* Primary and secondary processes of the same application (EAL multi
  process channel, shared hugepage memory), including dpdk-pdump,
  dpdk-dumpcap and dpdk-proc-info.
* The application and its configuration: EAL command line, devargs and
  kvargs, environment, config files parsed by lib/cfgfile, rte_flow rules,
  ACL/LPM/FIB/hash table contents, crypto keys and sessions, BPF programs
  and pcap filter strings, telemetry clients (the socket is protected by
  file system permissions on the runtime directory).

## API contract

* Data path APIs trust their arguments for performance. rx/tx burst,
  ring, mempool, mbuf, hash lookup, crypto enqueue and similar calls do not
  validate pointers, queue ids, counts or mbuf metadata; see "Mbuf
  contract". A crash from inconsistent arguments or mbuf metadata supplied
  by the application is not a vulnerability. It is in scope when DPDK
  itself derived the bad value from untrusted input (e.g. header lengths
  computed by rte_net_get_ptype, nb_segs overflowing in gro or
  reassembly). Report it against the code that derived the value, not the
  code that later consumed it.
* Control path misuse (bad config, NULL where not allowed, wrong order of
  calls, invalid devargs) is a bug, not a security problem. Report these
  as ordinary bugs at LOW at most.

## Mbuf contract

Earlier scans blamed the consumer of an invalid mbuf instead of the code
that produced it. Read this before reporting anything that involves an
mbuf.

Two things are distinguished:

* Mbuf metadata: buf_addr, buf_len, data_off, data_len, pkt_len, nb_segs,
  next, refcnt, pool, l2_len/l3_len/l4_len, tso_segsz, ol_flags,
  packet_type.
* Packet data: the bytes the metadata points to.

A valid mbuf is one rte_mbuf_check() accepts: sane pool, buffer address
and refcnt; data_off and data_off + data_len within buf_len for every
segment; the chain has exactly nb_segs segments; pkt_len equals the sum
of data_len.

Rules:

1. Received packet data is never trusted. Anything that processes
   receive data must validate it strictly. This is where findings are
   wanted. Examples:
   - lib/ip_frag reassembly: fragment offset and length, overlapping and
     duplicate fragments, total length beyond 65535, IPv6 extension
     header chains, fragment count and nb_segs limits, table exhaustion.
   - lib/gro: IP total length versus pkt_len, TCP data offset, sequence
     and length arithmetic, tunnel nesting, merged pkt_len and nb_segs
     limits.
   - lib/net ptype and header parsing, lib/ipsec and lib/pdcp inbound,
     lib/node, software Rx parsing in drivers.
   Such code must handle truncated or partial headers, a header split
   across segments, and length fields that exceed data_len or pkt_len or
   disagree with each other. Every read must be bounded by the mbuf
   metadata, not by what the packet claims. These libraries may trust
   the metadata of the mbufs they are given, but nothing inside the
   packet.

2. Producers must emit valid mbufs. A driver must not return from rx
   burst an mbuf with wrong nb_segs, pkt_len or data_len, a broken chain,
   or data outside the buffer. The same applies to libraries that build
   or modify mbufs: vhost dequeue, ip_frag reassembly and fragmentation,
   gro merge, gso split, ipsec and pdcp processing.
   - Hardware drivers may assume the device returns valid results
     (descriptor lengths, completion entries, segment counts). An invalid
     mbuf that needs the device or firmware to misbehave is not reported.
   - Virtual drivers with a trusted peer (virtio, vmxnet3, netvsc, tap,
     af_packet, af_xdp, memif in the client role) may trust the peer in
     the same way. Only the framing the peer supplies is trusted; the
     packet bytes still fall under rule 1.
   - Virtual drivers with an untrusted peer (vhost facing a guest, memif
     in the server role) must validate everything the peer supplies:
     lengths, offsets, region and descriptor indexes, chain length. An
     invalid mbuf or an out-of-bounds access caused by the peer is a
     vulnerability.
   - In any driver or library, invalid metadata caused by packet
     contents, packet size or packet sequence is a vulnerability.

3. Tx trusts the mbuf. tx burst and tx prepare may assume the mbufs they
   are given are valid, that l2_len/l3_len/l4_len/tso_segsz describe the
   packet, and that the headers those lengths cover are present.
   Validation is the caller's job. A Tx path that crashes or reads out
   of bounds on an invalid mbuf is not a vulnerability and not a finding.

4. Blame the producer, never the consumer. When an invalid mbuf passes
   from one component to another, the only defect is in the component
   that created or corrupted it. Example: a guest makes net_vhost return
   an mbuf with bad nb_segs or data_len, the application forwards it,
   and net_af_xdp Tx reads out of bounds. That is one finding, against
   vhost. af_xdp is correct and must not be reported, even though the
   crash or ASan trace is in af_xdp. If no producer inside DPDK can be
   identified (only the application or a trusted device or peer could
   have created the mbuf), there is no finding.

5. Offload flags. A driver should ignore ol_flags it does not support or
   that were not enabled at configure time. An application should not
   set them. Either side getting this wrong is a bug, not a security
   issue. The same holds for a driver setting Rx flags (checksum good,
   RSS hash valid, timestamp valid) incorrectly.

Debug-only checks are not validation. These compile to nothing unless
the named macro is defined, and no meson build type defines them; they
are off in /src/build, in /src/build-asan and in production:

* __rte_mbuf_sanity_check() in lib/mbuf (RTE_LIBRTE_MBUF_DEBUG)
* Tx mbuf and offload checks in drivers (RTE_ETHDEV_DEBUG_TX)
* RTE_ASSERT() (RTE_ENABLE_ASSERT)

So:

* Never conclude that an mbuf is valid at some point because
  __rte_mbuf_sanity_check() or RTE_ASSERT() is called there. The call
  does nothing in these builds. Do not treat such a check as a
  mitigation when deciding whether a bug on a receive path is reachable.
* Do not report that such a check is missing in release builds, and do
  not report a debug-only panic as a denial of service.
* Their absence on a Tx or consumer path is by design (rules 3 and 4).
* rte_mbuf_check() is always compiled in; use it in a reproducer to show
  that the mbuf was already invalid when the producer returned it.

## Components that matter most / least

Highest: lib/vhost, lib/net, lib/ip_frag, lib/gro, lib/gso, lib/ipsec,
lib/pdcp, lib/mbuf (chain handling), drivers/net/vhost, drivers/net/memif
in the server role, PF mailbox handlers, software crypto and compress
drivers on the decrypt/decompress side.

Medium: lib/node, lib/pdump, lib/pcapng, lib/bpf (interpreter and JIT on
packet data), lib/reorder, lookup libraries on packet-derived keys, software
packet handling in drivers/net, drivers/vdpa.

Low: examples/ (sample code, not production; ipsec-secgw, ip_reassembly and
l3fwd parse packets and may show library bugs, report the library bug),
app/ (testpmd, test-*, dumpcap, proc-info, graph), lib/cmdline,
lib/telemetry, lib/cfgfile, EAL argument parsing.

Out of scope: app/test, dts/, buildtools/, devtools/, usertools/, doc/,
kernel/, out-of-tree drivers, stable branches that are end of life.

## How to exercise it

* /src/build: gcc debugoptimized, all buildable drivers and examples.
  /src/build-asan: clang ASan + UBSan (alignment and function checks off),
  debug, virtual and software drivers only (hardware drivers are trusted
  and cannot run here). Confirm memory-safety findings with
  /src/build-asan.
* No hugepages and no NICs in the scanner. Always pass
  `--no-huge -m 512 --no-pci`, and use virtual devices:
  - net_pcap feeds a crafted capture through the Rx path:
    `--vdev net_pcap0,rx_pcap=in.pcap,tx_pcap=/tmp/out.pcap`
    (scapy is installed for writing pcaps)
  - net_ring, net_null for loopback and Tx paths
  - net_vhost + net_virtio_user over a unix socket for vhost; a hostile
    guest is best modelled with a small C program or a patched
    virtio_user that writes bad descriptors
  - net_memif role=server with a small C program acting as a hostile
    client
* When a reproducer forwards between two ports (vhost Rx to another
  driver's Tx, pcap Rx through gro to Tx), the faulting frame shows where
  the bad mbuf was used, not where the bug is. Find the producer: call
  rte_mbuf_check() on what rx burst or the library returned.
* testpmd: `/src/build-asan/app/dpdk-testpmd -l 0-1 --no-huge -m 512
  --no-pci --vdev ... -- -i`; forwarding modes csum, io, rxonly; `set
  verbose 1` decodes packets via rte_net_get_ptype; `set port 0 gro on`,
  `set gso segsz`, `csum` commands reach gro/gso.
* Unit tests: `/src/build-asan/app/test/dpdk-test --no-huge -m 512
  --no-pci` then the test name (ipfrag_autotest, reassembly_autotest,
  ipsec_autotest, pdcp_autotest, cksum_autotest, net_ipv6_autotest,
  mbuf_autotest, pcapng_autotest, bpf_autotest, ...), or
  `meson test -C /src/build --suite fast-tests`.
* Examples: /src/build/examples/dpdk-ip_reassembly,
  dpdk-ipsec-secgw, dpdk-l3fwd with net_pcap vdevs.
* Library reproducers: small C programs linked against
  `pkg-config --libs libdpdk` from the build directory
  (PKG_CONFIG_PATH=/src/build-asan/meson-uninstalled).

## How we rate severity

Rate by who can trigger it and what they get. State the entry point, the
required configuration (offloads, devargs, which library the application
must call) and whether a default build is affected.

* CRITICAL: memory corruption likely to give code execution, reachable by
  a remote packet in a common configuration; guest to host escape through
  vhost (write outside guest memory regions into the host process).
* HIGH: out-of-bounds write, use-after-free or double free reachable from
  packet data, from a guest or from a memif client without a demonstrated
  exploit; guest or memif client able to read host process memory; a
  single packet, a guest or a memif client causing crash, infinite loop or
  livelock of a data path core; a driver or library producing an invalid
  mbuf (bad nb_segs, lengths or chain) from any of those sources;
  per-packet mbuf or memory leak that lets a remote sender exhaust a
  mempool.
* MEDIUM: out-of-bounds read with limited disclosure; DoS that needs a
  high packet rate, non-default offloads or a rarely used library; packet
  data leaking between flows or queues; PF mailbox issues limited to the
  attacking VF.
* LOW: anything only in examples/ or app/; control path bugs; bugs that
  need application misuse of the data path API; undefined behaviour
  without demonstrated impact; leaks on error paths of setup code;
  offload flag handling (a driver acting on an unsupported or not enabled
  flag, or setting an Rx flag incorrectly).

## How we would like reports and patches

* One issue per report. Reproducer as a pcap plus the exact testpmd or
  dpdk-test command line, or a small C program; include the ASan/UBSan
  output from /src/build-asan and the commit tested.
* Patches against main as a git format-patch, following
  doc/guides/contributing/patches.rst and coding_style.rst: subject
  `component: short description`, a short plain commit message stating
  the bug and the fix, `Fixes: <12 char sha> ("subject")` and
  `Cc: stable@dpdk.org`. Minimal, no unrelated cleanups.
* Fix at the point where the untrusted value is first parsed rather than
  adding checks at each use. For an invalid mbuf that is the Rx driver or
  library that produced it. Do not add argument or mbuf checks to Tx or
  other data path functions; that is not a fix.
* A unit test in app/test is welcome when practical.

## Anything to leave alone

* Missing argument validation in data path APIs.
* Missing validation of mbuf metadata or headers in tx burst, tx prepare
  or any library that consumes mbufs. Report the producer of the invalid
  mbuf only.
* Debug-only checks (RTE_LIBRTE_MBUF_DEBUG, RTE_ETHDEV_DEBUG_TX,
  RTE_ASSERT) being absent from release builds.
* Requests to make drivers check offload flags per packet.
* Bugs that need a malicious device, firmware, hypervisor, kernel, memif
  server or secondary process.
* Hash table collision attacks on rte_hash, lookup performance under
  crafted keys, unless they cause a crash or unbounded memory use.
* Unaligned access on x86, strict aliasing warnings, and UBSan reports
  without a concrete failure.
* Same-host side channels, speculative execution, Rowhammer.
* Deprecated APIs and drivers scheduled for removal, unless reachable from
  packet data.
* Memory leaks at exit or on initialization error paths.
