# Threat model: laravolt/avatar

## What this project does and where untrusted input enters

`laravolt/avatar` is a PHP library (Laravel service provider + framework-agnostic `Avatar` class)
that turns a name, email address or any string into an initials-based avatar. Output formats:

- PNG data URI (`Avatar::toBase64()`), rendered with Intervention Image v4 (GD or Imagick driver)
- image file on disk (`Avatar::save($path)`, `HDAvatarResponse::export()`, `ImageExport::exportImage()`,
  `StorageOptimization::storeOptimized()`)
- inline SVG markup (`Avatar::toSvg()`)
- a Gravatar URL string (`Avatar::toGravatar()`); the library builds the URL only, it never fetches it
- an HTTP response with image bytes (`HDAvatarResponse::toResponse()`)

The package registers no routes and performs no outbound HTTP requests. It is always embedded in a
host application, so "untrusted" means "values a typical application passes through from its users".

Assume these are attacker-controlled in a typical deployment:

- **The name string** passed to `create()` / `createHD()` / `createAndExport()` / `batch*()`
  (user display names, emails, usernames). This is the primary input and is untrusted by default.
- **The `$name` used to build file names** in `storeOptimized()`, `createAndExport()`,
  `createSpriteSheet()` and `bulkExport()` (sanitised by `generateOptimizedFilename()` /
  `sanitizeFilename()` in `src/Concerns/`).

Treat these as developer-controlled (trusted) unless a report shows a realistic app pattern that
forwards request data into them: configuration arrays, themes, font paths (`setFont`, `fonts`),
colours (`setBackground`, `setForeground`, `setBorder`), `setFontFamily`, dimensions and font size
(`setDimension`, `setFontSize`), `save()` / `exportImage()` destination paths, export format strings,
storage disk/directory, and Gravatar `$param` arrays. Apps commonly expose size (`?s=`) and sometimes
colour or format via query strings, so issues there are in scope but rated lower (see below).

## Components that matter most / least

- Most: `src/Avatar.php` (initials handling, `toSvg()`, `toGravatar()`, `buildAvatar()`),
  `src/Generator/DefaultGenerator.php` (name parsing, email handling, multibyte/ASCII/RTL),
  file-name and path construction in `src/HDAvatarResponse.php`, `src/HDAvatar.php`,
  `src/Concerns/ImageExport.php`, `src/Concerns/StorageOptimization.php`.
- Less: `src/Concerns/AttributeSetter.php` / `AttributeGetter.php`, cache-key construction,
  storage statistics and cleanup helpers.
- Out of scope: `tests/`, `examples/`, bundled fonts in `fonts/`, config files in `config/`, and bugs that
  live entirely inside Intervention Image, GD, ImageMagick, FreeType or Laravel unless this package's
  own code makes them reachable with attacker input.

## Risks we care about

- **XSS via SVG output**: `toSvg()` concatenates initials, colours, border colour and font family into
  markup. Apps echo this SVG inline in HTML. Any way for an untrusted name to inject markup or
  attributes is in scope.
- **Path traversal / arbitrary file write or delete**: any way for an untrusted name (or other value an
  app plausibly forwards) to steer a write, overwrite or delete outside the configured export/storage
  directory, including through the cleanup helpers.
- **Arbitrary file read / existence oracle**: `setFont()` accepts any path that passes `is_file()`;
  report it only if untrusted input can reach it in a realistic flow or if font loading leaks file
  contents.
- **Denial of service**: unbounded width/height/font size or batch sizes causing huge memory or CPU use;
  pathological names (very long, multibyte, combining characters) causing errors or slow paths.
- **Cache poisoning / collision**: two different users receiving each other's avatar because of
  cache-key construction (`cacheKey()`, `generateCacheKey()`, `generateContentHash()`).
- **URL/parameter injection in `toGravatar()`**: the name is hashed, but `$param` values are appended
  without URL encoding.
- SSRF is not expected (no HTTP client in `src/`). Report it only with a concrete code path.

## How to exercise it

- After the Docker build, dependencies are in `/src/vendor`. Run the suite with
  `vendor/bin/phpunit -c phpunit.xml`.
- Standalone usage needs no Laravel app:
  `php -r 'require "vendor/autoload.php"; echo (new Laravolt\Avatar\Avatar(["driver"=>"gd"]))->create("Jane Doe")->toSvg();'`
- Both drivers are installed: pass `"driver" => "gd"` or `"driver" => "imagick"` in the config array.
- The `HDAvatar*` classes use the `Storage` / `Cache` facades; the tests under `tests/` show how they
  are mocked without a full application.

## How you rate severity

- Critical: remote code execution, or arbitrary file write outside the configured directory, from the
  name string with default configuration.
- High: stored/reflected XSS through `toSvg()` from the name string with default configuration;
  path traversal (read, write or delete) from the name string; one avatar request able to exhaust
  memory or crash the PHP worker with default configuration.
- Medium: XSS, traversal or resource exhaustion that needs a non-default but documented configuration
  (e.g. larger `chars`, `ascii`/`rtl` enabled), or needs the app to forward size/format/colour from the
  request; cache collisions that serve one user's avatar to another.
- Low: issues that require the developer to pass clearly unsafe values into setters documented as
  configuration (font path, colours, font family, save path); Gravatar parameter injection; error
  messages leaking local paths.
- Plain functional bugs (fatal errors, wrong colours, missing imports) are not security issues; mention
  them in a report only if they cause one of the impacts above.

## Report and patch format

- Please include a minimal PHP script or PHPUnit test that reproduces the issue against `/src`, the
  driver used (gd/imagick) and the configuration, plus a patch against `src/`.
- The scanned branch is 7.x (PHP >= 8.3, Laravel 10–13, Intervention Image ^4). Please say whether the
  issue also exists in 6.x, which laravolt/laravolt still depends on.

## Anything to leave alone

- Do not report that the host application should validate or rate-limit user input; only report what
  this package does with it.
- Do not report vulnerabilities in `roave/security-advisories`, PHPUnit, Pest or other dev dependencies.
- Do not report the use of `md5` for cache keys or content hashes as a cryptographic weakness unless a
  practical collision attack causes cache poisoning.
