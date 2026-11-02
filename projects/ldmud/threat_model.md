# Threat Model: LDMud Gamedriver

## 1. What LDMud Does and Where Untrusted Input Enters
LDMud is a virtual machine, Telnet/TLS/UDP server, and compiler for the LPC language, acting as the core gamedriver for LPMud-family virtual worlds. 

**Primary entry points for untrusted input include:**

* **Network & Protocol Parsers:** Inbound TCP/IP and UDP connections, Telnet negotiation streams and supported sub-protocols (e.g., MCCP, GMCP, MSDP, MXP), TLS handshakes, and raw packet processing from players or unauthenticated external clients.
* **The LPC Compiler & Runtime:** LPC code submitted, compiled, or evaluated dynamically within the game environment (by wizards or lower-privileged builders), as well as interactive command arguments passed from player prompts to MUDLib parser functions.
* **External Databases & Integrations:** Data fetched from external SQL databases (SQLite, MySQL, PostgreSQL) or passed via embedded Python extensions that may ingest untrusted user strings.

## 2. Components That Matter Most / Least

### Priority 0: Network-Facing & Unauthenticated Core (Critical Scope)

* **The absolute highest priority.** This includes the core C network loop, Telnet socket parsing (and sub-protocol handlers), UDP socket processing, TLS termination, packet handling, and buffer management.
* *Risk Profile:* Any vulnerability here (such as buffer overflows, heap corruption, format string bugs, or severe denial-of-service via malformed socket traffic) allows unauthenticated remote attackers to crash the driver or potentially achieve Remote Code Execution (RCE) on the host system.

### Priority 1: The LPC Virtual Machine, Interpreter & Wizard Boundary (High Scope)

* **Insider/Privileged attacks via LPC code.** Wizards (coders of LPC files / MUDLib objects) operate within a restricted environment, but bugs or bypasses in the driver's security context (e.g., `master.c` enforcement, efun argument checking, array/mapping bounds, shadow object privileges, object/closure/coroutine execution contexts, or type confusion) can be exploited.
* *Risk Profile:*
  * **Driver Crashes (Denial of Service):** Using VM bugs or unhandled C-level edge cases to crash the driver process directly.
  * **Resource Exhaustion:** Infinite loops, memory leaks, or RAM exhaustion via massive dynamic structures that bypass evaluation cost limits.
  * **Privilege Escalation & Exfiltration:** Arbitrary host file read/write via unsafe efuns, unauthorized access to sensitive master object state, or surveillance/exfiltration of player data and concurrent sessions.

### Priority 2: Extensions, Database Layers, and Python Subsystems (Medium Scope)

* Interfaces connecting LDMud to external interpreters or storage (Embedded Python extensions, PostgreSQL/MySQL/SQLite drivers, and ERQ daemons).
* *Risk Profile:* SQL injection paths exposed via poorly wrapped efuns, type-confusion bugs when translating between LPC types and C/Python runtime objects, or process-isolation failures in external helper daemons (like `erq`).

### Out of Scope / Least Concern

* Static documentation or historical conversion scripts that are never compiled into production gamedriver binaries.

## 3. Trust Boundaries & Assumptions

* **Trusted Parties (Admins):** Administrators running the host infrastructure and trusted developers writing code for the `master.c` object and embedded Python extensions (which load directly into the VM as efuns with full driver access). They have full root/host access and control over compiled C code.
* **Untrusted Parties:** Standard players, unauthenticated network connections, and lower-level "wizards" whose code execution must be strictly sandboxed by the gamedriver boundaries and the MUDLib's `master` authorization checks.

## 4. How to Exercise and Validate

* **Automated Test Suite:** The primary mechanism for exercising and regression-testing security and driver behavior is the integrated test suite located in `/test`.
* **Execution:** Tests can be executed using the main test runner script:
  ```bash
  cd test
  ./run.sh
  ```
* **Coverage:** The test suite covers LPC language parsing, efun logic, type safety, VM edge cases, and specific network behavior, including tests targeting the Telnet state machine and connection handling.

## 5. Severity Rating Guidelines

* **Critical:** Any unauthenticated remote code execution (RCE) via network sockets (TCP/UDP), severe heap corruption/buffer overflows triggered by raw network streams, or arbitrary host file system write capabilities granted to unauthenticated connections.
* **High:** Remote Denial of Service (crashing the gamedriver process via malformed network sequences), wizard-triggered driver crashes exploiting internal VM bugs, privilege escalation from a standard player/wizard to master/admin privileges, or unauthenticated disclosure of sensitive host memory.
* **Medium:** Wizard-level resource exhaustion that evades driver quotas (eval cost limits, memory limits), SQL bridge injection vulnerabilities requiring specific wizard permissions to trigger, or localized data leakage between concurrent player sessions.
* **Low:** Minor logic bugs in non-security-critical efuns, edge-case memory leaks that take weeks to exhaust server RAM under normal operation, or compiler warnings.
