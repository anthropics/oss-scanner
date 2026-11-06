<!--
Copied from the Express Security Working Group's threat model, which applies to every repository in the
expressjs, pillarjs and jshttp organizations:
https://github.com/expressjs/security-wg/blob/main/docs/ThreatModel.md
The Express security policy is at https://github.com/expressjs/.github/blob/master/SECURITY.md.
The "How to exercise it" section at the end is specific to this enrolment (expressjs/basic-auth-connect).
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

- `npm test` runs `make test`: mocha over `test.js` with `should`, using in-process connect servers via supertest on local ports only; it needs no network.
- `index.js` is the whole module: `basicAuth(callback | username, password, realm)` returns a middleware that reads the `Authorization` header, decodes the `Basic` credentials, and either compares them with the configured pair using `tsscmp` (constant time) or calls the callback (sync returning a boolean, or async with `(err, user)`); on success it sets `req.user` / `req.remoteUser` and calls `next()`, otherwise it answers 401 with a `WWW-Authenticate: Basic realm="..."` challenge, or 400 for a malformed header.
- Untrusted input is the `Authorization` header. The credentials, callback and realm are application code and trusted. In scope: any header that is accepted without matching the configured credentials (decoding or splitting bugs around colons, empty fields, encodings), a comparison path that is not constant time or that short-circuits on length in a way that leaks the password length, a callback error or exception that lets the request through or hangs it, `req.user` surviving across requests, and the realm or any header-derived value reaching a response header without validation (header injection). Parsing itself is small and inline here rather than delegated to `basic-auth`, so it is fully in scope.
