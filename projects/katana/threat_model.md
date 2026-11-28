# Threat model

## What katana is
Katana is a web crawler for security testing. It ships as a CLI (`cmd/katana`) and as a Go library (`pkg/engine/standard`, `pkg/engine/hybrid`, `pkg/engine/headless`, configured through `pkg/types`). It runs on the operator's machine or inside other tools, follows links from the seed URLs the operator gives it, and records what it finds. It has three engines: standard (Go HTTP client), hybrid (a Chrome tab with request interception), and headless (a Chrome-driven state crawler with form filling, login and CAPTCHA solving).

## Where untrusted input comes from
Everything a crawled site controls is hostile, including sites reached by following links, redirects and JavaScript:
- HTTP responses: status, headers (`Location`, `Set-Cookie`, `Content-Type`, `Content-Length`), bodies, compressed bodies, and redirect chains.
- Content parsed for endpoints: HTML, inline and external JavaScript (regex parser and jsluice), `robots.txt`, `sitemap.xml`, forms, and the knowledge-base extractors (`pkg/knowledgebase`).
- Pages rendered in Chrome: their scripts run next to katana's injected scripts (`pkg/engine/headless/js`, `pkg/engine/headless/captcha/js`, stealth assets), and they can navigate, open popups, raise dialogs, issue XHR/fetch, and set cookies.
- Login and CAPTCHA pages: their DOM decides where the auto-login (`-al`) credentials and recorded flow (`-rf`) steps are typed, and which CAPTCHA site key and page URL go to the solver provider.
- Answers from the AI provider (`-aip`, `-ai-url`), which are derived from page content, and AI replay files (`-ai-replay`) from other people.
- Recorded flow JSON files (`-rf`) and resume files when they come from someone else.

Trusted: the operator's flags, config files, form and field config (`-fc`, `-flc`, including their DSL), seed URL lists, proxy settings, and the Chrome instance named with `-cwu`.

## What matters most
- Scope enforcement (`pkg/utils/scope`, `-cs`, `-cos`, `-fs`, `-ns`, `-mdp`): a target must not steer katana, in any engine, to hosts or paths outside the configured scope. Redirects, `<base>`, JS navigation, popups, service workers, sitemap and robots entries, and path climbing (`-pc`) all count. One engine enforcing scope while another does not is a bug.
- Credentials and keys: auto-login credentials, recorded-flow values, session cookies, custom headers, proxy credentials, the CAPTCHA solver key (`-csk`), the AI key (`-ai-key`, `AI_API_KEY`), and the traffic export token (`KATANA_TRAFFIC_TOKEN`) must only reach the host they belong to. Typing credentials into an off-scope or cross-origin form, sending them after a redirect to another host, or exposing them to page JavaScript is in scope.
- Chrome isolation (`pkg/engine/headless`, `pkg/engine/hybrid`): page scripts must not read or tamper with katana's injected helpers to change crawler decisions, read `file://` or local resources, reach the DevTools endpoint, or affect other tabs and crawls sharing the browser pool. The `-v` debug server on `127.0.0.1:8089` (`pkg/engine/headless/debugger.go`) shares the loopback interface with rendered pages and must not leak crawl data to them.
- AI decider (`pkg/decider`): page content in prompts must not make the model pick options or actions the crawler did not offer, and replay files must not do so either.
- File writes from target data: stored responses and fields (`-sr`, `-srd`, `-sf`, `-sfd`, `pkg/output`), the index file, resume files, and error logs. Host names, URLs and field values must not cause path traversal, writes outside the chosen directory, or overwriting of unrelated files.
- Traffic export (`pkg/output/export`): it must keep TLS unless insecure is explicitly allowed, and must strip credentials unless the operator turns them on.
- Output formats (`pkg/output`: JSONL, templates via `-output-template`, screen output): a target must not inject records into JSONL or break out of the template.
- Library use: options, cookies, sessions and state must not leak between crawler instances or concurrent crawls in one process.

## Less important or out of scope
- `cmd/functional-test`, `cmd/integration-test`, `cmd/tools`, `internal/testutils` (including `authlab`), `integration_tests`, and test fixtures.
- Anything the operator explicitly allows: crawling internal hosts listed as seeds or scope, `-ns`, `-nos`/`-ho` browser flags, `-noi`, `-cwu` pointing to a remote Chrome, and DSL in form config.
- Vulnerabilities in Chrome, go-rod or other dependencies with no katana-specific path to reach them.
- Ordinary traffic katana is meant to send, such as form submissions with generated data to in-scope pages.

## How to exercise it
- `katana` is in `/usr/local/bin`, and `chromium` is on PATH. Use `-hl -sc -nos` (or `-hh -sc -nos`) for the browser engines: `-sc` avoids a browser download, which fails offline, and `-nos` is needed because Chrome refuses to start as root with its sandbox on. Do not report the missing sandbox itself; it is a constraint of this environment.
- Serve a hostile site from a local HTTP server in the container and point katana at it, for example `katana -u http://127.0.0.1:8000 -jc -kf all -sr -srd /tmp/out`.
- `internal/testutils` has a local test server and an auth lab that are useful starting points for login flows.

## Severity
- Critical: code execution on the katana host caused by a crawled site, a replay file, or a recorded flow.
- High: arbitrary file write or overwrite outside the output directory; reading local files or the DevTools endpoint from a rendered page; sending auto-login credentials, session cookies, or the CAPTCHA, AI, or export secrets to a host the operator did not scope them to.
- Medium: scope bypass that makes katana request off-scope hosts; crashes, hangs, or unbounded memory, disk, or goroutine growth triggered by a target; page content steering the AI decider outside the offered choices; state leaking between crawls in library use.
- Low: injection into JSONL, templates, or terminal output that misleads the operator; information leaks without credential exposure; issues that require an unusual flag combination with no realistic use.
