<!--
Copied from the Express Security Working Group's threat model, which applies to every repository in the
expressjs, pillarjs and jshttp organizations:
https://github.com/expressjs/security-wg/blob/main/docs/ThreatModel.md
The Express security policy is at https://github.com/expressjs/.github/blob/master/SECURITY.md.
The "How to exercise it" section at the end is specific to this enrolment (pillarjs/csrf).
-->
# The Express Threat Model

The Express threat model delineates the trusted elements within the framework, such as the underlying operating system or the runtime. Vulnerabilities necessitating the compromise of these trusted elements lie outside the scope of the Express threat model.

For a vulnerability to be considered, it must adhere to the context of the Express threat model. This implies that it cannot assume the compromise of a trusted element, such as the operating system.

**Elements Express Does NOT Trust**:

1. Data received from the remote end of inbound network connections and data sent to the remote end of outbound network connections, which are accepted through the use of the Express API and transformed/validated by Express before being passed to the application.

In simpler terms, if the data passing through Express to/from the application can initiate actions beyond those documented for the API, it likely signifies a security vulnerability. Examples of unwanted actions include polluting globals, causing an unrecoverable crash, or any other unexpected side effects jeopardizing confidentiality, integrity, or availability.

**Elements Express Trusts**:

1. Developers and infrastructure responsible for running it.
2. The operating system and JavaScript runtime Express operates under, including its configuration and anything within the control of the operating system.
3. The code it executes, comprising JavaScript and native code, even if dynamically loaded, such as dependencies installed from npm or similar repositories.
4. The resources it accesses, such as files, network connections, and other system resources, as long as they are accessed through the documented API.
5. The privileges of the execution user are inherited by the code it runs.
6. Inputs provided by the code it runs, as it is the application's responsibility to conduct necessary input validations, e.g., input to `JSON.parse()`.

## Examples of Vulnerabilities

Examples of vulnerabilities can be found in the [Express Security Updates](https://expressjs.com/en/advanced/security-updates.html).

## Examples of Non-Vulnerabilities

### Malicious Third-Party Modules (CWE-1357)

* Code trusted by Express implies that any scenario requiring a malicious third-party module does not result in a vulnerability in Express. For instance, if an application uses a vulnerable third-party module susceptible to a denial of service attack, it is not considered a vulnerability in Express.

### Prototype Pollution Attacks (CWE-1321)

* Express trusts the inputs provided by application code. Hence, scenarios necessitating control over user input are not considered vulnerabilities unless Express itself fails to sanitize the input properly.

### Uncontrolled Search Path Element (CWE-427)

* Express trusts the runtime environment accessible to it. Therefore, accessing/loading files from any accessible path is not a vulnerability. For example, misconfigurations with `express.static()` are not considered vulnerabilities. [Additional information](https://expressjs.com/en/starter/static-files.html).

### External Control of System or Configuration Setting (CWE-15)

* If Express automatically loads a configuration from the environment, any modification to that environment does not constitute a vulnerability. For example, tampering with the `NODE_ENV` environment variable, causing Express to behave in dev mode instead of production mode, is not considered a vulnerability. [Additional information](https://expressjs.com/en/advanced/best-practice-performance.html#set-node_env-to-production).

### Uncontrolled Resource Consumption (CWE-400) on Outbound Connections

* Express being asked to perform an action impacting the runtime's performance or causing resource exhaustion due to user application code is not a vulnerability.

### Vulnerabilities Affecting JavaScript Runtime

* Express provides a stable API for interacting with most JavaScript runtime versions. Vulnerabilities within the JavaScript runtime itself or those requiring execution on an end-of-life version are not considered vulnerabilities in Express.

## How to exercise it

- `npm test` runs the mocha suite in `test/test.js`; it needs no network. `npm run bench` runs the benchmarks in `benchmark/`.
- `index.js` is the whole module: `new Tokens(options)` exposes `secret(cb)` / `secretSync()` (a random secret from `uid-safe`, `secretLength` bytes), `create(secret)` (a token of the form `<salt>-<sha1(salt + "-" + secret)>` with a random salt from `rndm`, `saltLength` characters, optionally with `validity` and a timestamp), and `verify(secret, token)`, which recomputes the hash for the token's salt and compares with `tsscmp` in constant time, rejecting expired tokens when `validity` is set. `index.d.ts` carries the types.
- Untrusted input is the token given to `verify()`, which comes from the request (a form field or header). The secret is stored server side in the session or a cookie by the calling middleware and is trusted here. The whole value of the package is that a token cannot be produced without the secret, so in scope: any `verify()` input accepted without knowledge of the secret (hash or salt parsing, format tricks, type confusion when a non-string is passed, timestamp or validity bypass), secrets or salts that are predictable or shorter than configured, a comparison that is not constant time, and inputs that throw or run in super-linear time. The strength of SHA-1 as a MAC construction here is a known design choice, not a per-report finding, unless a practical forgery is shown.
