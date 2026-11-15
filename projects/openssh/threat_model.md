# Threat model

## What this project does and where untrusted input enters

- an SSH server and client implementing the specs at
  http://openssh.org/specs.html

- untrusted traffic enters over the network, typically on port 22.

## Components that matter most / least

- sshd, sshd-auth and sshd-session run as root and cooperate to provide
  the SSH service.  The file README.privsep describes how these work.

- the contrib/ directory is third-party and out of scope

## How to exercise it

- build/default/ contains a build with default options including
  debug symbols.

- build/no-openssl/ contains a build without OpenSSL or zlib.

- build/kitchensink/ contains a build with all of the optional features
  enabled including PAM and Kerberos5.

- regress/ contains the tests. regression tests are in there, and the
  subdirectory regress/unit/ contains unit tests

- running 'make tests' in the build directory will run all tests.

- running "make t-exec" in the build directory will run only the
  regression tests.  A lot of regression tests need a loopback network
  interface.

  - running it with SUDO=sudo in the environment will cause the relevant
    parts to run as root.  This requires sudo to be configured to allow
    the unprivileged user to run sudo without a password.  You probably
    want this.

  - running tests with the "LTEST" argument will run a subset of the
    regression tests.

  - running tests with "USE_VALGRIND=1" will run the tests under Valgrind,
    albeit slowly.

  - some of regression tests have side effects like creating listening
    ports so cannot be run concurrently.

- running "make unit" will run only the unit tests.  Those can run
  in parallel.

## How you rate severity

- any buffer overflow, use-after-free, or double free is high+ at
  a minimum.

- If the overflow is controlled and may lead to RCE then it should
  be critical.

- Any authentication bypass in sshd, sshd-auth or sshd-session should
  be critical.

- All DoS is medium.

## Anything to leave alone

- nothing currently.
