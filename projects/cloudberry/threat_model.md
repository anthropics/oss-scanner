# Threat model — Apache Cloudberry (incubating)

## What this project is and where untrusted input enters
Apache Cloudberry is a massively-parallel (MPP) analytical database derived
from Greenplum Database, which is itself a fork of PostgreSQL. A cluster is one
**coordinator** and many **segment** nodes. Untrusted input reaches the system
through several surfaces, in rough order of importance:

- **SQL from an authenticated client.** The primary surface. A connected,
  low-privilege database user (not a superuser) is the main attacker we care
  about. Anything that lets such a user read/write data they should not,
  execute code, or act as another role is in scope.
- **The frontend/backend wire protocol** before and during authentication,
  including startup packets, SASL/SCRAM, GSSAPI, and TLS negotiation.
- **Inter-node (interconnect) traffic** between coordinator and segments, and
  the internal libpq connections the coordinator opens to segments. Cloudberry
  adds MPP dispatch machinery on top of PostgreSQL here that upstream does not
  have.
- **External data paths**: `COPY`, external/foreign tables, `gpfdist`, cloud
  object storage (gpcloud/S3), and PAX/columnar storage readers parsing
  on-disk or remote files.
- **Backup/restore and expand/recover tooling** that moves catalog metadata and
  data between nodes.

## Components that matter most / least
**Most important — the Greenplum/Cloudberry-specific delta over PostgreSQL.**
Upstream PostgreSQL is heavily audited; the highest-value targets are the parts
this project *added or changed*:

- **`gp_*` built-in functions and the MPP catalog surface.** Many admin and
  internal operations are exposed as SQL-callable `gp_*` functions
  (e.g. `gp_add_coordinator_standby`, `gp_expand_lock_catalog`,
  `gp_expand_bump_version`, `gp_log_backend_memory_contexts`, and the
  `pg_file_*` family). **Please pay particular attention to authorization
  (CWE-862 / CWE-863): any `gp_*` or internal function that performs a
  privileged action — writing files, altering catalog/standby/expand state,
  signaling or inspecting other backends, moving data between segments — must
  be restricted to superusers, either by an in-code `superuser()`/role check or
  by a `REVOKE EXECUTE ... FROM PUBLIC` in `system_functions.sql`. A useful
  heuristic: where a PostgreSQL function `pg_foo` is REVOKE'd from PUBLIC but a
  Cloudberry-added sibling `gp_foo` (or a `gp_`-prefixed reimplementation) is
  not, treat the gap as a likely missing-authorization finding.**
- **MPP dispatch, interconnect, and the motion layer** (coordinator→segment
  command dispatch, internal libpq, UDP/TCP interconnect) — memory safety and
  trust of data received from peer nodes.
- **ORCA optimizer, PAX columnar storage, gpcloud/external-table readers** —
  parsers and deserializers over attacker-influenced data.

**Less important but still in scope:** the management tooling under `gpMgmt/`
(Python), build/packaging scripts.

**Out of scope / lower priority:** unmodified upstream PostgreSQL code paths
that are identical to a current community release (report only if Cloudberry
has diverged in a way that introduces the bug); third-party vendored code; test
fixtures under `src/test/`.

## How to exercise it
- Unit tests build and run in the image (`unittest-cloudberry.sh`).
- Regression and isolation suites live under `src/test/regress` and
  `src/test/isolation2`; the `gpMgmt` tooling has its own tests. These normally
  need a running demo cluster, which the scan image does not start — reason
  about the code statically rather than requiring a live cluster.

## How we rate severity
Guidance, not rigid rules — use judgement:

- **Missing authorization on a `gp_*`/internal function** (a non-superuser
  reaching a privileged action): **high** by default; **critical** if it yields
  arbitrary file write, code execution, or full superuser escalation; **medium**
  if impact is limited to information disclosure of low-sensitivity data or a
  narrow DoS.
- **Memory-safety bugs** (buffer overflow, use-after-free, double free,
  OOB read/write): **high** at minimum; **critical** if attacker-controlled and
  plausibly leading to RCE; an OOB *read* disclosing memory is **medium–high**
  depending on what leaks.
- **SQL/code execution as superuser reachable by a normal user:** **critical**.
- **Authentication bypass or cross-node trust violations:** **high–critical**.
- **Pure DoS** reachable by an authenticated user (crash a backend / segment):
  **medium**, unless it takes down the whole cluster cheaply (then **high**).

## Anything to leave alone
- Do not report issues that require superuser/coordinator-admin privileges to
  trigger *and* only affect that same admin's own session — superusers are
  trusted here (as in PostgreSQL).
- Do not report findings that are identical to current upstream PostgreSQL
  behaviour with no Cloudberry-specific divergence; those belong upstream.
