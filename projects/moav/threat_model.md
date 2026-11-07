# MoaV — threat model for OSS Scanner

## What MoaV is
Mother of All VPNs (MoaV) is an open-source, MIT-licensed, self-hosted, multi-protocol
censorship-circumvention stack. One command turns a VPS or Raspberry Pi into a private access
server running 18+ transports side by side (Reality/VLESS, Hysteria2, Trojan, AnyTLS,
Shadowsocks, WireGuard, AmneziaWG, several DNS tunnels, MTProxy, and more), so that when one
route is detected and blocked, the others keep carrying traffic. It keeps no user telemetry and
is operated by the operator themselves; there is no central service.

This enrolment scans **MoaV's own code**: the installer (`install.sh`), the dispatcher
(`moav.sh`), the `lib/*.sh` modules, `scripts/`, `dockerfiles/`, and the config/bundle generators
and `templates/`. The orchestrated upstream engines (sing-box, Xray-core, WireGuard, etc.) are
out of scope here (report those upstream); what matters is how MoaV configures, generates, and
hands out credentials and configs.

## Trust boundaries / where untrusted input enters
- **The operator is trusted.** They run `install.sh` and `moav` on their own box as root/admin.
- **Remote users are semi-trusted.** They receive per-user bundles and connect over the transports.
- **The network and the censor are hostile.** The server sits on a hostile network that actively
  probes, fingerprints, and injects. Anything exposed on a listening port is attacker-reachable.
- **Highest-value concerns, roughly in priority order:**
  1. **Secret handling / generation.** Key/password/bundle generation (X25519, Reality keys,
     Snell/DNS shared keys, admin + Grafana password), file permissions (`.env`, bundles, state),
     and anything that could weaken entropy, leak a secret into logs/`ps`/world-readable files, or
     reuse keys across users where they should be per-user.
  2. **Install / update path.** `install.sh` and `moav update`: command injection via env/args,
     unsafe `eval`, path traversal, writing outside `/opt/moav`, insecure `curl | bash` handling,
     the non-interactive/`--answers` input path (password must never reach argv), and `.env`
     rendering.
  3. **User provisioning & the admin dashboard.** `moav user add/remove`, bundle rendering, the
     admin panel and exporters: authz bypass, injection via usernames or config values, SSRF, or
     any way an unprivileged/remote actor escalates.
  4. **Config generation correctness.** A rendered config that silently downgrades security
     (missing encryption, weak obfuscation, exposed management ports) is a real finding, because
     at-risk users depend on it.

## Severity guidance
- **Critical:** remote unauthenticated code execution or key/secret disclosure on the server;
  generation of a config that fully exposes a user's traffic; admin-panel auth bypass from the
  network.
- **High:** local privilege escalation to root from an unprivileged user; secret written
  world-readable or leaked to logs/`ps`; command injection reachable via normal operator input
  (usernames, env, answers file); a downgrade that materially weakens a protocol's resistance.
- **Medium:** issues requiring an already-privileged operator to misuse, or hardening gaps with no
  demonstrated exploit (e.g., a non-exploitable `eval`, loose-but-not-world-readable perms).
- **Low / informational:** style/robustness, defense-in-depth suggestions.

Favor findings with a concrete reproducer. For MoaV, "a secret ends up somewhere an attacker or a
co-tenant can read it" and "input X reaches a shell" are the two patterns most worth flagging.

## Out of scope
- Vulnerabilities inside upstream binaries (sing-box, Xray-core, WireGuard, Hysteria, etc.) —
  report those to the respective projects.
- The inherent detectability/throughput limits of DNS tunneling and similar transports; MoaV
  targets usable connectivity under censorship, not clean-network benchmarks.
