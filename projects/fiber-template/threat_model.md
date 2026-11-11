# Threat model: Fiber template

## Start here

Fiber template (`github.com/gofiber/template`, the `master` branch) is ten Go modules: a small core (`template.go`, 307 lines, module `github.com/gofiber/template/v2`) and nine view engines, `ace`, `amber`, `django`, `handlebars`, `html`, `jet`, `mustache`, `pug` and `slim`. Each engine is one file of 159 to 364 lines that adapts a third-party template library to Fiber's `Views` interface (`Load() error` and `Render(out io.Writer, name string, binding any, layout ...string) error`). There are about 2,400 lines of non-test Go in total (tests: 4,800), no cgo, and the only `unsafe` is behind `utils.UnsafeString` and `utils.UnsafeBytes`. The template files, the views directory and every setting are the application's. A client controls the values inside the binding and, in applications that pass one through, the template or layout name.

The code is small but it was rewritten recently. Since 1 July 2026 `master` has 168 non-merge commits; 110 are automation (dependabot, release and sponsor sync). Of the other 58, 17 are code fixes, all made between 23 and 26 August 2026 in two pull requests: #537 rewrote the render path of all nine engines for speed (shared locks, lock-free snapshots, pooled template clones) and then fixed what the review of that rewrite found, and #458 rebuilt partial lookup in `mustache`. The bugs that review found are the classes to hunt, and the engines did not all get the same fixes. Spend your time in this order:

1. **State that crosses from one render to another.** The worst bug in the history was a layout function that outlived its request and wrote one request's page into another request's writer (`bfe5974`, `bac72f8`). Everything a render borrows and gives back is a candidate: the pooled template clones of `html`, `ace`, `amber` and `pug`, the pooled buffers of `mustache` and `slim`, the caller's binding map, the engine's function map.
2. **Siblings of the August fixes in the engines that did not get them.** Each fix names the engines it touched ("Bug classes seen here"). For each class, state the invariant, then check the engines the commit does not list. This has the best yield per hour.
3. **Process-wide state inside the third-party libraries.** Two engines of one kind in one process share pongo2's autoescape flag, `amber.FuncMap`, raymond's helper registry and ace's cache. `5faa507` was one `django` engine switching off another's escaping.
4. **Recursion and locking that can end or hang the process**: a page that embeds itself, an include cycle, a template function that renders again, a reload racing renders.
5. **Names**: what a template name and a layout name can select, per engine and per constructor.

If you can run workers in parallel, give each one area and have it read its files completely: (a) `template.go`, `html`, `ace`, `amber`, `pug` (the four engines built on `html/template`); (b) `django` and `jet`; (c) `handlebars`, `mustache`, `slim`.

Working rules. Give a hypothesis about fifteen minutes; without a lead, move on. Once a root cause has a reproducer and a patch, stop and write it up rather than listing variants. Read the tests for what they pin: a test that asserts a behavior marks it as deliberate. Skip `.github/`, the sponsor and benchmark sections of the READMEs, and the fixture templates under `views/` except as input for your own tests.

## What this project does and where untrusted input enters

An application creates one engine, `html.New("./views", ".html")` or `html.NewFileSystem(http.Dir("./views"), ".html")` (every engine has both constructors; `django` adds `NewPathForwardingFileSystem`, `mustache` adds `NewFileSystemPartials`), configures it (`Reload`, `Debug`, `Layout`, `Delims`, `AddFunc`, `AddFuncMap`; `html` has `Option`, `django` has `SetAutoEscape`) and hands it to Fiber as `fiber.Config{Views: engine}`. `Load` walks the directory or the `http.FileSystem`, keeps every file whose path ends in the extension, and registers it under its slash-separated path relative to the root without the extension (`./views/partials/footer.html` becomes `partials/footer`). `Render` looks up `name`, executes it with `binding`, and with a layout executes the layout around it; the layout reaches the page through the layout name, `embed` by default.

Fiber itself is not a dependency of any module here. What Fiber v3 does with an engine (checked at Fiber `main` `fe35f6725`): it calls `Load()` once when the application starts and only logs a warning when that fails; `c.Render(name, bind, layouts...)` calls `Views.Render` with a pooled buffer as the writer, under the read side of a lock Fiber keeps per engine, and on success sends the buffer as `text/html`; on an error it discards the buffer, and the default error handler answers 500 with the error text as `text/plain`. `ViewsLayout` supplies the layout when the handler passes none. `ViewBind` and `PassLocalsToViews` (off by default) add keys to a `fiber.Map` binding. `app.ReloadViews()` calls `Load()` under the write side of that lock.

Attacker-controlled:

- **Binding values.** Strings, numbers and nested values the handler copied from the request. They reach the template library's output path, where the library's escaping applies.
- **Binding keys**, when a handler builds the map from request data (a query or form turned into a `fiber.Map`). Keys reach `django`'s identifier filter (`isValidKey`), jet's `VarMap`, and the layout paths that add the layout name as a key.
- **The template name and the layout name**, when a handler renders a page named by a route parameter or a query value (`c.Render(c.Params("page"), ...)`). That is the application's decision, but what a name can select is this repository's.
- **Timing.** Many requests render concurrently on one engine, and with `Reload(true)` every render reloads.

Trusted: the template files and everything in the views directory or the `http.FileSystem`, including what a template includes, imports or extends; the functions registered with `AddFunc`; the engine's settings; the operator who chooses `Reload(true)` or `Debug(true)` (both are for development); the exported fields of `core.Engine`, which an application may assign directly.

Know the defaults, because they decide severity. `Reload` and `Debug` are off. The layout name is `embed`. `django` escapes by default (`autoEscape` is true). A failed `Load` leaves `Loaded` unset, so every later render loads again. The engines hold different locks while a template executes: `html`, `ace`, `amber`, `pug` and `django` execute on a snapshot with no engine lock (`django` takes the write lock only for templates with pongo2's `TrimBlocks` or `LStripBlocks`); `jet` and `mustache` hold the read lock for the whole render; `handlebars` and `slim` hold the write lock for the whole render. Fiber does not recover panics, so one that escapes `Render` ends the process unless the application mounts `recover`; a stack overflow or a deadlock cannot be recovered at all.

## What the engines promise (a violation is a finding)

Each promise ends with the check that tests it.

1. **A render writes only to its own writer, from its own binding.** Nothing of one render is visible in another: not through the layout function (a closure over the writer and the binding), not through a pooled template clone (`pool` in `html`, `ace` and `pug`, `pools` in `amber`) or a pooled buffer (`bytebufferpool` in `mustache` and `slim`), not through the engine's function map. The caller's binding is never written to: the layout name goes into a map the engine owns (`core.NewViewContext`, `jetVarMap`, `layoutBind`). *Check:* concurrent layout and plain renders with a unique marker each, under `-race`; then the sequences the tests name: a layout that skips the layout action or fails before it, followed by a plain render of a template that contains the action (`Test_Layout_Isolation_Unreached` pins it for `html` only); compare the caller's map before and after.
2. **A name selects only a template that `Load` registered.** For every engine built with `New`, and for every engine but `jet` built with a filesystem, `Render` resolves `name` and `layout` against what the walk registered and reads no file to do it, so a spelling that is not a registered name (a `..` segment, an absolute path, the name with its extension, a backslash, a NUL) is "does not exist". `jet` cleans a name with `path.Join` first, so there `./index` and `layouts/../index` are `index`, which is still a registered template. A missing layout is an error, never a page without its layout. `mustache` partials come only from the loaded templates and the partials filesystem, and a file that is only in the partials filesystem is not a page. `jet` with a filesystem is the documented exception (see "Anything to leave alone"); even there a name must not leave the filesystem's root. *Check:* the name matrix of the lab against all nine engines and both constructors, with an `http.FileSystem` wrapper that records every `Open`.
3. **Escaping stays on.** A binding value written with the library's ordinary output syntax is HTML-escaped by default in all nine engines: `html/template`'s contextual escaping in `html`, `ace`, `amber` and `pug`, pongo2's autoescape in `django`, raymond in `handlebars`, `cbroglie/mustache` in `mustache`, jet's default safe writer, go-slim's `=`. A `django` engine keeps its own `SetAutoEscape` value for the whole of each of its renders, whatever another `django` engine in the process is set to. The only content an engine marks as safe on its own is the page it has just rendered, when it hands it to the layout (`pongo2.AsSafeValue`, `raymond.SafeString`). *Check:* a hostile string in every context the fixtures offer, with and without a layout; two engines of one kind with opposite settings, interleaved; a binding key equal to the layout name must never put a client's string where the rendered page goes.
4. **A load is retried, and a broken template set is not served as if it were whole.** `Load` clears `Loaded` when it starts (`html` instead returns early when already loaded) and sets it only after the whole walk parsed, so a failed load is retried by the next render instead of answering "does not exist" until restart (`Test_Load_Retry` in all nine engines). *Check:* make one file unreadable or unparsable while renders are in flight, with `Reload` on and off, and with direct `Load` calls as `ReloadViews` makes them; every render returns either a whole page or an error.
5. **Rendering does not end or hang the process by itself.** A page that calls the layout function outside a layout render, or that is its own layout, gets an error (`layoutUnexpected`, the `embedded` flag; `Test_Render_SelfEmbed_Errors` in `html`, `ace`, `amber`, `pug`). A `mustache` include cycle or a missing partial is refused at load (`checkIncludes`). A template function may call `Render` on the same engine again in `html`, `ace`, `amber`, `pug` and `django` (`Test_Render_Reentrant`), and a nested render through a second `django` engine completes while a render with the opposite autoescape setting is queued (`Test_Render_Nested_Engines`). *Check:* each of these shapes in every engine, in a subprocess, with a test timeout.

The README of each engine and the comments in the code are the maintainers' statement of intended behavior. When they say a behavior is intended, that is not a finding. When the code contradicts them, it is.

## Components that matter most / least

Most important, in this order:

1. **The layout paths of `html`, `ace`, `amber` and `pug`** (`Render` and, in `html`, `renderFuncCreate`). They clone a never-executed `pristine` set, install a closure over the request's writer and binding as the layout function, execute, put the sentinel back and return the clone to a `sync.Pool`. `html` alone accepts a chain of layouts. This is where the cross-request bugs were.
2. **`django/django.go`** (364 lines, the largest): `getPongoBinding` and `isValidKey`, the lock-free snapshot with its exclusive fallback (`executionMutates`), and the `autoescape` gate (`acquireAutoescape`, `releaseAutoescape`), a hand-written counter with a condition variable around a package-global flag of pongo2.
3. **`mustache/mustache.go`** (294 lines): `collect`, `includeKeys` (the aliases a partial can be included by), `partialNames`, `checkIncludes`. The partial handling, more than half of the file, dates from 26 August 2026.
4. **`jet/jet.go`**: two loaders with different reach (an in-memory loader filled by the walk, or jet's `httpfs` loader resolving at render time), `jetVarMap`, and a layout closure stored in the binding.
5. **`template.go`**: `PreRenderCheck` (the reload state machine every render passes through), `NewViewContext`, `RangeViewContext`, `bindingMap` (reflection over the caller's binding), `HasExtension`, `TemplateName`.
6. **`handlebars/handlebars.go` and `slim/slim.go`**: short, fully serialized by the engine's write lock, with process-wide helper registration in `handlebars`.

Out of scope: `_test.go` files, the fixtures under `views/`, the READMEs, `Makefile`, `.github/`.

## Bug classes seen here (hunt for variants)

From the fixes of August 2026, grouped by class. For each, the invariant the fix restored and where a sibling might still be. `git show <hash>` has the full reasoning.

1. **A layout closure that outlives its render.** `bfe5974`, `bac72f8`, `2258130`: the layout function lived in the function map a whole template set shares, and was cleared only when the layout reached it. A layout that skipped the action left a closure over that request's writer and binding behind, and a later plain render of a template containing the action wrote the earlier request's page into the earlier request's writer, which under Fiber is a pooled buffer another request may already hold. Now each layout render works on a private clone and restores the sentinel before the clone goes back to the pool. *Siblings:* every path that leaves `Render` early between installing the closure and the deferred reset; a clone whose `Funcs` call affects more than the clone; `amber`, which pools per layout name and executes the page from the shared map; the `html` chain, where each link installs its own closure on the same clone; a render that is still running when a reload replaces `pristine` and `pool`.
2. **Shared mutable state under a shared lock.** `bfe5974`, `9dea681`, `dc41386`: plain renders raced layout renders on the function map in four engines; pongo2 rewrites a template's token stream at execution when trim options are set; jet assigns into the `VarMap` it is given, so a template could rewrite the caller's binding and two renders sharing one map raced; raymond parses a globally registered partial lazily with no lock (which is why `handlebars` is serialized). *Siblings:* any other library object that is written during execution and shared between renders, in the engines that now run with a shared lock or none: pongo2 templates and their `{% include %}` and `{% extends %}` caches, jet's template cache and globals, `html/template`'s lazy escaping of a set, go-slim and cbroglie templates.
3. **The caller's binding written to.** `916105d`, `f8e1918`, `dc41386`: the rendered page was stored under the layout name in the map the caller passed in (`handlebars`, `mustache`, `slim`, `jet`), where it stayed for whatever the caller did next, and two renders sharing a map raced on it. *Siblings:* `django` aliases the caller's map when all keys are valid (the comment says pongo2 copies before executing; check it for `ExecuteWriter`, `ExecuteBytes`, includes and macros); bindings that are not maps (`NewViewContext` then gives the layout an empty context); `jet.VarMap` and `pongo2.Context` passed directly.
4. **One engine's setting applied to another's render.** `5faa507`, `2258130`: pongo2's autoescape flag is package-global and `Load` used to write it, so loading an engine with `SetAutoEscape(false)` made an escaping engine serve unescaped output. The gate now holds the flag for a render's whole execution. *Siblings:* `amber.FuncMap`, a package variable that `Load` reassigns from the engine's functions; raymond's process-wide helpers (`RegisterHelpers`, once per engine); `ace.FlushCache()`; anything in pongo2 that reads the flag outside a gated section; a render that never returns while holding the gate.
5. **Recursion without a floor.** `79405d3`, `ef738de`: a page that embedded itself recursed until the stack overflowed, which killed the process in `ace` and `pug`; a `mustache` partial that included itself, or two that included each other, did the same at render time. A stack overflow is a fatal error that `recover` cannot stop. *Siblings:* the same shapes in the five engines `79405d3` does not list; a page rendered with itself as the layout; cycles through an alias in `includeKeys`; cycles through `{% include %}`, `{% extends %}`, jet's `include` and `extends`, pug and amber includes (these are the template author's, so rate them accordingly).
6. **Re-entrant renders and the engine lock.** `79405d3`, `2258130`: layout renders held the write lock, so a template function that called `Render` again deadlocked; the first autoescape guard could deadlock a nested render behind a queued render with the opposite setting. *Siblings:* the engines that still hold a lock across execution (see the defaults above), where a function, a method on a binding value or a `mustache` lambda renders again, or where `Reload`, `AddFunc`, `Layout` or `Load` waits for the write lock in between.
7. **A partial name turned into a file path.** `c268cce`, `4e38a6a`, `4e047e6`, `ef738de`: `mustache` built a file path from a partial's name and read it from disk at render time, so `{{> ../../../etc/passwd }}` and `{{> secrets/config }}` (resolved against the working directory) could read files outside the views directory. Partials now come from a `StaticProvider` built at load. *Siblings:* any remaining place where a string from a template or from `Render`'s arguments is joined into a path after the walk: jet's loaders, pongo2's loaders (`NewPathForwardingFileSystem` passes a base directory), `jade.ParseWithFileSystem`, `amber`'s `VirtualFilesystem`.
8. **Load state that lies.** `a1229e2`, `063324b`, `5faa507`: `Loaded` was set before the walk, so one transient error left an engine answering "does not exist" until restart. *Siblings:* `html`, the one engine whose `Load` returns early when already loaded; the snapshot a render takes (`Templates`, `pristine`, `pool`) while a failing reload has replaced only part of it; `PreRenderCheck` under concurrent `Reload` calls.

## Hypotheses worth testing

Each with its oracle. They are leads: treat each as open until you have run its oracle.

1. **The sentinel always returns.** After any layout render ends (success, a template error, a panic inside a template function, a layout that never reaches the action, a writer that fails) the pooled clone holds `layoutUnexpected` and no reference to the request. *Oracle:* a plain render of a template containing the layout action fails and writes nothing that belongs to another render; a finalizer on the writer or the binding runs after a GC, which shows that no pooled clone still holds it.
2. **Self-embedding in all nine engines.** A page that calls the layout action, a page rendered with itself as its layout, and in `html` a chain that names one layout twice. *Oracle:* an error in every engine. Run it in a subprocess: a failure is `fatal error: stack overflow`, not a test failure.
3. **Nested renders against every lock mode.** A function in the function map, a method on a binding value, and a `mustache` lambda that call `Render` on the same engine, with `Reload` off and on, and with another goroutine calling `Reload`, `AddFunc`, `Layout` or `Load` in a loop. *Oracle:* every combination returns; with `-timeout 30s` a hang shows as a goroutine dump with a render parked in `sync.(*RWMutex)`.
4. **Two engines of one kind.** Two `django` engines with opposite `SetAutoEscape`, two `amber` engines with different functions of one name, two `handlebars` engines, loads and renders interleaved. *Oracle:* each engine's output depends only on its own configuration, `-race` is silent, and no render waits on the other engine longer than that engine's renders take.
5. **The autoescape gate under stress.** Renders that fail, that panic inside a function, that nest across engines, and one slow render (a function that sleeps) holding the gate while the other setting queues. *Oracle:* `autoescape.active` returns to zero, no render observes the other setting (assert on escaped output), and the wait of the opposite setting is bounded by the renders in flight.
6. **The name matrix.** For each engine and each constructor: `..` segments, absolute paths, the name with its extension, a trailing dot (`ace` trims trailing dots from walked paths), backslashes, a NUL, case variants, the empty name, a name that exists only in `mustache`'s partials filesystem, and the same for the layout argument. *Oracle:* promise 2, with a canary file outside the root and a recording `http.FileSystem`.
7. **Binding shapes and keys.** `nil`, a typed nil map, a pointer to a map, `fiber.Map`-like named maps, `map[string]string`, a struct, `jet.VarMap`, `pongo2.Context`; keys with every byte class, very long keys, a key equal to the layout name. `django` filters keys with `isValidKey` and pongo2 checks them again with its own rule; the two must agree on every key. *Oracle:* no panic, the caller's map is unchanged, the layout sees the same values as the page, and a key the engine is meant to drop does not fail the render.
8. **Reload under fire.** `Reload(true)` with concurrent plain and layout renders while files are rewritten, truncated or removed; a directory that disappears (pongo2's `MustNewLocalFileSystemLoader` and jet's constructors treat errors differently from the other engines). *Oracle:* promise 4; an error, never a panic, and the next render after the fault clears succeeds.
9. **The zero-copy conversions.** `utils.UnsafeString(buf)` hands file contents to the `html`, `handlebars`, `jet` and `mustache` parsers, `django` wraps the rendered page with it, and `handlebars` writes its output through `utils.UnsafeBytes`. *Oracle:* the bytes behind such a string are never written again: no pooled buffer is converted without a copy, and a writer that keeps or modifies the slice it is given cannot change a later render. Run the suites once with `-gcflags=all=-d=checkptr`.
10. **Error text.** Render and load errors carry the template name, file system paths and, from some libraries, template source lines or binding values. Under Fiber's default error handler that text is the response body. *Oracle:* what a client that controls only the binding (and, separately, the name) can read from an error that it could not read otherwise.

## Already tried

At commit `f158722` (`master`, 2026-11-11):

- In this image (Go 1.27.4, network off): `go test -race -count=1 ./...` passes in all ten modules, each suite in one to two seconds. `go vet ./...` is clean in all ten and `gofmt -l .` lists nothing. The same three checks pass on a developer machine with Go 1.26.0 on macOS.
- `go test -race -count=20 ./...` in this image: nine modules pass (`django` takes about 18 s). `handlebars` fails from the second iteration on, in `Test_Reload`, with `panic: Helper already registered: testHelper`: raymond keeps helpers in a process-wide registry, so that suite cannot run twice in one process. That is a property of the test, not a finding; use `-count=1` there.
- The lab below, in this image with `-race`: only `index` and `partials/header` of its nine names render, the other seven are refused with `does not exist`, the hostile value is escaped with and without the layout, and 6,400 concurrent layout renders each contain their own marker and no other.
- Each engine's `simple` fixture rendered with `Title` set to `<script>alert(1)</script>`, with and without `layouts/main` (Go 1.26.0, macOS): all nine engines escape it.
- A ten-second run of a scratch fuzz target over `TemplateName` and `HasExtension` in this image (about 210,000 executions): no crash. The repository has no fuzz target of its own.

Not tried: `govulncheck` and `golangci-lint` (neither is installed here; CI runs both, and `gosec`), `-gcflags=all=-d=checkptr`, Windows paths, and any measurement of memory or time.

## How to exercise it

The image has the checkout at `/src` with its full git history (1,379 commits and 306 tags; engines are tagged `<engine>/vX.Y.Z`, the core `vX.Y.Z`), Go 1.27 (1.27.4 when this was written), every module's dependencies in the module cache, every package and test binary already compiled (plain and with `-race`), `GOPROXY=off` and `GOTOOLCHAIN=local`. `/src/.oss-scanner/` is the scanner's own untracked copy of the Dockerfile; keep it out of patches. The test suites leave `views/ShouldReload.*` files behind, which `.gitignore` covers. Only loopback is reachable. `golangci-lint` and `govulncheck` are not installed; use `go vet ./...` and `gofmt -l .`. Fiber is not in the module cache, because no module here imports it: drive `Render` directly with an `io.Writer`, as the tests do.

- **One module at a time.** There is no `go.work`. The core is `/src`, an engine is `/src/<engine>`; run every `go` command inside the module: `cd /src/html && go test -race -count=1 ./...`.
- **Core and engines together.** Every engine's `go.mod` has `replace github.com/gofiber/template/v2 => ../.`, so an engine in the image builds against `/src/template.go` and a change there reaches all nine at once. Published engines use the released core instead, `v2.1.6`, which is identical to the checkout at this commit (`git diff v2.1.6 -- template.go` is empty). All engine code on `master` is released: no engine file has changed since its latest tag.
- **History.** `git log --no-merges --since=2026-08-20 --until=2026-09-01 --format='%h %ad %s' --date=short | grep fix` lists the fixes; the messages of `bfe5974`, `79405d3`, `2258130` and `ef738de` are long and explain what was reproduced. `git log -S'<text>' -- <file>` finds when a line appeared.
- **Scratch tests.** The tests are in the engine's own package (`package html`, `package django`; the core's are `package template_test`), so a throwaway `zz_probe_test.go` beside them reaches unexported helpers (`isValidKey`, `getPongoBinding`, `includeKeys`, `checkIncludes`, `jetVarMap`, `renderFuncCreate`, the `autoescape` gate). Run it with `go test -run TestZZ -v -count=1 .` and delete it before you write a patch. They use `testify`.
- **Fixtures.** Every engine has `index`, `simple`, `layouts/main`, `partials/header`, `partials/footer`, `errors/404` and `reload` under `./views`. In `html`, `ace` and `pug` the load fails unless a function named `isAdmin` is registered first, because a fixture calls it. For your own templates, create a directory with `os.MkdirTemp(".", "")` as the `django` tests do, or serve them from an `http.FileSystem` you write, which also lets you record every `Open`.
- **Process-killing and hanging cases.** A stack overflow ends the test binary (`goroutine stack exceeds 1000000000-byte limit`), and a deadlock only ends at the test timeout. Give each such case its own test and run it alone with `-timeout 30s`.
- **Library sources** are in the module cache: `cd /src/django && go list -m -f '{{.Dir}}' github.com/flosch/pongo2/v6`.
- **Fuzzing** works offline: write a `func FuzzX(f *testing.F)` in a scratch file and run `go test -run '^$' -fuzz FuzzX -fuzztime 2m .`. Useful oracles: `isValidKey` against the rule pongo2 applies itself; `includeKeys` and `checkIncludes` over generated include graphs; a name against the set of files a recording filesystem saw opened.
- **Races.** `go test -race -count=20 -run <test> .` (not the whole `handlebars` suite, see above).
- **Speed.** Each engine has `Benchmark_<Engine>` and `Benchmark_<Engine>_Parallel`: `go test -run '^$' -bench . -benchmem`.

### The lab

Save as `/src/html/zz_lab_test.go` and run `cd /src/html && go test -race -run TestZZLab -v -count=1 .`. It drives the `html` engine over its own fixtures three ways: a matrix of names, a hostile value, and concurrent layout renders that must each see their own binding. Port it to another engine by changing the package, the constructor and the extension (`ace` and `pug` need `isAdmin` too), extend it with a case from the hypotheses, and delete it before you write a patch.

```go
package html

import (
	"bytes"
	"fmt"
	"strings"
	"sync"
	"testing"
)

// TestZZLab drives the html engine over its own fixtures: a matrix of names, a hostile value,
// and concurrent layout renders that must each see their own binding and nothing else.
func TestZZLab(t *testing.T) {
	engine := New("./views", ".html")
	engine.AddFunc("isAdmin", func() bool { return false }) // views/admin.html needs it to parse
	if err := engine.Load(); err != nil {
		t.Fatal(err)
	}

	// 1. Names: only what Load registered may render.
	names := []string{"index", "/index", "./index", "index.html", "layouts/../index", "../views/index", "partials/header", "", "\x00"}
	for _, name := range names {
		var out bytes.Buffer
		err := engine.Render(&out, name, map[string]any{"Title": "x"})
		t.Logf("name=%-20q bytes=%-3d err=%v", name, out.Len(), err)
	}

	// 2. Escaping: a value from the binding must not arrive as markup, with or without a layout.
	hostile := map[string]any{"Title": `<script>alert(1)</script>`}
	for _, layout := range []string{"", "layouts/main"} {
		var out bytes.Buffer
		err := engine.Render(&out, "index", hostile, layout)
		t.Logf("layout=%-14q raw=%v err=%v", layout, strings.Contains(out.String(), "<script>"), err)
	}

	// 3. Isolation: run with -race. A render that sees another goroutine's marker is a finding.
	var wg sync.WaitGroup
	for i := range 32 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			marker := fmt.Sprintf("marker-%d-", i)
			for range 200 {
				var out bytes.Buffer
				if err := engine.Render(&out, "index", map[string]any{"Title": marker}, "layouts/main"); err != nil {
					t.Error(err)
					return
				}
				if s := out.String(); strings.Count(s, "marker-") != 1 || !strings.Contains(s, marker) {
					t.Errorf("foreign data in a render: %q", s)
					return
				}
			}
		}()
	}
	wg.Wait()
}
```

## How you rate severity

A finding counts when a network client of an application that uses an engine as its README describes can make it misbehave. State the engine, the constructor, the settings, the template files and the handler code the reproducer needs. A finding against the defaults (`Reload` off, one engine, a handler that passes a fixed template name and a `fiber.Map` with request values) weighs more than one that needs a development setting, a client-chosen template name, or templates written in an unusual way. Template files are trusted: a finding that needs a hostile template is not a vulnerability in this repository.

- **Critical**: content, a binding or a writer of one render reaching another render (a stale layout closure, a pooled clone or buffer, a shared function map, a caller's map carried across requests). A data race on template state, or on a string or slice in a render path, that ordinary concurrent renders trigger with `Reload` off. A template name, layout name or partial name that reads a file outside the engine's directory or filesystem root. A binding value that reaches the output unescaped although the engine's configuration has escaping on (another engine's setting, the layout path, the value stored under the layout name), or that is parsed as template source by the engine's own doing.
- **High**: a render that ends the process (stack overflow, fatal error, a panic that escapes `Render`) or blocks every later render (a deadlock on the engine lock or on the autoescape gate), triggered by binding values or binding keys alone, or by concurrent ordinary renders, with `Reload` off. Memory that grows without bound across requests in a pool, a cache or the function map.
- **Medium**: the High classes when they need a client-chosen template or layout name, `Reload(true)`, two engines of one kind in the process, a template function that renders again, or a template that embeds itself. A failed render that writes partial output where the engine says it writes none (`django`). The caller's binding modified by a render. A layout that receives other values than its page did. A load state that leaves an engine answering "does not exist" after the fault has cleared.
- **Low**: error text that exposes file system paths, template source or binding values; a name that selects a registered template through an unexpected spelling without reading anything new; a panic or `log.Fatalf` that only a wrong configuration or a missing directory reaches; a hardening gap between two engines with no demonstrated effect.

When a finding sits between two levels, choose the lower and say what would raise it. A difference from the upstream library's behavior with no security consequence is a bug and not a vulnerability.

## How to report

Verify before you report. A finding needs all of these:

1. A reproducer that runs in this image from a clean checkout: a Go test in the engine's package with the template files it needs written out (in a temporary directory or an in-memory `http.FileSystem`), the binding and the names passed to `Render`, and what you observed against the promise it breaks. For a crash or a hang, the output of the subprocess; for a leak or a race, the `-race` report or the assertion that sees foreign data.
2. A check that it is not intended: read the engine's README, the comments around the code and the tests (`grep -rn '<behavior>' --include='*_test.go' .`; `git log -S'<text>'`). A test that pins the behavior, or a comment that states the trade-off, usually means it is deliberate.
3. A check that it is present on `master` now (`git log --oneline -5 -- <file>`) and since which engine version (`git tag --contains <commit>`).
4. A minimal patch against `master` with a regression test written as the engine writes its tests (`testify/require`, `t.Parallel()` where the neighbors use it). The test must fail before the patch and pass after it, with `go test -race`. Change only the engine concerned; when the same root cause sits in several engines, patch each and say so. A fix in `template.go` reaches users only with a core release and a `go.mod` bump in each engine, so say when a fix needs that. The render paths were tuned for speed in August (`b89c907`, `916105d`): run the engine's benchmarks before and after, and expect a fix that adds an allocation or a lock to an ordinary render to be questioned. Update the engine's README when a documented behavior changes.

Report one root cause once, listing each engine it reaches. Say plainly when a finding depends on something this image cannot reproduce (Windows paths, a case-insensitive file system, a real Fiber application). Do not report best-practice gaps without a concrete render that misbehaves.

## Dependencies

Each engine wraps one library. `html` uses the standard library's `html/template`; the others pin theirs in `go.mod`: `yosssi/ace` v0.0.5, `eknkc/amber` (a 2017 commit), `flosch/pongo2/v6` v6.1.0, `mailgun/raymond/v2` v2.0.48, `CloudyKit/jet/v6` v6.3.3, `cbroglie/mustache` v1.4.2, `Joker/jade` v1.1.3 with `Joker/hpp` v1.0.0, and `mattn/go-slim` v0.0.5. `ace`, `amber` and `pug` compile their source into `html/template` templates. `mustache` and `slim` also use `valyala/bytebufferpool`. The core and five engines import `github.com/gofiber/utils/v2` (`ReadFile`, `Walk`, `UnsafeString`, `UnsafeBytes`).

The parsers, the template languages, their escaping rules and their include mechanisms belong to those libraries, and several of them are old and rarely released. A flaw that lies wholly inside one, or inside `gofiber/utils`, Fiber core (enrolled as its own project) or fasthttp, belongs to its maintainers. Report it here only when this repository is what exposes it to a client under its documented use: an option the engine sets or fails to set, state the engine shares between renders or between engines, a value the engine marks as safe. Say which side holds the fix, and give the reproducer through the engine's `Render`.

## Anything to leave alone

- Everything a template author can do. Template files are the application's code: a template that reads files through `{% include %}`, `{% ssi %}`, `{% extends %}`, a jet, pug or amber include or import, that calls a registered function with request data, or that recurses through its own includes, is doing what its author wrote. Symbolic links under the views directory are followed.
- Escaping the application switched off: `SetAutoEscape(false)`, `{% autoescape off %}` and the `safe` filter in `django`, `{{{ }}}` in `handlebars` and `mustache`, `==` in `slim`, `template.HTML` values and helpers such as the `unescape` function in the `html` README. The layout mechanism inserts the rendered page unescaped by design (`{{{embed}}}`, `== embed`).
- `jet.NewFileSystem` resolves names through jet's own loader at render time: `Load` walks nothing, so any file in the filesystem the application supplied can be named, with or without one of jet's extensions, whatever extension the engine was given. Report only a read outside that filesystem's root. `jet` also parses a template at its first render, so a syntax error appears then and not at load.
- A client-chosen template or layout name is the application's decision. That such a name can select any registered template, including a layout or a partial, and that the error for a missing one repeats the name, is not a finding.
- `Reload(true)` and `Debug(true)` are development settings: a reload per render, serialized on the engine lock, and template names in the log are what they are for. A failed load is retried by every render on purpose (`a1229e2`, `063324b`), so a broken template costs a walk per request until it is fixed.
- Refusing a bad configuration loudly: `jet.New` and `jet.NewFileSystem` call `log.Fatalf` for an extension jet does not know, `html`'s `Option` panics on an unknown option, `slim` panics at load on a function of the wrong type, `ace` needs a non-empty extension, and a second `handlebars` engine that registers a helper name the first one used panics in raymond's registry.
- `FuncMap()` returns the engine's live map, and the fields of `core.Engine` are exported: an application that writes to them while requests render is on its own. `AddFunc` after the first load takes effect at the next load, and in `handlebars` only helpers present at the first load are registered.
- Linear cost: a render costs what its template and binding cost, and a layout render in `django`, `handlebars`, `mustache` and `slim` holds the page in memory once more while the layout runs. Report super-linear cost or memory that outlives the render.
- A layout whose binding is not a map receives only the layout name in `handlebars`, `mustache` and `slim`; only `html` accepts more than one layout; a direct `Load` on an `html` engine that is already loaded returns at once, so Fiber's `ReloadViews` does not reload it. These are functional limits.
- Findings that exist only in Fiber core, fasthttp, `gofiber/utils` or a template library (see "Dependencies"), or only in `_test.go` files, the `views/` fixtures, the READMEs, benchmarks and `.github/`.
