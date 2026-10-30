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
  - software parsing in drivers/net (virtual PMDs, tunnel and ptype
    parsing done in software, Tx prepare paths that read packet headers
    forwarded from the network)
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
* memif peers. memif is for cooperating processes that share trust; the
  peer can write to shared regions (and to mbufs with zero-copy). Missing
  validation of region index, offset or descriptor chain is a bug, not a
  vulnerability.
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
  validate pointers, queue ids, counts or mbuf metadata (l2_len, l3_len,
  ol_flags, nb_segs, pkt_len vs data_len). A crash from inconsistent
  arguments or mbuf fields supplied by the application is not a
  vulnerability. It is in scope when DPDK itself derived the bad value from
  packet contents (e.g. header lengths computed by rte_net_get_ptype and
  then trusted by gso or a Tx path).
* Control path misuse (bad config, NULL where not allowed, wrong order of
  calls, invalid devargs) is a bug, not a security problem. Report these
  as ordinary bugs at LOW at most.

## Components that matter most / least

Highest: lib/vhost, lib/net, lib/ip_frag, lib/gro, lib/gso, lib/ipsec,
lib/pdcp, lib/mbuf (chain handling), drivers/net/vhost, PF mailbox handlers,
software crypto and compress drivers on the decrypt/decompress side.

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
  packet data or from a guest without a demonstrated exploit; guest able to
  read host process memory; a single packet or a guest causing crash,
  infinite loop or livelock of a data path core; per-packet mbuf or memory
  leak that lets a remote sender exhaust a mempool.
* MEDIUM: out-of-bounds read with limited disclosure; DoS that needs a
  high packet rate, non-default offloads or a rarely used library; packet
  data leaking between flows or queues; PF mailbox issues limited to the
  attacking VF.
* LOW: anything only in examples/ or app/; control path bugs; bugs that
  need application misuse of the data path API; undefined behaviour
  without demonstrated impact; leaks on error paths of setup code.

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
  adding checks at each use. Do not add argument checks to data path
  functions; that is not a fix.
* A unit test in app/test is welcome when practical.

## Anything to leave alone

* Missing argument validation in data path APIs.
* Bugs that need a malicious device, firmware, hypervisor, kernel, memif
  peer or secondary process.
* Hash table collision attacks on rte_hash, lookup performance under
  crafted keys, unless they cause a crash or unbounded memory use.
* Unaligned access on x86, strict aliasing warnings, and UBSan reports
  without a concrete failure.
* Same-host side channels, speculative execution, Rowhammer.
* Deprecated APIs and drivers scheduled for removal, unless reachable from
  packet data.
* Memory leaks at exit or on initialization error paths.
