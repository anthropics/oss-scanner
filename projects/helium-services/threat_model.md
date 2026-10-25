# Helium services threat model

## What this repository is

The public web services that the Helium browser talks to, and the tooling that publishes its updates. They run at
`services.helium.imput.net`, `crash.helium.computer` and `updates.helium.computer`.

- `svc/nginx`: the reverse proxy in front of the other services; also serves spellcheck dictionaries and `bangs.json`.
- `svc/extension-proxy`: proxies extension downloads from the Chrome Web Store so the browser never contacts Google
  directly; signs proxied URLs with `HMAC_SECRET`.
- `svc/ubo`: mirrors uBlock Origin filter lists and serves the `assets.json` that Helium's uBlock Origin loads.
- `svc/minidumpster`: accepts Crashpad crash uploads from browsers, symbolicates them with symsorter and Sentry's
  symbolicator, and has a web UI for the imputnet GitHub organization. Crash reports can contain fragments of process
  memory, so they are sensitive.
- `svc/minipush`: a storageless Web Push server compatible with Mozilla autopush.
- `svc/bangs`, `filters/`: data (the !bangs list and Helium's filter lists).
- `util/sparkler`: turns GitHub releases into the signed Sparkle appcast that macOS clients update from.
- `util/release-collector`: builds the manifest of the latest download for each platform.
- `deploy/`, `setup.sh`, `compose.yml`: how the services are deployed.

In the scanner image, `/src` is this repository. Each Deno project's dependencies are cached, so `deno task` commands
and `deno test` work offline; `symsorter` is on PATH. minidumpster has a test suite (`cd svc/minidumpster && deno task
test`) and a mock mode (`deno task dev:seed && deno task dev:mock`).

## Scope

The attacker is anyone on the internet: every endpoint is public and unauthenticated unless the code says otherwise,
and the browser trusts what these services return. Things that matter:

- Anything that lets an attacker change what a browser receives: a different extension, filter list, `assets.json`,
  bangs or update than the one the service intends to serve, or one served to other users (cache poisoning, request
  smuggling between nginx and the services, open proxying of arbitrary hosts).
- Reading or tampering with crash reports, or getting into minidumpster's web UI, without being an imputnet member.
- Server-side request forgery, path traversal, code execution, and resource exhaustion that one client can trigger
  cheaply and that takes a service down for everyone.
- Bypassing the HMAC on extension-proxy URLs, or recovering the secret.
- In sparkler, anything that lets a third party get an update into the appcast that Helium did not release and sign.

## Out of scope

- Attacks that need control of the hosts, the deploy machine, the GitHub organization, or the secrets in `.env`.
- Upstream services the proxies fetch from (the Chrome Web Store, filter list hosts, Kagi's bangs) serving bad
  content themselves.
- Volumetric denial of service.

## How you would like reports

Name the service and the file and line. Give a reproducer against the service run locally where possible, and say
when a finding was only confirmed by reading code.
