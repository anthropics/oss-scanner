# Threat model: btcwallet

## What this project does and where untrusted input enters

btcwallet is the wallet daemon and library of the btcsuite family, and it is the wallet lnd embeds. It
holds private keys, decides which coins a spend may consume, tracks the chain against its own
transaction history, and exposes gRPC and legacy JSON-RPC surfaces. It has no peer wire protocol; its
exposure is the operator's RPC endpoint and the chain data it is fed.

- **The chain backend** (`rpc/walletrpc` gRPC, or btcd on the legacy path). A malicious backend as an
  attacker is largely out of scope, since withholding data alone can cost funds. Everything it hands
  over is parsed and acted on, so adversarial-but-plausible messages are in scope: duplicate
  transactions, a reorg that contradicts prior history, a filtered block that does not match its header.
- **The RPC surface** (`rpc/legacyrpc`, generated stubs in `rpc/walletrpc`). The legacy server
  authenticates by macaroon or by username and password over TLS. Argument parsing that disagrees
  with the documented method help (`internal/rpchelp`) is a real bug class.
- **PSBT and transaction import** (`wallet/psbt.go`, `wallet/import.go`). Partial and raw transactions
  come from a possibly hostile caller and the wallet then signs parts of them. This is the most direct
  path from attacker-controlled bytes to a signature over something the user did not intend.
- **The on-disk wallet database** (`walletdb`, `waddrmgr`, `wtxmgr`). A wallet file is not normally an
  attacker input, but some services ingest wallet files, so malformed records that panic or corrupt
  state on open are worth reporting.
- **Passphrase and key material** (`snacl/snacl.go`, key scopes in `waddrmgr`). Nothing should learn a
  secret it was not given or write one somewhere it can be recovered.

## Components that matter most

1. **`waddrmgr/`** (`manager.go`, `scoped_manager.go`, `db.go`, `tlv.go`). Decides which keys belong
   to the wallet, which scopes are unlocked, and how a derived key is bound to a branch and index. A
   flaw is uncontrolled key derivation or a key released for a purpose it was not created for. The TLV
   decoder defines how much a crafted record can make the manager believe.
2. **`wallet/psbt.go` and `wallet/import.go`.** The wallet must sign only inputs it owns, for the
   amounts and scripts it believes, and a PSBT must not add, reorder or redirect an input after the
   check. Watch for duplicate inputs, a UTXO that disagrees with the wallet's record, SIGHASH types
   that cover less than the caller assumed, and partial-signature merging that lets one participant
   change what another signed.
3. **Transaction construction** (`wallet/createtx.go`, `wallet/multisig.go`, `wallet/common.go`). A
   spend must never silently overpay the fee or underpay an output, and change must go to a
   wallet-owned script.
4. **`wtxmgr/`** (`db.go`, `query.go`, `migrations.go`). A transaction is recorded once, a reorg
   unconfirms rather than duplicates, the unspent set is never derived from a conflicting view, and a
   migration completes or leaves prior state intact.
5. **`wallet/chainntfns.go` and `wallet/recovery.go`.** Reorg handling and the seed-recovery scan,
   which processes the whole chain with attacker-influenced block ordering.
6. **`snacl/snacl.go`.** Scrypt and NaCl secretbox for the master key. Derivation parameters, nonce
   handling and zeroing of intermediates (`internal/zero`) are in scope.
7. **`rpc/legacyrpc/methods.go`.** Type mismatches and unchecked conversions that reach a wallet
   operation with a value the caller did not mean.

## How we rate severity

We rate on what an attacker gains and what they must control to get it. The attacker is usually a
local caller or a malicious PSBT author, not an anonymous remote peer, so "critical" is about
consequences rather than reachability.

| Severity | What falls here |
| --- | --- |
| **Critical** | Any path to spending, redirecting or freezing wallet funds without the owner's intent. Signing an input the wallet does not own, or signing for an amount, fee or destination other than what was presented. Extracting a private key, seed or master key in any encoded form, including via a derived key or an error message. A crafted PSBT or RPC request that yields a broadcastable transaction paying a third party. An unlocked-scope bypass that signs for a scope the caller never unlocked. |
| **High** | Persistent loss or corruption of wallet state that costs funds or requires reseeding: a migration that destroys records, a reorg path that drops a UTXO from the store, change sent to a non-wallet script. A PSBT flaw that needs the victim to co-sign or only works under a specific sighash type. Seed recovery that, given a valid seed, yields a wallet missing keys it should have found. Denial of service needing no unusual resources that leaves state unrepairable without manual intervention. |
| **Medium** | A panic or unrecoverable error reachable from a crafted PSBT, RPC request or database record, where the input is not accepted and no state is lost. Bounded memory or CPU exhaustion by an authenticated caller. An authorization gap on a method that reveals only wallet metadata (addresses, balances, history), not key material or signing capability. Wrong malformed-input handling whose worst outcome is a refused operation. |
| **Low** | Missing validation with no demonstrated effect. A misconfiguration that harms only the operator who made it. Crashes on input a real caller cannot produce. Hygiene issues, such as a missing nil check behind an existing guard or an error path that logs a non-secret value. |
| **Out of scope for rating** | Anything requiring the attacker to already hold the wallet passphrase, an unlocked wallet, or write access to the wallet database. A malicious database can simply delete itself; that is a property of holding the file. Code that exists only under a non-default build tag. |

We discount the rating of, but still want reported: a flaw reachable only after unlock, an issue that
needs the attacker to be the wallet's own operator, and a DoS needing an authenticated RPC client.

## Out of scope or low priority

- `rpc/walletrpc/api.pb.go` and `internal/rpchelp/helpdescs_en_US.go`: generated code. Complaints
  about generated fields belong upstream in the generator.
- `internal/legacy/keystore/`, `internal/legacy/rename/`: migration helpers for pre-1.0 wallet files.
  Only interesting if a realistic upgrade path exists.
- `cmd/`: flag parsing and startup. A flaw that affects only a misconfigured operator's own machine,
  with no effect on wallet state, is not worth a report.
- `tools/`, `make/`, `scripts/`, `build/`, `docs/`: build and documentation support. `netparams/`:
  network constants, where a wrong value is an obvious bug that tests catch.
- Test fixtures and mocks (`wallet/mock.go`, `walletdb/db_test.go`, every `*_test.go`).
- A malicious or offline chain source. Stalling is a deployment property. The finding is btcwallet's
  only if it acts on bad data in a way that loses value, and the report must say which.

## Recurring non-findings

- `-gcflags "all=-N -l"` in the image is deliberate, so stack traces match the source.
- `unsafe` in `waddrmgr/` and `wallet/` is partly byte-slicing over fixed-layout structures with a
  length check just before. Report only a missing check or a slice escaping its bound.
- Constant-time comparison in `snacl/` and key paths is deliberate. Ordinary comparison of addresses,
  hashes and public identifiers is fine; confirm a value is secret before reporting timing.
- Manual zeroing (`internal/zero/`): report an unwiped buffer only if you name it and show it survives
  to a place a secret should not be.
- Low-cost scrypt parameters are gated by test build tags and never in production builds.
- A panic on a hand-corrupted bolt bucket, with nothing signed and no key released, is a robustness
  note at best.
- Methods documented as unprivileged (reachable before unlock) returning unprivileged data are
  intentional. Missing authorization on a method that reads only public wallet metadata is not a finding.
- A wallet backed by filtered blocks learns only its own transactions; the privacy consequences are
  understood. Report only a correctness failure that loses funds.

## How to exercise it

The image has the Go toolchain, a pre-fetched module graph and compiled test binaries. Run
`go test ./...` for the root module. `walletdb`, `wtxmgr`, `wallet/txauthor`, `wallet/txrules` and
`wallet/txsizes` are separate modules; run `go test ./...` inside each. Harnesses that need no chain:
`waddrmgr/manager_test.go`, `wallet/psbt_test.go` (handing a crafted PSBT to the same entry point is
the strongest report for that area), `wtxmgr/query_test.go`, `wtxmgr/migrations_test.go`,
`wallet/chainntfns_reorg_test.go`, `wallet/chainntfns_replay_test.go` and
`rpc/legacyrpc/rpcserver_test.go`. Extend these rather than building a new harness.

Reproducers needing a live node, a second wallet or a real chain cannot run in the image. Say so and
give the smallest in-process equivalent, usually a direct call on `waddrmgr`, `wtxmgr` or `wallet`
with a hand-built input. Such a report is still in scope but weighted lower.

## Report and patch preferences

- Propose a merge-ready patch when the fix is local (a bound, a validation, an ordering). For changes
  to transaction construction or key derivation, give a minimal patch plus a paragraph on the intended
  invariant rather than a large rewrite.
- Give the reproducer as a Go test next to the existing table-driven tests, failing before the patch
  and passing after. If it needs a chain, give the full scenario and the in-process substitute, and say
  which one you ran.
- Name the package and function in the first line, and state what the attacker gains in one sentence
  before the mechanism.
- For a fund-loss claim, give the exact amount and direction, for example: "this PSBT makes the wallet
  sign a 0.5 BTC output to script X while believing it signed a 0.5 BTC change output to itself."
- Quote only the relevant lines with the function name, not whole files.
