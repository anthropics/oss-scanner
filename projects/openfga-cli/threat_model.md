# Threat model: OpenFGA CLI

## What this project does and where untrusted input enters

The OpenFGA CLI (`fga`, built from `cmd/fga`) is a command-line client for an OpenFGA server. It creates and deletes stores, writes and reads authorization models and relationship tuples, runs `check`, `list-objects`, `list-users` and `expand` queries, imports and exports stores, and runs model tests from `.fga.yaml` files. It calls the server through `github.com/openfga/go-sdk` and converts models between the DSL and JSON through `github.com/openfga/language`. It is run by developers and CI jobs, often with credentials for a production server in the environment. It is not a server and listens on no port.

Treat the following as attacker-controlled:

- **Files the user is handed**: authorization models (DSL, JSON, and `.fga.yaml` store and test files), tuple files (JSON, YAML, CSV), and the `file:` references inside a store file (`internal/tuplefile/`, `internal/safefile/`, `cmd/store/`, `cmd/tuple/`, `cmd/model/`). A user may clone a repository or download an example and run `fga` on it.
- **Responses from the server named by `--api-url`**, and any redirect or TLS behaviour on the way. A malicious or compromised server must not be able to make the CLI read local files, write outside the requested path, or leak credentials.
- **Mapping and test definitions** (`cmd/mapping/`) that name files, commands or expected output.

Trusted: the person running the command, the flags, environment variables and config file they set, and the host.

## Components that matter most / least

Most important, in this order:

1. **Credentials**: the API token, client-credentials flow (`client_id`, `client_secret`, `api_token_issuer`, audience, scopes) and custom headers in `internal/fga/fga.go`. Watch for secrets written to logs, errors, output files or the config file, secrets sent to a host other than the one configured (including via redirect, or an issuer URL taken from untrusted input), and TLS verification being skipped.
2. **Reading and writing files**: `internal/safefile/`, `internal/tuplefile/`, store import and export, and anything that follows a path found inside an input file. Path traversal, symlink following, special files (FIFOs, devices) and unbounded reads are in scope.
3. **Parsing**: the CSV, JSON and YAML tuple and store readers, and model transformation through `openfga/language`. A crash, hang or unbounded memory use from a crafted file is in scope.
4. **Output**: terminal output and rendering (`internal/output/`), including control sequences taken from server or file content.

Less important: help text, shell completions, manpages (`scripts/`), `internal/mocks/`, the release and CI configuration, and the `example/` directory.

Not in scope:

- Bugs in the OpenFGA server (query correctness, caching, datastores, authentication). They belong to the `openfga` enrolment. If a finding needs a server flaw to be reachable, it is a server finding.
- Findings that need the operator to pass a hostile command line, config file or environment variable on purpose.
- Vulnerabilities in third-party dependencies with no path from `fga` input to the vulnerable code. Report those only if reachable.

## How to exercise it

- `fga` is at `/usr/local/bin/fga`; the source is at `/src`. Unit tests: `cd /src && go test ./...`.
- An OpenFGA server is at `/usr/local/bin/openfga`, built from the version this CLI depends on. Start it in the background with `openfga run &`. It serves HTTP on `:8080` and gRPC on `:8081`, with no authentication and an in-memory datastore.
- A SQLite database, already migrated, is at `/var/lib/openfga/openfga.db`. Run it with `openfga run --datastore-engine sqlite --datastore-uri 'file:/var/lib/openfga/openfga.db'`.
- Then run `fga` against it, for example `fga store create --name test --api-url http://localhost:8080`. `/src/tests/` holds YAML test cases showing each command; they are meant for the `commander` runner, which is not installed, and can be read as examples.
- To test the credential paths, run a small local HTTP server that answers as a token issuer or as the API, since there is no network.

## How you rate severity

- **Critical**: the CLI sends a user's API token, client secret or bearer token to a host other than the configured API or issuer; or crafted input makes it execute code or commands.
- **High**: a crafted file or server response makes the CLI write or overwrite a file outside the path the user asked for, read a local file and send its contents to the server, or print a secret that was not meant to be shown.
- **Medium**: TLS verification skipped without the user asking; a secret written to a log or an error message; reads that follow a symlink or a special file in a way the safefile helpers are meant to prevent.
- **Low**: a panic, hang or unbounded memory use from a malformed file or server response, since the user can stop the process and the CLI is not a long-running service; terminal control sequences in output.
- Informational findings with no demonstrated path from attacker input are not worth reporting.

## Anything to leave alone

- Do not report that `--api-url` accepts plain `http://`, or that a token can be passed on the command line. Both are documented.
- Do not report the absence of authentication on the sample server in the image; it is there only for testing.
- Do not report issues in `internal/mocks/` or in test files.
