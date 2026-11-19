# How we would like patches made

## Branch

- Write the patch against `master`, the branch that was scanned (the 0.21.5.x release line).
- Much of `src/libmw` and `src/mweb` is shared with the `24.x` branch. If the same fix applies there, say so in the
  report; do not send a second patch.

## Size and scope of a fix

- As narrow as possible: fix the root cause at the faulty check. No refactoring, renaming or reformatting of code the
  fix does not need to touch, and no unrelated clean-ups.
- Consensus code: never change a consensus rule silently.
  - A fix that makes nodes reject blocks they accept today is a soft fork. Gate it on a new activation height in
    `Consensus::Params` (`src/consensus/params.h`, set in `src/chainparams.cpp`), the way
    `mweb_pegout_feature_activation_height` and `mweb_extradata_feature_activation_height` were added. Use `0` on
    regtest and testnet in the patch and leave the mainnet height as an obvious placeholder for the maintainers to set.
  - A fix that makes nodes accept blocks they reject today is a hard fork. Do not write one; describe the problem
    instead.
  - Where a relay-policy check (`src/policy`, `src/mweb/mweb_policy.cpp`, mempool acceptance) can stop the problem
    before a consensus change activates, include it in the same patch and say which part is policy and which is
    consensus.
- Avoid changing the bundled subtrees (`src/secp256k1-zkp`, `src/leveldb`, `src/crc32c`, `src/univalue`) and
  `src/libmw/deps`. If the bug really is there, keep the change minimal and say in the report that it touches a
  subtree.
- Do not bump version numbers, edit release notes, or change checkpoints, DNS seeds or other chain parameters beyond
  what the fix needs.

## Code style

- Follow `doc/developer-notes.md` (Bitcoin Core style: 4-space indentation, braces as in the surrounding code).
  `src/libmw` has its own conventions; match the file you are editing.
- Few comments: only where the reason for a check is not obvious from the code.
- Comments, log messages, error strings, test names and commit messages must be neutral. Describe what the code does
  ("reject kernels with an empty pegout list"), never that it fixes a vulnerability, exploit or attack, or that an
  attacker could do something. These become public when the fix is merged, before users have upgraded.

## Tests

- Add a regression test that fails before the fix and passes after it, and run it.
  - P2P, consensus, mempool and mining behaviour: a regtest functional test under `test/functional/`, in the closest
    existing `mweb_*.py` or `p2p_*.py` file, or a new file listed in `test/functional/test_runner.py`.
  - Library-level code with no reachable functional path: a unit test in `src/libmw/test` or `src/test`.
- Run the existing tests nearest to the change as well, and give the commands and results in the report.

## Commit message

- Subject line in the form `component: what changed`, matching our history, for example
  `validation: reject empty MWEB pegout features` or `net: rate-limit MWEB leafset requests`.
- A short neutral body if the subject is not enough. The same rule about neutral wording applies.
