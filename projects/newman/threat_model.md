# Threat model

## What this project does
- Newman is the command line runner for Postman collections. It is often used in CI pipelines.

## Trust model
- Collections, environments, globals, data files, and the scripts inside them are trusted. The user chose to run them, just like running their own code. Anything a script does through the access the pm API gives it is not a vulnerability. Sandbox escapes are bugs in postman-sandbox or uvm, so report them against those projects, not this one.
- The untrusted side is the network: HTTP responses (status, headers, body, cookies, redirects) and any server the collection talks to.

## Components that matter most
- Reporters (lib/reporters/*): CLI, JSON, JUnit. Response data must not break out into the terminal (escape sequences) or the report format (XML injection in JUnit output).
- Secret handling: secrets must not end up in reports or logs unless the user asked for it.
- Request execution and scripts are handled by postman-runtime and postman-sandbox. Report bugs there only if Newman adds the problem.

## How to exercise it
- bin/newman.js is the CLI entry point. Example: node bin/newman.js run examples/sample-collection.json
- test/unit and test/cli have drivers. Run with: npm run test-unit

## How we rate severity
- Critical: code execution on the host caused by data from a server (a response body, header, cookie, or redirect), with no script in the collection that asks for it.
- High: sending credentials (auth tokens, cookies, vault values, client certificates) to a host the collection did not target, for example across a redirect to another origin. Bypassing TLS or certificate checks that the user turned on.
- Medium: a server response that can read or write local files, or corrupt state in a way that leaks secrets into logs or reports.
- Low: denial of service from a hostile server (ReDoS, deep recursion, huge responses, memory use). Crashing or hanging a run the user started is low.
- Every report must include a working reproducer against the current default branch. Without one, cap the severity at low.

## Anything to leave alone
- Anything that needs a hostile collection, environment, data file, or script. These are trusted, so prototype pollution from collection JSON and file reads by scripts are out of scope. Sandbox escapes belong to postman-sandbox and uvm.
- Code under test/, examples/, benchmark/, and npm/ build scripts.
- Known CVEs in dependencies, unless our code calls the vulnerable path in a reachable way from a server response.
- Missing hardening with no attack path, such as missing headers or generic best practices.
