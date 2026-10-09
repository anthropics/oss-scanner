#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Check every projects/<name>/ directory against the enrolment rules in README.md.

    tools/validate.py

If there are problems, prints one line per problem and exits 1. Otherwise prints one summary line per
project and exits 0. Runs offline and never writes anything. Requires PyYAML (pip install pyyaml).

Fields allowed in project.yaml:

    repo: https://...[#branch-or-tag]   required   a single git repository, https only
    primary_contact: a@b.c              required
    dockerfile: <path in your repo>     required   unless a Dockerfile is next to project.yaml (no default)
    threat_model: <path in your repo>   optional   defaults to .oss-scanner/threat_model.md
    auto_ccs: [a@b.c, ...]              optional   cannot be combined with pgp
    homepage: https://...               optional
    pgp: <armored public key>           optional   if set, reports are encrypted to this key
    disabled: true|false                optional   true pauses reports

The only other files allowed next to project.yaml are a Dockerfile and a threat_model.md. Each one must
live in exactly one place: either next to project.yaml, or in your repository at the path set by its key.

The scanner enforces these same rules, with the same error messages, when it imports a project. It does
not share code with this repository, so any rule change must be made in both places.
"""
import argparse
import pathlib
import re
import stat
import sys
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    sys.exit("tools/validate.py needs PyYAML: pip install pyyaml")

PROJECTS = pathlib.Path(__file__).resolve().parent.parent / "projects"

REQUIRED_KEYS = ("repo", "primary_contact")
OPTIONAL_KEYS = ("auto_ccs", "homepage", "pgp", "disabled", "dockerfile", "threat_model")
ALLOWED_KEYS = REQUIRED_KEYS + OPTIONAL_KEYS
# Settings controlled by the scanner's operators. A pull request may not set them.
OPERATOR_KEYS = ("workflow", "workflows", "budget", "budget_usd", "cadence", "cadence_hours", "schedule", "priority")
# Maps each file that may sit next to project.yaml to the key that would point to it in the project's repository.
FILE_KEYS = {"Dockerfile": "dockerfile", "threat_model.md": "threat_model"}
MAX_FILE_BYTES = 64 * 1024
MAX_CONFIG_BYTES = 128 * 1024

NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,62}")
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
URL = re.compile(r"https://[^\s#]+(#[A-Za-z0-9._/-]{1,100})?")
# A relative path with no `..` that uses only safe characters (no spaces, backslashes or control characters).
REPO_PATH = re.compile(r"(?!/)(?!.*\.\.)[A-Za-z0-9._/-]+")
PGP_BEGIN = "-----BEGIN PGP PUBLIC KEY BLOCK-----"
PGP_END = "-----END PGP PUBLIC KEY BLOCK-----"


def is_https_url(value):
    """Return True if `value` is an https:// URL with a host and at most one simple #fragment."""
    if not (isinstance(value, str) and URL.fullmatch(value)):
        return False
    try:
        return bool(urlparse(value.split("#", 1)[0]).hostname)
    except ValueError:
        return False


def is_public_key(text):
    """Return True if `text` is exactly one armored PGP public key block.

    This only checks the format. The scanner checks whether the key actually works.
    """
    text = text.strip()
    return (
        text.startswith(PGP_BEGIN)
        and text.endswith(PGP_END)
        and text.count(PGP_BEGIN) == 1
        and text.count(PGP_END) == 1
        and "PRIVATE KEY" not in text
        and len(text) <= MAX_FILE_BYTES
    )


def check_keys(config):
    """Yield a problem for each unknown, operator-only, or missing required key."""
    for key in config:
        if key in OPERATOR_KEYS:
            yield f"{key!r} is set by the operators, not in project.yaml (steer the scan with threat_model.md)"
        elif key not in ALLOWED_KEYS:
            yield f"unknown field {key!r} (allowed: {', '.join(ALLOWED_KEYS)})"
    for key in REQUIRED_KEYS:
        if not config.get(key):
            yield f"missing {key}"


def check_types(config):
    """Yield a problem for each scalar field that has the wrong YAML type."""
    for key in ("primary_contact", "homepage", "pgp"):
        if config.get(key) is not None and not isinstance(config[key], str):
            yield f"{key} must be a string"
    if config.get("disabled") is not None and not isinstance(config["disabled"], bool):
        yield "disabled must be true or false"


def check_urls(config):
    """Yield a problem if repo or homepage is not a valid https:// URL."""
    if config.get("repo") is not None and not is_https_url(config["repo"]):
        yield "repo must be ONE https:// URL of a git repository (a string, not a list; add #branch-or-tag to pin one)"
    homepage = config.get("homepage")
    if isinstance(homepage, str) and not is_https_url(homepage.split("#", 1)[0]):
        yield "homepage must be an https:// URL"


def check_addresses(config):
    """Yield a problem for auto_ccs that is not a list, and for each malformed email address."""
    addresses = []
    if isinstance(config.get("primary_contact"), str):
        addresses.append(config["primary_contact"])
    ccs = config.get("auto_ccs")
    if isinstance(ccs, list) and all(isinstance(address, str) for address in ccs):
        addresses += ccs
    elif ccs is not None:
        yield "auto_ccs must be a list of addresses"
    for address in addresses:
        if not EMAIL.fullmatch(address):
            yield f"bad email {address!r}"


def check_pgp(config):
    """Yield a problem if pgp is malformed, or is combined with auto_ccs."""
    key = config.get("pgp")
    if key and config.get("auto_ccs"):
        yield "pgp and auto_ccs together are not supported: an encrypted report goes to primary_contact only"
    if isinstance(key, str) and not is_public_key(key):
        yield (
            f"pgp must be one armored public key: the text from {PGP_BEGIN} to {PGP_END} "
            "(not a fingerprint, a URL or a private key)"
        )


def check_files(config, files):
    """Yield problems with the Dockerfile and threat model, whether they are next to project.yaml or in the repo.

    `files` maps the name of each file next to project.yaml to its text, or to None if it could not be read.
    """
    for key in FILE_KEYS.values():
        path = config.get(key)
        if path is not None and not (isinstance(path, str) and REPO_PATH.fullmatch(path)):
            yield f"{key} must be a relative path inside your repository"

    # In YAML, an empty `dockerfile:` (or `~`, or `null`) means the key is not set.
    if "Dockerfile" not in files and config.get("dockerfile") is None:
        yield (
            "a Dockerfile is required, in exactly one place: beside project.yaml, or in your repository "
            "at the path you give as dockerfile: (there is no default path)"
        )

    for name, text in files.items():
        if name not in FILE_KEYS:
            yield f"{name}: only project.yaml, {', '.join(FILE_KEYS)} may sit in a project's directory"
            continue
        if text is None:
            yield f"{name} is larger than {MAX_FILE_BYTES // 1024} KiB (or not text)"
        elif name == "Dockerfile" and not text.strip():
            yield "Dockerfile is empty: it is the whole build"
        if config.get(FILE_KEYS[name]) is not None:
            yield f"{name} is given both beside project.yaml and as {FILE_KEYS[name]}: in your repository — one place only"


def check_config(config, files):
    """Return a list of every problem with a parsed project.yaml and the files next to it."""
    if not isinstance(config, dict):
        return [f"not a mapping (top level is a {type(config).__name__})"]
    return [
        *check_keys(config),
        *check_types(config),
        *check_urls(config),
        *check_addresses(config),
        *check_pgp(config),
        *check_files(config, files),
    ]


def read_text(path):
    """Return the file's text, or None if it is too large, unreadable, or not UTF-8."""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def check_project(directory):
    """Check one projects/<name>/ directory. Return (problems, summary line).

    The summary line is None when there are problems. This runs on pull requests from anyone, so it
    never reads through a symbolic link.
    """
    name, config_file = directory.name, directory / "project.yaml"
    if not NAME.fullmatch(name):
        return ["the directory name must be a-z 0-9 . _ - (starting with a letter or digit, at most 63)"], None
    if directory.is_symlink():
        return [f"symbolic links are not accepted (projects/{name} is one)"], None
    if config_file.is_symlink():
        return [f"symbolic links are not accepted (projects/{name}/project.yaml is one)"], None
    if not config_file.is_file():
        return [f"projects/{name}/project.yaml is missing"], None

    beside = sorted(path for path in directory.iterdir() if path != config_file)
    irregular = [path.name for path in beside if not stat.S_ISREG(path.lstat().st_mode)]
    if irregular:
        return [f"symbolic links (and anything else that is not a regular file) are not accepted: {irregular}"], None

    if config_file.stat().st_size > MAX_CONFIG_BYTES:
        return [f"project.yaml is larger than {MAX_CONFIG_BYTES // 1024} KiB"], None
    try:
        config = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, UnicodeDecodeError, RecursionError) as error:
        return [f"project.yaml does not parse: {type(error).__name__}: {str(error)[:300]}"], None

    files = {path.name: read_text(path) if path.name in FILE_KEYS else None for path in beside}
    problems = check_config(config, files)
    if problems:
        return problems, None

    where = "beside project.yaml" if "Dockerfile" in files else f"in the repository at {config['dockerfile']}"
    return [], f"{name:<24} {config['repo']}  -> {config['primary_contact']}  (Dockerfile: {where})"


def printable(text):
    """Text for the terminal or a CI log: control characters (escape sequences, BEL, newlines) from a project.yaml or a
    directory name are shown as \\xNN, never sent raw."""
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", lambda m: f"\\x{ord(m.group()):02x}", text)


def main():
    # Parsed only so that --help works; there are no options.
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()

    directories = sorted(path for path in PROJECTS.glob("*") if path.is_dir() or path.is_symlink())
    problems, summaries = [], []
    for directory in directories:
        found, summary = check_project(directory)
        problems += [printable(f"{directory.name}: {problem}") for problem in found]
        summaries.append(summary)

    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print(f"ok: {len(summaries)} project(s)")
    for summary in summaries:
        print(f"  {printable(summary)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
