# Zammad threat model for scanner reports

Zammad is a self-hosted web-based helpdesk. Agents work on tickets that customers create by email, web form,
chat, messenger channels and the customer portal. One installation serves one organisation running a helpdesk,
but it holds the conversations, personal data and attachments of many customers and customer organisations,
which must stay separated from each other. The backend is Ruby on Rails with PostgreSQL and Redis; the agent
interface exists twice, as the legacy CoffeeScript app (`app/assets/javascripts/`) and as the new Vue 3 apps
(`app/frontend/`).

## Roles and trust

From least to most trusted:

- **Anonymous visitors** of the login page, the public knowledge base, the web form and the chat widget.
- **External senders** who never log in: anyone who can send an email, a Telegram, WhatsApp, Facebook or SMS
  message, or a CTI or monitoring callback to the installation.
- **Customers** (`ticket.customer`): see their own tickets, and those of their organisation if it is shared.
- **Agents** (`ticket.agent`): see the tickets of the groups they are assigned to, with per-group access
  levels (`read`, `create`, `change`, `overview`, `full`).
- **Admins** and the **operator** of the installation: trusted with what their permissions allow. Admin
  permissions are granular (`admin.user`, `admin.channel_email`, `admin.webhook` and more); an admin holding
  some of them is not trusted with the others.

## Where untrusted input enters

- Inbound email (IMAP, POP3, Microsoft 365, Google, stdin): MIME parsing, HTML bodies, attachments, S/MIME and
  PGP, postmaster filters (`app/models/channel/`).
- REST API (`app/controllers/`, `config/routes/`), GraphQL API (`app/graphql/gql/`), the MCP server
  (`app/controllers/mcp_controller.rb`) and the WebSocket server (`lib/sessions/`).
- Authentication: password login, two-factor authentication, SSO (SAML, OAuth providers), LDAP, API tokens,
  password reset and signup.
- Unauthenticated surfaces: web form (`app/controllers/form_controller.rb`), chat, public knowledge base,
  calendar subscriptions and other token-protected URLs.
- Webhooks and callbacks from integrations (Telegram, WhatsApp, Facebook, SMS, Sipgate, Placetel, generic CTI,
  Checkmk, monitoring) under `app/controllers/`.
- Content rendered in other users' browsers: ticket articles, user and organisation fields, knowledge base
  answers, in both frontends.

## Components that matter most

- **Authorization**: Pundit policies (`app/policies/`), GraphQL object and field authorization, group access
  levels and customer/organisation separation. A customer or agent reaching tickets, users or organisations
  outside their access is the most serious class of bug for us.
- **Authentication and sessions**, including SSO, two-factor authentication and token handling.
- **HTML sanitization** of email and user content (`lib/html_sanitizer.rb`, `lib/html_sanitizer/`), and every
  place that renders it.
- **Template and placeholder rendering** in notifications, triggers, macros, text modules and webhooks
  (`lib/notification_factory/`).
- **Outbound requests** (webhooks, integrations, external data sources). The SSRF guard is
  `lib/hostname_safety_check.rb`, used through `lib/user_agent.rb`.
- **File handling**: attachments, uploads, imports and previews.
- **Packaging**: the DEB/RPM packages (`.pkgr.yml`, `contrib/packager.io/`) and the container image
  (`Dockerfile`, `bin/docker-entrypoint`), for privilege escalation on the host.

Out of scope:

- `spec/`, `test/`, `.dev/`, `.devcontainer/`, `.gitlab/` and `i18n/`.
- Routes that exist only outside production (`config/routes/test.rb`, `TestsController`).
- Third-party code vendored under `vendor/`, `public/assets/` and `app/assets/javascripts/app/lib/`
  (`base/`, `bootstrap/`, `flot/`, `rangy/`, `spine/`), unless Zammad's own use of it makes it exploitable.
  The embeddable chat and web form widgets under `public/assets/chat/` and `public/assets/form/` are Zammad's
  own code and in scope.
- Behaviour you classify as a functional bug rather than a security issue.

## How to exercise it

Every dependency is installed and the test database is migrated and seeded (`RAILS_ENV=test`). PostgreSQL,
Redis and Elasticsearch are installed but stopped, so start them first:

```sh
zammad-services
```

- `bundle exec rspec spec/requests/...` for REST endpoints, `spec/graphql/...` for GraphQL, `spec/models/...`
  and `spec/lib/...` for the rest. Factories are in `spec/factories/`, and the existing request and GraphQL
  specs make good starting points for a reproducer. Specs tagged `searchindex: true` use the local
  Elasticsearch (`ES_URL` and `ES_INDEX` are set). They recreate all indices for each example and are slow;
  run single examples (`path/to/spec.rb:LINE`) rather than whole files.
- `bundle exec rails runner '...'` to try code against the test database.
- For a reproducer against a running server, create users with known passwords and start Rails. RSpec resets
  the test database, so run this again after a spec run:

  ```ruby
  # /tmp/users.rb, run with: bundle exec rails runner /tmp/users.rb
  UserInfo.current_user_id = 1
  group = Group.first
  { 'admin@example.com' => %w[Admin Agent], 'agent@example.com' => %w[Agent], 'customer@example.com' => %w[Customer] }.each do |email, roles|
    user = User.create!(login: email, email: email, firstname: roles.first, lastname: 'Test', password: 'Scanner-Test-123!', roles: Role.where(name: roles))
    user.update!(group_names_access_map: { group.name => 'full' }) if roles.include?('Agent')
  end
  ```

  Then `bundle exec rails server -p 3000 -b 127.0.0.1` serves the REST API under `/api/v1/` and GraphQL under
  `/graphql`, with HTTP basic authentication for these users. `zammad-services` starts Elasticsearch empty;
  for search against the server, set `Setting.set('es_url', ENV['ES_URL'])` and
  `Setting.set('es_index', ENV['ES_INDEX'])`, then run `bundle exec rake zammad:searchindex:rebuild`.
- S/MIME and PGP: certificates, keys and signed or encrypted sample mails are in `spec/fixtures/files/smime/`
  and `spec/fixtures/files/pgp/`, and `spec/lib/secure_mailing/` shows how to drive the incoming and outgoing
  checks with them.
- Browsers and external mail servers are not available: `spec/system/` and the browser-based frontend specs do
  not run here. Frontend unit tests do (`pnpm test --run <path>`).

## How reports should look

State the scanned commit, the role the attacker holds (the least privileged one that works), any setting that
differs from the default, the route or entry point, and the full path to the impact. A failing RSpec request or
GraphQL spec written from the attacker's role is the ideal reproducer. Mark which parts you demonstrated and
which come from reading the source. Many features are reachable through both the REST and the GraphQL API, so
say whether the other API has the same gap. Merge findings that share one root cause, and send one report per
finding, in English. Patches should fix the check where it is enforced, follow the conventions in
`.dev/agent_docs/`, and come with an RSpec example that fails without the fix.

Before reporting, check that the finding is new and still present:

- Scan the current `develop` branch, and look at the commits since the scanned one: findings are often fixed
  shortly after the code that introduced them.
- Check the published advisories. A finding one of them already covers is a duplicate; say so instead of
  reporting it again.
- Fixes reach the `stable` branches as cherry-picks with different commit hashes. Compare the code on the branch,
  not commit ancestry, before concluding that a fix is missing from a release.
- A finding that bypasses or extends the fix of a published advisory is a new finding. Name the advisory and
  show the path its fix misses.
- Variants that reach the same sink are one finding: different message structures, other ways to plant the same
  reference, or other forms served by the same code. Merge them across the whole scan, not only within one
  report.

## How we rate severity

Every confirmed finding gets a GitHub security advisory with a CVSS v4.0 base vector, and its band is the one
GitHub computes from that vector: low (0.1–3.9), moderate (4.0–6.9), high (7.0–8.9), critical (9.0–10.0).
Propose a vector with every report and use these band names. The examples below show where typical findings
land; when an example and the vector disagree, the vector decides, and the report should say why. Our published
advisories (https://github.com/zammad/zammad/security/advisories) show how we rated past findings; follow them
where this section is silent.

Rate a finding by what it reaches, including any pivot, and by the least privileged role that can trigger it.
Features that are on by default, such as customer self-registration, count as available to the attacker. A
finding that needs a feature that is off by default, a specific hosting environment or a state the attacker
cannot bring about still counts, but usually lands one band lower.

- **Critical**: unauthenticated remote code execution; authentication bypass or takeover of an agent or admin
  account by someone without an account; unauthenticated read and write access to tickets, users or
  attachments; SQL injection reachable without an account.
- **High**: remote code execution or SQL injection by any signed-in role; privilege escalation (customer to
  agent, agent to admin, an admin with some granular permissions to the rights of a full admin);
  unauthenticated read access to tickets, users or attachments; a customer reaching tickets or data of other
  customers or organisations; an agent reading or changing tickets of groups they have no access to; script
  that runs in another user's session, whoever places it; denial of service that stops the web application,
  background jobs or email processing for everyone and that someone without an agent account causes with a few
  requests or messages; local privilege escalation to root through the packages or the container image.
- **Moderate**: HTML injection that the shipped Content Security Policy keeps from running script, when the
  victim only has to open the page; disclosure of personal data, internal fields or internal metadata to an
  authenticated user on a default installation; account enumeration on login, signup or password reset; missing
  brute-force protection; an admin reading stored credentials or data outside their admin permissions; SSRF
  that a customer or agent can trigger against internal hosts; denial of service that degrades one function but
  leaves the service usable; CSRF on a state-changing action that any website can mount.
- **Low**: findings of the kinds above whose impact stays small (one record, metadata, a single message) and
  that also need a non-default setting, a specific setup of the victim, a race or a captured message; CSRF that
  only a same-site page can mount; issues that need a deliberate or unusual action by the victim; denial of
  service that needs an agent or admin account.

An admin who holds only some granular admin permissions is not a full admin: rate what they reach beyond those
permissions as above. An issue that needs full admin permissions is **low** at most, unless it reaches the host
beyond what a full admin already reaches as the application user (code execution as root or another host user,
reading files outside the installation), which is **high**.

## CVSS v4 conventions

We score base metrics against a default installation of the current release.

- `AV:N` for anything reached over HTTP, email, messengers, webhooks or callbacks; `AV:L` only from a shell on
  the host.
- `AC:L` unless the attacker must defeat a protection they cannot influence. Preconditions go into `AT`, not
  `AC`.
- `AT:P` when the attack needs a feature or integration that is off by default (S/MIME, PGP, LDAP, SSO, the web
  form, chat, monitoring, AI features, messenger channels and similar), a specific hosting environment, a state
  the attacker cannot bring about (an admin action, a temporary state of the installation), a specific setup of
  the victim (role combinations, several organisations, a message the attacker must have captured), a race or a
  timing measurement, or a same-site position for CSRF. `AT:N` when a default installation is enough, including
  features that are on by default such as self-registration.
- `PR:N` for anonymous visitors and external senders. `PR:L` for customers (self-registered ones too), agents
  and their API tokens. `PR:H` for any admin permission, also a single granular one, and for permissions that
  only the Admin role holds by default, such as knowledge base editor.
- `UI:N` when no person has to act, including the automatic processing of an incoming message. `UI:P` when the
  victim only uses Zammad as usual: opens a ticket, record, public page or link, or relies on what Zammad shows.
  `UI:A` when the victim has to take a deliberate step: sign in, send or confirm something, run a search, change
  configuration, or click a link inside an email.
- `VC`/`VI`/`VA`: `H` for data of all groups or organisations, a full session or account, script running in the
  victim's session, forged content shown as authentic, or a stop of the service, background jobs or email
  processing. `L` for limited reach (one record or field, metadata), HTML injection that cannot run script, or
  one degraded function.
- `SC`/`SI`/`SA` for impact outside Zammad: a website that embeds the chat widget, a connected external service
  or directory, or a cloud account behind leaked credentials.
- Chains: score the finding on its own. If you demonstrated that a second weakness raises the impact, give that
  vector as well and name the weakness it needs.

## Anything to leave alone

The left column is intended behaviour. The right column says what would make it a finding.

| Intended behaviour | Report it when |
|---|---|
| Admins and the operator are trusted with what their permissions allow. | A lower role, or an admin without that permission, can do the same thing. |
| Email cannot prove its sender: Zammad identifies the customer by the `From` address. | A signed or encrypted email (S/MIME, PGP) is accepted although its signature or encryption check fails. |
| An email that names a ticket number in its subject is added to that ticket as a follow-up, whoever sends it. | The follow-up reaches a ticket whose number was not in the email. |
| Whether an inbound message becomes an agent or a customer article follows the sender address, which is not authenticated. | The message gains more than a forged `From` and a known ticket number already give. |
| Automatic replies and rejection notices go to the sender the inbound mail names. | A reply carries data of the installation or of another user. |
| The web form, the chat and the public knowledge base accept or show content without login. | They expose internal content, or create data outside what their configuration allows. |
| Customers of a shared organisation see all tickets of that organisation. | A customer sees tickets of an organisation they do not belong to, or of a non-shared one. |
| An agent with `read` access to a group sees every ticket in it. | An agent changes a ticket with only `read` access, or reaches a group without access. |
| Admins may point webhooks, integrations, LDAP and SSO at private and loopback addresses of their network. | The request reaches cloud metadata, or a non-admin can choose the destination. |
| Operators can choose less safe settings than the defaults. | A default setting is insecure. |
| Group and channel workflow settings decide how legitimate input is routed and shown: whether closed tickets accept follow-ups, how closed states are detected, whether a channel is active, whether agents may create new tag names, the chat's visitor restrictions. They are not access control. | Getting past one lets someone read data, or change a ticket, user or record that is not their own. |
| A link between records a user can open is metadata of those records. | The link reveals a record the user cannot open, or changes its content. |
| Aggregate counters and timestamps without personal data are not protected, and neither is metadata about records inside the user's own access. | The response contains personal data, content or credentials, or reveals records outside the requester's access. |
| Admins decide which certificates and keys are trusted; one they import is trusted as imported. The descriptive text of a signature status is informational. | A message shows as validly signed for a sender whose key did not sign it, without an admin importing anything the attacker supplied. |
| Messenger and social channels file messages under the sender's platform identity. Wrong author attribution, or one item failing to import, is a functional bug. | The sender reaches another user's data or account. |
| Access an attacker keeps after first compromising the victim's session, mailbox or a mailed link belongs to that compromise. | The attacker gets the session, the mailbox content or the link without a prior compromise. |
| A missing cleanup or guard that matters only after a separate bug has fired. | Report the bug that fires it, and add what the missing cleanup adds to its impact. |

Also leave these alone:

- Denial of service through large volumes of legitimate input (many requests, tickets or emails), and missing
  rate limits outside authentication.
- Missing security headers or cookie flags, self-XSS and clickjacking without a sensitive action, unless the
  report shows a concrete impact.
- Attackers with direct access to the database, the file storage or the host, including values that reach
  only server-side logs or process output.
- A vulnerable dependency, unless the report shows a working exploit through Zammad's own code.
- External services (mail servers, LDAP, SSO providers, messengers) cannot be exercised
  offline; reason about them from the source and say so.
