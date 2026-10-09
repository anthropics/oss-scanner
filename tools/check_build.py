#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""
The scanner's build steps for a project. tools/check uses this module to do the actual build.

Without --qemu, tools/check imports it and runs it on your machine. With --qemu, it runs inside the build
virtual machine as:

    python3 check_build.py <job directory>
"""
import codecs
import dataclasses
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time

CACHE = pathlib.Path(os.environ.get("XDG_CACHE_HOME") or "~/.cache").expanduser() / "oss-scanner-check"

# The resources the scanner gives each project.
BUILD_MINUTES = 45  # time limit from the start of the clone to the finished image
BUILD_MACHINE = {"cpus": 16, "mem_gb": 64, "disk_gb": 120}
AGENT_MACHINE = {"cpus": 2, "mem_gb": 8}

# Where in the checkout a Dockerfile from next to project.yaml is copied to.
SHIPPED_DOCKERFILE = ".oss-scanner/Dockerfile"

# The scanner's layer on top of your image: Claude Code, plus common analysis tools.
# The packages in `need` must install or the build fails. The packages in `tools` are best effort.
TOOLS_LAYER = r"""
ARG BASE
FROM $BASE
USER 0
RUN set -e; \
    need="curl ca-certificates git python3 bash procps"; \
    if command -v apt-get >/dev/null; then \
        tools="build-essential clang gdb strace ltrace valgrind lsof file xxd jq netcat-openbsd python3-venv python3-pip pkg-config cmake"; \
        apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $need \
        && (DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $tools || true) && rm -rf /var/lib/apt/lists/*; \
    elif command -v dnf >/dev/null; then dnf install -y $need procps-ng && (dnf install -y gcc gcc-c++ make clang gdb strace valgrind lsof file jq nmap-ncat cmake || true) && dnf clean all; \
    elif command -v yum >/dev/null; then yum install -y $need procps-ng && (yum install -y gcc gcc-c++ make clang gdb strace valgrind lsof file jq cmake || true) && yum clean all; \
    elif command -v apk >/dev/null; then apk add --no-cache $need libstdc++ gcompat && (apk add --no-cache build-base clang gdb strace valgrind lsof file jq cmake || true); \
    elif command -v zypper >/dev/null; then zypper -n install $need && (zypper -n install gcc gcc-c++ make clang gdb strace valgrind lsof file jq cmake || true); \
    elif command -v pacman >/dev/null; then pacman -Sy --noconfirm $need && (pacman -S --noconfirm base-devel clang gdb strace valgrind lsof file jq cmake || true); \
    else echo "no package manager found: curl, git, python3 and bash must already be in the image"; fi
ENV HOME=/root
RUN curl -fsSL https://claude.ai/install.sh | bash \
 && ln -sf /root/.local/bin/claude /usr/local/bin/claude \
 && claude --version
ENTRYPOINT []
CMD ["bash"]
ENV IS_SANDBOX=1 \
    DISABLE_AUTOUPDATER=1 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    DISABLE_TELEMETRY=1 \
    DISABLE_ERROR_REPORTING=1 \
    CLAUDE_CODE_IDE_SKIP_AUTO_INSTALL=1
"""


class Failed(Exception):
    """The build failed, so it would also fail in the scanner. The message says which step failed and why."""


@dataclasses.dataclass
class Job:
    """One project's build settings, taken from its project.yaml.

    Saved as job.json so the build machine can read it. If the Dockerfile is kept next to project.yaml, it is
    copied into the same job directory.
    """

    name: str
    repo: str
    ref: str  # branch or tag; "" means the repository's default branch
    dockerfile: str  # path in the repository; "" if it is kept next to project.yaml
    threat_model: str  # path in the repository; "" if it is kept next to project.yaml

    def save(self, directory):
        """Write this job to <directory>/job.json."""
        (directory / "job.json").write_text(json.dumps(dataclasses.asdict(self), indent=2) + "\n")

    @classmethod
    def load(cls, directory):
        """Read a job from <directory>/job.json."""
        return cls(**json.loads((directory / "job.json").read_text()))


def image(stage, name):
    """Return the Docker tag for one stage of a project's image.

    Stages: `target` is your Dockerfile's output, `tools` adds the scanner's layer, and `built` is the
    finished image.
    """
    return f"oss-scanner-check/{stage}:{name}"


_UNSAFE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def terminal_safe(text):
    """Text from the project (its commits, its build output) for the terminal: control characters other than tab, newline
    and carriage return (escape sequences, BEL, ...) are shown as \\xNN, never sent raw."""
    return _UNSAFE.sub(lambda m: f"\\x{ord(m.group()):02x}", text)


def say(text=""):
    """Print a line and flush right away, so output stays in order with subprocess output. Everything goes through
    terminal_safe(): much of what is printed (names, URLs, logs, the image's settings) comes from the project."""
    print(terminal_safe(str(text)), flush=True)


def step(text):
    """Print a timestamped heading for the next build step."""
    say(f"\n[{time.strftime('%H:%M:%S')}] {text}")


def banner(job, where, *notes):
    """Print the message shown just before the shell opens. `where` describes the environment."""
    say(f"\n── {job.name} is built. You are root in /src of the finished image, with no network, {where} ──")
    say("   Try what somebody studying your project would need: run the tests, start the program, use gdb.")
    say("   Whatever fails here for want of a network fails in a scan too: fetch it in the Dockerfile.")
    for note in notes:
        say(f"   {note}")
    say()


def run(*argv, limit=None, stdin=None, quiet=False):
    """Run a command and return its exit code, or 124 if it was killed after `limit` seconds.

    `stdin` is text to send to the command. `quiet` hides its output. Otherwise its output (the project's build, its git
    server's messages) reaches the terminal through terminal_safe(), never raw.
    """
    if quiet:
        # Never let the command read whatever was piped into tools/check.
        given = {"stdin": subprocess.DEVNULL} if stdin is None else {"input": stdin}
        try:
            return subprocess.run(argv, **given, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=limit).returncode
        except subprocess.TimeoutExpired:
            return 124
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL if stdin is None else subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def copy():
        decode = codecs.getincrementaldecoder("utf-8")(errors="replace")
        while chunk := os.read(proc.stdout.fileno(), 65536):
            sys.stdout.write(terminal_safe(decode.decode(chunk)))
            sys.stdout.flush()

    reader = threading.Thread(target=copy, daemon=True)
    reader.start()
    if stdin is not None:
        proc.stdin.write(stdin.encode())
        proc.stdin.close()
    try:
        code = proc.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        code = 124
    reader.join(timeout=5)
    return code


def image_has(tag, test, *args):
    """Return True if the shell command `test` succeeds inside the image. `args` become $1, $2, ..."""
    return run("docker", "run", "--rm", "--entrypoint", "sh", tag, "-c", test, "sh", *args, quiet=True) == 0


def add_layer(tag, dockerfile, context=None):
    """Build image `tag` from Dockerfile text. `context` is the directory to COPY from, if one is needed."""
    where = ["-f", "-", str(context)] if context else ["-"]
    done = subprocess.run(["docker", "build", "-t", tag, *where], input=dockerfile, text=True, capture_output=True)
    if done.returncode != 0:
        raise Failed(f"could not add this layer to the image:\n{dockerfile}\n{done.stderr[-2000:]}")


def in_checkout(checkout, path):
    """Return checkout/path. Raise Failed if a symbolic link makes it point outside the checkout."""
    if not (checkout / path).resolve().is_relative_to(checkout.resolve()):
        raise Failed(f"{path} resolves to a place outside the repository and is not used")
    return checkout / path


def remove(path):
    """Delete the file or directory at `path`. Symbolic links are deleted, not followed."""
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def fetch(job, checkout):
    """Clone the project's repository into `checkout`."""
    step(f"clone {job.repo}" + (f" ({job.ref})" if job.ref else ""))
    shutil.rmtree(checkout, ignore_errors=True)
    checkout.parent.mkdir(parents=True, exist_ok=True)
    # Clone anonymously like the scanner does, so a private repository fails here too.
    os.environ["GIT_TERMINAL_PROMPT"] = "0"
    branch = ["--branch", job.ref] if job.ref else []
    # Allow only https, even if the URL or a server redirect asks for another protocol.
    only_https = ["-c", "protocol.allow=never", "-c", "protocol.https.allow=always"]
    if run("git", "-c", "credential.helper=", *only_https, "clone", "--quiet", *branch, "--", job.repo, str(checkout)) != 0:
        raise Failed(f"cannot clone {job.repo}" + (f" at {job.ref}" if job.ref else ""))
    head = subprocess.run(["git", "-C", str(checkout), "log", "-1", "--format=HEAD is %h %s (%cs)"],
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace").stdout
    say(head.rstrip("\n"))


def place_dockerfile(job, directory, checkout):
    """Find or place the Dockerfile. Return its path relative to the checkout."""
    if job.dockerfile:
        if not in_checkout(checkout, job.dockerfile).is_file():
            raise Failed(f"no Dockerfile at {job.dockerfile} in the repository")
        say(f"Dockerfile: the repository's own, {job.dockerfile}")
        return job.dockerfile

    # Always build the Dockerfile from next to project.yaml, replacing anything the repository has at that path.
    parent = in_checkout(checkout, pathlib.Path(SHIPPED_DOCKERFILE).parent)
    if parent.exists() and not parent.is_dir():
        raise Failed(f"{parent.name} in the repository is not a directory: the Dockerfile cannot be placed in it")
    parent.mkdir(exist_ok=True)
    remove(checkout / SHIPPED_DOCKERFILE)
    shutil.copyfile(directory / "Dockerfile", checkout / SHIPPED_DOCKERFILE)
    # The repository's .dockerignore was written for its own images. Remove it so it can't hide sources from this build.
    remove(checkout / ".dockerignore")
    say(f"Dockerfile: the one beside project.yaml, placed at {SHIPPED_DOCKERFILE}")
    return SHIPPED_DOCKERFILE


def report_threat_model(job, checkout):
    """Report where the threat model is. It is optional, so a missing one never fails the build."""
    if not job.threat_model:
        return say("threat model: the one beside project.yaml")
    try:
        found = in_checkout(checkout, job.threat_model).is_file()
    except Failed as failure:
        return say(f"threat model: NONE. {failure}")
    if found:
        say(f"threat model: the repository's own, {job.threat_model}")
    else:
        say(f"threat model: none (nothing at {job.threat_model} in the repository). It is optional, and worth writing")


def build_project(job, checkout, dockerfile, seconds, in_vm):
    """Build the project's Dockerfile into the `target` image, within `seconds`."""
    step(f"docker build: your Dockerfile is the whole build ({int(seconds / 60)} min left of {BUILD_MINUTES})")
    network = ["--network=host"] if in_vm else []
    where = ["-f", str(checkout / dockerfile), "-t", image("target", job.name), str(checkout)]
    code = run("docker", "build", "--progress=plain", *network, *where, limit=seconds)
    if code == 124:
        raise Failed(
            f"docker build did not finish in the {int(seconds / 60)} minutes it had. A step that hangs "
            "(a test waiting on a socket, a watch mode, a prompt) must be bounded or left out"
        )
    if code != 0:
        raise Failed(f"docker build of your Dockerfile exited {code}")


def ensure_src(job, checkout):
    """Make sure the image has /src, because every later step expects the project there.

    If the image's working directory looks like the project, /src becomes a link to it. Otherwise the plain
    checkout is copied to /src, and a warning explains that nothing in it has been built.
    """
    target = image("target", job.name)
    if image_has(target, "test -d /src"):
        return
    inspect = subprocess.run(
        ["docker", "inspect", "-f", "{{.Config.WorkingDir}}", target], capture_output=True, text=True
    )
    workdir = inspect.stdout.strip()
    # The working directory counts as the project if it holds at least half of the checkout's top-level
    # entries (checking at most 12 of them).
    names = sorted(path.name for path in checkout.iterdir() if path.name != ".git")[:12]
    found = sum(image_has(target, 'test -e "$1"', f"{workdir}/{name}") for name in names) if workdir.strip("/") else 0
    if names and found * 2 >= len(names):
        say(f"the image has no /src; its working directory {workdir} holds the project: /src -> {workdir}")
        add_layer(target, f"FROM {target}\nUSER 0\nRUN ln -s {shlex.quote(workdir)} /src\n")
    else:
        say(
            f"WARNING: the image has no /src, and its working directory ({workdir or 'none'}) does not hold the "
            "project.\n/src becomes a plain checkout in which NOTHING IS BUILT. Use `COPY . /src` and build there."
        )
        add_layer(target, f"FROM {target}\nUSER 0\nCOPY . /src\n", checkout)


def add_tools(job, in_vm):
    """Install the scanner's layer on top of the `target` image, producing the `tools` image."""
    step("docker build: the scanner's layer (Claude Code, debuggers, compilers)")
    network = ["--network=host"] if in_vm else []
    tools = image("tools", job.name)
    base = ["--build-arg", f"BASE={image('target', job.name)}"]
    code = run("docker", "build", "--progress=plain", *network, *base, "-t", tools, "-", stdin=TOOLS_LAYER)
    if code != 0 or not image_has(tools, "claude --version"):
        raise Failed(
            "the scanner's layer does not install on your image. The final stage of your Dockerfile needs a package "
            "manager (apt, dnf, yum, apk, zypper or pacman), or curl, git, python3 and bash: not scratch or distroless"
        )


def finish(job, checkout):
    """Produce the `built` image: add .git if missing, set the working directory, check it starts offline."""
    step("finish the image")
    tools, layer = image("tools", job.name), ["USER 0"]
    if not image_has(tools, "test -d /src/.git"):
        say("adding the git history your Dockerfile left out: /src/.git")
        layer.append("COPY .git /src/.git")
    layer += ["WORKDIR /src", "ENTRYPOINT []", 'CMD ["bash"]']
    remove(checkout / ".dockerignore")  # so it can't exclude .git from the COPY above
    add_layer(image("built", job.name), "\n".join([f"FROM {tools}", *layer]) + "\n", checkout)
    run("docker", "image", "rm", image("target", job.name), tools, quiet=True)
    if run("docker", "run", "--rm", "--network=none", image("built", job.name), "true") != 0:
        raise Failed("the finished image does not start without a network")


def build(job, directory, checkout, in_vm=False):
    """Run every build step: clone, build, add the scanner's layers.

    On success, the `built` image exists. On failure, raises Failed. `directory` is the job directory holding
    job.json (and the Dockerfile, if it is kept next to project.yaml).
    """
    os.environ["DOCKER_BUILDKIT"] = "1"
    deadline = time.time() + BUILD_MINUTES * 60
    fetch(job, checkout)
    dockerfile = place_dockerfile(job, directory, checkout)
    report_threat_model(job, checkout)
    # Keep a tenth of the time limit for the steps after your Dockerfile, but always give it at least a minute.
    build_project(job, checkout, dockerfile, max(60, deadline - time.time() - BUILD_MINUTES * 6), in_vm)
    ensure_src(job, checkout)
    add_tools(job, in_vm)
    finish(job, checkout)
    shutil.rmtree(checkout, ignore_errors=True)  # no longer needed: the image has its own copy
    if time.time() > deadline:
        raise Failed(f"the build took more than the {BUILD_MINUTES} minutes it has")


def main():
    """Entry point inside the build VM. On failure, writes the reason to <job directory>/failed."""
    directory = pathlib.Path(sys.argv[1])
    try:
        build(Job.load(directory), directory, pathlib.Path("/src"), in_vm=True)
    except Failed as failure:
        (directory / "failed").write_text(f"{failure}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
