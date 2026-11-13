# Threat model

## What this project does and where untrusted input enters

selinux provides the core SELinux userspace libraries, daemons, and
tools. It also includes some optional SELinux userspace daemons and
tools that are not installed by default. Applications use libsepol to
generate and read SELinux policy files, libsemanage to perform policy
management tasks, and libselinux to look up access and labeling
decisions, interact with the SELinux daemons, and invoke the
SELinux-specific kernel APIs (/proc/pid/attr/*, /sys/fs/selinux/*, and
the [l][f][gs]etxattr(2) system calls with the security.selinux xattr
name).

libsepol parses and validates binary and CIL source policy files and
memory buffers, but any bug that requires attacker-controlled policy
is handled as a regular bug, not as a security bug (i.e. no security
advisory). checkpolicy and checkmodule parse and validate source
policy files, but any bug that requires attacker-controlled source
policy is likewise handled as a regular bug, not a security bug.  The
libsepol API is not a trust boundary. The checkpolicy and checkmodule
interfaces are not a trust boundary. Similarly, the semodule-utils
programs operate on binary policy modules but their interfaces are not
a trust boundary.

All root-owned configuration files used by the SELinux userspace are
considered to be trusted. Any bug that requires attacker-controlled
root-owned configuration is handled as a regular bug, not a security
bug.

libsemanage parses and validates many different configuration files,
but the caveat above regarding root-owned configuration files holds.
The libsemanage API is not a trust boundary. The semodule, semanage,
and setsebool program interfaces are not trust boundaries.

The kernel interfaces are considered to be trusted by all of the
SELinux userspace. Reading from the /proc/pid/attr/* interfaces will
always return an attribute (context) value canonicalized against the
policy by the kernel. Similarly, reading from any of the
/sys/fs/selinux/* interfaces will always return a canonicalized value
against the policy or the set of valid values for a given interface
(e.g. 0 or 1 for enforce). In the case of the security.selinux xattrs
returned by getxattr(2) and similar system calls, the underlying xattr
value may originate from an untrusted filesystem in some cases,
although these xattr values will only be used and returned by the
kernel if the policy specifies the fs_use_xattr behavior for the
filesystem type and the mounter did not specify a SELinux context=
mount option at mount time to override it. Otherwise, the kernel will
assign a default value from policy or use the value specified via the
context= mount option and will always return this trusted value on
getxattr(2) calls. Even when the kernel uses the filesystem-provided
xattr values, it canonicalizes them against the policy before
returning them to userspace unless the process has the CAP_MAC_ADMIN
capability and has the SELinux mac_admin permission in the policy;
such processes are considered to be trusted with respect to handling
raw attribute values.

Despite the items noted above as being trusted or not being trust
boundaries, please report and fix bugs in parsing and processing
inputs, but there is no need to open a security advisory for these.

Depending on build configuration (any of AUDIT_LOG_PRIV=y,
NAMESPACE_PRIV=y, LSPP_PRIV=y), the newrole utility may run with
greater privileges than its caller and therefore considers all of its
caller-supplied inputs and environment to be untrusted and considers
the shell or command it launches in the new role to be untrusted.

The sandbox/seunshare utility considers all of its caller-supplied
inputs and environment to be untrusted and considers anything it runs
within the sandboxed process to be untrusted.

restorecond considers its environment, arguments, and configurations
to be trusted but not the file trees it walks. Note that walking of
user home directories is done by a separate per-user restorecond
instance.

mcstrans considers its environment, arguments, and configurations to
be trusted. mcstrans considers its clients to be untrusted but is
known to be subject to denial of service attacks. Fixes for such
denial of service attacks will be accepted but not treated as security
bugs.

## Components that matter most / least

Start with policycoreutils/newrole, sandbox/seunshare, restorecond,
and mcstrans (in that order) since they often run as root or with
Linux capabilities and deal with untrusted inputs. These are however
all optional components in Linux and unused by Android.

Next prioritize libselinux since it is the most widely linked library
across both Linux and Android userspace.

Next prioritize libsepol, checkpolicy, and secilc since they are used
by both Linux and Android, but remember that bugs that depend on
attacker-controlled policy are handled as regular bugs, not security
bugs.

Next prioritize libsemanage, followed by policycoreutils and python/*,
since they are widely used by Linux but not by Android.

Next review dbus and gui; while these often run as root or with Linux
capabilities, they are optional components, rarely used, and gated by
polkit or invoked by privileged authorized users.

Last review any remaining components e.g. semodule-utils.

## How to exercise it

.github/actions/build-userspace/action.yml is the GitHub action for
building the code, and .github/workflows/run_tests.yml is the workflow
for running the tests. The TL;DR version is 'make DESTDIR=/src/build test'.

FUZZING.md contains instructions for fuzzing selected components;
oss-fuzz is used to regularly run the fuzzers.

## How you rate severity

Anything that depends on attacker-controlled policy is low.

All DoS is low.

For memory-safety findings, provide a reproducer using a public API
where possible. Separate observed corruption or undefined behavior
from any claim of code execution; explain attacker control and
required features. Describe realistic impact.

## Anything to leave alone

The policy compilers (checkpolicy, checkmodule, and secilc) will
consume resources in accordance with the size and complexity of the
policies they are compiling. Small memory leaks on fatal error paths
during policy compilation are not of interest because the policy
compiler will exit shortly thereafter.
