# Threat model

## What this project does and where untrusted input enters

Caffeine is an in-process cache for Java. It holds the keys and values that an application gives
it, evicts them by size, weight or time, and calls the application's loaders, weighers, expiry
policies and listeners. The core does no I/O and parses no wire format. The Guava (`guava/`) and
JCache (JSR-107, `jcache/`) adapters wrap the same core.

Untrusted input reaches it only through the application:

- Keys. A cache keyed on request data (user and session ids, tokens, URLs, host names) lets a
  remote client choose the keys, their hash codes (`String` collisions are easy to produce), how
  often each one is read, and how many distinct keys arrive.
- Weights and durations. A `Weigher` or `Expiry` may compute its result from remote data, such
  as a response's size or its `Cache-Control: max-age`. Treat any weight up to
  `Integer.MAX_VALUE` and any duration that a `long` holds as reachable.
- Timing. Concurrent requests race operations on one key: a read against `invalidate`, a load
  against `put`, a refresh against a removal.
- Java deserialization. Deserializing an untrusted stream is the application's vulnerability,
  but Caffeine's `Serializable` classes are on its classpath. A cache serializes as its
  configuration (`SerializationProxy`), never its entries, and the cache classes reject a stream
  that bypasses the proxy.

The application's own code and configuration are trusted: the callbacks themselves, the builder's
arguments, `CaffeineSpec` strings, and the JCache adapter's configuration files and the classes
they name.

## Components that matter most / least

- The core, `caffeine/src/main/java/com/github/benmanes/caffeine/cache/`: `BoundedLocalCache`
  (eviction, expiration, compute, refresh), `UnboundedLocalCache`, the async caches
  (`LocalAsyncCache`, `LocalAsyncLoadingCache`), `TimerWheel`, `FrequencySketch` and the
  admission policy, the read and write buffers, and `SerializationProxy`. The generators in
  `caffeine/src/javaPoet/` produce the node and cache classes, which the image holds in
  `caffeine/build/generated/sources/`.
- The adapters, `jcache/` and `guava/`, are in scope but thinner.
- Out of scope: `simulator/` (a research tool that reads traces its operator chooses),
  `examples/`, the benchmarks (`caffeine/src/jmh/`), and test code (the `src/test` and
  `src/*Test` source sets, `caffeine/src/testFixtures/`, `caffeine/src/jcstress/`).
- `.github/` matters only where untrusted input (a pull request from a fork, an issue or a
  comment) runs with a token that writes to the repository or with the release secrets.

## How to exercise it

- The image compiled every module and source set, and Gradle runs offline. Tests run on JDK 11,
  the minimum supported, and `-PjavaTestVersion` selects another JDK in `~/.gradle/jdks`, such
  as the one that compiles the project.
- Most methods in `caffeine/src/test/` run across a matrix of cache configurations
  (`@CacheSpec`), so select methods rather than classes, as in
  `./gradlew :caffeine:test --tests 'com.github.benmanes.caffeine.cache.CacheTest.put_insert'`.
  When one configuration is enough, narrow the matrix with `-Pimplementation=caffeine
  -Pcompute=sync -Pkeys=strong -Pvalues=strong -Pstats=disabled`. A whole class is slow on two
  CPUs, and a hook in `.claude/settings.json` refuses one without a `-P` filter.
- The simplest reproducer is a plain JUnit 5 test that builds its cache with
  `Caffeine.newBuilder()`. In `caffeine/src/test/java/com/github/benmanes/caffeine/cache/` it can
  reach package-private internals.
- A race is best shown deterministically. Fray (`:caffeine:frayTest`) explores interleavings at
  synchronization points, Lincheck (`:caffeine:lincheckTest`) checks linearizability by model
  checking, and jcstress (`:caffeine:jcstress`) covers weak memory ordering.
  `.claude/docs/testing.md` says which races each one can see.
- Each Jazzer fuzzer in `caffeine/src/fuzzTest/` runs for five minutes, so select one with
  `--tests`; `.github/workflows/build.yml` lists the selectors.
- The adapters' tests run the same way, as in `./gradlew :jcache:test --tests '<class>'`. The
  `osgiTest` suites need a network and do not run here.
- `.claude/CLAUDE.md` maps the project's notes, and `.claude/docs/synchronization.md` gives the
  lock order and where callbacks run.

## How you rate severity

Rate a finding by what an application that trusts the cache does with the wrong answer, on a
realistic configuration: the default executor and the system ticker, not `Runnable::run` or a
frozen ticker unless the report shows an application that uses them.

- Critical: a read returns a value that belongs to another key, or one whose removal
  (`invalidate`, `remove`, `clear`, a successful conditional remove) returned before the read
  began. Applications cache credentials and authorization decisions, so either can honor a
  revoked grant or show one user's data to another. Code execution during deserialization is
  also critical.
- High: keys, weights or durations alone make the cache exceed its maximum without bound, make
  an operation's cost grow without bound, or hang or deadlock it; an exception reaches the caller
  from a reachable weight or duration (an arithmetic overflow, for example); an expired entry is
  served beyond the races that `.claude/docs/design-decisions.md` accepts; a Caffeine class
  allocates far more during deserialization than the stream's size.
- Medium: an attacker forces the hit rate down despite the admission policy's defense against
  hash flooding (`BoundedLocalCache.admit`), moving the load onto the resource the cache
  protects; a lost removal notification, which leaks whatever the listener releases; a removed
  key or value kept reachable.
- Low: hardening without a demonstrated impact.

## Reports and patches

- Patch against `master`. Keep Java 11 compatibility and the public API (add or deprecate, do not
  change a signature), and follow Google Java Style.
- Change a generated class through its generator in `caffeine/src/javaPoet/`, not the output
  under `caffeine/build/`.

## Anything to leave alone

- `.claude/docs/design-decisions.md`, `.claude/docs/ruled-out.md` and the module rules in
  `.claude/rules/` record intentional trade-offs and adjudicated reports: lossy read buffers,
  approximate frequency counts, best-effort statistics, eventual consistency of size and weight,
  early expiration within a tolerance. Report one of them only for an impact that those documents
  do not account for.
- Misbehaving application code: a callback that throws, blocks or re-enters the cache; `equals`
  or `hashCode` that is inconsistent or changes; a `Ticker` that moves backwards; an `Executor`
  or `Scheduler` that drops or waits on tasks. The cache is only required to fail reasonably.
- An unbounded cache growing with its keys. Bounding it is the application's choice.
- JVM errors (`OutOfMemoryError`, `StackOverflowError`), and anything reached through the JCache
  adapter's `unwrap`.
- A crafted stream that builds a cache which misbehaves only when used. Serialized forms are
  compatible only within a release.
- The JCache adapter's store-by-value copier deserializing what it just serialized from the
  application's own value, and configuration that names classes to load.
- `Unsafe`, `VarHandle` and reflection in themselves.
- CI choices already made: no Gradle dependency verification, and the release workflow's egress
  policy in audit mode.
