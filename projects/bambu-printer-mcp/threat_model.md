# bambu-printer-mcp threat model

## Project and security impact

bambu-printer-mcp is a GPL-2.0 Node.js/TypeScript MCP server that lets AI clients inspect, slice, upload, and print 3D models on Bambu Lab printers. It also handles printer heaters and invokes local slicer and Blender processes. A malicious model or tool input can cross from downloaded data into a host process or a physical machine with moving parts and heated components. The safety gates are security boundaries, even when a legitimate user has authorized an ordinary print.

The project is published on npm and as a desktop MCP extension. It offers stdio and streamable HTTP transports. The HTTP transport defaults to loopback; do not assume that every installation is Internet-exposed. Evaluate realistic deployment and attacker prerequisites in each report.

## Inputs and trust boundaries

Treat imported STL, 3MF/ZIP, XML, JSON, G-code, embedded plate paths, slicer metadata, and model/profile dependencies as potentially malicious. Also examine MCP tool arguments, filenames and output paths, HTTP requests and headers, remote file listings and bytes, and malformed printer status messages. Separate an attacker who supplies a print file from one who can call tools directly or control a printer/LAN service.

Administrator-selected executable paths, BLENDER_MCP_COMMAND/BLENDER_MCP_ARGS, access tokens, and environment configuration are trusted configuration. Simply selecting a malicious executable through those settings is not a vulnerability. However, using untrusted filenames, profile content, or tool arguments to escape an intended subprocess or filesystem boundary is in scope. Do not assume a malicious MCP argument has permission to bypass confirmation or print safety checks.

## Highest-priority components and invariants

- src/safety/: archive consistency, duplicate and case-colliding ZIP names, bounded parsing, plate selection, exact inspected bytes, and independent model, component, and declared-material temperature limits. Check for parsing different bytes or commands at inspection and dispatch.
- src/index.ts and src/printers/bambu.ts: every print and positive-heating route must retain its shared safety checks. Missing models, conflicting live identity, stale status, missing nozzle evidence, unsafe state, and actionable errors must prevent dispatch. Human confirmation must be enforced where required, with fresh state rechecked after the response. Stop/cancel and heater-off must remain available.
- src/bambu-native.ts, src/bambu-network-bridge.ts, src/bambu-connect.ts, and native/: alternate transports and native helpers must not bypass the same gates. X2D native operation is macOS-specific; Linux can inspect source and run mock/helper tests but cannot establish that physical route's behavior.
- src/3mf_parser.ts, src/ams-mapping.ts, src/slicer/, and src/stl/: malformed archives, profile inheritance/include graphs, command arguments, temporary files, traversal, symlinks, resource exhaustion, filament slot mapping, and model/nozzle preset selection. Failed inspection or slicing must not fall back to sending an unchecked original. Remote starts must dispatch an immutable checked copy.
- src/blender-mcp-bridge.ts: subprocess lifecycle, schema validation, cancellation, output receipts, finite geometry, preservation of an existing scene, and refusal to overwrite existing outputs. A timed-out edit must not be replayed automatically.
- scripts/install-patches.mjs, patches/, and scripts/package-mcpb.mjs: correct dependency patching, installation layouts, archive contents, secret exclusion, and isolation from the developer checkout.

Configured model/serial values are not substitutes for fresh observed printer identity. A manual material declaration is supported but does not prove spool contents or physical nozzle hardware. BAMBU_REQUIRE_CONFIRMATION=0 intentionally opts out of ordinary confirmation; it does not disable model/temperature/state validation or the mandatory bed-clearance and hardware-error acknowledgments. Review AGENTS.md in the source checkout for the detailed supported-model invariants.

## How to exercise the project

The checkout and compiled output are in /src. Node.js 24, npm, TypeScript, runtime dependencies, C/C++ build tools, Python, and Git are installed. npm ci runs the bundled dependency patch installer. The Docker build runs the full npm test suite with network access and saves its output in /opt/oss-scanner-validation/build-tests.log and exit status in build-tests.exit. Installation and compilation failures stop setup; test failures are logged without preventing a scan.

Run `test-offline` inside the finished container with networking disabled. It rebuilds TypeScript and runs the test suite except the test named `published tarball patches the resolved dependency in local, global, and npm-exec installs`. That test deliberately creates an empty private npm cache and requires the registry; it already ran during the networked build. The desktop packaging test uses the cache populated during that build. npm is configured offline after setup, so cache misses fail rather than making network requests.

Useful focused commands after building:

- `node --test tests/safety/*.test.mjs tests/safety-dispatch.test.mjs tests/upload-safety.test.mjs`
- `node --test tests/behavior.test.mjs tests/print-routing.test.mjs tests/x2d-print-safety.test.mjs`
- `node --test tests/slicer/*.test.mjs tests/print-auto-slice.test.mjs`
- `node --test tests/blender-mcp.test.mjs tests/blender-stl-memory.test.mjs`

Tests use dummy credentials and mocked printer boundaries. Optional installed slicer-profile and macOS-only tests may skip in Linux; report these separately from passes. No real BambuStudio/Orca/FULU installation, Blender application/addon, proprietary networking plug-in, or physical printer is provided. Their source-facing boundaries remain in scope; report runtime validation limits precisely.

Never run tests/live-print-cancel.mjs, connect to a physical printer, start a print, heat hardware, clear real hardware errors, or modify a user's live Blender scene. Use disposable files, fake helper processes, mock MQTT/FTPS/native transport, and isolated fixtures. Demonstrate unsafe dispatch by capturing the attempted command at the mock boundary, not by executing it on hardware.

## Severity and useful reports

Prioritize demonstrated host code execution, credential exposure, unauthorized file writes, and reachable bypasses that allow unsafe printing or heating. Rate severity from the demonstrated attacker capabilities, default versus non-default configuration, required user interaction, and resulting impact. A file-triggered safety bypass can be high severity without proof of physical damage; do not claim injury, fire, or successful physical printing from a mock command alone. Critical severity requires evidence of broad impact and a realistic low-prerequisite attack path.

Distinguish a malformed-input crash or bounded resource exhaustion from code execution or a hardware safety bypass. Ordinary unsupported-device errors, intentionally trusted executable configuration, and cosmetic diagnostics are not security findings without an additional trust-boundary violation.

Include a self-contained offline reproducer, affected revision and route, attacker-controlled input, expected versus actual behavior, and a minimal suggested patch with regression coverage. Exercise both the affected model/transport and an unaffected route when proposing safety fixes. Consolidate duplicate root causes, while listing all affected entry points. Keep reports private to the configured security contact until triaged and resolved.
