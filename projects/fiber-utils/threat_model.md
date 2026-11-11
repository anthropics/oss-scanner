# Threat model: Fiber utils

## Start here

Utils (`github.com/gofiber/utils/v2`, the `master` branch) is the helper library under Fiber v3, its middleware, Schema and the contrib and storage modules. It is small (about 6,100 lines of Go outside tests, about 1,600 lines of AVX2 assembly for amd64 in `simd/`, one `go.mod`, no cgo), and most of it runs on the request path of every Fiber application: it replaces standard-library functions with hand-written ones built on eight-byte word loops (SWAR), packed-key tables, AVX2 kernels and `unsafe` views between `string` and `[]byte`. Nearly every exported function documents itself against a reference (`netip.ParseAddr`, `net.ParseIP`, `net.SplitHostPort`, `net/url`, `strconv`, `net/http.ParseTime`, `http.CanonicalHeaderKey`, `json.Marshal`). So a finding here is one of two things: a memory-safety bug in a word loop, a kernel or an `unsafe` view, or a helper that disagrees with its reference where a consumer's security check rests on the answer. The module has been through a concentrated review cycle: since 1 July 2026 `master` has 206 non-merge commits, 32 of them typed `fix`, and the tests hold 27 fuzz targets. The shallow cases are gone. Spend your time in this order:

1. **Parsers that a security decision rests on.** `ParseIPv4`, `ParseIPv6`, `IsIPv4`, `IsIPv6` and `SplitHostPort` (in Fiber: `req.go`, `middleware/proxy/ssrf.go`, `middleware/hostauthorization`, `client/cookiejar.go`); `IndexControl` and `IndexControlExceptTab` (`res.go`, `middleware/proxy/redirect.go`, `middleware/static`, `internal/logtemplate/sanitize.go`); the three escapers in `url.go` (Fiber's router, redirects and cache keys) and the two unescapers; `ParseHTTPDate`; the case-folding comparisons (`EqualFold` alone has over a hundred call sites in Fiber). For each: an input the helper accepts and its reference refuses, or the reverse, or one input read as two different values.
2. **The AVX2 kernels and their dispatch** (`simd/*.s`, `simd/*_amd64.go`): a read past the end of the slice, a wrong index, a missed or invented match at the 32-byte vector and 128-byte block boundaries, and for `memchrPairAVX2` at every `offset`. One kernel had exactly this bug (`21ac610`).
3. **Word loops at the edges**: lengths 0 to 40 and around every multiple of 8, 16 and 32, the overlapping last word (`swar.Load8(s, n-8)`), index arithmetic that can wrap (`f468fc3`, on 32-bit), `len` against `cap` (`808ded9`), shift counts that reach 64.
4. **`unsafe` views and aliasing** (`internal/unsafeconv`, `convert.go`, `headerkey.go`, `strings/case.go`, `bytes.go`): a result that is a writable view of a string or of a constant, a result that aliases the input where the doc says copy, a `dst` written outside the bytes it appended.
5. **Work per byte**: `IndexFold` and its Rabin-Karp switch, `ParseFloat64` and `ParseFloat32` on long inputs (`parseLong`, `maxSlowDigits`), `ConvertToBytes` and `ParseByteSize`, `GetMIME`'s table probes, `ToString`'s reflection fallback.
6. **Process-wide state**: `Timestamp` and its updater goroutine under concurrent start and stop, and the two random-value helpers (`SecureToken`, `UUIDv4`); Fiber's `csrf`, `session` and `requestid` take their identifiers from `SecureToken`.

If you can run workers in parallel, give each one area and have it read its files completely: (a) `simd/` with `swar/` and `internal/caseconv`; (b) `ipparse.go`, `ips.go`, `hostport.go`, `url.go`, `httpdate.go`, `headerkey.go`; (c) `parse.go`, `format.go`, `common.go`, `convert.go`; (d) `search.go`, `byteseq.go`, `ascii.go`, `control.go`, `jsonstring.go`, `http.go`, `seq.go`, `cut.go`, `time.go`.

Working rules. Give a hypothesis about fifteen minutes; without a lead, move on. Once a root cause has a reproducer and a patch, stop and write it up rather than listing variants. Read the tests for what they pin, not in full (there are about 15,500 lines of them): a test that asserts a behavior marks it as deliberate. Skip `scripts/` and `.github/`.

## What this project does and where untrusted input enters

Utils is a set of free functions. It opens no socket and keeps no state apart from the cached timestamp; the only I/O is `Walk` and `ReadFile` over an `http.FileSystem` the caller supplies, and `crypto/rand`. You are auditing the library, not an application: the caller is Fiber, Schema or a middleware, and what matters is what that caller passes in.

- **Request bytes.** Header names and values, the request target, the host, query keys and values, cookie values and body fields reach the scans (`IndexAny2`, `IndexAny3`, `IndexControl`, `IndexNonQuotable`, `IsASCII`), the folds (`EqualFold`, `HasPrefixFold`, `HasSuffixFold`, `IndexFold`, `HashFold`), the trim and cut helpers, the number, IP, host-and-port and HTTP date parsers and the escapers. Everything about them is the client's: any byte value, any length up to what the server reads (in Fiber, `ReadBufferSize` for the head and `BodyLimit` for the body), and both the `string` and the `[]byte` instantiation of a generic helper, which do not always share a code path.
- **Layout, not only content.** The same bytes at another alignment, ending on the last byte of a page, as a subslice with spare capacity behind it, as a string literal in read-only memory, or as a view of a pooled buffer that the caller reuses after the call (Fiber hands such views to these helpers all the time).
- **The needle.** `IndexFold`, `ContainsFold`, `HasPrefixFold` and `HasSuffixFold` take the needle as a string; since `fa2816c` the doc no longer asks callers to keep an outsider's needle away, so treat it as attacker-chosen too.

Trusted: single-byte arguments (`sep`, `cutset`, the needles of `IndexAny2` and `IndexAny3`), `dst` buffers, the `length` given to `GenerateSecureToken`, the `http.FileSystem` and root given to `Walk` and `ReadFile`, the values and time layout given to `ToString`, `os.Args`, and whatever the application registers with `mime.AddExtensionType`.

How the consumers use it matters for severity. Fiber `main` imports the root package and the `bytes`, `strings` and `swar` subpackages; Schema imports the root package, `strings` and `swar`; contrib also imports `simd`; `gofiber/template` loads its views through `Walk` and `ReadFile`. Fiber, Schema, contrib and storage are enrolled as their own projects and their checkouts are not in this image, so name the call site from memory of their source or say that you could not check it. Fiber v3 pins a released version of Utils (v2.6.5, tagged 2026-11-11; `master` was two commits past it at the time of writing), so say which release first contains a bug and whether a tagged version has it.

## What Utils promises (a violation is a finding)

Each promise ends with the check that tests it.

1. **Memory safety for any bytes, any length and any layout.** No helper reads or writes outside the `string` or `[]byte` it was given, on any architecture: not past `len` into spare capacity (`swar.Load8` and `swar.Store8` check `len`, not `cap`), not past the last byte of a page (every AVX2 kernel is self-bounding and may be called with any length, as the comment in `simd/guard_amd64_test.go` states), not through an index that wrapped. A helper that appends writes only behind `len(dst)`. *Check:* place the input flush against an unmapped page (`guardedTail` in the guard test shows how) at every length from 0 to 300 and every alignment, and compare each kernel and word loop with a byte-at-a-time reference for every match position; `go test -race` turns on `checkptr`.
2. **The reference decides.** Where a doc comment says "exactly", "byte for byte" or "like", the helper accepts and returns what the reference does: `ParseIPv4` and `ParseIPv6` against `netip.ParseAddr`, each for its family; `IsIPv4` and `IsIPv6` against `net.ParseIP`, so without a zone; `SplitHostPort` against `net.SplitHostPort`; the escapers and unescapers against `net/url`, including the `url.EscapeError`; the integer parsers against `strconv` for decimal input, including which error; `ParseFloat64` and `ParseFloat32` against `strconv.ParseFloat` for decimal input, with the differences their comments list; `ParseHTTPDate` against `net/http.ParseTime` apart from surrounding whitespace; `AppendHTTPDate` against `http.TimeFormat`; `CanonicalHeaderKey` against `net/http.CanonicalHeaderKey`; `AppendJSONString` against `json.Marshal` through Go 1.26. *Check:* a differential fuzz target per pair. Most pairs have one (`FuzzParseIP`, `FuzzIsIP`, `FuzzSplitHostPort`, `FuzzURLEscape`, `FuzzParseHTTPDateStdlib`, `FuzzParseIntWidths`, `FuzzParseFloat`, `FuzzCanonicalHeaderKey`, `FuzzAppendJSONString`); read what each one generates and feed it the shapes it does not.
3. **Every tier and both instantiations agree.** The AVX2 kernel, the SWAR loop and the byte loop return the same result for the same bytes, and so do the `string` and the `[]byte` form of a generic helper. *Check:* the same corpus with and without `GODEBUG=cpu.avx2=off` (and `cpu.popcnt=off` for `CountNonASCII`), and through both type arguments. `Test_PortableTier` does this for eight named tests only.
4. **Views and copies are what the doc says.** A result documented as a subslice aliases the input and nothing else. A result documented as new does not alias it (`CopyString`, `CopyBytes`, `AddTrailingSlashBytes` when it appends a slash). No result is a writable view of a string or of a constant unless the function is named `Unsafe`. On an error the unescapers return `dst` at its original length. *Check:* write to the result and look at the input, and the reverse; pass a string literal and write to a `[]byte` result (a fault is the finding).
5. **Time linear in the input.** `IndexFold` is linear in `len(s)` and `len(needle)` short of hash collisions; the other scans, folds and parsers are one pass; the float parsers keep at most `maxSlowDigits` (768) significant digits for the slow path, however long the input. *Check:* time and bytes allocated at two input sizes, for an input built against the algorithm.
6. **Random and time values.** `SecureToken` is 32 bytes from `crypto/rand` in base64url; `UUIDv4` is a version 4 UUID from `crypto/rand`. `Timestamp` is at most about a second old while the updater runs and reads the clock when none runs; `StartTimeStampUpdater` and `StopTimeStampUpdater` may be repeated and called concurrently. *Check:* `-race` with goroutines starting, stopping and reading; no path that returns a token built from anything but `crypto/rand`.

The doc comments and `README.md` are the maintainers' statement of intended behavior, and since October most contracts are written out in them. When they call a behavior intended or a caveat, that is not a finding; when the code contradicts them, it is.

## Components that matter most / least

Most important, in this order:

1. **`simd/`**: nine AVX2 kernels in four assembly files (`memchr_amd64.s`, `memchr_class_amd64.s`, `memchr_digit_amd64.s`, `ascii_amd64.s`), their dispatch (`*_amd64.go`, gated on `hasAVX2`, `hasPOPCNT` and `MinLen` = 32), the SWAR fallbacks and `Memmem`'s prefilter (`memmem.go`, `byte_frequencies.go`). Adapted from the coregex project. The root package routes `IsASCII`, `IndexAny2` and `IndexAny3` here for inputs of `simd.MinLen` bytes or more.
2. **`swar/swar.go`, `internal/caseconv/swar.go`, `internal/unsafeconv/unsafeconv.go`**: the word primitives and the four `unsafe` conversions everything else is built on. `swar.ZeroLanes` is exact only in and below its first marked lane; a caller that reads a higher lane needs the exact `MatchByteMask` or a verification.
3. **`ipparse.go`, `ips.go`, `hostport.go`**: two IP parsers and two IP validators with different references (`netip` and `net`), and the host-and-port split.
4. **`url.go`, `control.go`, `ascii.go`, `headerkey.go`, `jsonstring.go`**: escaping, unescaping (also in place, with a dense and a sparse path) and the byte-class scans that guard header and quoted-string output.
5. **`parse.go`** (the largest Go file), **`httpdate.go`**, **`common.go`** (`ConvertToBytes`, `ParseByteSize`, the token and UUID helpers): number and date parsing with fast paths in front of `strconv` and `time.Parse`.
6. **`search.go`, `byteseq.go`, `seq.go`, `cut.go`, `http.go`** (`GetMIME`'s packed-key table of 512 slots), **`time.go`, `convert.go`** (`ToString`, `ByteSize`), **`file.go`**.

Out of scope: `scripts/` (it regenerates the benchmark tables in `README.md` on a maintainer's machine), `_test.go` files, the benchmark numbers in `README.md`, `.github/`.

## Bug classes seen here (hunt for variants)

From the fixes since July 2026, most security-shaped first. For each, the invariant the fix restored and where a sibling might still be.

1. **A kernel reads past the slice.** `21ac610`: `countNonASCIIAVX2` looped while `base < end` and read whole vectors past the input (24 bytes past a 40-byte slice, a SIGSEGV at a page boundary); its one caller masked the length, so no test reached it. *Siblings:* the other eight kernels' tails and their overlapping-window epilogues, `memchrPairAVX2` with a large `offset`, any kernel called with a length its Go wrapper never passes, `Memmem`'s prefilter positions.
2. **Index arithmetic that wraps.** `f468fc3`: the word loops asked `i+K <= n`, which wraps for a slice near `math.MaxInt32` on 386 and arm, so the loop sliced with a negative bound; the fix changed thirteen source files. `1406ead`: an exponent clamped before it was combined gave 1e75 for a number near 1e10. *Siblings:* every `i+8`, `n-8`, `pos+k`, `MinLen+offset` and `8*n` shift count; `escapedLen` and `growUnescaped` (three bytes per input byte); `parseExp`.
3. **`len` against `cap`.** `808ded9`: `Load8` and `Store8` resliced against capacity, so a miscounted offset read stale bytes and `Store8` overwrote the caller's spare capacity without a panic. *Siblings:* every reslice of a `[]byte` argument that is not a three-index one, in `internal/caseconv`, `url.go` (`dst` growth), `headerkey.go`, `jsonstring.go`.
4. **A view of memory the caller may not write.** `8ad8c0d`: `AddTrailingSlashBytes(nil)` returned a slice over the constant `"/"`, and the first write through it ended the process. `12bdc57`: a nil check read the interface layout of the gc compiler without a build tag. *Siblings:* every `unsafeconv.Seq`, `unsafeconv.Bytes`, `UnsafeBytes` and `UnsafeString` whose result leaves the function (`CanonicalHeaderKey`, `strings.ToLower` and `ToUpper`, the trim and cut helpers, `SplitTrimSeq`), and every early return of a constant.
5. **Disagreeing with the reference.** `afed3d4`: `IsIPv6` bounded a hex field's value and not its digit count, so `00001::2` passed where `net.ParseIP` refuses it. `1c2a8e0`: a packed key did not hold the length, so `html\x00` was `html` to `GetMIME`. `a5aff50`: `ParseVendorSpecificContentType` took a `/` from the parameters and could return more than it was given. `2759976`: HTAB was treated as not quotable. `e9c7e98`, `e47cc10`, `f5a06cf`, `6004dbe`: integer and float parsing against `strconv` (error kind, digit-less input, rounding, inputs past strconv's 800 digits). *Siblings:* every helper under promise 2, on the shapes its fuzz target does not generate; padding and NUL bytes in any packed or folded key (`foldNeedle`, `mimeKey`, `pack3` in `httpdate.go`); a value check where a count check is needed.
6. **Quadratic time on built input.** `fa2816c`: `IndexFold` verified every first-byte candidate word by word, so `aaaa...a` searched for `AAAA...b` cost `len(s)*len(needle)/8` (20.8 ms for 1 MiB before, 1.7 ms after). *Siblings:* `Memmem`'s rare-byte prefilter on a haystack made of the rare byte, `indexFoldRK` under hash collisions, `SplitTrimSeq` and the trims on long runs, `ToString` on nested slices.
7. **A table that must not fill.** `541bbbc`: the MIME table's insert and lookup loops would not end once it was full; it now panics at init above 256 entries. *Siblings:* probe sequences in `http.go` for extensions that hash to one slot, `ByteRank` and the escape tables.
8. **Process state read before it is set.** `2fff020`: `Timestamp` was 0 until the updater started and frozen after it stopped, so expiry computed from it was wrong for ever. *Siblings:* the window between `StopTimeStampUpdater` and the next start, a second `Start` racing a `Stop`, consumers that cache the value.
9. **A panic on legal input.** `59406a3`, `3ed579b`, `4a416ef`, `03569b4`: `ToString` on a nil pointer with a `String` method and on `type T *T` (a stack overflow), `GetArgument` without `os.Args`, `Walk` returning `filepath.SkipDir` to its caller. *Siblings:* reflection over maps, channels, funcs and cyclic values in `toStringReflect`; `FunctionName`; `IncrementIPRange` on a short slice.
10. **Scaling in floats or past the integer width.** `3ab4753`, `ba90d6c`, `cfbfc44`, `c0adca9`, `c718abc`, `3ed579b`: `ConvertToBytes` and `ByteSize` lost digits, mis-scaled long exponents and capped at the wrong value. *Siblings:* `ParseByteSize`, `AppendDuration`, the `Format*` and `Append*` integer writers at the minimum and maximum of each width.

## Hypotheses worth testing

Each with its oracle.

1. **`memchrPairAVX2` at every offset.** The dispatch is `len(haystack) >= MinLen+offset`; the kernel then compares two positions `offset` apart. Haystack lengths around `32+offset` and `128+offset`, `byte1 == byte2`, a pair that straddles two vectors or two blocks, the last possible position. *Oracle:* a two-line byte loop; the guard page.
2. **Block and vector boundaries in the other kernels.** A hit at index 31, 32, 63, 64, 127, 128 and at the last byte; two different needles in one vector; a hit only in the overlapping tail. `Test_BlockLoopBranchesStayInWindow` and `Test_KernelsAreSelfBounding` cover part of this. *Oracle:* the SWAR fallback (`*Generic`) and a byte loop, for every length up to 300 and every position.
3. **The overlapping last word.** Most word loops finish with `Load8(s, n-8)` and must not report a lane twice or miss one: `hostport.go` clears the lanes it has seen with `1<<(8*old) - 1`, `headerkey.go` masks with `swar.HighBits<<(8*n)`, `search.go` shifts by `8*(pos-from)`. *Oracle:* a byte loop for every length from 0 to 40 with the interesting byte at every position, in both instantiations.
4. **Bytes 0x20 apart that are not letters.** Only `A` to `Z` and `a` to `z` fold: `@` and the backtick, `[` and `{`, `\` and `|`, `]` and `}`, `^` and `~`, `_` and DEL, a control byte and the digit or punctuation 0x20 above it (the doc's example is `no\rcache` against `no-cache`). *Oracle:* a table-driven comparison over all 65,536 byte pairs in every lane, for `EqualFold`, `HasPrefixFold`, `HasSuffixFold`, `IndexFold`, the short-needle path (`foldNeedle`, 8 bytes or fewer) and the long one, `HashFold` (equal under `EqualFold` implies equal hash) and `CanonicalHeaderKey`.
5. **IP grammar.** An embedded IPv4 tail with leading zeros or five octets, `::` at either end and beside eight fields, upper-case hex, a zone that is empty or holds `%`, `]`, NUL or a megabyte of text, an IPv4-mapped address through each of the four functions. *Oracle:* `netip.ParseAddr` and `net.ParseIP`; the returned `netip.Addr` must be equal, not only the verdict. A string that `IsIPv4` or `IsIPv6` accepts and a later `netip.ParseAddr` in the consumer reads differently is what an SSRF or allow-list bypass needs.
6. **Host and port.** Unbalanced or nested brackets, several colons without brackets, an empty host or port, a zone inside brackets, bytes after `]`. *Oracle:* `net.SplitHostPort`, with `ok == false` wherever it returns an error.
7. **Unescaping in place.** `dst` may be `s[:0]`; the sparse path copies runs and the dense path (`appendUnescapeDense`) goes byte by byte. A malformed escape after valid ones, `%` as the last or second-to-last byte, a `dst` with spare capacity that is not `s`. *Oracle:* `net/url`; on error `len(dst)` is unchanged and nothing before it was written.
8. **Escaping into a short `dst`.** `escapedLen` sizes the result before the copy. A `dst` that holds `s` but not the escapes, an input that is all escapes, an input that is one long clean run. *Oracle:* `net/url`; `cap` and the bytes beyond the result.
9. **The HTTP date fast path.** `parseRFC1123` reads canonical input itself and hands everything else to `time.Parse`. Year 0000 and 9999, 29 February, hour 24, second 60, a weekday that does not match the date, lower-case names. *Oracle:* `http.ParseTime` on the trimmed input: same instant, same location, error for error.
10. **Number parsing at the widths.** 19 and 20 digits through `parseDigitsBig`, the minimum of each signed width, `+` and `-` alone, a megabyte of digits, of zeros, and of zeros behind a point. *Oracle:* `strconv` for value and error kind; `math/big` where strconv's 800-digit limit applies; time and allocations at two lengths.
11. **`GetMIME` with an outsider's extension.** Fiber passes extensions taken from a request to it (`req.go`, `res.go`, `helpers.go`). Extensions of 7 and 8 bytes (`mimeKeyMaxLen` is 7), upper case, a leading dot, non-ASCII bytes, bytes that fold onto a letter. *Oracle:* the map lookup the table replaced (`FuzzGetMIME` pins it).
12. **Start and stop of the timestamp updater.** `Start` and `Stop` from many goroutines while others call `Timestamp`. *Oracle:* `-race`; never 0, never older than about two seconds.

## Already tried

At commit `be84d1c` (`master`, 2026-11-11), inside the image this directory's Dockerfile builds, with the network off (Go 1.27.4, linux/arm64):

- `go vet ./...` and `gofmt -l .` are clean. `go test -vet=off -race -count=1 ./...` passes in all eight packages (about 15 s for the root package).
- The lab below passes: the IP, host-and-port and query-unescape helpers agree with `netip`, `net` and `net/url` on its 25 hostile strings, also when decoding in place, and a 64-byte needle built against a haystack of one repeated letter takes 83 µs over 64 KiB and 2.2 ms over 1 MiB.
- `go test -run '^$' -fuzz FuzzParseIP -fuzztime 10s .` runs offline (about 40,000 executions a second) and reports nothing.
- `GOARCH=386 go vet ./...` is clean and `GOARCH=386 go test -c .` compiles offline.

Not tried: anything on amd64. That run was on arm64, where `simd.Accelerated()` is false, so none of the nine AVX2 kernels ran, and neither did `simd/guard_amd64_test.go` and `simd/block_align_amd64_test.go`. The 386 tests were compiled, not run. Also not tried: `-gcflags=all=-d=checkptr=2`, `govulncheck`, fuzzing for more than seconds, and every hypothesis above beyond the existing tests. Treat them as open.

## How to exercise it

The image has the checkout at `/src` with its full git history, Go 1.27, the module's dependencies in the module cache, every test binary already compiled (plain and with `-race`), `GOPROXY=off` and `GOTOOLCHAIN=local`. `/src/.oss-scanner/` is the scanner's own untracked copy of the Dockerfile; keep it out of patches. Only loopback is reachable. `golangci-lint` and `gofumpt` are not installed (`make lint`, `make format` and `make test` fetch their tools); use `go vet ./...`, `gofmt -l .` and plain `go test`.

- **Which tier you are on.** `go test -run Test_Accelerated -v ./simd` logs `simd.Accelerated()`. On amd64 with AVX2 the kernels are live; set `GOFIBER_SIMD_REQUIRE_AVX2=1`, as the maintainers' CI does, to fail when they are not. On any other architecture only the SWAR fallbacks run, and the assembly can be read but not executed: say so in a report.
- **Tests.** `cd /src && go test -race -count=1 -shuffle=on ./...`. The root package is the long one; iterate with `-run`.
- **The other tier.** `GODEBUG=cpu.avx2=off go test -count=1 ./...` runs everything on the SWAR loops on amd64.
- **Over-reads.** `go test -run 'Test_KernelsAreSelfBounding|Test_CountNonASCIIAVX2_CountsExactly' -v ./simd` (amd64 and linux only) puts each input against an unmapped page. Copy `guardedTail` from `simd/guard_amd64_test.go` into a scratch test to do the same for a root-package helper; an over-read then faults where an ordinary slice would hide it in the allocator's slack.
- **32-bit.** `GOARCH=386 GOFIBER_TEST_HUGE_SLICES=1 go test -count=1 ./...` is the maintainers' CI step for the wrap class; the test binary maps one slice of `math.MaxInt32` bytes. Cross-compiling works offline. If the kernel will not run a 386 binary, `GOARCH=386 go vet ./...` and `go test -c` still type-check and build it.
- **Fuzzing** works offline: `go test -run '^$' -fuzz FuzzParseIP -fuzztime 2m .`, one target per run. The root package has 20 targets, `simd/` has 6 (`FuzzMemchr2`, `FuzzMemchr3`, `FuzzMemchrPair`, `FuzzMemmem`, `FuzzIsASCII`, `FuzzMemchrClass`), `internal/caseconv` one. `grep -rn '^func Fuzz' --include='*_test.go' .` lists them.
- **History.** `git log --no-merges --since=2026-07-01 --format='%h %ad %s' --date=short | grep -i fix` lists the fixes; the commit messages state the failing input and the reasoning, so `git show <hash>` is worth reading before a file is.
- **Scratch tests.** Put a throwaway `zz_probe_test.go` in the package directory, `package utils` for unexported helpers (`parseRFC1123`, `appendUnescape`, `indexFoldRK`, `foldNeedle`) or `package utils_test` for the public API, and run `go test -run TestZZ -v -count=1 .`. Delete it before you write a patch.
- **Assembly.** `go vet ./simd` runs `asmdecl` over the frame sizes and argument offsets. `go test -c -o /tmp/simd.test ./simd && go tool objdump -s 'simd\.memchr2AVX2' /tmp/simd.test` shows what was assembled.

### The lab

Save as `/src/zz_lab_test.go` and run `cd /src && go test -run TestZZLab -v -count=1 .`. It holds four parsers to their references on hostile strings and times `IndexFold` on an input built against it. Extend the list with a shape the fuzz targets do not generate, and delete the file before you write a patch.

```go
package utils_test

import (
	"net"
	"net/netip"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/gofiber/utils/v2"
	"github.com/gofiber/utils/v2/simd"
)

var hostile = []string{
	"1.2.3.4", "01.2.3.4", "1.2.3.4 ", "1.2.3", "256.1.1.1", "::1", "::ffff:1.2.3.4", "fe80::1%eth0", "::1%",
	"00001::2", "1:2:3:4:5:6:7:8:9", "[::1]", "[::1]:80", "[::1%25en0]:80", "host:80", "host:", ":80", "a:b:80",
	"[::1]x:80", "%41", "%4", "%zz", "a+b%20c", "%00%0d%0a", strings.Repeat("%41", 40) + "%",
}

func TestZZLab(t *testing.T) {
	t.Logf("simd.Accelerated() = %v", simd.Accelerated())
	for _, s := range hostile {
		ref, err := netip.ParseAddr(s)
		a4, ok4 := utils.ParseIPv4(s)
		a6, ok6 := utils.ParseIPv6(s)
		if (ok4 || ok6) != (err == nil) || (ok4 && a4 != ref) || (ok6 && a6 != ref) {
			t.Errorf("ParseIP %q: v4=%v,%v v6=%v,%v netip=%v,%v", s, a4, ok4, a6, ok6, ref, err)
		}
		if got, want := utils.IsIPv4(s) || utils.IsIPv6(s), net.ParseIP(s) != nil; got != want {
			t.Errorf("IsIP %q: %v, net.ParseIP says %v", s, got, want)
		}

		h, p, ok := utils.SplitHostPort(s)
		rh, rp, rerr := net.SplitHostPort(s)
		if ok != (rerr == nil) || (ok && (h != rh || p != rp)) {
			t.Errorf("SplitHostPort %q: %q %q %v, net says %q %q %v", s, h, p, ok, rh, rp, rerr)
		}

		got, gerr := utils.AppendQueryUnescape(nil, s)
		want, werr := url.QueryUnescape(s)
		if (gerr == nil) != (werr == nil) || (gerr == nil && string(got) != want) {
			t.Errorf("QueryUnescape %q: %q %v, net/url says %q %v", s, got, gerr, want, werr)
		}
		in := []byte(s) // the documented in-place form: dst is s[:0]
		if got, gerr = utils.AppendQueryUnescape(in[:0], in); gerr == nil && string(got) != want {
			t.Errorf("QueryUnescape in place %q: %q, net/url says %q", s, got, want)
		}
	}

	// IndexFold must stay linear when the haystack is built against the needle.
	for _, n := range []int{1 << 16, 1 << 20} {
		hay := strings.Repeat("a", n)
		needle := strings.Repeat("A", 63) + "b"
		start := time.Now()
		i := utils.IndexFold(hay, needle)
		t.Logf("IndexFold miss over %7d bytes: %v (index %d)", n, time.Since(start).Round(time.Microsecond), i)
	}
}
```

## How you rate severity

A finding counts when bytes that a client of a Fiber application controls can make a helper misbehave, called as its doc comment and `README.md` describe. State the function, the type argument (`string` or `[]byte`), the architecture and tier (AVX2 or SWAR), the exact bytes, and what you observed against the promise or the reference. A finding that a consumer reaches on a default request path (name the call site in Fiber, Schema, contrib or storage) weighs more than one in a helper no enrolled consumer calls with request data.

- **Critical**: memory corruption or disclosure from request bytes: a read or write outside the slice or string (a kernel or word loop reading past the end, a `Store8` into spare capacity, an append that writes before `len(dst)`), a write through a view of a string, a data race inside the library on memory it owns. A `SecureToken` or `UUIDv4` that is predictable, repeats, or carries less randomness than documented.
- **High**: a panic, fatal error or stack overflow in a scan, fold, trim, parse or escape helper on some input bytes, because none of them documents one and Fiber does not recover it by default. A parser difference that a Fiber defense rests on, shown through the call site: an address that `ParseIPv4`, `ParseIPv6`, `IsIPv4` or `IsIPv6` accepts and the reference refuses or reads as another address, a host and port split unlike `net.SplitHostPort`, a control byte that `IndexControl` or `IndexControlExceptTab` misses, a fold that equates two bytes which are not the same letter. Time or memory that grows faster than the input's length in a helper called on request bytes.
- **Medium**: the High classes when no enrolled consumer turns them into a bypass or a crash today (say which call sites you checked), or when they need the 32-bit build and a slice near 2 GiB. An escaper, unescaper, date or number parser whose result differs from its reference in a way that changes a routing, caching, comparison or expiry decision. A `Timestamp` that is zero, or stale by more than about a second while the updater runs. Tiers or instantiations that disagree (promise 3) without a memory-safety consequence.
- **Low**: a difference from the reference with no security consequence that the doc does not already state, a result that aliases where the doc says copy without a write reaching shared memory, a precondition that is cheap to check and is not, a slow path with a large constant that stays linear.

When a finding sits between two levels, choose the lower and say what would raise it. A difference from the standard library that the function's doc comment or `README.md` states is intended, and is not a finding.

## How to report

Verify before you report. A finding needs all of these:

1. A reproducer that runs in this image from a clean checkout: a Go test in the package concerned, with the bytes written out, the architecture it needs, and for resource use the measured time or memory at two input sizes. For an over-read, a test that faults against a guard page, not an argument from reading the assembly.
2. A check that it is not intended: read the doc comment, the `README.md` section of the function and the tests (`grep -rn '<behavior>' --include='*_test.go' .`; `git log -S'<text>'`). A test that pins the behavior usually means it is deliberate.
3. A check that it is present on `master` now (`git log --oneline -5 -- <file>`), and which tag first contains it (`git tag --contains <hash>`).
4. A minimal patch against `master` with a regression test written as the repository writes them: `testify/require`, `t.Parallel()` first in the test, a differential or fuzz target where the function has a reference. The test must fail before the patch and pass after it with `go test -race`, and with `GODEBUG=cpu.avx2=off` when it touches a tiered helper. Keep the hot path as it is: several tests assert allocation counts with `testing.AllocsPerRun`, the maintainers accept performance claims only from `benchstat` with `-count=10` on one machine, and a fix that costs a helper its inlining or adds an allocation will be questioned. A change to a documented contract also changes the doc comment and the function's `README.md` section.

Report one root cause once, listing each exported function it reaches. Say plainly when a finding concerns assembly that this image could not execute, and what you checked instead. Do not report best-practice gaps without a concrete input that misbehaves.

## Dependencies

Outside tests the module imports two third-party packages: `github.com/google/uuid` (`UUIDv4`) and `golang.org/x/sys/cpu` (the AVX2 and POPCNT bits). `fxamacker/cbor`, `shamaton/msgpack` and `testify` are in `go.mod` for tests and benchmarks; the `JSONMarshal`, `CBORMarshal`, `MsgPackMarshal` and `XMLMarshal` families in the root package are function types, not codecs. A flaw wholly inside a dependency, the Go standard library or the runtime is out of scope; how Utils calls them is in scope (for example, what it hands to `strconv.ParseFloat` and `time.Parse` behind its fast paths).

## Anything to leave alone

- `UnsafeString`, `UnsafeBytes` and the `UnsafeToLower` and `UnsafeToUpper` functions of the `strings` and `bytes` subpackages do what their names and comments say. A consumer that misuses one is that consumer's bug; only Utils' own use of them counts.
- `HashFold` takes no seed and its comment says not to use it for keys an attacker picks. How Schema uses it is Schema's concern.
- `GenerateSecureToken` does not cap `length`, `Walk` follows symbolic links and can block on a named pipe, `ReadFile` reads the path it is given, and `AppendPathSegmentsEscape` passes empty and dot segments through. The comments say so and leave the check to the caller.
- `IsIPv6` refuses a zone and `ParseIPv6` accepts one, by design. `ParseFloat64` and `ParseFloat32` read decimal input only and return 0 with an error on overflow. `TrimSpace` trims ASCII whitespace only. `ParseHTTPDate` ignores space, tab, CR and LF around the date. `AppendJSONString` writes `�` for an invalid byte where Go 1.27's `json.Marshal` writes the raw character.
- `Timestamp` is up to about a second old while the updater runs and wraps in 2106.
- Documented panics: `swar.Load8` and `swar.Store8` out of range, `UUIDv4` when the random source fails, the table builders at init, `Walk` with a nil filesystem or callback.
- Linear cost in the input, and speed differences between the tiers, architectures or instantiations.
- Findings that exist only in a consumer (Fiber, Schema, contrib, storage, template: enrolled separately or maintained elsewhere), in `scripts/`, in `_test.go` files, in benchmarks or in `.github/`.
