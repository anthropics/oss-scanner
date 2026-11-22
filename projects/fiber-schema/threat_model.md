# Threat model: Schema

## Start here

Schema (`github.com/gofiber/schema`, the `main` branch) turns a `map[string][]string` of form values into a Go struct, and back. It is a small library (about 4,200 lines of Go outside tests, one `go.mod`, no cgo), and it sits behind Fiber's query, form, multipart, header, cookie and URI binders, so the keys and values it decodes are an HTTP client's. It has been through a concentrated hardening cycle: since 1 July 2026 `main` has 119 non-merge commits, and the fixes that were security-shaped are nearly all one class, a single request making `Decode` spend memory, stack or time that its size does not justify (see "Bug classes seen here"). The shallow cases of that class are gone. Spend your time in this order:

1. **Siblings of the allocation and recursion fixes.** `Decode` has several independent budgets (`maxSize`, `maxParserIndex`, `maxPathDepth`, the 8 MiB per-call allocation budget, the path cache bounds, the 4 KiB first allocation of an unmarshaler slice), added one fix at a time. For each, state what it bounds, then look for a way to reach the same allocation or recursion that the budget does not count. The history is in `/src/.git`; `git log --no-merges --since=2026-07-01 --format='%h %s' | grep -i 'fix'` is the list.
2. **Mass assignment and field resolution.** Which struct fields a key can reach is the decoder's one security promise (see below). The decoder resolves a key through three code paths that must agree: the precomputed direct paths and fast paths, the generic path parser, and the case-folded fallback. A key that one path refuses and another accepts is a finding.
3. **The hand-written code on the hot path**: `cache.go` (path parser, `nextPathSegment`, the path cache, `requiredGroups`), `values.go` (`pairIndex`, the open-addressing table behind `DecodeValues`), `floatfmt.go`, and the `unsafe` stores in `decodeNativeSlice` and in the cache's slot index. Read them line by line with the tests that pin their behavior beside them.
4. **Required, default and zero-empty semantics**, where a request can make a field look provided when it was not (or the reverse). Two such bugs were fixed in the last months (#103 and its follow-ups).
5. **Concurrency**: a shared `Decoder` or `Encoder` while another goroutine reconfigures it, under `-race`.

If you can run workers in parallel, give each one area and have it read its files completely: (a) `decoder.go` and the `growTracker`; (b) `cache.go` and `values.go`; (c) `encoder.go`, `converter.go`, `floatfmt.go`.

Working rules. Give a hypothesis about fifteen minutes; without a lead, move on. Once a root cause has a reproducer and a patch, stop and write it up rather than listing variants. Read the tests for what they pin, not in full (`decoder_test.go` is 7,000 lines): a test that asserts a behavior marks it as deliberate. Skip `.github/`.

## What this project does and where untrusted input enters

An application creates a `schema.Decoder`, usually one per process because it caches struct metadata, and calls `Decode(&dst, values)` or `DecodeValues(&dst, keys, values)`. `dst` is a pointer to a struct the application wrote; the destination type, its `schema:"..."` tags and the decoder's settings are the application's. The source is the attacker's:

- **Keys.** Dotted paths: `name`, `Phone.Label`, `Phones.2.Number`, `Attributes.eyes`. Everything a path can express is attacker-controlled: field names in any letter case, indexes (with leading zeros, signs, huge values), depth, repeated separators, empty segments, very long segments, non-ASCII bytes, `.` inside a map key, and the number of distinct keys (bounded only by the caller, in Fiber by `BodyLimit`, 4 MiB by default, so hundreds of thousands of keys per call are realistic).
- **Values.** Any string, any number of values per key. Slices of numbers and bools also split each value on commas (`1,2,3`), so one value can stand for many elements. Strings do not split.
- **Multipart file headers** (`Decode`'s optional third argument): a key per file field, each treated as a key with one empty value.
- **The order in which a map is iterated** is random in Go, so a result that depends on it (a conflict between two spellings of one key, which of several errors is reported first) is itself worth a look.

Trusted: the destination type and its tags, the decoder's configuration (`MaxSize`, `ZeroEmpty`, `IgnoreUnknownKeys`, `SetAliasTag`), registered converters, `TextUnmarshaler` implementations, and the `Encoder`'s input (a struct the application built, though its string fields may hold client data, which the encoder must carry through unchanged).

You are auditing the library, not an application. A finding needs a destination type that an application could plausibly declare. A type that points to itself (`Children []Node`, `Parent *Node`) is plausible, since trees and comment threads are common form targets, and the maintainers have fixed several bugs reachable only through one.

How Fiber configures it matters for severity (`fiber/binder/mapping.go`): `IgnoreUnknownKeys(true)` and `ZeroEmpty(true)` by default, `MaxSize` left at its default of 16,000, one pooled decoder per binder kind, each with the alias tag of its source (`query`, `form`, `header`, `respHeader`, `cookie`, `uri`). Fiber v3 pins a released version of Schema, so a bug on `main` reaches Fiber users only once released; say which `main` commit introduced it.

## What Schema promises (a violation is a finding)

Each promise ends with the check that tests it.

1. **A key reaches only the fields it names.** A field tagged `schema:"-"`, an unexported field, a field of an unexported embedded struct, and a field that does not exist are never set by any spelling of any key: not by letter case, not by an index with padding or a sign, not by a path through an embedded or promoted field, not through a map entry, not by the fast path, the generic parser or the folded fallback. *Check:* for a type with each kind of excluded field, decode every spelling you can think of (a generated matrix) with `IgnoreUnknownKeys(true)` and compare the struct with a zero value; then run the same keys through each code path (a cold decoder; a decoder warmed with the exact key; a decoder whose path cache is full, see `maxFastPaths`, `maxSpillPaths`).
2. **Bounded work per call.** One call to `Decode` or `DecodeValues` uses memory, stack and time bounded by the size of its input times a small constant, not by what the keys choose. The recorded limits: an index above `maxSize` (16,000 by default) or above the parser's `maxParserIndex` (1,000 for the cached parser) is an error; a path naming more than `maxPathDepth` (64) fields is an error; slices and pointer targets that keys allocate beyond the destination's own slice fields share one 8 MiB budget per call (`maxAllocBytes`); the path cache holds at most `maxFastPaths` (512) plus `maxSpillPaths` (16,384) entries of at most `maxCachedPathLen` (256) bytes and `maxPathCacheBytes` (8 MiB) in weight, and keeps only the spelling the struct declares; an unmarshaler slice reserves at most 4 KiB before a value is accepted. *Check:* measure time and bytes allocated at the key count that fills a request (a few hundred thousand keys), then at double. Linear growth is intended; super-linear growth, or growth in memory that outlives the call (the caches), is not. `Decode` recovers panics and returns them as errors, but cannot recover a stack overflow or the kernel's OOM kill.
3. **`required` means provided.** A `required` field is satisfied only by a key that the decoder would have decoded into that field, in any letter case, with the last value non-empty for a scalar. A key the decoder drops, an empty map entry, or a bare key for a slice of structs does not satisfy it. A `required` field with a `default` is refused when the struct's metadata is built. *Check:* a differential between "is the field populated after `Decode`" and "did `Decode` report it missing", over generated spellings (the existing tests pin the fixed cases).
4. **Decode and Encode do not share state across calls.** No value of one call is visible in another: pooled buffers, the shared `fileKeyValues` slice, the scratch array of the encoder (`maxScratchValueLen`), map-entry and `reflect.Value` pools. The caller's `src` map is never mutated. *Check:* decode two inputs concurrently under `-race` with unique markers and look for a marker in the other's destination, or in a `src` map afterwards.
5. **Case folding and cache keys agree.** The parsed-path cache is keyed by the client's spelling, but `ITEMS.0001.value` and `items.1.value` mean one thing. The cache stores a path only in its declared spelling. *Check:* spellings that parse to one meaning must share one entry or none; no spelling may select a cached entry that was built for a different path (a collision in the direct-mapped slot index, `typeCacheSlots`, which is derived from the type word of the interface).

The package documentation (`doc.go`) and `README.md` are the maintainers' statement of intended behavior. When they say a behavior is intended or a caveat, that is not a finding; when the code contradicts them, it is.

## Components that matter most / least

Most important, in this order:

1. **`decoder.go`** (`decodeSource`, `decodeKey`, `decode`, `walkHops`, `walkIndexChain`, the `growTracker`, `setDefaults`, `checkRequired` and the `markProvided*` family). It recurses per path segment and grows slices by index.
2. **`cache.go`** (about 1,200 lines): struct metadata, the path parser, the direct-path and fast-path tables, the bounded path cache, the required groups.
3. **`values.go`**: `DecodeValues` and its `pairIndex`, a hand-written hash table over request keys (a per-process `maphash` seed since the last fix).
4. **`converter.go`, `floatfmt.go`, `encoder.go`**: number parsing and formatting, the encoder's plan cache and scratch array. Parsing is delegated to `github.com/gofiber/utils/v2` (see "Dependencies").
5. **`multierror`-style error types** (`MultiError`, `ConversionError`, `UnknownKeyError`): an error holding a client's key is returned to the application, which often renders it. Check that error text stays bounded for a key of any length and that building it is not super-linear in the number of errors.

Out of scope: `_test.go` files, `.github/`, benchmarks.

## Bug classes seen here (hunt for variants)

From the last four months of fixes, newest first. For each, the invariant the fix restored and where a sibling might still be.

1. **A key chooses how much the decoder allocates.** `88a8668`, `c9b86da`, `7c7f969`, `2190e56`: slices grown inside slice elements, slices reached through two or more hops (`l.r.l.items`), and pointer targets on a self-referential type each reached allocations that no per-field limit saw (121 MiB kept alive by 50 keys; 2.9 GiB reallocated in 1.6 s by 140,140 keys). The budget is now counted in `growTracker`. *Siblings:* every `reflect.MakeSlice`, `reflect.New`, `reflect.Append`, `reflect.MakeMap` and `make` in `decoder.go`, `cache.go` and `values.go`; the map-entry pool; `setDefaults`, which instantiates slice and pointer defaults per call; embedded pointers to structs that embed pointers back.
2. **A key chooses how deep the decoder goes.** `2a7e67c`: `children.0.` repeated 100,000 times took 64 MiB of stack, and the process exits with a fatal error that `recover` cannot catch; `38bfd6e`: a promoted copy of a struct field made `setDefaults` visit it twice per level, so a recursive type doubled the work per level. *Siblings:* any other recursive walk (`setDefaults`, `walkHops`, `checkRequired`, the encoder's `recurseStructPtr`, the requiredGroups builder over a recursive type, `maxDirectPaths` precomputation for deep fan-out). Check the encoder too: a self-referential value (`Parent` pointing at a cycle) is the application's input, but look at whether `Encode` terminates.
3. **An unbounded cache keyed by the client's spelling.** `3fcc7ae`, `c638eef`: 5,000 spellings of one path left 5,000 entries; a self-containing type's 256-byte path parses into sixty parts and 190 MB was pinned per decoder and root type. *Siblings:* every other map or `sync.Map` that a request can add to: the converter lookup (`BenchmarkConverterMiss`), `encCache`, the struct-info cache keyed by type (the type is the application's, but `SetAliasTag` and `RegisterConverter` clear them while requests run), the `pairIndex` table.
4. **Hash-flooding.** `3728e3f`: `DecodeValues` hashed with a case-folding hash and compared exactly, so every case variant of one key landed in one slot (n(n+1)/2 probes). *Siblings:* any other table keyed by request strings that is not a Go map: `requiredGroups` lookups, the direct-path and fast-path tables, the `markProvidedFolded` pass.
5. **Required and provided-ness disagreeing with the decoder.** `cb5832e`, `b0d68cb`, `9a2949e`: the check looked keys up exactly while the decoder folds case; a key the decoder drops satisfied `required` through its prefix; a bare key satisfied a required slice of structs. *Siblings:* `required` inside embedded structs, maps, pointer-to-struct fields and slices of pointers; `DecodeValues` against `Decode` for the same pairs (the lookup returns the last value there).
6. **Reserving by the client's count.** `1b4987e`, `32c2ca6`: an unmarshaler slice reserved `len(values)` elements before looking at one, and the parser reserved from a key's separator count. *Siblings:* `decodeBuiltinSlice` (`n` counts commas across all values, so a body of commas asks for one element per byte before any is parsed; measure the allocation against the body size for `[]int64` and `[]float64`), `decodeBoxedSlice`, `growCap`.
7. **Map and `TextUnmarshaler` interplay.** `f0b02a2`, `d8b360f`, `10be6d8`, `c11466f`: map fields from dotted keys are new, and a map type that implements `TextUnmarshaler` is decoded as a whole. *Siblings:* map values that are slices, pointers or unmarshalers; keys containing `.`; map fields inside slice elements; maps and `required` or `default`.

## Hypotheses worth testing

Each with its oracle.

1. **Excluded fields via the direct paths.** The precomputed direct paths (`maxDirectPaths`, `maxDirectKeyLen`) are built from the struct's fields; a field with `schema:"-"` that sits inside an embedded struct, or an embedded struct that is itself tagged `-`, must be excluded from them too. *Oracle:* promise 1 above; the generic parser is the reference.
2. **Alias collisions.** Two fields whose aliases differ only by case, or a field whose alias equals another field's Go name, or an embedded struct's field that shadows a field of the outer struct. The decoder resolves case-insensitively, so one key can name two fields. *Oracle:* the key must decode into exactly one field, the same one on a cold and a warm decoder and on both parsing paths.
3. **Index parsing at the edges.** Indexes with `+`, `-`, leading zeros, a value of exactly `maxParserIndex` and `maxSize`, `maxSize` set to 0, a negative value or `math.MaxInt` through `MaxSize`, an index that overflows `int` in `growCap`. *Oracle:* error or the same element, never a panic, never an allocation near `maxSize` times the element size for a single key on a type with a large element.
4. **The `unsafe` stores.** `decodeNativeSlice` writes `[]T` through `UnsafeAddr`; the dispatch compares the field type to `[]int`, `[]string` and the like exactly. A named slice type, a slice of a named element type, a slice reached through an interface or a field of an embedded type whose layout differs. *Oracle:* `go test -race` turns on `checkptr`, which reports a bad pointer cast; also run the suite once with `-gcflags=all=-d=checkptr=2`.
5. **`DecodeValues` against `Decode`.** The same pairs through both must produce the same struct and the same errors, including repeated keys, case variants, empty values and file-less multipart. *Oracle:* a differential test over generated inputs (write it as a fuzz target; there is none in the repository).
6. **Float and integer parsing.** `floatfmt.go` formats floats by hand, and parsing goes through `utils.ParseFloat32`/`ParseFloat64`/`ParseInt`. *Oracle:* `strconv` as the reference: parse of any string accepted by both must agree, and a string accepted by Schema but refused by `strconv` (hex floats, `Inf`, `NaN`, underscores, a sign after whitespace) should be intended; encode followed by decode should round-trip for finite values and report what it does for `NaN` and infinities.
7. **Error text.** `MultiError.Error()` and `UnknownKeyError` include the client's key. *Oracle:* error size and time against the key count; a request of 100,000 unknown keys without `IgnoreUnknownKeys` must not make `Error()` super-linear.
8. **Concurrent reconfiguration.** `SetAliasTag` and `RegisterConverter` clear caches under a lock while `Decode` reads them. *Oracle:* `-race`, and a decode that observes half of a reconfiguration (the new tag with a stale struct info).
9. **Multipart.** A file key and a value key with the same name, a file key that is not a field, a file key with a depth or index past the limits. *Oracle:* the same errors as the equivalent value key; `src` is not mutated.

## Already tried

At commit `770d170` (`main`, 2026-11-04), on a developer machine with the network on and Go 1.26, outside the scanner image:

- `go vet ./...` and `gofmt -l .` are clean. `go test -vet=off -race -count=1 ./...` passes (about 20 s on four CPUs, the first run also compiles the race build).
- The adversarial lab below, on a self-referential type: a path of 200 `parent.` segments is refused with `schema: path exceeds depth limit`; 2,000 keys of the form `children.<i>.children.1000.name` return `index exceeds parser limit` after 19 MiB and 37 ms; 5,000 zero-padded spellings of one index add 1.0 MiB; 50,000 map keys take 36 ms and 5.4 MiB; 100,000 values for a `[]int` take 2 ms and 0.8 MiB. The limits above hold for those shapes.

Not tried: `-gcflags=all=-d=checkptr`, fuzzing (the repository has no fuzz target), `govulncheck`, any of the hypotheses above beyond the existing tests. Treat them as open.

## How to exercise it

The image has the checkout at `/src` with its full git history, Go 1.27, the module's dependencies in the module cache, the test binary already compiled (plain and with `-race`), `GOPROXY=off` and `GOTOOLCHAIN=local`. `/src/.oss-scanner/` is the scanner's own untracked copy of the Dockerfile; keep it out of patches. Only loopback is reachable. `golangci-lint` is not installed; use `go vet ./...` and `gofmt -l .`.

- **Tests.** `cd /src && go test -race -count=1 ./...`. `decoder_test.go` is the long one; iterate with `-run`.
- **History.** `git log --no-merges --since=2026-07-01 --format='%h %ad %s' --date=short | grep -i fix` lists the fixes; `git show <hash>` has the reasoning in the message; `git log -S'<text>' -- <file>` finds when a line appeared.
- **Scratch tests.** Put a throwaway `zz_probe_test.go` in the package directory, `package schema` for unexported helpers (`newCache`, `parsePathInfo`, `growTracker`, `pairIndex`) or `package schema_test` for the public API, and run `go test -run TestZZ -v -count=1 .`. Delete it before you write a patch.
- **Fuzzing** works offline: write a `func FuzzX(f *testing.F)` in a scratch file, seed it with real keys, and run `go test -run '^$' -fuzz FuzzX -fuzztime 2m .`. Good oracles: `DecodeValues` against `Decode`; the fast path against the generic parser; `Encode` then `Decode` round-trip.
- **Measuring allocation.** `runtime.ReadMemStats` before and after (`TotalAlloc` for what was allocated, `HeapAlloc` after a GC for what stayed), or `go test -bench . -benchmem`. For a stack overflow, run the decode in a subprocess (`go test -run TestX` exits with `goroutine stack exceeds 1000000000-byte limit`).

### The lab

Save as `/src/zz_lab_test.go` and run `cd /src && go test -run TestZZLab -v -count=1 .`. It decodes five hostile shapes into a self-referential type and logs time, bytes allocated and the error. Extend it with a shape the existing budgets do not see, and delete it before you write a patch.

```go
package schema_test

import (
	"fmt"
	"net/url"
	"runtime"
	"strings"
	"testing"
	"time"

	"github.com/gofiber/schema"
)

type Node struct {
	Name     string            `schema:"name"`
	Children []Node            `schema:"children"`
	Parent   *Node             `schema:"parent"`
	Items    []int             `schema:"items"`
	Attrs    map[string]string `schema:"attrs"`
}

// measure decodes q into a fresh Node and reports the time, the bytes allocated and the error.
func measure(t *testing.T, name string, q url.Values) {
	t.Helper()
	d := schema.NewDecoder()
	d.IgnoreUnknownKeys(true)
	var before, after runtime.MemStats
	runtime.GC()
	runtime.ReadMemStats(&before)
	start := time.Now()
	var n Node
	err := d.Decode(&n, q)
	el := time.Since(start)
	runtime.ReadMemStats(&after)
	msg := ""
	if err != nil {
		msg = err.Error()
		if len(msg) > 80 {
			msg = msg[:80] + "..."
		}
	}
	t.Logf("%-28s keys=%-7d time=%-10v alloc=%6.1f MiB err=%q", name, len(q), el.Round(time.Millisecond), float64(after.TotalAlloc-before.TotalAlloc)/(1<<20), msg)
}

func TestZZLab(t *testing.T) {
	measure(t, "deep parent chain", url.Values{"parent." + strings.Repeat("parent.", 200) + "name": {"x"}})

	nested := url.Values{}
	for i := 0; i < 2000; i++ {
		nested.Set(fmt.Sprintf("children.%d.children.1000.name", i), "x")
	}
	measure(t, "slice in slice element", nested)

	padded := url.Values{}
	for i := 0; i < 5000; i++ {
		padded.Set("ITEMS."+strings.Repeat("0", i)+"1", "1")
	}
	measure(t, "zero-padded index spellings", padded)

	wide := url.Values{}
	for i := 0; i < 50000; i++ {
		wide.Set(fmt.Sprintf("attrs.k%d", i), "v")
	}
	measure(t, "50k map keys", wide)

	items := url.Values{"items": make([]string, 100000)}
	for i := range items["items"] {
		items["items"][i] = "1"
	}
	measure(t, "100k values for []int", items)
}
```

## How you rate severity

A finding counts when a client of an application that uses Schema as its README and `doc.go` describe can make it misbehave. State the destination type, the decoder settings and the exact keys and values the reproducer needs, and what you observed against what the promises above say. A finding against the configuration Fiber uses (`IgnoreUnknownKeys(true)`, `ZeroEmpty(true)`, `MaxSize` 16,000) and a type that a form or query binder would plausibly decode into weighs more than one that needs an unusual setting or a contrived type.

- **Critical**: a key that sets a field the type excludes (`schema:"-"`, unexported, or not a field), by any spelling, so that a form can set `IsAdmin` or the like. Memory corruption: a bad pointer cast, a write through `unsafe` to the wrong type, a data race on a string, slice or map in the destination or in a pooled buffer. Data of one call visible in another call's destination.
- **High**: a request that makes the process exit (stack overflow, out-of-memory, a fatal error that `recover` cannot catch) or that holds far more memory or CPU than the input's size and the documented limits explain, on a plausible type under Fiber's configuration. A panic that escapes `Decode`, `DecodeValues` or `Encode` despite the recover. A cache that a client can grow without bound for the life of the process.
- **Medium**: the High denial-of-service classes when they need a non-default setting (`MaxSize` raised, `ZeroEmpty(false)`) or a self-referential type with several fields reaching each other. A `required` check that passes for a field the decoder did not set, or that fails for one it set. Hash or probe flooding that costs milliseconds per request rather than seconds. A `default` applied when a key was provided, or not applied when it was not.
- **Low**: a hardening gap (a limit one step looser than its sibling's), a documented but surprising behavior, an error message that is larger than it needs to be, a difference from `encoding/json` or `strconv` with no security consequence beyond the surprise.

When a finding sits between two levels, choose the lower and say what would raise it. A deviation from the Gorilla `schema` behavior that the README does not promise is a bug and not a vulnerability.

## How to report

Verify before you report. A finding needs all of these:

1. A reproducer that runs in this image from a clean checkout: a Go test in the package (`package schema` or `schema_test`), with the destination type and the keys written out, and for resource use the measured memory or time at two sizes of input.
2. A check that it is not intended: read `doc.go`, `README.md` and the tests (`grep -rn '<behavior>' --include='*_test.go' .`; `git log -S'<text>'`). A test that pins the behavior usually means it is deliberate.
3. A check that it is present on `main` now (`git log --oneline -5 -- <file>`) and since which release.
4. A minimal patch against `main` with a regression test written as the package writes its tests (`testify` is not a dependency: the tests use the standard library). The test must fail before the patch and pass after it, with `go test -race`. Keep the hot path fast: the maintainers rewrote it for speed (`perf` commits) and a fix that adds an allocation to an ordinary decode will be questioned; run `go test -run '^$' -bench 'BenchmarkAll' -benchmem` before and after.

Report one root cause once, listing each entry point it reaches (`Decode`, `DecodeValues`, `Encode`). Do not report best-practice gaps without a concrete input that misbehaves.

## Dependencies

`github.com/gofiber/utils/v2` (number parsing, `HashFold`, string helpers, SWAR scanners) and its dependencies `github.com/google/uuid` and `golang.org/x/sys` are reached from Schema. A bug in `utils` that Schema exposes to a client is in scope here when it is reached through `Decode`, `DecodeValues` or `Encode`: report it with a Schema reproducer, and say that the fix belongs in `utils`. Findings only in `utils`' other packages are out of scope.

## Anything to leave alone

- Linear cost in the input: a request of a million keys costs a million decodes, and `Decode` does not bound the key count; the caller bounds the body (in Fiber, `BodyLimit`). Report super-linear cost, or a bound that fails to hold.
- `MaxSize` is a documented knob: a large value "may create many zero-value slice elements" (the comment on `MaxSize` says so). A finding that needs it raised is Medium at most.
- Case-insensitive matching of keys to fields, `ZeroEmpty` and `IgnoreUnknownKeys` behaviors, comma-splitting of numeric and bool slice values, `on` as `true`, and the first-value-wins or last-value-wins rules the README and tests describe.
- Converters, `TextUnmarshaler` implementations and `RegisterConverter` callbacks are the application's code: a panic or slow converter is the application's. A panic inside one is recovered and returned as an error by design.
- Behavior documented as differing from the original Gorilla `schema`.
- Findings that exist only in the Fiber binder, fasthttp or another consumer; in `_test.go` files, benchmarks or `.github/`.
