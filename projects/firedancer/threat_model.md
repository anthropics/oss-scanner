# Threat model

Firedancer is a Solana validator client written in C. It runs as a set of sandboxed processes, called tiles, that pass messages over shared memory. This file follows the Firedancer bug bounty terms https://bounty.firedancer.io/terms.html and adds guidance on what to look at first and how to report.

## What this project does and where untrusted input enters

The scan target is the `firedancer` binary in `src/app/firedancer`, built with GCC and run with the default mainnet config (`config/default.toml` and `config/mainnet.toml` in that directory). Firedancer runs Alpenglow consensus, and Tower consensus is out of scope. The tiles and the links between them are set up in `src/app/firedancer/topology.c`.

Assume a remote attacker with no access to the validator host and no code running in any tile. The attacker can send any packet to the ports a validator exposes by default, and can submit transactions, deploy sBPF programs and create accounts. They may hold up to 500,000 SOL, or control validators with up to 5% of the stake, of which 500,000 SOL is their own. Firedancer validators hold up to 20% of the stake.

Untrusted input enters the validator in these places:

- QUIC, TLS and UDP transaction ingest (`src/waltz/quic`, `src/waltz/tls`, `src/disco/quic`,
  `src/disco/net`, `src/waltz/xdp`).
- Gossip (`src/flamenco/gossip`, `src/discof/gossip`).
- Turbine shreds and the FEC sets built from them (`src/ballet/shred`, `src/disco/shred`,
  `src/ballet/reedsol`, `src/ballet/bmtree`), and repair, where the rotor tile fetches missing shreds
  and the repair server (`src/discof/repair/fd_rserve_tile.c`) answers requests from other validators.
- Transaction parsing and signature verification (`src/ballet/txn`, `src/ballet/ed25519`,
  `src/disco/verify`, `src/disco/dedup`).
- Execution. Program code and account contents are attacker controlled, so this covers the runtime,
  native programs, precompiles and account serialization (`src/flamenco/runtime`), and the sBPF VM,
  loader and syscalls (`src/flamenco/vm`, `src/ballet/sbpf`, `src/ballet/elf`). The execrp tile
  (`src/discof/execrp`) executes replayed blocks and the execle tile (`src/discof/execle`) executes the
  validator's own leader blocks.
- Alpenglow consensus, which is the most important area to scan. Votes and certificates from other
  validators reach the votor tile over QUIC (`src/discof/votor`, `src/choreo/votor`), and their BLS
  signatures are checked in `src/ballet/bls`. Rotor (`src/discof/rotor`, `src/choreo/rotor`) repairs
  missing shreds and orders FEC sets for replay, motor (`src/discof/motor`) builds the validator's own
  blocks, and block markers are in `src/flamenco/alpenglow`.
- Replay and block production (`src/discof/replay`, `src/disco/pack`).
- The GUI, RPC and HTTP server (`src/disco/gui`, `src/discof/rpc`, `src/waltz/http`). Operators are not
  expected to expose these publicly, so a finding that needs one rates lower than the same bug on a
  default port, and a crash, stall or bank hash mismatch that needs one is Low.

## Components that matter most / least

In priority order:

1. Anything that makes Firedancer vote, certify or finalize differently from Agave's Alpenglow, or that a
   remote peer can use to crash or stall it.
2. Consensus divergence, where Firedancer computes a different bank hash, account state or execution
   result than Agave for the same block.
3. Signature and transaction validation.
4. Memory safety in the sBPF VM, loader and syscalls.
5. Parsing of QUIC, TLS, shreds, repair and gossip messages.
6. Escaping a tile's sandbox to reach the host.

The following are out of scope:

- Tower consensus, and the switch from Tower to Alpenglow.
- Frankendancer and the `fdctl` binary, and bugs in Agave itself, which belong in Agave's bug bounty.
- The `firedancer-dev` binary, `src/app/fddbg`, the other tools in the repository, the scripts in
  `contrib/`, and the tests and fuzz harnesses themselves.
- Bugs that only appear in Clang builds. The bounty covers GCC 8.5, 13 and 14, and the Clang sanitizer
  build in this image is there to help find bugs, not as a target.
- Solana protocol bugs that affect every client, including cases where Firedancer follows a SIMD and
  Agave does not. Temporary disagreement with Agave over duplicate blocks, duplicate proofs or fork
  choice is also out of scope, but a permanent fork from the rest of the cluster is in scope.
- Attacks that start from code execution in a tile, and escapes from one tile into another. A weakness
  in a tile's sandbox, such as its seccomp policy, only counts as part of a chain that starts with a
  remote input.
- Config changes outside `[paths]`, `[snapshots.sources.gossip]` and `[tiles.bundle]`, unless a real
  mainnet operator might plausibly run that config, in which case the finding rates Low.
- Feature gates that are neither active on mainnet or testnet nor listed in
  `book/guide/protocol/feature_gates.md`, and bugs that rely on gates activating in an order other than
  the planned one. Live activation status cannot be checked offline, so name the gates a finding
  depends on.
- Bugs that need a malformed bundle. Bundles are assumed to be well formed and to hold valid, non-vote
  transactions.
- Anything that needs social engineering or compromised trusted keys.

## How to exercise it

The image holds three builds of the checkout, all compiled with -O3, -g2 and frame pointers:

| Directory | Build | Contents |
|---|---|---|
| `/src/build/gcc` | GCC 14, `linux_gcc_x86_64` (AVX2) | `bin/firedancer`, `unit-test/test_*`, and `fuzz-test/fuzz_*` built with a stub engine that replays the inputs named on its command line |
| `/src/build/gcc-avx512` | GCC 14, `linux_gcc_icelake` (AVX-512) | the same, with the AVX-512 code paths that production validators run |
| `/src/build/clang-san` | Clang 19 with ASan, UBSan, libFuzzer and handholding checks | `unit-test/test_*` and `fuzz-test/fuzz_*` as real libFuzzer binaries |

Only use `/src/build/gcc-avx512` if `/proc/cpuinfo` lists `avx512ifma`, since on other CPUs its binaries
die with SIGILL. The copies directly under `/src/build`, such as `/src/build/firedancer`, start out as
the `gcc` binaries, but make overwrites them whenever it builds the same binary in another build
directory, so use the paths inside the build directories instead.

To rebuild after a change or to compile a reproducer, pass the same variables the image was built with,
or make will rebuild the whole tree:

    make -j"$(nproc)" MACHINE=linux_gcc_x86_64   CC=gcc   BUILDDIR=gcc        <target>
    make -j"$(nproc)" MACHINE=linux_gcc_icelake  CC=gcc   BUILDDIR=gcc-avx512 <target>
    make -j"$(nproc)" MACHINE=linux_clang_x86_64 CC=clang BUILDDIR=clang-san EXTRAS="asan ubsan fuzz" <target>

Run the test binaries directly, because `make run-unit-test` expects gigantic pages and does not work
here. There are no huge pages in the image, so pass `--page-sz normal --page-cnt <n>` to tests that
create a workspace (262144 pages is 1 GiB). The table at the top of `contrib/test/run_unit_tests.sh`
lists the few tests that need more than 1 GiB. Workspace memory is locked, so if a test fails with
`fd_numa_mlock ... failed` or `FAIL: wksp`, run `ulimit -l unlimited` first. Warnings about NUMA binding
or `fd_numa_move_pages` are expected in a container and can be ignored. Pass `--log-path ""` to keep a
test from writing a log file under /tmp.

UBSan works as it does in Firedancer's own CI. Most checks print a `runtime error:` report and let the
program carry on, so a report neither fails a test nor counts as a crash under libFuzzer, and you have
to look for it in stderr. To make UBSan abort instead, for example to get a crash artifact, set
`UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1`. Several tests and harnesses print misaligned access
reports, which are covered under "Anything to leave alone".

Two failures in this image are expected. `test_config_json` refuses to run as root, which is how the
container runs, and `fuzz_ed25519_sigverify_diff` needs a reference library built from Rust in
`contrib/ed25519/dalek_target` that the image does not include.

Each fuzz harness sits next to the code it covers (`src/**/fuzz_*.c`). Only `corpus/fuzz_sbpf_loader`
has a seed corpus, but the fixture files next to many tests, such as the `*.bin` files, make good seeds.

A good reproducer is either an input for a fuzz harness or a small program that drives the real entry
point, such as `fd_txn_parse`, `fd_quic_process_packet`, `fd_shred_parse` or the VM interpreter. For a
consensus bug, give the input, Firedancer's result, the result that Agave's code implies, and the point
where the two diverge.

The bounty asks for an end-to-end exploit against a local validator, but a full validator will not fit
on this machine, since Firedancer's documented minimum is a 24-core CPU and 256 GB of RAM. Show the path
from the network or a transaction to the faulty code instead, and say what you did and did not
demonstrate. A crash in a harness does not by itself prove a remote crash.

## How you rate severity

Critical:

- Loss of funds, meaning funds drained, moved or permanently frozen without the owner's signature.
  Running the wrong program version, divergence in epoch rewards, fees paid to the wrong leader and
  transactions executed out of order do not count.
- Accepting an invalid or forged signature.
- Minting native SOL without authorization.
- A complete chain that steals the validator's private key.

High, for attacks that could halt the cluster:

- A deterministic bank hash mismatch or consensus bug that forks all Firedancer validators at once.
- A remotely triggered crash or stall of all Firedancer validators at once.
- Escaping a tile's sandbox to the host, or to resources the tile was not given.
- A deterministic arbitrary write in transaction execution in the execle or execrp tiles, such as
  escaping the sBPF VM.

Medium:

- Making a validator produce an invalid block or skip its leader slots.
- A deterministic bank hash mismatch, consensus bug, crash or stall that an attacker can aim at a
  specific validator but not at all of them.

Low:

- A crash, stall or bank hash mismatch that only works during a window the attacker cannot open on
  demand, such as boot, catch-up, replay bank eviction or waiting for supermajority.
- An attack that a different config prevents, such as one needing a public GUI, RPC or events
  endpoint, bundles turned on or off, or a particular tile count.
- A race that a remote attacker cannot win reliably.
- A fork that hits validators the attacker cannot choose.

Informational findings are usually not worth reporting. These include memory corruption with no
practical impact, bugs during boot (the validator is trusted on first use and the operator will simply
restart it), and bad input from trusted sources such as genesis, snapshots from configured sources,
bundle servers, entrypoints, telemetry and ipecho.

Rate a finding lower when the attack needs stake, a narrow timing window, a race, unusual hardware or
config, or a prior compromise, and also when it exhausts a resource that would run out on an average
Agave host first. State the attacker model and what you demonstrated, because the team downgrades
reports whose severity is overstated.

## Anything to leave alone

A bug is already known, and should not be reported, if a code comment of any kind, a commit message, a
public issue, a pull request (open, closed or draft) or code on any public branch mentions the
underlying bug or fixes it. Search the checkout before reporting, including the history of every branch
(`git log --all`), keeping in mind that GitHub issues and pull requests cannot be seen offline. Variants
that the same patch would fix count as one report.

Do not report misaligned accesses on their own. Firedancer only runs on x86-64, where they are not a
security problem unless the GCC build actually faults, as an aligned vector load from a misaligned
address would. Also leave out `FD_TEST` and `FD_LOG_ERR` aborts caused by config or command-line input
from the operator.

A handholding or `FD_DCHECK` assertion that fires in the clang-san build is a lead rather than a
finding, because production builds compile those checks out. Report what the GCC build does with the
same input.

## How we would like reports and patches to look

Report one bug at a time. Say which build reproduced it (`gcc`, `gcc-avx512` or `clang-san`), give the
commit from `git -C /src log -1`, and name the feature gates and config it depends on.

Include the input file, the exact command and the sanitizer or crash output, and keep what you ran
apart from what you only read in the source.

Patches should be small and focused, written against `main`, and follow the style of `src/tango/` and
CONTRIBUTING.md, with two-space indents, spaces inside parentheses as in `foo( a, b )`, and
`FD_UNLIKELY` on error paths. Put the fix where the input is first parsed or validated rather than at a
single point where it is used. Where it makes sense, add a regression test next to the code, either as
a case in a `test_*.c` file or as a fuzz seed, and use the repository's commit style of
`<area>: <change>`, as in `quic: reject empty packets`.
