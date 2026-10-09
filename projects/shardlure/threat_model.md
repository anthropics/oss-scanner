# Threat model — ShardLure

## What this project does and where untrusted input enters

ShardLure runs beside the Cowrie SSH honeypot on an Internet-facing sensor. It ingests what attackers do, clusters them into actors and campaigns, enriches their IPs, captures the payloads they fetch, and can share vetted samples and IOCs with abuse.ch (MalwareBazaar, URLhaus, ThreatFox) and AbuseIPDB. One Go binary (`cmd/shardlure`) runs the live daemon (`shardlure live`), a web dashboard and CLI subcommands; Python scripts install and patch Cowrie.

**Treat everything an SSH client can influence as hostile.** That input reaches ShardLure through:

- **Cowrie's JSON log** (`internal/ingest/cowrie`). Every field is attacker-controlled: usernames, passwords, commands (up to ~2 MB lines), client versions, HASSH strings, file names and URLs. Ingest is incremental and must survive any line.
- **journald sshd lines** (`internal/ingest/journal`): usernames and addresses from the real sshd.
- **Captured payloads** (`internal/capture`, `internal/intel/bazaar` classifier, `internal/intel/payload`). Files attackers download or upload are hashed, classified (ELF/script parsing, XOR-decoded config tables) and stored. They are never executed. Any path that runs, imports or loads payload content is critical.
- **Outbound fetches of attacker URLs** (`capture.SafeFetcher`): DNS rebinding, redirects, size limits, private/reserved ranges (SSRF into the sensor's network or the Tailscale range `100.64.0.0/10`).
- **Cowrie TTY logs** (`capture.DecodeTTYReader`, a packed binary format with its own length fields).
- **Attacker command text** (`internal/script` normaliser, a hand-written bash word scanner; `internal/intel/deobf`).
- **The web dashboard** (`internal/web`). With `SHARDLURE_DASH_TOKEN` set, every `/api/*` call needs a bearer token. Without it, "open mode" is meant only for loopback/Tailscale binds and relies on Host/Origin/Sec-Fetch checks (`host_policy.go`, `origin_policy.go`). Attacker data is rendered into HTML/JS: stored XSS through any attacker-supplied field is in scope.
- **Backup bundles** (`internal/backup`, `internal/safefile`): `backup verify/restore` reads a bundle that may be tampered with.
- **The installer and persona scripts** (`scripts/shardlure.py`, `scripts/install.sh`, `scripts/apply-stealth.sh`, `install/persona/`). They run as root over a Cowrie tree owned by the low-privilege `cowrie` account, which handles attacker sessions. Any way for that account (or an attacker inside the emulated shell) to make root write, chown, follow a symlink or unpickle something it controls is a privilege escalation.

## Components that matter most / least

Most important:
1. Anything that could execute attacker content, or let the `cowrie` account escalate to root.
2. SSRF or a size-cap bypass in `SafeFetcher`.
3. Memory/CPU exhaustion or a permanent ingest stall from a single crafted log line, payload or TTY log (the daemon must keep ingesting).
4. Dashboard auth bypass, stored XSS from attacker data, CSRF against mutating routes.
5. Outbound-sharing gates (`internal/intel/*/vet.go`): anything that makes ShardLure submit host identifiers, admin IPs or unvetted data to a third party.

Less important: the forensic TUI (`tui/`), CLI output formatting (must still be escape-safe via `termSafe`), performance tuning.

Out of scope: upstream Cowrie itself (a separate project; only ShardLure's patches under `install/persona/patches/` are ours), the vendored front-end libraries in `internal/web/vendor/` and the vendored fonts.

## How to exercise it

- `go test ./...` (unit and integration tests; fuzz seed corpora for `journal.FuzzParseLine`, `cowrie.FuzzParseReader`, `capture.FuzzDecodeTTYReader`, `script.FuzzNormalizeCommand`). `make fuzz` runs them for longer.
- `./shardlure ingest journal testdata/sample.journal --replace`, then `./shardlure actors`; `./shardlure ingest cowrie <file> --replace` for a Cowrie JSON log.
- `./shardlure web 127.0.0.1:8080` serves the dashboard over the local database (set `SHARDLURE_DASH_TOKEN` to test token mode).
- Python: `python3 -m unittest scripts/test_*.py`. The persona patches apply to a Cowrie v3.1.1 checkout with `install/persona/apply-patches.py <cowrie_home>`; `scripts/check-cowrie-patches.sh` needs network to clone Cowrie and will not run offline.

## How we rate severity

- Critical: code execution from attacker input (including payload execution or unsafe deserialisation), root escalation from the `cowrie` account, or SSRF reaching internal services.
- High: dashboard auth bypass or stored XSS reachable from honeypot data, a single input that permanently stops ingest or crashes the daemon in a loop, path traversal or symlink-following writes outside the data/evidence directories, sharing data the vetting gates are meant to withhold.
- Medium: bounded DoS (a slow parse or memory spike that recovers), information disclosure of non-secret operational data, CSRF on low-impact routes.
- Low: hardening gaps without a demonstrated impact.

Please include a reproducer (a log line, payload file or HTTP request) and, where possible, a patch with a test.

## Anything to leave alone

- Cowrie's emulated shell diverges from bash on purpose in places (documented in `CLAUDE.md` and the persona patch docstrings, e.g. deep nesting is refused). These are not bugs unless they let input escape the emulation.
- Open mode without a token on a public address is refused at startup by design. Reports that assume an operator bypassed that refusal are low.
