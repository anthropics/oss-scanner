# Threat model

## What this project does and where untrusted input enters

Harvest is a metrics collector written in Go. Each `poller` process connects to one storage system or switch
(ONTAP, StorageGRID, E-Series, Cisco Nexus, or Arista). It polls that device's REST, ZAPI (XML), or CLI-over-REST
APIs and publishes the results as metrics. Most deployments export to Prometheus, which scrapes an HTTP endpoint
on each poller. Pollers can also push to InfluxDB or VictoriaMetrics. Harvest runs inside customer data centers.
It holds credentials for every system it monitors, and those credentials are the most valuable thing it has.

Trust levels, from most to least trusted:

1. **The operator.** `harvest.yml`, the collector templates under `conf/`, `credentials_file`,
   `credentials_script` and `certificate_script`, TLS keys, and command-line flags are trusted. Anyone who can write
   them can already run code as the Harvest user.
2. **The monitored device's administrator.** Harvest assumes the device is the one it was configured to reach.
   Responses are still parsed defensively: a buggy or compromised device must not be able to crash the poller,
   run code, or read files on the poller host.
3. **Less-privileged users of a monitored device.** These users control strings that Harvest copies into metric
   labels. Examples include ONTAP SVM and tenant administrators (volume, qtree, and SVM names, comments, tags) and
   unauthenticated users whose actions appear in EMS events (such as the username in a failed login).
   Treat these strings as untrusted.
4. **Anyone on the network.** This includes anyone who can reach a poller's Prometheus port, the `harvest admin`
   HTTP service-discovery endpoint, or the MCP server's HTTP port. It also includes anyone who can intercept
   traffic between Harvest and a device.

Untrusted input enters through:

- **Device responses:** JSON parsed with the in-tree gjson fork (`third_party/tidwall`), ZAPI XML
  (`pkg/api/ontapi/zapi`, `pkg/tree`), E-Series SYMbol, StorageGRID, and switch CLI output. All parsing code
  lives under `cmd/collectors/**`.
- **Inbound HTTP:**
  - The Prometheus exporter (`cmd/exporters/prometheus/httpd.go`) serves `/`, `/metrics`, and `/health`. Access can
    be limited with `allow_addrs` and `allow_addrs_regex` and protected with TLS.
  - The admin service-discovery server (`cmd/admin`) uses optional basic auth and TLS.
  - The MCP server (`mcp/`) uses stdio or streamable HTTP and binds to localhost by default.
- **MCP tool arguments**, which come from an LLM client. These include PromQL strings and the optional
  `tsdb_override` URL and credentials.
- **TSDB responses** (Prometheus or VictoriaMetrics) read by the MCP server.

## Components that matter most / least

Most important:

- **Credential handling:** `pkg/auth` (passwords, credential and certificate scripts, client certificates, TLS
  configuration) and `pkg/conf`. Secrets must never reach logs, metrics, HTTP responses, error messages, or
  `harvest doctor` output (`cmd/tools/doctor` redacts configuration for support bundles).
- **TLS to devices:** when `use_insecure_tls` is false (the default), certificate and hostname verification must
  actually happen on every client Harvest builds.
- **Exporter access control:** `allow_addrs`, `allow_addrs_regex`, TLS, and admin basic auth. The pprof handlers
  on the exporter port, and the `--profiling` listener, are intended to be reachable only from the local machine.
- **Output encoding:** label values from devices must stay escaped in Prometheus exposition format and InfluxDB
  line protocol (`cmd/exporters/utils.go`, `cmd/exporters/influxdb`). A malicious label value must not be able to
  inject new series or labels.
- **Parser robustness:** a malformed or hostile device response must not cause a panic that kills the poller, a
  goroutine leak, or unbounded memory growth.
- **The MCP server:** PromQL handling, the label filter that scopes queries to Harvest metrics, and the
  per-request `tsdb_override` (an attacker-supplied URL that the server fetches with its own TLS settings).

Less important, but still in scope:

- The `harvest` CLI tools under `cmd/tools/` (`rest`, `zapi`, `grafana import/export`, `generate`, `template`).
  They run interactively under the operator's control. `grafana` handles a Grafana API token.
- The in-tree forks under `third_party/` ship in the binary and are in scope.

Out of scope:

- `vendor/` (report those issues upstream), `integration/`, `docs/`, the Grafana dashboard JSON under `grafana/`,
  and the container and Kubernetes examples under `container/`.
- The closed-source AutoSupport binary (`autosupport/asup`). The Go code that builds and launches it
  (`cmd/poller/collector/asup.go`) is in scope.

## How to exercise it

- Build: `go build -o bin ./cmd/harvest ./cmd/poller`. The MCP server builds with `cd mcp && go build ./cmd/server`.
- Tests: `go test ./...` in the repository root and in `mcp/`. Both run offline.
- Recorded device responses for driving parsers and plugins without a live device live under
  `cmd/collectors/**/testdata` (JSON, gzipped JSON, and ZAPI XML). `cmd/collectors/collectorstest.go` has helpers
  that load them. Most plugin tests show how to feed a response through a collector into a `matrix.Matrix`.
- Exporter tests (`cmd/exporters/**/*_test.go`) show how to render a matrix. They are the easiest way to check
  label escaping.
- A poller starts with `bin/poller --config <harvest.yml> --poller <name>`. A live poll needs a reachable
  device, which the scanner does not have, so prefer the recorded responses above.

## How you rate severity

- **Critical:** remote code execution, or theft of a device credential or private key, by a network attacker or
  a less-privileged device user who has no operator access.
- **High:**
  - Credentials or private keys leaked into logs, metrics, HTTP responses, or `doctor` output.
  - TLS verification skipped while `use_insecure_tls` is false.
  - A bypass of `allow_addrs`, TLS client checks, or admin basic auth.
  - Reaching pprof or other debug handlers from a remote host.
  - Reading or writing files outside the configured directories based on device- or network-supplied input.
  - SSRF from the MCP server that sends the configured TSDB credentials to an attacker's host.
- **Medium:**
  - Metric or label injection through exporter escaping.
  - A device response, or an unauthenticated HTTP request, that crashes or hangs a poller, admin node, or MCP
    server, or drives unbounded memory growth.
  - A bypass of the MCP label filter that exposes non-Harvest metrics.
- **Low:**
  - Anything that requires writing `harvest.yml`, templates, or credential scripts.
  - Issues that only affect the interactive CLI tools when they are pointed at a hostile host.
  - Missing hardening headers.
  - Disclosure of metric data that the endpoint already serves by design.

Go is memory safe, so bugs in the Go code without `unsafe` are not memory corruption. A plain panic is a
denial-of-service finding (medium at most) unless it leads to one of the outcomes above.

## Anything to leave alone

- Running `credentials_script` or `certificate_script` is intended behavior. The operator chooses the path.
- When the operator sets `use_insecure_tls: true`, skipping certificate verification is intended.
- `/metrics` and `/` are unauthenticated by design when `allow_addrs` and TLS are not configured. Reachability of
  the exporter port is left to network policy.
- An MCP server bound to a non-localhost address with `--host` is an operator decision. The streamable HTTP
  transport has no built-in auth.
- Read-only ONTAP accounts are recommended, but some deployments use admin accounts. Do not report "Harvest could
  use stronger credentials" findings.
