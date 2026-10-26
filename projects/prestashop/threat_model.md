# Threat model: PrestaShop

## What this project does and where untrusted input enters

PrestaShop is an open-source e-commerce platform written in PHP (legacy ObjectModel and controllers, plus Symfony for the newer back office and the Admin API), on MySQL or MariaDB. A merchant installs it on their own hosting; one installation runs one shop, or several shops when multistore is enabled. Shops are public websites that take payments and hold customers' personal data, so a vulnerability usually affects both the merchant and their customers.

The scan is of the core repository's **maintenance branch** for the supported release line (`9.2.x` at the time of writing, the branch in `project.yaml`), built the way the release archive is built. Code on this branch is what merchants run or will get in the next patch release. `composer install` also installs the native modules and themes that `composer.json` requires, into `/src/modules/<name>` and `/src/themes/<classic|hummingbird>`. They are **in scope**, as our security policy covers the core and every module listed in `composer.json`. Each comes from its own repository (`https://github.com/PrestaShop/<name>`, for example `PrestaShop/ps_facetedsearch`, `PrestaShop/classic-theme`, `PrestaShop/hummingbird`); name the module and its version (from `composer.lock`) in every report about one.

Untrusted input enters through:

- **Front office**, reached by anonymous visitors and customers: `index.php` and the front controllers in `controllers/front/` (catalog, search, cart, checkout and order, account, addresses, order history and detail, order return, guest tracking, contact, password reset, attachment and virtual product download, customization upload), module front controllers (`index.php?fc=module&module=<name>&controller=<c>` and their friendly URLs), AJAX endpoints, and payment module validation and return URLs. Customer self-registration and guest checkout are **on by default**, so assume any attacker has a customer account.
- **Content stored by one actor and rendered to another**: product customizations (text and uploaded files), order and contact messages, gift messages, addresses, customer names, product reviews (`productcomments`), wishlists (`blockwishlist`), newsletter sign-ups, cart and order data, and everything employees enter in the back office.
- **Cookies**: the front and back office cookies (`classes/Cookie.php`, encrypted with the `new_cookie_key` from `app/config/parameters.php`), the cart and customer identifiers inside them, and the employee session (`employee_session` table).
- **Back office**, `/admin-dev/` in this image (see the trust model). Legacy controllers in `controllers/admin/` and module admin controllers, Symfony controllers in `src/PrestaShopBundle/Controller/Admin/` guarded by `#[AdminSecurity]` attributes, and the CSRF tokens they use (`_token` on Symfony routes, `token` on legacy ones).
- **Admin API** (`/admin-api/`, `src/PrestaShopBundle/ApiPlatform`, the `ps_apiresources` module): OAuth2 client credentials, each API client limited to the scopes it was granted. Configured in Advanced Parameters > Admin API.
- **Webservice** (`/api/`, `webservice/dispatcher.php`, `classes/webservice/`): the legacy XML/JSON API. Disabled by default; each key has per-resource, per-method permissions and is bound to shops.
- **Files**: CSV import (`AdminImportController`, including image URLs it fetches), image and attachment uploads, module and theme ZIP archives, localization packs.
- **Server-side fetches**: image URLs in import, "import from the web" for themes, the module catalogue (`ps_distributionapiclient`), localization and translation pack downloads.

## Trust model

Severity depends first on who the attacker is. From least to most privileged:

| Actor | How they get there | Trust |
|---|---|---|
| Anonymous visitor | none | Untrusted |
| Customer or guest | self-registration or guest checkout, on by default | Untrusted. Must only reach their own carts, orders, addresses, messages, invoices, credit slips, returns, customizations and wishlists |
| Admin API client | created by an employee, with a set of scopes | Untrusted beyond its scopes. A client must not grant itself scopes, reach resources outside them, or keep working after it is disabled or its token revoked |
| Webservice key | created by an employee, with per-resource permissions and shop association | Untrusted beyond its permissions and shops |
| Employee with a restricted profile | created by a SuperAdmin; default profiles Logistician, Translator, Salesman, or a custom one | Untrusted beyond their profile. Permissions are per back office page (tab) and per action (view / add / edit / delete), plus per-module permissions, and in multistore the shops they are associated with. Doing something the profile does not allow is a finding |
| Employee whose profile grants code-execution features | has *Modules* (upload or install a module), *Design > Theme & Logo* (import a theme), or equivalent permissions | Trusted with code execution through those features by design, but not beyond them |
| SuperAdmin | created at install | Fully trusted |
| Operator | shell, database, `app/config/parameters.php`, `config/defines*.inc.php`, the web server | Fully trusted |

Points about the back office:

- When installing from a release archive, the installer gives the back office folder a random name (`admin` + random characters), and merchants are expected to keep it private: it keeps the back office login and its endpoints away from automated attacks. In this image it is `admin-dev`, its name in the repository. A way for an anonymous visitor to learn the folder name from a shop with default settings (in a page, header, script, error or file the shop serves) is a finding, rated Low. A finding in an unauthenticated back office endpoint is in scope; say that the attacker needs the folder name, and score it with `AC:H`.
- **Uploading or installing a module, or importing a theme, runs PHP by design.** "An employee who may upload modules can run code" is not a finding. A finding is code execution, file write or path traversal reached with a permission that should not allow it (for example through translations, email templates, import, the SQL manager, performance or debug settings, the image settings or the file system of another feature), or with a narrower permission than the one that grants module or theme installation.
- **Advanced Parameters > Database > SQL Manager** runs `SELECT` queries by design. Its restrictions (`classes/RequestSql.php`: only `SELECT`, blocked functions, masked `passwd` and `secure_key` columns, current database only) are a boundary; bypassing them is a finding.
- Employees may enter HTML in descriptions and CMS pages; it is filtered by HTMLPurifier when `PS_USE_HTMLPURIFIER` is on (the default). Script that survives that filter, or reaches a page through a field that is meant to be plain text, is a finding.
- In multistore, an employee or a Webservice key associated with some shops must not read or change another shop's data.

## Components that matter most / least

Highest priority:

1. **Unauthenticated or customer-level** SQL injection, code execution, object injection (`unserialize()` and PHP sessions or cookies an attacker can influence), file write or upload bypass, and authentication bypass in the front office, module front controllers, the Admin API and the Webservice.
2. **Access control for customers and guests**: object ids taken from the request (`id_order`, `id_address`, `id_cart`, `id_customization`, `id_order_return`, wishlist ids and tokens, `secure_key`, order references) in front controllers and module front controllers. A check enforced on the main path is often missing from a secondary one: PDF invoices and credit slips, AJAX actions, guest tracking, file download, module controllers.
3. **Back office authorization**: `#[AdminSecurity]` attributes on Symfony routes, `$this->access()` / `viewAccess()` / `tabAccess` checks and the `action=` and `submit*` dispatch of legacy controllers, bulk actions, AJAX actions, and module admin controllers. Compare a route with its siblings: a check present on `edit` but missing on `bulkDelete` or on an AJAX twin is a common real defect.
4. **XSS**: Smarty templates (front office Smarty escapes by default; `nofilter` turns that off, and back office Smarty does not escape by default), Twig `|raw`, JavaScript that builds HTML, and HTML emails (`mails/`, the email templates, contact and order messages). Stored XSS from a customer that runs in an employee's session is the most important case.
5. **Checkout and payment logic**: getting goods, discounts or free orders the customer is not entitled to (cart rules, prices, currency or country changes during checkout, race conditions in `PaymentModule::validateOrder()`, order duplication). Show a concrete cart and order outcome.
6. **CSRF** on state-changing back office actions, and on front office actions that change a customer's account, addresses or orders.
7. **SSRF** through image URLs in import, theme import from the web, and any other server-side fetch.
8. **Secrets and crypto**: cookie encryption, `secure_key`, password reset tokens, Admin API tokens, and trusted proxy handling of `X-Forwarded-For` (client IP is used for login restrictions and logs).

Lower priority:

- Feature-flagged code that is off by default (`ps-console prestashop:feature-flag list`): in scope, but say which flag the finding needs.
- The installer (`install-dev/`, `install/` in a release). Merchants must delete it after installation (the back office refuses logins until they do), so this image keeps it off the web. Report an installer issue only if it is reachable on a shop whose merchant has not deleted it yet, and say so.

Out of scope:

- `vendor/` and the third-party JavaScript under `js/` and in the themes and modules, unless PrestaShop's own code uses them in a way that creates the vulnerability. Report those upstream.
- Third-party modules and themes from PrestaShop Addons or elsewhere, and custom overrides.
- Modules from PrestaShopCorp that are not in `composer.json` (for example `ps_accounts`, `ps_checkout`, `ps_mbo`, which the Classic edition archive adds), and the cloud services they talk to.
- `tests/`, `tools/`, `.github/`, `.docker/` and other development files a release archive does not ship (`tools/build/` decides what it ships).
- PrestaShop 1.6, 1.7 and 8.x, except to say a finding also affects them.

## How to exercise it

- Run `ps-start` first. It starts MariaDB and Apache (the container has no init system) and is safe to run again. `ps-stop` stops both. The shop is at `http://127.0.0.1/` (friendly URLs on) and the back office at `http://127.0.0.1/admin-dev/`.
- The shop is installed with the demo catalog and these accounts:

  | Login | Password | Role |
  |---|---|---|
  | `admin@example.com` | `OssScanner-admin1!` | SuperAdmin employee |
  | `logistician@example.com` | `OssScanner-logistician1!` | Logistician profile |
  | `translator@example.com` | `OssScanner-translator1!` | Translator profile |
  | `salesman@example.com` | `OssScanner-salesman1!` | Salesman profile |
  | `alice@example.com` | `OssScanner-alice1!` | customer |
  | `bob@example.com` | `OssScanner-bob1!` | customer |
  | `pub@prestashop.com` | `123456789` | demo customer with an address and orders |

  To test a specific back office permission, create a profile in Advanced Parameters > Team > Profiles, give it only the permissions the scenario needs in Permissions, and assign it to a new employee.
- `ps-console` runs `bin/console` as `www-data`, the Apache user. Useful commands: `ps-console prestashop:config set <KEY> --value <v>`, `ps-console prestashop:module install <name>`, `ps-console prestashop:feature-flag enable <flag>`, `ps-console prestashop:api-client create <client-id> --scopes=<s1,s2>` (Admin API clients), and `ps-console prestashop:theme:enable classic` (the default theme is Hummingbird; Classic is installed too).
- To enable the Webservice: `ps-console prestashop:config set PS_WEBSERVICE --value 1`, then add a key in Advanced Parameters > Webservice.
- To enable multistore: `ps-console prestashop:config set PS_MULTISHOP_FEATURE_ACTIVE --value 1`, then add a shop in Advanced Parameters > Multistore.
- The database is `mysql://prestashop:prestashop@127.0.0.1/prestashop`, table prefix `ps_`. `mariadb prestashop` opens a client as root.
- `_PS_MODE_DEV_` is off, as on a production shop: PHP errors go to Apache's log on stderr, not into responses. It is set in `config/defines_custom.inc.php`; you may turn it on there while debugging, but do not report findings that need it.
- Mail is not sent (`PS_MAIL_METHOD` 3). To read a password reset or other token, take it from the database, not from an email.
- The PHP code Apache serves is `/src`, so a patch takes effect on the next request (OPcache revalidates every request). After changing Symfony configuration or services, run `ps-console cache:clear`.
- Dependencies are installed with `--no-dev`, as in a release, so the test suites do not run here. Reproduce over HTTP.
- `/src` is the git checkout. Files the build and the installer create are ignored by git, so `git -C /src diff` shows your patch and `git -C /src checkout -- .` undoes it.

### Reproducers must not fabricate the attacker's state

Set up only what a legitimate merchant would: create employees with real profiles, set real configuration, add content. Then drive the attack **as the claimed actor**, through HTTP. Do not take a CSRF token from a SuperAdmin session for a lower-privileged employee, grant the attacker the permission they are supposed to gain, or change the target through the database. Reading the database to observe the outcome is fine. Run a positive control as the same actor: a 403 or a redirect can come from a check unrelated to the one under test.

For XSS, show that the payload executes in a browser context, not only that it appears in the HTML. Prove impact without maximising it, and do not destroy data you did not create.

## How you rate severity

We publish advisories on GitHub with a **CVSS v3.1** score. Give the vector and score with every report, for example `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` (9.8), then apply the caps below and say if a cap lowered the band.

Map the actor to `PR`:

- Anonymous visitor: `PR:N`.
- Customer (self-registration is on by default), Admin API client, Webservice key: `PR:L`.
- Any back office employee, whatever their profile: `PR:H`.

**Findings that need a back office login are capped at Medium (CVSS below 7.0)**, whatever the impact: SQL injection, file read, write or deletion, SSRF, XSS and code execution included. Do not use `S:C` to lift such a finding above the cap. Within the cap:

- **Medium**: an employee with a restricted profile gets something their profile does not allow: changing or deleting data, running SQL, reading or writing files, running code, or acting on another shop in multistore.
- **Low**: the employee's profile already gives broad access to the feature involved, or they only read low-value data outside their profile.
- **Not rated**: anything that needs the SuperAdmin profile, or a permission that already lets the employee install modules or import themes (see the trust model).

Some older advisories scored findings that need a back office login as High or Critical; the cap above replaces that practice.

For everyone else, as rules of thumb:

- **Critical**: an anonymous visitor or a customer gets code execution, SQL injection or an employee account takeover, or stores XSS that runs in an employee's back office session (for example through the contact form, order messages or the customer service view).
- **High**: a customer or anonymous visitor reads or changes other customers' personal data or orders in bulk; checkout or payment logic yields goods, discounts or free orders; an Admin API client grants itself scopes or keeps working after it is disabled; a Webservice key or API client reaches another shop's data; SSRF that reads internal responses; bypassing IP-based restrictions.
- **Medium**: a customer or anonymous visitor reads or changes one specific record they should not (another customer's invoice, address, message or customization file); reflected XSS; stored XSS between customers; CSRF that changes a customer's account, addresses or orders; customer email enumeration; denial of service from a single small request.
- **Low**: blind SSRF; path disclosure in normal responses; issues that need an uncommon configuration or a non-default feature flag.
- Object injection without a working gadget chain in installed code is Low at most; name the gadget.
- Volumetric DoS, brute force and rate limiting are out of scope.

## How reports and patches should look

- State the claim as one sentence: *&lt;actor&gt; can &lt;action&gt; against &lt;target&gt;, which they otherwise could not.* Then the least privileged actor that works, whether it needs a non-default setting (multistore, Webservice, a feature flag, the installer still present), the CVSS vector and score, the commit (`git -C /src rev-parse HEAD`), the affected file and function, and the module name and version when the code is in `/src/modules/<name>` or `/src/themes/<name>`.
- Give a self-contained reproducer: `ps-console` and SQL setup plus `curl` requests.
- Write core patches as `git -C /src diff`. For a module or theme, give a separate diff against its directory and name its upstream repository, because each is fixed and released separately. Follow PrestaShop's coding standards, use existing APIs (`Validate::is*`, `pSQL()` and `bqSQL()` only where a prepared or typed value is not possible, `(int)` casts, `Tools::getValue()` plus validation, `#[AdminSecurity]`, CSRF tokens, Smarty and Twig escaping) rather than ad hoc checks, and fix every entry point that shares the root cause.

## Anything to leave alone

- Anything a SuperAdmin or the operator can already do, including installing modules and themes, running SQL through the SQL manager within its restrictions, and editing files.
- Missing security headers, version disclosure, `X-Powered-By`, path disclosure that needs `display_errors` or debug mode, and the default credentials of this test image.
- Brute-forcing the back office folder name.
- Self-XSS, CSRF on login or logout, clickjacking with no real impact, and open redirects that do not leak a token.
- Findings that need `_PS_MODE_DEV_` on, the debug profiler, a server misconfiguration (for example the web root set above the shop, `.htaccess` ignored), or an already compromised host.
- Files only reachable because this image serves a git checkout (development files, `.git`).
- Vulnerabilities in Composer or npm dependencies with no path from PrestaShop's own code.
