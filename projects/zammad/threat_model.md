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

## How we rate severity

Rate a finding by what it reaches, including any pivot, and by the least privileged role that can trigger it.
Our published advisories (https://github.com/zammad/zammad/security/advisories) show how we rated past
findings; follow them where this section is silent.

- **Critical**: unauthenticated remote code execution; authentication bypass to any account; unauthenticated
  access to tickets, users or attachments; account takeover of an agent or admin without user interaction;
  SQL injection that reads all tickets or grants access.
- **High**: remote code execution by a customer or agent; privilege escalation (customer to agent, agent to
  admin); a customer reaching tickets or data of other customers or organisations; an agent reaching groups
  they have no access to; other SQL injection; stored XSS that an external sender (email, form, chat,
  messenger) can place into an agent's session; SSRF that reaches cloud metadata; local privilege escalation to
  root through the packages or the container image; denial of service that an unauthenticated attacker causes
  with a few requests.
- **Medium**: stored XSS that needs an authenticated agent or customer to place; SSRF that a customer or agent
  can trigger against internal hosts; CSRF on state-changing actions; disclosure of personal data to an
  authenticated user who should not see it; an admin reading stored credentials or settings outside their
  admin permissions; brute force of passwords or two-factor codes because a rate limit is missing; account
  enumeration on login, signup or password reset.
- **Low**: disclosure of non-personal metadata (counts, IDs, existence of records); issues that need unusual
  user interaction; denial of service that needs authentication.

An issue that needs full admin permissions is **low** at most, unless it breaks out of the application to the host
(code execution, reading files outside the storage), which is **high**.

## Anything to leave alone

The left column is intended behaviour. The right column says what would make it a finding.

| Intended behaviour | Report it when |
|---|---|
| Admins and the operator are trusted with what their permissions allow. | A lower role, or an admin without that permission, can do the same thing. |
| Email cannot prove its sender: Zammad identifies the customer by the `From` address. | A signed or encrypted email (S/MIME, PGP) is accepted although its signature or encryption check fails. |
| An email that names a ticket number in its subject is added to that ticket as a follow-up, whoever sends it. | The follow-up reaches a ticket whose number was not in the email, or a group that does not allow follow-ups. |
| The web form, the chat and the public knowledge base accept or show content without login. | They expose internal content, or create data outside what their configuration allows. |
| Customers of a shared organisation see all tickets of that organisation. | A customer sees tickets of an organisation they do not belong to, or of a non-shared one. |
| An agent with `read` access to a group sees every ticket in it. | An agent changes a ticket with only `read` access, or reaches a group without access. |
| Admins may point webhooks, integrations, LDAP and SSO at private and loopback addresses of their network. | The request reaches cloud metadata, or a non-admin can choose the destination. |
| Operators can choose less safe settings than the defaults. | A default setting is insecure. |

Also leave these alone:

- Denial of service through large volumes of legitimate input (many requests, tickets or emails), and missing
  rate limits outside authentication.
- Missing security headers or cookie flags, self-XSS and clickjacking without a sensitive action, unless the
  report shows a concrete impact.
- Attackers with direct access to the database, the file storage or the host.
- A vulnerable dependency, unless the report shows a working exploit through Zammad's own code.
- External services (mail servers, LDAP, SSO providers, messengers) cannot be exercised
  offline; reason about them from the source and say so.
