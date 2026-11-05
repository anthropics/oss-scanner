#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Say whether a pull request that turns on GitHub security advisories has `oss-scanner` confirmed as a trusted
reporter, as one line of JSON on standard output.

    GITHUB_TOKEN=... .github/scripts/trusted_reporter.py --repo anthropics/oss-scanner --pr 123

Run by .github/workflows/trusted-reporter.yaml, or by hand to see what it would say. Prints nothing for a pull
request that is not open, or that turns on no GitHub security advisories and was never asked about them.

Nobody but a repository's admins can read its list of trusted reporters, so this goes by what they say in a comment.
Like triage.py, it reads the pull request as data through the GitHub API with a read-only token.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import tempfile

import triage
import validate  # triage.py puts tools/ on the path
from triage import ApiError, GitHub, code

# The comment to update is the one by this account that starts with this line.
COMMENTER = "github-actions[bot]"
MARKER = "<!-- oss-scanner-trusted-reporter -->"
TRUSTED_REPORTER_DOCS = (
    "https://docs.github.com/en/code-security/security-advisories/working-with-repository-security-advisories/"
    "configuring-private-vulnerability-reporting-for-a-repository"
)
ROOT = pathlib.Path(__file__).resolve().parents[2]
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"
OWNER = re.compile(r"@([A-Za-z0-9-]+)(?![A-Za-z0-9/-])")
PAGE = 100
MAX_CHANGED_FILES = 3000  # GitHub lists no more
MAX_DESCRIPTION = 140  # of a commit status

OPENER_PHRASE = "I have added oss-scanner as a trusted reporter on"
# Each is matched against one whole line. The repository is part of it, so that a confirmation for one repository
# does not count for another that project.yaml is changed to name later.
OPENER_LINE = re.compile(
    r"(?:✅\s*)?(?:i|we)(?: have|['’]ve)? added @?oss-scanner as a trusted reporter (?:on|to|for|in) (\S+)",
    re.IGNORECASE,
)
# Different words, so that a reviewer who shows someone what to reply does not confirm by accident.
REVIEWER_LINE = re.compile(r"confirmed: @?oss-scanner is a trusted reporter on (\S+)", re.IGNORECASE)


class Unreadable(Exception):
    """What the pull request does cannot be told, so it must not pass."""


def pages(gh: GitHub, path: str):
    """Every item of a list."""
    page = 1
    while True:
        items = gh.get(path, per_page=PAGE, page=page)
        yield from items
        if len(items) < PAGE:
            return
        page += 1


def target(repo: object) -> str | None:
    """How comments name a project's repository: owner/name on GitHub, the URL elsewhere."""
    if not validate.is_https_url(repo):
        return None
    match = triage.GITHUB_REPO.fullmatch(repo)
    return f"{match[1]}/{match[2]}" if match else repo.split("#", 1)[0]


def opted_in(config: dict) -> bool:
    """Does this project.yaml send reports to GitHub? A setting we do not recognise counts as yes."""
    output_format = config.get("output_format")
    advisories = output_format.get("github_security_advisory") if isinstance(output_format, dict) else None
    severity = advisories.get("min_severity") if isinstance(advisories, dict) else advisories
    return advisories is not None and severity != "none" and config.get("disabled") is not True


def newly_opted_in(gh: GitHub, repo: str, pull: dict) -> list[str]:
    """The repositories that this pull request makes send reports to GitHub. Not those that already do on the
    default branch: a pull request that updates a Dockerfile is not held up."""
    if pull["changed_files"] > MAX_CHANGED_FILES:
        raise Unreadable(f"This pull request changes more than {MAX_CHANGED_FILES:,} files.")
    files = pages(gh, f"repos/{repo}/pulls/{pull['number']}/files")
    paths = [path for file in files for path in (file["filename"], file.get("previous_filename")) if path]
    targets = {}
    for name in triage.split_paths(paths)[0]:
        if not validate.NAME.fullmatch(name):
            raise Unreadable("This pull request has a projects/ directory whose name is not accepted.")
        with tempfile.TemporaryDirectory() as scratch:
            directory = pathlib.Path(scratch) / name
            if not triage.fetch_project(gh, repo, pull["head"]["sha"], name, directory):
                continue  # withdrawn
            config = triage.read_config(directory)
        repository = target(config.get("repo"))
        if repository is None:
            raise Unreadable(f"projects/{name}/project.yaml cannot be read, or names no repository.")
        before = triage.read_config(ROOT / "projects" / name)
        already = opted_in(before) and (target(before.get("repo")) or "").lower() == repository.lower()
        if opted_in(config) and not already:
            targets[repository.lower()] = repository
    return sorted(targets.values(), key=str.lower)


def reporting_is_off(gh: GitHub, repository: str) -> bool:
    """Is private vulnerability reporting known to be off? Then there can be no trusted reporter yet."""
    if "://" in repository:
        return False
    try:
        answer = gh.find(f"repos/{repository}/private-vulnerability-reporting")
    except ApiError:
        return False
    return isinstance(answer, dict) and answer.get("enabled") is False


def confirmed_by(comment: dict, opener: str, reviewers: set[str]) -> set[str]:
    """The repositories, in lower case, that a comment confirms."""
    login = ((comment.get("user") or {}).get("login") or "").lower()
    patterns = [OPENER_LINE] * (login == opener.lower()) + [REVIEWER_LINE] * (login in reviewers)
    found = set()
    for line in (comment.get("body") or "").splitlines() if patterns else ():
        # As people copy it: with its code marks, in bold, as a list item, or ended like a sentence. Not quoted (">").
        line = line.replace("`", "").replace("*", "").strip().lstrip("- ").rstrip(".! ")
        for pattern in patterns:
            if match := pattern.fullmatch(line):
                named = re.sub(r"^https://(?:www\.)?github\.com/", "", match[1].lower())
                found.add(named.removesuffix(".git").rstrip("/") if "://" not in named else named)
    return found


def confirmations(comments: list[dict], opener: str, reviewers: set[str]) -> dict[str, dict]:
    """The first comment that confirms each repository (in lower case)."""
    first = {}
    for comment in comments:
        for repository in confirmed_by(comment, opener, reviewers):
            first.setdefault(repository, comment)
    return first


def reviewer_logins() -> set[str]:
    """The people in CODEOWNERS, who may confirm what they were told by email."""
    lines = CODEOWNERS.read_text(encoding="utf-8").splitlines()
    return {login.lower() for line in lines for login in OWNER.findall(line.split("#", 1)[0])}


def request_text(opener: str, waiting: list[str], off: list[str], confirmed: dict[str, dict]) -> str:
    """The comment that asks whoever opened the pull request to confirm the repositories still waiting."""
    # A bot's login has brackets, and is not worth a mention anyway.
    greeting = f"@{opener}, this" if triage.LOGIN.fullmatch(opener) else "This"
    shown = ", ".join(code(repository) for repository in waiting)
    off_note = "".join(
        f"\n⚠️ Private vulnerability reporting is off on {code(repository)}. Please turn it on first: until then "
        "GitHub accepts no reports, and this check cannot pass. After turning it on, comment here to run the check "
        "again.\n"
        for repository in off
    )
    replies = "\n".join(f"{OPENER_PHRASE} {repository}" for repository in waiting)
    done = confirmed_list(confirmed)
    return (
        f"{MARKER}\n### Trusted reporter: confirmation needed before we merge\n\n"
        f"{greeting} pull request turns on GitHub security advisories for {shown}. Our reports come from the account "
        "[`oss-scanner`](https://github.com/oss-scanner), which Anthropic operates. GitHub limits how many it can "
        f"send you unless it is a trusted reporter.\n{off_note}\n"
        "1. Please add `oss-scanner` as a trusted reporter, under Settings → Advanced Security → Private "
        f"vulnerability reporting ([GitHub's instructions]({TRUSTED_REPORTER_DOCS})).\n"
        "2. Then confirm it by commenting here with exactly this:\n\n"
        f"```\n{replies}\n```\n\n"
        + (f"{done}\n" if done else "") +
        "<sub>The `trusted-reporter` check passes once you have. It goes away if you take "
        "`github_security_advisory` out of `project.yaml`, to get reports by email only.</sub>\n"
    )


def confirmed_list(confirmed: dict[str, dict]) -> str:
    return "".join(
        f"- ✅ {code(comment['user']['login'])} [confirmed]({comment['html_url']}) {code(repository)}.\n"
        for repository, comment in confirmed.items()
    )


def decide(gh: GitHub, repo: str, pull: dict) -> dict | None:
    """The commit status, and the text of our comment (None: leave it as it is). With the state None: no status, and
    the comment is to be deleted. None: there is nothing to do."""
    try:
        targets = newly_opted_in(gh, repo, pull)
    except Unreadable as problem:
        return {"state": "failure", "description": str(problem), "body": None, "comment": None}
    comments = list(pages(gh, f"repos/{repo}/issues/{pull['number']}/comments"))
    ours = next((c for c in comments if (c.get("user") or {}).get("login") == COMMENTER
                 and (c.get("body") or "").startswith(MARKER)), None)
    verdict = {"comment": ours["id"] if ours else None}

    if not targets:
        return {**verdict, "state": None, "description": "", "body": None} if ours else None

    opener = pull["user"]["login"]
    first = confirmations(comments, opener, reviewer_logins())
    off = [repository for repository in targets if reporting_is_off(gh, repository)]
    confirmed = {repository: first[repository.lower()] for repository in targets
                 if repository.lower() in first and repository not in off}
    waiting = [repository for repository in targets if repository not in confirmed]
    if waiting:
        problem = "Private vulnerability reporting is off" if off else "Waiting for confirmation"
        listed = ", ".join(off or waiting)
        verdict |= {"state": "failure", "description": f"{problem}: {listed}"}
        body = request_text(opener, waiting, off, confirmed)
    else:
        who = ", ".join(sorted({comment["user"]["login"] for comment in confirmed.values()}))
        verdict |= {"state": "success", "description": f"Confirmed by {who}"}
        body = f"{MARKER}\n### Trusted reporter: confirmed\n\n{confirmed_list(confirmed)}\nThank you!\n"

    # GitHub keeps a body without its trailing newline, and may return its lines with \r.
    unchanged = ours and body and ours["body"].replace("\r", "").strip() == body.strip()
    return {**verdict, "body": None if unchanged else body}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True, help="the repository the pull request is in, as owner/name")
    parser.add_argument("--pr", required=True, type=int, help="the pull request's number")
    options = parser.parse_args()
    gh = GitHub(os.environ.get("GITHUB_TOKEN"))
    pull = gh.get(f"repos/{options.repo}/pulls/{options.pr}")
    verdict = decide(gh, options.repo, pull) if pull["state"] == "open" else None
    if verdict:
        verdict["description"] = verdict["description"][:MAX_DESCRIPTION]
        print(json.dumps({"sha": pull["head"]["sha"], **verdict}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
