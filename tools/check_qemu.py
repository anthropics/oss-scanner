#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""tools/check --qemu: the same build and shell as tools/check, but inside virtual machines set up like the scanner's.

Three virtual machines are used:

    base machine    Debian 12 with Docker installed. Created once (about ten minutes) and kept in the cache.
    build machine   A copy of the base machine, with network access. Runs check_build.py, then powers off.
                    Its disk is kept for the shell machine.
    shell machine   A copy of the build machine's disk, with no network access: no route out and no DNS. It
                    first confirms that it really is offline, then starts the container (privileged, as in
                    the scanner) and connects your terminal to it through a serial port.

Requires Linux on x86-64 with qemu-system-x86_64 and qemu-img. Uses /dev/kvm if you have access to it.
Without KVM, every instruction is emulated and a build takes many times longer.

The last section of this file runs inside the shell machine, as `check_qemu.py <image>`, so it uses only
the standard library.
"""
import codecs
import fcntl
import functools
import hashlib
import http.server
import json
import os
import pathlib
import pty
import select
import shlex
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import termios
import textwrap
import threading
import time
import tty
import urllib.request

from check_build import AGENT_MACHINE, BUILD_MACHINE, BUILD_MINUTES, CACHE, Failed, banner, image, say, step, terminal_safe

HERE = pathlib.Path(__file__).resolve().parent

# Use the "generic" image, not "genericcloud": only the full kernel has the 9p modules needed for the shared folder.
DEBIAN = "https://cloud.debian.org/images/cloud/bookworm/latest/"
DEBIAN_IMAGE = "debian-12-generic-amd64.qcow2"
BASE_READY = "base-machine-ready"  # printed to the serial console once the base machine is set up
CUT = b"\x1d"  # Ctrl-], which disconnects from the shell machine

# Runs on every boot of the build and shell machines (installed by USER_DATA below).
JOB_RUNNER = """\
#!/bin/bash
# Mount the folder shared by the host, run its job.sh, save the exit code, then power off.
modprobe 9pnet_virtio
mkdir -p /mnt/job
mount -t 9p -o trans=virtio,version=9p2000.L,msize=524288,cache=none job /mnt/job || exit 0
for _ in $(seq 60); do docker info >/dev/null 2>&1 && break; sleep 2; done
cd /mnt/job
bash ./job.sh >> job.log 2>&1
echo $? > exit_code
sync
sleep 2
systemctl poweroff --force --force
"""

# The systemd service that runs JOB_RUNNER once Docker is up.
JOB_UNIT = """\
[Unit]
Description=tools/check job runner
After=docker.service local-fs.target
Wants=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/check-job
StandardOutput=journal+console
StandardError=journal+console
TimeoutStartSec=infinity

[Install]
WantedBy=multi-user.target
"""

# cloud-init instructions that turn a stock Debian image into the base machine, on its first and only setup boot.
#
# Network setup: every machine has one network card that gets its address from qemu by DHCP. The base and build
# machines need it to install packages and run `docker build`. The shell machine's card can't reach anything;
# the shell machine uses it to prove there is no way out (see in_machine). Because cloud-init is disabled once
# setup is done, 10-check.network is what brings the card up on every later boot:
#   - net.ifnames=0 keeps the kernel's name for the card (eth0), so nothing renames it during boot.
#   - The wait-online override stops the offline shell machine from stalling its boot for two minutes.
USER_DATA = """\
#cloud-config
hostname: check
manage_etc_hosts: true
ssh_pwauth: false
package_update: true
packages: [docker.io, git, ca-certificates, curl, python3]
write_files:
  - path: /usr/local/sbin/check-job
    permissions: "0755"
    content: |
{job_runner}
  - path: /etc/systemd/system/check-job.service
    content: |
{job_unit}
  - path: /etc/modules-load.d/9p.conf
    content: |
      9p
      9pnet_virtio
  - path: /etc/systemd/network/10-check.network
    content: |
      [Match]
      Type=ether
      [Network]
      DHCP=ipv4
      LinkLocalAddressing=no
      IPv6AcceptRA=no
      [DHCPv4]
      UseHostname=no
  - path: /etc/systemd/system/systemd-networkd-wait-online.service.d/override.conf
    content: |
      [Service]
      ExecStart=
      ExecStart=/lib/systemd/systemd-networkd-wait-online --any --ipv4 --timeout=30
  - path: /etc/default/grub.d/90-check.cfg
    content: |
      GRUB_CMDLINE_LINUX="$GRUB_CMDLINE_LINUX net.ifnames=0"
      GRUB_TIMEOUT=0
runcmd:
  - rm -f /etc/netplan/*.yaml /etc/systemd/network/*cloud-init* /etc/udev/rules.d/*cloud-init*net* || true
  - update-grub
  - systemctl enable check-job.service docker.service
  - systemctl disable apt-daily.timer apt-daily-upgrade.timer unattended-upgrades.service || true
  - touch /etc/cloud/cloud-init.disabled
  - command -v docker git python3 >/dev/null && echo {ready} > /dev/ttyS0
  - sync
power_state: {{mode: poweroff, condition: true}}
"""


# ------------------------------------------------------------------------------------ runs on your machine


def require():
    """Exit if this computer can't run --qemu."""
    if not sys.platform.startswith("linux") or os.uname().machine != "x86_64":
        sys.exit("tools/check --qemu needs Linux on x86-64. Without --qemu it needs only Docker.")
    if os.geteuid() == 0:
        sys.exit("tools/check --qemu: run this as yourself, not as root.")
    missing = [name for name in ("qemu-system-x86_64", "qemu-img") if not shutil.which(name)]
    if missing:
        sys.exit(f"tools/check --qemu needs {' and '.join(missing)} (Debian, Ubuntu: apt install qemu-system-x86 qemu-utils)")


def has_kvm():
    """Return True if hardware acceleration (/dev/kvm) is available to this user."""
    return os.access("/dev/kvm", os.R_OK | os.W_OK)


def fit(machine):
    """Scale a scanner machine size down to fit this computer: at most all its CPUs and half its memory."""
    memory_gb = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") >> 30
    return {"cpus": min(machine["cpus"], os.cpu_count() or 1), "mem_gb": min(machine["mem_gb"], max(2, memory_gb // 2))}


def overlay(backing, disk):
    """Create `disk` as a copy-on-write layer over `backing`. Writes go to `disk`; `backing` is never changed."""
    disk.unlink(missing_ok=True)
    create = ["qemu-img", "create", "-q", "-f", "qcow2", "-b", str(backing.resolve()), "-F", "qcow2", str(disk)]
    subprocess.run(create, check=True)
    return disk


def fresh(directory):
    """Delete `directory` if it exists, then create it empty."""
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    return directory


def option(path):
    """Escape a path for use inside a qemu option, where commas separate fields."""
    return str(path).replace(",", ",,")


def start(name, disk, work, machine, online, share=None, extra=()):
    """Boot a virtual machine and return its qemu process.

    `online` controls network access. `share`, if given, is a host folder the machine mounts as /mnt/job.
    The machine's console is written to work/console.log, and qemu's own messages to work/qemu.log.
    """
    argv = [
        "qemu-system-x86_64", "-name", name, "-machine", "q35",
        "-m", f"{machine['mem_gb'] * 1024}M", "-smp", str(machine["cpus"]),
        "-display", "none", "-no-reboot", "-nodefaults", "-rtc", "base=utc", "-device", "virtio-rng-pci",
        "-serial", f"file:{option(work / 'console.log')}",
        "-drive", f"file={option(disk)},if=virtio,format=qcow2,discard=unmap,cache=unsafe",
        # When offline, restrict=on keeps all traffic inside qemu, and qemu's built-in DNS does not answer.
        "-netdev", "user,id=n0,ipv6=off" + ("" if online else ",restrict=on"),
        "-device", "virtio-net-pci,netdev=n0,addr=0x3",
    ]
    argv += ["-accel", "kvm", "-cpu", "host"] if has_kvm() else ["-accel", "tcg,thread=multi,tb-size=1024", "-cpu", "max"]
    if share:
        # With mapped-xattr, anything the machine creates in the share (links, devices, file owners) is stored on
        # your side as a plain file owned by you.
        argv += ["-fsdev", f"local,id=fs0,path={option(share)},security_model=mapped-xattr,multidevs=remap"]
        argv += ["-device", "virtio-9p-pci,fsdev=fs0,mount_tag=job,addr=0x8"]
    with open(work / "qemu.log", "wb") as log:
        return subprocess.Popen(
            [*argv, *extra], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
        )


def stop(machine):
    """Stop the machine if it is still running: politely first, then by force after ten seconds."""
    if machine.poll() is None:
        machine.terminate()
        try:
            machine.wait(timeout=10)
        except subprocess.TimeoutExpired:
            machine.kill()


def watch(machine, log, minutes):
    """Print new lines from `log` until the machine powers off. Return False if `minutes` run out first."""
    seen, deadline = 0, time.time() + minutes * 60
    decode = codecs.getincrementaldecoder("utf-8")(errors="replace")     # a character split across two reads stays whole
    while True:
        off = machine.poll() is not None
        if log.exists():
            with open(log, "rb") as file:
                file.seek(seen)
                new = file.read()
            seen += len(new)
            sys.stdout.write(terminal_safe(decode.decode(new)))
            sys.stdout.flush()
        if off:
            return True
        if time.time() > deadline:
            return False
        time.sleep(1)


def why_it_died(work):
    """Return the end of qemu's log, or a pointer to the console log if qemu said nothing."""
    return (work / "qemu.log").read_text(errors="replace").strip()[-300:] or f"see {work / 'console.log'}"


def download_debian(to):
    """Download the Debian image to `to` and verify it against Debian's published SHA-512 checksums."""
    step(f"download {DEBIAN}{DEBIAN_IMAGE}")
    with urllib.request.urlopen(DEBIAN + "SHA512SUMS", timeout=60) as response:
        sums = {name: digest for digest, name in map(str.split, response.read().decode().splitlines())}
    digest, part = hashlib.sha512(), to.with_suffix(".part")
    with urllib.request.urlopen(DEBIAN + DEBIAN_IMAGE, timeout=60) as response, open(part, "wb") as file:
        while chunk := response.read(1 << 20):
            digest.update(chunk)
            file.write(chunk)
    if digest.hexdigest() != sums.get(DEBIAN_IMAGE):
        part.unlink()
        sys.exit(f"{DEBIAN_IMAGE} does not match Debian's SHA512SUMS: the download was cut short or altered. Try again.")
    part.rename(to)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """A file server that does not log each request to the terminal."""

    def log_message(self, *_):
        pass


def base_machine():
    """Return the base machine's disk, creating it first if it does not exist yet."""
    base = CACHE / "base.qcow2"
    if base.exists():
        return base
    work, debian = fresh(CACHE / "base"), CACHE / DEBIAN_IMAGE
    if not debian.exists():
        download_debian(debian)
    disk = work / "base.qcow2"
    shutil.copyfile(debian, disk)
    subprocess.run(["qemu-img", "resize", "-q", str(disk), f"{BUILD_MACHINE['disk_gb']}G"], check=True)

    # cloud-init fetches its instructions over HTTP. Inside the machine, 10.0.2.2 reaches this computer's 127.0.0.1.
    seed = fresh(work / "seed")
    indent = functools.partial(textwrap.indent, prefix=" " * 6)
    (seed / "user-data").write_text(
        USER_DATA.format(job_runner=indent(JOB_RUNNER), job_unit=indent(JOB_UNIT), ready=BASE_READY)
    )
    (seed / "meta-data").write_text("instance-id: check-base\nlocal-hostname: check\n")
    (seed / "vendor-data").write_text("")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(seed)))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    step("make the base machine: Debian 12 with Docker (once; about ten minutes, much longer without /dev/kvm)")
    say(f"its console: {work / 'console.log'}")
    where = f"type=1,serial=ds=nocloud-net;s=http://10.0.2.2:{server.server_address[1]}/"
    machine = start("check-base", disk, work, fit({"cpus": 4, "mem_gb": 4}), online=True, extra=["-smbios", where])
    try:
        machine.wait(timeout=90 * 60)
    except subprocess.TimeoutExpired:
        sys.exit(f"the base machine was not ready after 90 minutes: see {work / 'console.log'}")
    finally:
        stop(machine)
        server.shutdown()
    if BASE_READY not in (work / "console.log").read_text(errors="replace"):
        sys.exit(f"the base machine was not set up (qemu exited {machine.returncode}): {why_it_died(work)}")
    disk.rename(base)
    return base


def build(job, share, work):
    """Run check_build.py in the build machine. Raise Failed if the build fails.

    `share` already contains job.json, plus the Dockerfile if it is kept next to project.yaml. On success, the
    build machine's disk is saved as work/build.qcow2.
    """
    machine_size = fit(BUILD_MACHINE)
    base = base_machine()
    shutil.copy(HERE / "check_build.py", share)
    (share / "job.sh").write_text("exec python3 /mnt/job/check_build.py /mnt/job\n")
    (work / "build.qcow2").unlink(missing_ok=True)
    disk = overlay(base, work / "building.qcow2")

    step(
        f"boot the build machine: online, {machine_size['cpus']} CPUs, {machine_size['mem_gb']} GB "
        f"(the scanner's: {BUILD_MACHINE['cpus']} CPUs, {BUILD_MACHINE['mem_gb']} GB), "
        + ("KVM" if has_kvm() else "EMULATED, there is no /dev/kvm: this is slow, and the time limit still applies")
    )
    machine = start(f"check-build-{job.name}", disk, work, machine_size, online=True, share=share)
    try:
        in_time = watch(machine, share / "job.log", BUILD_MINUTES + 5)
    finally:
        stop(machine)
    if (share / "failed").exists():
        raise Failed((share / "failed").read_text().strip())
    if not in_time:
        raise Failed(f"the build machine was stopped: it had been up for the {BUILD_MINUTES} minutes a build has")
    if not (share / "exit_code").exists() or (share / "exit_code").read_text().strip() != "0":
        raise Failed(f"the build machine ended before the build did: {why_it_died(work)}")
    disk.rename(work / "build.qcow2")


def window_size():
    """Return this terminal's size as "rows columns\\n", or 24x80 if it is not a terminal."""
    try:
        size = os.get_terminal_size(sys.stdin.fileno())
        return f"{size.lines} {size.columns}\n"
    except OSError:
        return "24 80\n"


def relay(line, keyboard, screen, machine):
    """Copy bytes between this terminal and the serial line until the line closes or Ctrl-] is pressed."""
    sources = [line, keyboard]
    while True:
        ready, _, _ = select.select(sources, [], [], 1.0)
        if not ready and machine.poll() is not None:
            return
        if line in ready:
            data = line.recv(65536)
            if not data:
                return
            os.write(screen, data)
        if keyboard in ready:
            data = os.read(keyboard, 4096)
            if not data:
                # stdin was a script and it has all been sent. Stop reading it, but keep showing the output.
                sources.remove(keyboard)
            elif CUT in data:
                return
            else:
                line.sendall(data)


def attach(path, share, machine):
    """Connect this terminal to the machine's second serial port (the unix socket at `path` on this side).

    Window resizes are passed on by writing the new size to share/winsize.
    """
    keyboard, saved = sys.stdin.fileno(), None
    line = socket.socket(socket.AF_UNIX)
    line.connect(path)
    signal.signal(signal.SIGWINCH, lambda *_: (share / "winsize").write_text(window_size()))
    try:
        if os.isatty(keyboard):
            saved = termios.tcgetattr(keyboard)
            tty.setraw(keyboard)
        line.sendall(b"\n")  # get a new prompt, since the first was printed before we connected
        relay(line, keyboard, sys.stdout.fileno(), machine)
    finally:
        signal.signal(signal.SIGWINCH, signal.SIG_DFL)
        if saved:
            termios.tcsetattr(keyboard, termios.TCSADRAIN, saved)
        line.close()


def shell(job, work):
    """Open a shell in the finished image, inside an offline machine. Return False if the shell never started."""
    share = fresh(work / "shell")
    for name in ("check_qemu.py", "check_build.py"):
        shutil.copy(HERE / name, share)
    terminal = shlex.quote(os.environ.get("TERM") or "xterm")
    (share / "job.sh").write_text(f"TERM={terminal} exec python3 /mnt/job/check_qemu.py {image('built', job.name)}\n")
    (share / "winsize").write_text(window_size())
    disk = overlay(work / "build.qcow2", work / "shell.qcow2")
    # A short, private temp directory: unix socket paths are limited to 107 bytes.
    sockets = tempfile.mkdtemp(prefix="check-")
    serial = ["-chardev", f"socket,id=shell0,path={sockets}/tty,server=on,wait=off", "-serial", "chardev:shell0"]

    machine_size = fit(AGENT_MACHINE)
    step(f"boot the shell machine: offline, {machine_size['cpus']} CPUs, {machine_size['mem_gb']} GB")
    machine = start(f"check-shell-{job.name}", disk, work, machine_size, online=False, share=share, extra=serial)
    try:
        while machine.poll() is None and not (share / "shell.ready").exists():
            time.sleep(0.5)
        if not (share / "shell.ready").exists():
            say((share / "job.log").read_text(errors="replace") if (share / "job.log").exists() else why_it_died(work))
            return False
        found = json.loads((share / "canary.json").read_text())
        banner(
            job,
            "in a privileged container in a virtual machine, as in a scan",
            f"the machine looked for a way out before it started this shell: DNS {found['dns']}, connections {found['egress']}",
            "exit or Ctrl-D ends it. Ctrl-] cuts the line and stops the machine.",
        )
        attach(f"{sockets}/tty", share, machine)
        return True
    finally:
        stop(machine)
        disk.unlink(missing_ok=True)
        shutil.rmtree(sockets, ignore_errors=True)


# ------------------------------------------------------------------------------ runs inside the shell machine


def answers_dns(server):
    """Return True if `server` answers a DNS query for example.com."""
    query = bytes.fromhex("abcd01000001000000000000076578616d706c6503636f6d0000010001")  # example.com, A
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.settimeout(4)
        try:
            probe.sendto(query, (server, 53))
            return bool(probe.recvfrom(512))
        except OSError:
            return False


def connects(host, port):
    """Return True if a TCP connection to host:port succeeds."""
    try:
        socket.create_connection((host, port), timeout=5).close()
        return True
    except OSError:
        return False


def write_all(fd, data):
    """Write all of `data` to `fd`, retrying after partial writes."""
    while data:
        data = data[os.write(fd, data) :]


def resize(terminal, seen):
    """Apply the size in /mnt/job/winsize to the shell's terminal if it changed. Return the text read."""
    try:
        text = pathlib.Path("/mnt/job/winsize").read_text()
        if text != seen:
            rows, columns = map(int, text.split())
            fcntl.ioctl(terminal, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
        return text
    except (OSError, ValueError):
        return seen


def in_machine(built, line="/dev/ttyS1"):
    """Confirm the machine is offline, then start the container the way the scanner starts an agent's.

    If DNS answers or an outbound connection succeeds, no shell is started. Otherwise the container gets its
    own terminal (for job control, window size and Ctrl-C), and this process copies bytes between that
    terminal and the serial line. The serial line is set to raw mode so nothing echoes or translates them.
    """
    found = {
        "dns": "answered" if any(map(answers_dns, ("10.0.2.3", "8.8.8.8"))) else "none",
        "egress": "made" if connects("1.1.1.1", 443) or connects("8.8.8.8", 53) else "none",
    }
    pathlib.Path("/mnt/job/canary.json").write_text(json.dumps(found))
    if set(found.values()) != {"none"}:
        say(f"this machine has a way out ({found}): no shell is started in it")
        return 66

    wire = os.open(line, os.O_RDWR | os.O_NOCTTY)
    tty.setraw(wire)
    child, terminal = pty.fork()
    if child == 0:
        # --network host is safe here: the machine is offline, so the container is too.
        container = ["--rm", "-it", "--init", "--privileged", "--network", "host", "-w", "/src", "-e", "TERM"]
        os.execvp("docker", ["docker", "run", *container, built, "bash"])
    seen = resize(terminal, None)
    pathlib.Path("/mnt/job/shell.ready").touch()
    while True:
        ready, _, _ = select.select([terminal, wire], [], [], 1.0)
        seen = resize(terminal, seen)
        if terminal in ready:
            try:
                data = os.read(terminal, 65536)
            except OSError:  # the shell has exited and closed its terminal
                break
            if not data:
                break
            write_all(wire, data)
        if wire in ready:
            write_all(terminal, os.read(wire, 65536))
    write_all(wire, b"\r\n[the shell ended: the machine is powering off]\r\n")
    return os.waitstatus_to_exitcode(os.waitpid(child, 0)[1])


if __name__ == "__main__":
    sys.exit(in_machine(sys.argv[1]))
