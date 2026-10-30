# Lustre threat model

## What Lustre is

Lustre is a distributed parallel filesystem. One cluster has a management
server (MGS), metadata servers (MDS, which serve MDTs), object storage servers
(OSS, which serve OSTs) and many client nodes. All of them run Lustre kernel
modules from this tree. Servers and clients talk over LNet, Lustre's own
network layer, which runs on TCP (`ksocklnd`) and on InfiniBand/RoCE
(`ko2iblnd`). The RPC layer above LNet is `ptlrpc`. Userspace holds the
administration tools (`lctl`, `lfs`, `lnetctl`, `mkfs.lustre`,
`mount.lustre`), `liblustreapi`, and daemons such as the GSS daemons
(`lsvcgssd`, `lgss_keyring`) and the HSM copytool (`lhsmtool_posix`).

The image holds a full server + client build (ldiskfs backend, GSS) for a
Rocky Linux 10 kernel. The modules are compiled but cannot be loaded: the
sandbox kernel is not the one they were built for, so a Lustre filesystem
cannot be mounted or run here. Userspace tools are installed and can be run.

## Where untrusted input enters

Ranked from most to least exposed.

1. **LNet frames from the network.** Anything reachable on the LNet network
   can send bytes to a server or client. Parsing of LND-level handshakes and
   frames (`lnet/klnds/socklnd/`: `ksocknal_process_receive()`,
   `ksocknal_recv_hello()`; `lnet/klnds/o2iblnd/`: `kiblnd_handle_rx()`,
   `kiblnd_passive_connect()`), LNet message headers and routing
   (`lnet_parse()` in `lnet/lnet/lib-move.c`, `lib-msg.c`, `router.c`),
   ping/push/discovery (`lnet/lnet/peer.c`, `api-ni.c`, `lib-ptl.c`) and the
   LNet selftest module (`lnet/selftest/`) happens before any Lustre
   authentication. Treat every byte as attacker controlled.

2. **ptlrpc requests at servers.** A client node sends RPCs that the MGS,
   MDT, OST handlers unpack and act on. Requests enter at
   `ptlrpc_server_handle_req_in()` (`lustre/ptlrpc/service.c`) and are
   dispatched by opcode in `tgt_request_handle()`
   (`lustre/target/tgt_handler.c`). In scope: unpacking and swabbing
   (`lustre/ptlrpc/pack_generic.c`, `pack_server.c`, request formats in
   `layout.c`), bulk descriptors, the handler tables in `lustre/mdt/`,
   `lustre/ofd/`, `lustre/mgs/`, `lustre/target/`, `lustre/ldlm/` and the
   quota and LFSCK code. Lustre has no claim to protect a server from
   a client that *is* root on its own node and sends legitimate but hostile
   metadata; it does promise that malformed or out-of-range wire data cannot
   corrupt server memory, crash the server, or let one client read or alter
   another client's data outside the normal permission model. A client is
   authenticated only when GSS (Kerberos or SSK) is configured, so by default
   the server-side RPC surface is reachable by any host on the LNet network.

3. **Security layer.** `lustre/ptlrpc/sec*.c` (`sptlrpc_svc_unwrap_request()`),
   `lustre/ptlrpc/gss/` (kernel, `gss_svc_accept()` in `sec_gss.c`) and
   `lustre/utils/gss/` (the `lsvcgssd` daemon, `handle_channel_request()`
   in `svcgssd_proc.c`, and the `lgss_keyring` upcall, which process tokens
   relayed from the network through the kernel), plus nodemap
   (`lustre/ptlrpc/nodemap_*.c`, `nodemap_classify_nid()` and
   `nodemap_map_id()` in `nodemap_handler.c`) which maps client identities.
   Bypasses of these, or memory errors in token parsing, are high value.

4. **Client-side ioctls and xattrs from unprivileged local users.** On a
   client node any user can call the Lustre ioctls (`ll_file_ioctl()` in
   `lustre/llite/file.c`, `ll_dir_ioctl()` in `dir.c`, PCC ioctls into
   `pcc.c`), set layouts (`lfs setstripe`, LOV/LMV EAs parsed in
   `lustre/lov/`, `lustre/lmv/`, `lustre/obdclass/`), use HSM, changelogs,
   lease, ladvise, lockahead, lseek, fallocate, and project quota calls. NFS
   file handles from an NFS re-export enter at `ll_fh_to_dentry()`
   (`llite_nfs.c`). A local privilege escalation or kernel memory corruption
   from an unprivileged user is high. Layout and link EAs a client sets
   travel to the MDT and are parsed again there (`lod_verify_striping()`,
   `lod_verify_md_striping()` in `lustre/lod/`, `lustre/obdclass/linkea.c`),
   so bugs in EA parsing count for both.

5. **Server replies parsed by clients.** A hostile or compromised server
   (or a man in the middle without GSS) sends replies that `lustre/osc/`,
   `lustre/mdc/`, `lustre/mgc/`, `lustre/lov/`, `lustre/lmv/`, `lustre/llite/`
   parse. Client memory corruption from a malformed reply is in scope, rated
   one step below the same bug on the server side.

6. **Userspace parsers of files and command lines.** `lnetctl import`
   (YAML, `lnet/utils/lnetconfig/`), `lctl` and `lfs` argument handling,
   `mkfs.lustre`/`tunefs.lustre`/`mount.lustre` reading device parameters,
   `llog_reader` and `lr_reader` reading on-disk config and last_rcvd files,
   `l_getidentity`/`l_getsepol` upcalls, `lhsmtool_posix`. These run as root
   on inputs an administrator mostly controls, so rate them lower unless the
   input can come from a less privileged party.

## Trust boundaries, in one line each

- Network peer → server or client kernel: fully untrusted.
- Client node → server: untrusted for memory safety and for cross-tenant
  isolation; trusted for the UID/GID it claims unless nodemap or GSS is on.
- Unprivileged process → client kernel: untrusted.
- Server → client: semi-trusted; still in scope.
- Administrator → userspace tools and on-disk MDT/OST data: trusted. Bugs
  that need a hand-crafted disk image or a root shell on the server are
  informational unless they can be triggered through one of the boundaries
  above.

## In scope and out of scope

In scope: everything under `lnet/`, `lustre/`, `lib/`, `lustre_compat/`,
`include/`, the ldiskfs patch series in `ldiskfs/kernel_patches/` (the
patches, not the upstream ext4 code they modify), and the Rust bindings in
`rustreapi/`.

Out of scope: `lustre/tests/` (test scripts and test-only programs),
`contrib/`, `debian/`, `rpm/`, `config/` (build system), documentation,
generated files, the base ext4 code that ldiskfs copies from the kernel, and
the `lnet/selftest/` module beyond the frame parsing it shares with the
network boundary. Code under `#ifdef` for debugging only
(`CONFIG_LUSTRE_DEBUG_EXPENSIVE_CHECK`, `LIBCFS_DEBUG`-only paths) is low
priority.

## Severity

- **Critical:** remote code execution or arbitrary kernel memory write on a
  server or client from the network, with no authentication; or a
  cross-tenant data read or write bypassing nodemap/GSS isolation.
- **High:** remote kernel memory corruption or out-of-bounds read of
  sensitive memory from the network, even if exploitability is unproven;
  kernel memory corruption or privilege escalation by an unprivileged local
  user on a client; a server crash (`LBUG`, `LASSERT`, oops) reachable from
  the network before authentication; GSS/SSK/nodemap bypass.
- **Medium:** server or client crash that needs an authenticated client;
  client crash from a hostile server; unprivileged-user denial of service of
  a client node; information leak of kernel memory contents to the network
  or to an unprivileged user; memory corruption in a root userspace tool
  from a file or network input that an unprivileged party can influence.
- **Low:** denial of service that needs root on a client; bugs in
  administrator-controlled userspace inputs; resource leaks; theoretical
  issues with no clear trigger.

An `LASSERT` or `LBUG` reached from attacker-controlled data is a crash,
not a mitigation: rate it by who can reach it. A pure `CERROR` return is a
correct rejection, not a finding.

## How to work in this image

- Sources are in `/src`, configured and built. `make -C /src -j"$(nproc)"`
  rebuilds; `make -C /src/lustre/utils` rebuilds just the tools.
- Userspace binaries are installed (`lctl`, `lfs`, `lnetctl`, `mkfs.lustre`,
  `llog_reader`, `lr_reader`, `wiretest`, `lsvcgssd` ...). They can be run
  against crafted files and arguments, but anything that needs the modules
  (`lctl` commands that open `/dev/obd`, mounting) fails here.
- `lustre/utils/wiretest` and `lustre/ptlrpc/wiretest.c` document the exact
  wire layout of every RPC structure; `include/uapi/linux/lustre/`
  and `include/uapi/linux/lnet/` hold the on-the-wire types.
- Kernel findings cannot be executed here. For them, give the exact code
  path from the entry point (`lnet_parse()`, `tgt_request_handle()`, an ioctl)
  to the bug, the bytes or struct values that trigger it, and a userspace
  program or Python script that would emit those bytes to a server if one
  were reachable. Say plainly that it was reasoned, not run.

## Reports and patches

- One root cause per report. Group the same missing bounds check hit from
  several call sites into one report that lists every site.
- Name the function and file, the trust boundary crossed, the severity
  under the rubric above, and the reasoning or reproducer.
- A patch should follow Linux kernel style as described in
  `.agents/skills/lustre-coding-style/SKILL.md`, be the minimal fix, and
  compile in this image (`make -C /src`). Use `CERROR`/`-EPROTO` style
  rejection for malformed wire data, never a new `LASSERT`.
