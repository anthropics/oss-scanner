# Threat model

## What this project does and where untrusted input enters
Open vSwitch (OVS) is a production-quality, multilayer virtual switch. It forwards
network traffic in software (the userspace datapath in this build) under the control
of OpenFlow controllers and OVSDB management clients.

The security boundary that matters for scanning is **the data plane**: actual network
packets (Ethernet frames and their payloads - VLAN/MPLS tags, IPv4/IPv6, TCP/UDP,
ICMP, ARP, tunnel encapsulations such as VXLAN/GRE/Geneve, conntrack-tracked flows,
etc.) that OVS parses, matches, and forwards. **Treat all packet data as untrusted.**
An attacker who can get a packet onto a bridge port can reach this code, so bugs in
packet parsing/handling (`lib/flow.c`, `lib/packets.c`, `lib/odp-*`, `lib/conntrack*`,
`lib/netdev*` receive paths, and the ofproto/dpif forwarding paths) are the primary
concern.

## Components that matter most / least
- **Most important (untrusted input):** the packet-processing data plane listed above -
  flow extraction, action execution, tunnel decap/encap, connection tracking, and
  anything that walks attacker-controlled packet bytes.
- **Trusted control/management plane (in scope, but see severity):** the OpenFlow
  interfaces and the OVSDB socket interfaces are **considered trusted**. OVS already
  assumes these are operated by an authorized controller/administrator. If they are
  exposed to an untrusted attacker, that attacker can already break networking directly
  (reprogram or tear down forwarding, DoS the switch, etc.), so a malformed message on
  these channels crashing or misbehaving is not, by itself, a meaningful new finding.
  Memory-safety bugs reachable from these channels are still worth noting but should be
  rated with this trust assumption in mind (see below).
- **Less important / out of scope:** DPDK is intentionally not built here (see the
  Dockerfile) and is out of scope. The Linux kernel datapath module is not built;
  only the userspace datapath is in scope. The test harness under `tests/` and build
  tooling are not product code.

## How to exercise it
- The build produces the daemons and utilities in `/src`: `vswitchd/ovs-vswitchd`,
  `ovsdb/ovsdb-server`, and the `utilities/ovs-*` and `ovsdb/ovsdb-*` tools.
- `tests/ovstest` bundles many of the unit tests for the library (flow parsing,
  classifier, conntrack, odp, packets, etc.) and is a good driver for data-plane code.
- The full regression suite runs with `make check` from `/src`
  (`make check -j"$(nproc)" TESTSUITEFLAGS="-j$(nproc)"`); it is large, so a subset such
  as `make check TESTSUITEFLAGS="ovs-ofctl"` is often enough to reproduce a finding.

## How you rate severity
- A memory-safety bug (buffer overflow/overread, use-after-free, double free, OOB write)
  reachable from **untrusted packet data** is high at a minimum; critical if it is
  controllable in a way that plausibly leads to remote code execution.
- A remotely triggerable crash or DoS of the switch from **untrusted packet data** is
  high (it takes down forwarding for everything on the switch).
- Issues reachable only via the **trusted** OpenFlow or OVSDB interfaces are capped
  lower: a plain crash/DoS there is low/informational, because an attacker on those
  channels can already break networking. A clear memory-corruption primitive on those
  channels can still be medium if it provides capability beyond what the trusted
  interface already grants.

## Anything to leave alone
- Do not report the trust assumption itself (that OpenFlow/OVSDB sockets are trusted) as
  a vulnerability, or DoS/misbehavior that requires already having access to those
  trusted control channels.
- Do not report DPDK-related or kernel-datapath code; neither is built in this image.
