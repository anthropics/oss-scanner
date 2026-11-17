# Threat model: ActivityPub for WordPress

## What this project does and where untrusted input enters

The ActivityPub plugin turns a WordPress site into a Fediverse server: users (and optionally the blog itself) become
ActivityPub actors that Mastodon and other servers can follow, reply to, like, boost and quote. This enrollment covers
the plugin as developed in `Automattic/wordpress-activitypub`, on `trunk`: `activitypub.php`, `includes/`,
`integration/`, `templates/` and the block and admin JavaScript in `src/` (built to the committed `build/`).

WordPress core is not in scope; it has its own enrollment (`projects/wordpress`). A finding whose root cause is in core
belongs there, unless the plugin uses core in a way that creates the vulnerability.

Untrusted input enters through:

- **Inbound federation.** The shared inbox and per-actor inboxes (`includes/rest/class-inbox-controller.php`,
  `class-actors-inbox-controller.php`), authenticated by HTTP signatures (draft-cavage and RFC 9421,
  `includes/signature/`, `includes/class-signature.php`), dispatched to the handlers in `includes/handler/`
  (Create, Update, Delete, Undo, Follow, Accept, Reject, Announce, Like, Move, QuoteRequest and others). Every field
  of an incoming activity except the signed top-level `actor` is attacker-controlled.
- **Data fetched from remote servers**: actors and their public keys, objects, collections, WebFinger, NodeInfo, and
  OAuth Client ID Metadata Documents (`includes/class-http.php`, `includes/collection/class-remote-*.php`,
  `includes/class-webfinger.php`, `includes/oauth/class-client.php`). A remote server controls everything it serves,
  including the `id` it declares for itself.
- **Public read endpoints**: content negotiation on any front-end URL (`Accept: application/activity+json` or
  `?activitypub`), the REST routes under `/wp-json/activitypub/1.0/` (actors, outbox, followers, following, liked,
  collections, replies, posts, comments, interactions, proxy), WebFinger and NodeInfo.
- **The client-to-server API and OAuth 2.0** (`includes/oauth/`, `includes/rest/oauth/`): dynamic client
  registration, authorization with PKCE, tokens and scopes, the outbox POST, and the event streams
  (`includes/rest/trait-event-stream.php`).
- **Logged-in users who are not fully trusted**: Authors and Contributors whose posts, comments and profile fields are
  federated or rendered to others; per-user settings; the plugin's admin screens and blocks.
- **Content from remote actors rendered on the site**: names, bios, avatars, emoji, comment content, links and media
  shown in comments, blocks, the reader and wp-admin.

### Actors

| Actor | Trust |
|-------|-------|
| Anyone on the Internet, including a remote Fediverse server they control | Untrusted. High band |
| A remote actor whose server the attacker does **not** control (another user on a shared instance) | Untrusted. High band. Crossing between two actors on the same remote host is a real boundary |
| An OAuth client holding a token for a user | Trusted only with that user's identity **and** the scopes granted |
| Subscriber (self-registration, when the site allows it) | Untrusted. High band |
| Contributor, Author | Untrusted beyond their own capabilities. Low band |
| Editor | Trusted with `unfiltered_html`, as in core. Non-XSS escalation is rated in the low band |
| Administrator | Fully trusted. Not rated |

## Components that matter most / least

Most important:

- **Signature verification and identity binding.** Both verifiers must enforce the same rules; the key's owner must
  be the activity's `actor`, not only share its host; every other reference a handler acts on (`object`,
  `attributedTo`, inner activities of an `Announce`) must be bound to the signing actor. Compare canonical hosts
  (`is_same_host()`, `fold_host()`); a gate that compares raw or differently decoded values is suspect.
- **Handlers that change or delete stored records** (Update, Undo, Delete, Move, Accept, QuoteRequest): who may change
  which comment, follower, remote actor or remote post. Ownership fallbacks that pass when no owner is recorded are a
  known defect class.
- **The remote cache**: anything written under a remote-controlled key (`id`, `url`, handle, `keyId`) must be bound to
  the origin that served or signed it, so one host cannot write a record under another host's identifier.
- **Content exposure**: drafts, pending, scheduled, private and password-protected posts, posts with ActivityPub
  visibility `local` or `private`, and posts that stopped being public, on every read path (content negotiation, REST
  collections, per-post routes, outbox, replies, event streams, block render callbacks). `is_post_publicly_queryable()`
  is the exposure gate; `is_post_disabled()` is a pipeline gate and leaks if used for exposure.
- **Authorization on REST routes and OAuth**: owner checks (`verify_owner()`), user ID `0` (the blog actor's ID is
  also the logged-out user's ID), and OAuth scopes on every read and write path.
- **SSRF** on every outbound fetch whose URL a remote can influence, including every hop of a chain and redirects.
- **Output**: remote values reaching HTML, an `href`, a redirect or `window.open()`; emoji and other remote names
  matched in content.

The maintainers keep their review checklists per area in `.agents/skills/review/guidelines/` in the checkout
(`signatures.md`, `inbox.md`, `remote-fetch.md`, `content-exposure.md`, `authorization.md`, `output.md`,
`multisite.md`, `cron.md`, `integrations.md`). Each lists past issues and the invariants that must hold. Use them to
find where to look; a finding still has to be shown against the current code.

Less important: `integration/` (code that only runs with a third-party plugin active) is in scope, but say which plugin
it needs. `tests/`, `bin/`, `local/`, `snippets/`, build tooling and Composer/npm dev dependencies are out of scope,
unless they put a vulnerability into what sites run.

## How to exercise it

- Run `wp-start` first. It starts MariaDB and Apache and is safe to run again. The site is at `http://127.0.0.1/` with
  `/%year%/%monthnum%/%postname%/` permalinks; `wp-stop` stops both.
- The site is a single-site install with the plugin active and one user per default role. Each password is the same
  as the username: `admin`, `editor`, `author`, `contributor`, `subscriber`. Registration is off.
- `wp --path=/var/www/html ...` (WP-CLI) sets up content, options and users; `wp --path=/var/www/html eval '...'` runs
  PHP in a loaded WordPress. The actor mode is the `activitypub_actor_mode` option (`actor`, `blog`, `actor_blog`).
- The plugin served by Apache is a symlink to `/src`, so a patch to `/src` takes effect on the next request.
- PHPUnit: `cd /src && vendor/bin/phpunit --filter <TestName>`, with MariaDB running. The suite uses the
  `wordpress_test` database.
- **There is no network.** Federation reproducers that need a remote server (a signing actor, a key, a fetched object)
  are best written as PHPUnit tests that answer remote requests through the `pre_http_request` filter, as the existing
  tests in `tests/phpunit/tests/` do, and sign inbound requests with a key pair generated in the test.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate administrator or a legitimate remote server would. Drive the attack as the claimed
actor: an unsigned or self-signed request from the attacker's own (mocked) server, a request with the attacker's own
OAuth token, or a login as the attacker's role. Do not sign as the victim's key, write the victim's stored actor or
key into the database, grant the attacker a capability or scope, or bypass the signature check in the test. Reading the
database to observe the outcome is fine.

## How you rate severity

The band is set by who the attacker is: anyone who can run a Fediverse server (that is, anyone), or a self-registered
Subscriber, is the high band; an admin-created Contributor or Author is the low band. Say in every report whether the
finding needs a non-default setting (actor mode, a visibility option, self-registration, a third-party plugin).

### Remote attacker, anonymous visitor or Subscriber

| Finding | Severity |
|---|---|
| Proven RCE, unchained | Critical |
| Acting as another actor: making the site accept activities, keys or profile data from one remote actor as another's, or as a local user | Critical when it reaches local users or content; High when it only affects stored remote data |
| Deleting, editing or approving content the attacker does not own (comments, followers, remote posts, quote approvals) | High |
| Stored XSS, SQL injection | High |
| Disclosure of non-public post content or titles (draft, private, password-protected, `local`/`private` visibility), or of private user data, with no guessing | High |
| Reading or changing another user's data through the client-to-server API or OAuth (wrong owner, missing scope) | High |
| SSRF that reads responses from internal hosts | High |
| Bypassing a block, a moderation rule or an interaction policy | Medium |
| Anything else with real security impact | Medium |
| Blind SSRF (no response body), including to link-local or CGNAT ranges core does not block | Low |
| No real security impact | Informative |

### Contributor or Author

| Finding | Severity |
|---|---|
| RCE | Medium to High |
| Stored XSS, SQL injection, IDOR, broken access control | Low |
| Anything else | Low |

### Rules by class

- **Validity comes before severity.** Name the actor, what they can already do, and what they gain. A missing guard in
  a helper is a finding only if a reachable caller passes it unvetted input; read every caller first.
- **Do not propose fixes that break federation.** A fix that tightens what the inbox or the fetcher accepts (algorithms,
  headers, content types, actor fields) must say what Mastodon, Pleroma/Akkoma, Misskey, Pixelfed, GoToSocial and
  Friendica send on that path and why they keep working.
- **XSS that leads to RCE is still XSS.**
- **Deserialization** needs a real gadget in installed code; without one it is Informative.
- **CSRF** needs realistic cross-origin exploitation under default `SameSite` cookies and a real gain.

## Anything to leave alone

- The deferred signature check in `includes/handler/class-delete.php`: a deleted actor's key may already be gone; a
  Tombstone check covers it.
- Link-local (`169.254.0.0/16`) and CGNAT (`100.64.0.0/10`) being reachable through core's `wp_safe_remote_*`: known,
  pending in core, and CGNAT stays allowed on purpose. Report only if the plugin bypasses core's validation.
- The `activitypub_allow_non_public_host` filter and other `activitypub_*` filters that a site owner or plugin uses to
  relax a check on purpose.
- Public data by design: actor profiles, public posts, follower and following counts or lists the user made public,
  WebFinger and NodeInfo contents, public keys.
- Username and author enumeration, version disclosure, missing security headers, rate limiting except on paths that
  trigger outbound fetches or allocate state for unauthenticated callers.
- Denial of service by volume, brute force, spam and social engineering.
- Anything an Administrator can already do, and XSS by an Editor or Administrator.
- Findings that need `WP_DEBUG` or `display_errors` on, a server misconfiguration or a compromised host.
