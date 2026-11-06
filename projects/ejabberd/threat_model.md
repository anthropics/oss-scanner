# Threat model

## What this project does and where untrusted input enters

ejabberd is an XMPP server written in Erlang/OTP, with MQTT, SIP, STUN/TURN and HTTP services in the same node. Treat
everything that arrives on a listener as untrusted until authentication completes, and treat authenticated users and
remote servers as untrusted towards other users, other virtual hosts and the server itself.

- **Client-to-server XMPP** (`ejabberd_c2s`, ports 5222 with STARTTLS and 5223 with direct TLS): the XML stream, stream
  features, STARTTLS, stream compression (`ezlib`), SASL (PLAIN, SCRAM-SHA-*, with or without channel binding,
  DIGEST-MD5, X-OAUTH2, ANONYMOUS, FAST tokens in `mod_auth_fast`), SASL EXTERNAL with client certificates
  (certificate to JID mapping through xmppAddr, CN or SRV-ID, chain building in `pkix`), SASL2 and Bind 2, SCRAM
  downgrade protection (XEP-0474, `mod_scram_upgrade`, XEP-0480), JWT authentication (`ejabberd_auth_jwt`: key
  handling, algorithm confusion, `jwt_jid_field`, token parsing in the third-party `jose` dependency), legacy auth,
  in-band registration (`mod_register`), stream management resumption (`mod_stream_mgmt`), then every stanza a
  logged-in user sends, including the `from` rewriting that must stop a user from forging another user's address.
- **Server-to-server XMPP** (`ejabberd_s2s_in`/`ejabberd_s2s_out`, port 5269): remote servers, STARTTLS and certificate
  checks, SASL EXTERNAL with certificate to domain mapping, dialback (`mod_s2s_dialback`), bidirectional streams
  (`mod_s2s_bidi`). A remote server must not be able to spoof a domain it does not own.
- **Components** (`ejabberd_service`, XEP-0114 handshake) and `mod_privilege`/`mod_delegation`: a component holds a
  shared secret; once authenticated it is trusted only for its allowed domains and for what its configured privileges
  allow, and must not send stanzas from addresses outside that scope.
- **HTTP** (`ejabberd_http`, ports 5280/5443): request parsing, `X-Forwarded-For` with `trusted_proxies`, path
  normalisation and the request handlers: BOSH (`mod_bosh`), WebSocket (`ejabberd_http_ws`, `ejabberd_websocket`),
  HTTP File Upload (`mod_http_upload`, signed PUT/GET URLs), `mod_http_fileserver`, the ReST API (`mod_http_api`, HTTP
  Basic or OAuth tokens checked against `api_permissions`), OAuth (`ejabberd_oauth`: the authorization endpoint and its
  `redirect_uri` handling, open redirect and token leaks, scope checks such as `ejabberd:admin` versus `ejabberd:user`,
  token storage back ends), XML-RPC (`ejabberd_xmlrpc`), web
  admin (`ejabberd_web_admin`), web registration (`mod_register_web`), invites landing pages (`mod_invites_http`),
  CAPTCHA (`ejabberd_captcha`), ACME challenges, `mod_conversejs`, `mod_host_meta` and the Matrix gateway
  (`mod_matrix_gw*`, signed federation requests).
- **MQTT** (`mod_mqtt`, `mqtt_codec`, `mod_mqtt_ws`; port 1883 and MQTT over WebSocket): packet decoding, authentication
  and topic ACLs.
- **STUN/TURN** (`ejabberd_stun`, port 5478 UDP/TCP) and **SIP** (`ejabberd_sip`, `mod_sip*`): message parsing, TURN
  allocation and relay permissions, credentials handed out by `mod_stun_disco`.
- **Stanza payloads** stored and redistributed to other users: PubSub/PEP (`mod_pubsub`, `node_*`, `nodetree_*`), MUC
  (`mod_muc`, `mod_muc_room`, `mod_muc_log` which renders HTML), MIX, MAM queries and archives, offline messages,
  vCard and avatars (images re-encoded by `eimp`), private XML storage, roster and shared roster, privacy and blocking
  lists, ad-hoc commands (`mod_adhoc`, `mod_adhoc_api`, `mod_configure`), push, proxy65 bytestreams, carbons, CSI,
  MucSub subscriptions in `mod_muc`.
- **Other modules handling untrusted input**: `mod_caps` (entity capabilities cache, cache poisoning), `mod_vcard`
  search and `mod_disco` (user and service enumeration), `mod_last` (last activity), `mod_multicast` (XEP-0033 address
  lists, amplification), `mod_sip_proxy` (must not act as an open SIP relay, toll fraud), `mod_fail2ban` (enabled by
  default: a client must not get around the ban that follows failed logins), `mod_mqtt_bridge` and `mod_metrics`.
- **PROXY protocol** (`proxy_protocol`) when a listener enables `use_proxy_protocol`.
- **Storage back ends**: SQL queries are built with the `?SQL` parse transform (`ejabberd_sql_pt`) and escaping in
  `ejabberd_sql`; any user-controlled value reaching a query unescaped is in scope. LDAP filters (`eldap_filter`) built
  from user input are in scope too, as are the MSSQL/ODBC back end and the Redis session store (`ejabberd_redis`,
  `eredis`).
- **Native code in the dependencies** that parse untrusted data: `fast_xml` (expat-based XML parser NIF), `stringprep`
  (JID normalisation NIF), `fast_tls` (OpenSSL NIF), `ezlib` (zlib NIF), `eimp` (image conversion port), `sqlite3`.
  The XMPP codec and SASL code live in the `xmpp` dependency. These are maintained by ProcessOne alongside ejabberd;
  bugs in them that a remote peer can reach through ejabberd are in scope.

Trusted: the configuration files (`ejabberd.yml`, `ejabberdctl.cfg`), the Erlang distribution cookie, `ejabberdctl`
run by the operator, the database, Redis and LDAP servers themselves and the external authentication script.

## Components that matter most / least

- Most: anything reachable before authentication (stream setup, TLS, SASL/SCRAM, SASL EXTERNAL and certificate
  mapping, SASL2/Bind 2 and downgrade protection, JWT and OAuth token checks, registration, HTTP request parsing,
  BOSH/WebSocket session handling, MQTT CONNECT, STUN, s2s dialback), the authorisation checks in `mod_http_api`,
  `ejabberd_access_permissions`, `acl` and OAuth, cross-user and cross-vhost isolation (rosters, MAM, PubSub access
  models, MUC roles and affiliations, offline storage, HTTP upload slots) and the C NIFs listed above.
- Medium: modules that are not in the default configuration but commonly enabled (`mod_mix`, `mod_matrix_gw`, `mod_sip`,
  `mod_invites`, `mod_antispam`, `mod_muc_log`) and SQL/LDAP back ends.
- Least: features only an operator can reach (web admin pages behind the admin ACL, `ejabberdctl`, commands restricted
  to admins in `api_permissions`), import/export tools (`ejd2sql`, `jd2ejd`, `prosody2ejabberd`, `ejabberd_piefxis`),
  documentation generators (`ejabberd_doc`, `ejabberd_commands_doc`, `ejabberd_options_doc`).

## How to exercise it

- The image is built with `./configure --with-rebar=./rebar3 --enable-all --disable-elixir` and debug info. Compiled
  modules are in `_build/default/lib/*/ebin`, the NIFs in `_build/default/lib/*/priv/lib`. The sources of the
  dependencies, NIF C code included, are in `_build/default/lib/<dep>/src` and `c_src`.
- A development release with a ready configuration (virtual host `localhost`, test certificates, `admin@localhost` in
  the admin ACL) is in `_build/dev/rel/ejabberd`:
  - `_build/dev/rel/ejabberd/bin/ejabberdctl start && _build/dev/rel/ejabberd/bin/ejabberdctl started`
  - `_build/dev/rel/ejabberd/bin/ejabberdctl register admin localhost secret`
  - `_build/dev/rel/ejabberd/bin/ejabberdctl live` for an Erlang shell instead of a background node.
  - Configuration in `_build/dev/rel/ejabberd/conf/ejabberd.yml`, logs in `_build/dev/rel/ejabberd/logs/`.
  It listens on 5222/5223 (XMPP), 5269 (s2s), 5443 (HTTPS: `/api`, `/bosh`, `/ws`, `/upload`, `/captcha`, `/admin`),
  5280 (HTTP: `/admin` and ACME), 1883 (MQTT) and 5478/UDP (STUN/TURN). Raw XMPP can be sent with
  `nc localhost 5222` or `openssl s_client -starttls xmpp`; the API with
  `curl -k -X POST -d '{}' https://127.0.0.1:5443/api/status`.
- Tests: `make test` runs the Common Test suite (`test/ejabberd_SUITE.erl` and the `test/*_tests.erl` groups) against
  an in-process server with the back ends in `CT_BACKENDS`, which the image sets to `agnostic,mnesia,sqlite,ldap,extauth`
  (`agnostic` covers the `no_db`, `component` and `s2s` groups). `make test-<group>` runs one group, for example
  `make test-no_db` (about a minute). `make testeunit` runs the EUnit tests. The image is compiled for Common Test:
  `make testeunit` first recompiles the project, and the next Common Test run recompiles it back, about two minutes
  each way on two CPUs. Without a network, `s2s_dialback` in `no_db` fails on a DNS lookup; that failure is expected.
  MySQL, PostgreSQL, MSSQL and Redis groups need servers that are not in the image. `test/suite.erl` has helpers to open client streams and send stanzas,
  which is the quickest way to write a reproducer.

## How you rate severity

- Critical: remote code execution or authentication bypass (logging in as another account, a remote server
  impersonating another domain over s2s, calling admin commands without the admin ACL), without prior authentication.
  This includes flaws in SASL EXTERNAL certificate mapping, SASL2/Bind 2, SCRAM downgrade protection, JWT validation
  and OAuth token or scope checks.
  `binary_to_term` without `[safe]` on data an unauthenticated peer controls counts here, and so does SQL or LDAP
  injection reachable before authentication, such as from the SASL/auth path in `ejabberd_auth_sql` or
  `ejabberd_auth_ldap`.
- High: memory corruption in a NIF or port program reachable from the network (even without a working exploit), account
  takeover or privilege escalation from a normal account (user to admin, MUC participant to owner, one virtual host to
  another), forging another user's `from` address (from a client, a component or a privileged entity), SQL or LDAP
  injection that needs an authenticated session, reading or changing another user's private data (roster, MAM,
  offline messages, private storage, uploaded files) and unauthenticated remote denial of service that takes the node
  down or makes it unusable (crashing the VM, atom table exhaustion, unbounded memory growth, a single packet that
  blocks a listener).
- Medium: denial of service that needs a valid account or a federated server, stored XSS in pages rendered by ejabberd
  (`mod_muc_log`, web admin, invites pages), open redirect or CSRF on authenticated HTTP endpoints and TURN relay
  abuse beyond the configured permissions.
- Information leaks: rate by what is exposed. Passwords, SCRAM keys, OAuth/FAST tokens or private keys are high; message
  content or presence of another user is high; existence of an account or server internals is low.
- Low: crashes of a single session process that the supervisor restarts with no effect on other users, verbose errors.
- Resource use that a configured limit bounds (`max_stanza_size`, shapers, `max_fsm_queue`, `max_user_sessions`,
  upload size limits) is not a vulnerability while the limit holds; an unbounded default, or a way around the limit,
  is rated as above.
- A finding in a module the example configuration does not enable is rated as if the module were enabled; the report
  says which configuration it needs.

## Reports

- Name the scanned commit, the listener or module where the input enters, the configuration needed beyond
  `ejabberd.yml.example` and what the attacker needs (nothing, a local account, a federated server, a component, the
  admin ACL).
- Give a reproducer, preferably a Common Test case built with the helpers in `test/suite.erl`, otherwise a raw XMPP
  or HTTP exchange against the development release.
- Propose a patch against master. When the bug is in a dependency (`fast_xml`, `xmpp`, `stringprep`, `fast_tls`, ...),
  say so: the fix goes to that repository under github.com/processone, and ejabberd then bumps it in `rebar.config`.
- Report findings that share a root cause together.

## Anything to leave alone

- `test/`, `tools/`, `rel/`, `.github/`, `lib/` (Elixir glue) and dev-only code paths (`relive`, `sync`).
- Behaviour that requires the admin ACL or the operator: web admin and `ejabberdctl` commands that are powerful by
  design (`ext_mod` installing modules, `ejabberd_admin` reloading code, backups and restores, executing SQL) and any
  command an `api_permissions` rule deliberately opens (the example configuration lets any loopback client call
  `/api` without credentials). Report these only when the permission check itself can be bypassed.
- Anything that requires control of the configuration file, the Erlang cookie, epmd/distribution ports, the database or
  LDAP server or the external authentication script.
- Weak settings chosen in configuration (plain-text authentication allowed, `starttls_required: false`, anonymous
  login, open registration, `trusted_proxies: all`): these are operator choices, not vulnerabilities.
