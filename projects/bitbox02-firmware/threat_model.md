# Threat model: BitBox02 firmware

## Project and attacker model

Review the production firmware for BitBox02 and BitBox02 Nova, in both Multi and
Bitcoin-only editions, including bootloaders, firmware updates, and dependencies.
Investigate any relevant code using the security goals below.

Assume the connected computer or phone, wallet application, and communication path
are fully attacker-controlled. All external requests and supplied data are untrusted.
Pairing or legitimate user unlocking does not make the host trustworthy.

Start with genuine, physically unmodified hardware running the intended firmware.
Assume the user protects their recovery material and checks the device's display.
The firmware's display and confirmation logic are themselves part of the review.

## Security goals

- Protect funds, wallet secrets, and private information against unauthorized access,
  disclosure, modification, or use.
- What the device displays and asks the user to approve must match what it actually
  does. Include misleading approvals, unauthorized signing or authentication, and
  other ways to cause theft or loss without extracting keys.
- Preserve the intended wallet and recovery behavior, including correct backup and
  restore. Prevent unauthorized code execution and bypasses of firmware authenticity
  or other security controls.
- Also report firmware defects causing denial of service, crashes, hangs, reboot
  loops, or bricking, even without another security impact. Include defects triggered
  by a malicious host, ordinary use, malformed input, or user mistakes.

Prioritize fund loss, secret compromise, code execution, and authorization failures
over availability-only defects. Assess severity from credible impact, attacker
prerequisites, and recovery options.

## Scope limits

- Physical tampering, hardware implants, invasive attacks, and physical fault
  injection are outside this software scan.
- Damage caused solely by power removal/loss or hardware failure is outside scope.
  This scan does not require the device or local seed to survive arbitrary power
  interruptions. Firmware flaws allowing a host to cause unintended erasure or
  destruction through the communication interfaces remain in scope.
- Intended behavior, such as authorized reset, approved secret export, or reset after
  the intended password-attempt limit, is not itself a defect. Bypassing the required
  authorization or protections remains in scope.
- External theft of recovery backup material (sd card, paper/steel backups)
  or firmware-release signing keys, and knowingly approving correctly displayed malicious
  actions, are outside scope. Firmware bugs that mislead the user or bypass signature
  verification remain in scope.

Also report crashes, hangs, reboot loops, and bricking. These findings are useful
to us even when they fall outside our published threat model or bug bounty scope.

## Exercising the firmware

The Dockerfile prepares the environment and builds all four application variants.
Use the host tests for executable checks; the embedded ARM firmware binaries do not
run as Linux programs. Check findings against the applicable production configuration,
especially for bootloaders, where `DEBUG=no` alone does not select production behavior.

C tests, inside the container with networking disabled:

```sh
cd /src
make -j4 unit-test
make run-unit-tests
```

Run Rust tests from their workspace to load vendored dependencies, with one test thread:

```sh
cd /src/src/rust
cargo test --locked --offline --all-features -- --test-threads 1
```

## Reporting

Explain the affected product, trigger, required user actions, and credible impact.
Provide a reproducer where feasible and distinguish demonstrated results from
assumptions; a working on-device exploit is not required. For crashes or bricking,
describe persistence and whether recovery needs a restart, reflash, replacement
device, or wallet backup. Keep proposed fixes focused and include regression tests.

## References

- [BitBox product threat model](https://bitbox.swiss/bitbox02/threat-model/)
- [BitBox bug bounty policy](https://bitbox.swiss/policies/bug-bounty-policy/)
