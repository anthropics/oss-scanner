# Threat model

OpenOlat is a web-based learning management system. One instance serves many institutions, courses and groups that
must stay apart. Architecture and coding rules: `CLAUDE.md` and `doc/openolat-architecture.md` in the repository.

## Trust model

- **Anyone** can reach the login, guest access and self-registration (both on by default), so "any user" includes
  guests and self-registered accounts.
- **Learners** see only their own results and what their memberships grant. **Coaches** see the participants they
  coach. **Authors** and course **owners** manage only their own resources.
- **Organisation roles** (administrator, user manager, roles manager, ...) act only inside their organisation and its
  sub-organisations. Reaching another organisation, or gaining a role one does not hold, is a finding.
- **System administrators** and the configuration are trusted. Admin-only issues count only if they reach the host.

Most sensitive: grades, test answers and submissions, assessment results, anonymous survey results, personal data.

Focus on authentication, authorization (roles, organisations, course and group membership, REST endpoints), XSS,
file handling (uploads, ZIP and course/test imports), SQL injection and SSRF. Out of scope: `src/test/`, `doc/`, and
third-party code unless OpenOlat reaches a flaw in it.

## How to exercise it

- `openolat-start` runs PostgreSQL and OpenOlat on `http://localhost:8088/`; `openolat-stop` stops both. After a
  code change: `mvn -o -q -Ptomcat -DskipTests package && openolat-stop && openolat-start` (2–3 minutes).
  Log: `/opt/tomcat/logs/catalina.out`. Config: `/opt/tomcat/lib/olat.local.properties`.
- The only account is `administrator` / `openolat`. Create the users and courses you need through REST
  (HTTP Basic as administrator; `/restapi/openapi.json` lists everything):
  - user: `PUT /restapi/users` with JSON `{"login", "password", "firstName", "lastName", "email"}`; passwords need
    12+ characters, a letter and a digit or special character
  - role: `POST /restapi/users/{key}/roles` with JSON `{"author": true}`
  - course: `PUT /restapi/repo/courses?title=...&initialAuthor={key}` (without a `Content-Type` header), then
    `PUT /restapi/repo/entries/{entryKey}/status?newStatus=published`
  - member: `PUT /restapi/repo/entries/{entryKey}/participants|coaches|owners/{key}`
- JUnit: `mvn -o -Ptomcat -Dwith-postgresql -Dtest=<Class> -Dsurefire.failIfNoSpecifiedTests=false test`.

### The web UI with a headless browser

Playwright for Python with Chromium is installed (`python3` imports it). Use it to prove issues in the UI: XSS (the
victim's `alert()` fires a `dialog` event), pages a role must not reach, multi-step flows. Use one browser context
per user.

- Login at `/dmz/` takes two steps: fill `o_fiooolat_login_name`, click `o_fiooolat_login_button`, then fill
  `o_fiooolat_login_pass` and click the button again.
- A user's first login shows the terms of use (tick `acknowledge_checkbox`, click "Accept"). Later logins may ask
  "resume your last session?" in a modal that blocks the page.
- The UI is AJAX. After each click, wait until `o_info.linkbusy` is false before reading the page. Component ids in
  URLs change per session, so never guess them.
- `/url/RepositoryEntry/{entryKey}` opens a course directly.

curl works too, e.g. to replay a POST recorded in the browser with changed parameters. After login, `/auth/` answers
with a JavaScript reload to `?oow=`; follow it by hand.

## How we rate severity

- **Critical**: code execution on the server, file access on the host, SQL injection, authentication bypass or
  account takeover, as any user or without login.
- **High**: escalation to another role or organisation; reading or changing other users' grades, submissions or
  personal data across courses, groups or organisations; stored XSS against other users; SSRF with response.
- **Medium**: authorization bypass inside one course or group; reflected XSS; CSRF; open redirect in login or SSO;
  blind SSRF; a normal user taking the server down with few requests.
- **Low**: information disclosure without personal data, DoS that needs admin rights or many requests, admin-only
  issues.

Rate an issue that needs a common non-default setting (SSO, LDAP, LTI, WebDAV) the same; one that needs an unusual
setting one level lower.

## Leave alone

- Content authors publish by design (HTML, JavaScript, SCORM) running for their own participants. The image has no
  separate content domain (`server.content.domainname`), which production should use.
- Missing rate limits or security headers, clickjacking and self-XSS, unless they lead to one of the outcomes above.

## Reports

One report per root cause, with the role and settings needed and a reproducer: a Playwright script, HTTP requests or a
JUnit test. Patches against `master`, following `CLAUDE.md`, with a regression test where practical.
