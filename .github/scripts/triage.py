#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Write the triage comment for an enrolment pull request, as Markdown on standard output.

    GITHUB_TOKEN=... .github/scripts/triage.py --repo anthropics/oss-scanner --pr 123

Run by .github/workflows/triage.yaml, and by hand to see what it would say. Prints nothing when the pull request
does not touch projects/. The comment helps a reviewer; it decides nothing, and every row can be wrong.

The pull request is read as data through the GitHub API. Nothing from it is checked out or executed, the only host
contacted is api.github.com, and a read-only token is enough. Text from the pull request and from the enrolled
repository reaches the comment only through code(), so it cannot inject Markdown.

Requires PyYAML, as tools/validate.py does.
"""
from __future__ import annotations

import argparse
import http.client
import json
import math
import os
import pathlib
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
import validate  # noqa: E402  (tools/validate.py: the enrolment rules, and PyYAML)

API = "https://api.github.com"
MAX_RATE_LIMIT_WAIT = 65  # seconds
RAW = "application/vnd.github.raw"
# The workflow finds the comment to update by this first line.
MARKER = "<!-- oss-scanner-triage -->"
CRITERIA = "https://red.anthropic.com/oss-scanner"

OK, WARN, FAIL, INFO = "✅", "⚠️", "❌", "ℹ️"
NOW = datetime.now(timezone.utc)
YEAR_AGO = NOW - timedelta(days=365)
# "Established", "active" and "critical" have no published numbers. These only decide when a row gets a warning.
ESTABLISHED_MONTHS = 12
STALE_MONTHS = 12
# A project below both is warned about. Either alone is not: a busy young project scores well with few stars, and
# a quiet, widely used one has the stars but a middling score.
FEW_STARS = 100
LOW_CRITICALITY = 0.4

GITHUB_REPO = re.compile(r"https://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?(?:#(.+))?")
LOGIN = re.compile(r"[A-Za-z0-9-]+")
# GitHub's author_association values that mark a maintainer rather than a contributor, and how the comment words them.
ASSOCIATIONS = {
    "OWNER": "owns the repository",
    "MEMBER": "member of the owning organisation",
    "COLLABORATOR": "collaborator on the repository",
}
# Who merged the repository's latest pull requests. Merging takes write access, whatever GitHub shows of the roles.
RECENT_MERGES = """query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) {
  pullRequests(states: MERGED, first: 100, orderBy: {field: UPDATED_AT, direction: DESC}) {
    nodes { mergedBy { login } } } } }"""
CHECKBOX = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.+)$", re.MULTILINE)
# The files we read from a project's directory, and the size above which validate.py refuses each.
PROJECT_FILES = {"project.yaml": validate.MAX_CONFIG_BYTES}
PROJECT_FILES.update(dict.fromkeys(validate.FILE_KEYS, validate.MAX_FILE_BYTES))

# SPDX ids, as GitHub reports them, of the licenses we accept without a second look. BSL-1.0 is the Boost license;
# the Business Source License is BUSL-1.1, which GitHub does not recognise and reports as "Other".
COMMON_LICENSES = {
    "0BSD", "AGPL-3.0", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "BSL-1.0", "EPL-2.0", "GPL-2.0", "GPL-3.0",
    "ISC", "LGPL-2.1", "LGPL-3.0", "MIT", "MIT-0", "MPL-2.0", "PostgreSQL", "Unlicense", "Zlib",
}  # fmt: skip
# Phrases that mark a source-available license, looked for in the license text when GitHub cannot name it.
SOURCE_AVAILABLE = (
    "Business Source License", "Server Side Public License", "Elastic License", "Commons Clause",
    "Functional Source License", "PolyForm", "Sustainable Use License", "Fair Source License",
    "Confluent Community License", "Redis Source Available License", "Attribution-NonCommercial",
)  # fmt: skip

# The OpenSSF criticality score (Rob Pike's formula): signal -> (weight, threshold).
CRITICALITY_SOURCE = "https://github.com/ossf/criticality_score"
CRITICALITY_SIGNALS = {
    "created_since": (1, 120),
    "updated_since": (-1, 120),
    "contributor_count": (2, 5000),
    "org_count": (1, 10),
    "commit_frequency": (1, 1000),
    "recent_releases_count": (0.5, 26),
    "closed_issues_count": (0.5, 5000),
    "updated_issues_count": (0.5, 5000),
    "comment_frequency": (1, 15),
    "dependents_count": (2, 500000),
}
TOP_CONTRIBUTORS = 15
ISSUE_WINDOW_DAYS = 90


class ApiError(Exception):
    """A request to the GitHub API failed. `status` is the HTTP status, or 0 if there was no response."""

    def __init__(self, status: int, path: str):
        super().__init__(f"GitHub API {status or 'unreachable'} for {path}")
        self.status = status


def retry_delay(error: urllib.error.HTTPError) -> float | None:
    """Seconds to wait before asking once more, or None if the answer will not change."""
    if error.code >= 500:
        return 2
    if error.code not in (403, 429):
        return None
    # Out of requests. The search API allows 30 a minute, so that wait is short; the hourly limit is not waited for.
    if error.headers.get("Retry-After"):
        delay = float(error.headers["Retry-After"])
    elif error.headers.get("X-RateLimit-Remaining") == "0":
        delay = float(error.headers.get("X-RateLimit-Reset", 0)) - time.time() + 1
    else:
        return None
    return max(delay, 1) if delay <= MAX_RATE_LIMIT_WAIT else None


class GitHub:
    """A read-only client for api.github.com. Callers quote every path segment that comes from a pull request."""

    def __init__(self, token: str | None):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "oss-scanner-triage",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def fetch(self, path: str, accept: str | None = None, body: dict | None = None, **params) -> tuple[bytes, str]:
        """GET a path, or POST `body` to it. Return the response's body and its Link header."""
        query = urlencode({key: value for key, value in params.items() if value is not None})
        headers = {**self.headers, "Accept": accept} if accept else self.headers
        data = json.dumps(body).encode() if body else None
        request = urllib.request.Request(f"{API}/{path}{'?' + query if query else ''}", data=data, headers=headers)
        for last_try in (False, True):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return response.read(), response.headers.get("Link") or ""
            except urllib.error.HTTPError as error:
                delay = retry_delay(error)
                if last_try or delay is None:
                    raise ApiError(error.code, path) from None
            except (OSError, http.client.HTTPException):
                delay = 2  # no usable response: a dropped or cut-off connection
                if last_try:
                    raise ApiError(0, path) from None
            time.sleep(delay)

    def get(self, path: str, **params):
        """GET a path and parse its JSON."""
        return json.loads(self.fetch(path, **params)[0])

    def graphql(self, query: str, **variables) -> dict:
        """Run a GraphQL query, for what the REST API cannot say in one request."""
        answer = json.loads(self.fetch("graphql", body={"query": query, "variables": variables})[0])
        if answer.get("errors") or not answer.get("data"):
            raise ApiError(0, "graphql")
        return answer["data"]

    def find(self, path: str, **params):
        """Like get(), but None when the path does not exist."""
        try:
            return self.get(path, **params)
        except ApiError as error:
            if error.status == 404:
                return None
            raise

    def count(self, path: str, **params) -> int:
        """How many items a list has: asked for one per page, the number of the last page is the count."""
        try:
            body, link = self.fetch(path, per_page=1, **params)
        except ApiError as error:
            if error.status != 404:
                raise
            return 0  # e.g. the comments of a repository with issues turned off
        last = re.search(r'[?&]page=(\d+)[^>]*>; rel="last"', link)
        if not last and 'rel="next"' in link:
            raise ApiError(0, f"{path} (GitHub gave no count)")
        return int(last.group(1)) if last else len(json.loads(body))

    def total(self, kind: str, query: str) -> int:
        """How many results a search for issues or commits has."""
        return self.get(f"search/{kind}", q=query, per_page=1)["total_count"]


@dataclass
class Row:
    mark: str
    check: str
    result: str


def code(text: object, limit: int = 120) -> str:
    """Untrusted text as a Markdown code span that cannot end the span, the table cell or the comment."""
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", str(text)).replace("`", "'").replace("|", "¦")
    if len(text) > limit:
        text = text[:limit] + "…"
    return f"`{text or ' '}`"


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def iso(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def months_since(when: datetime) -> int:
    return (NOW - when).days // 30


def ago(when: datetime) -> str:
    days = (NOW - when).days
    if days < 2:
        return "today" if days < 1 else "yesterday"
    if days < 60:
        return f"{days} days ago"
    if days < 730:
        return f"{days // 30} months ago"
    return f"{days // 365} years ago"


# --- the pull request ---


def changed_paths(gh: GitHub, repo: str, number: int) -> list[str]:
    """Every path the pull request touches (the first 300; an enrolment has three at most)."""
    paths = []
    for page in (1, 2, 3):
        files = gh.get(f"repos/{repo}/pulls/{number}/files", per_page=100, page=page)
        paths += [name for file in files for name in (file["filename"], file.get("previous_filename")) if name]
        if len(files) < 100:
            break
    return paths


def split_paths(paths: list[str]) -> tuple[list[str], list[str]]:
    """Return the names of the projects touched, and the paths that are not directly inside a projects/<name>/."""
    names, outside = set(), []
    for path in paths:
        parts = path.split("/")
        if len(parts) == 3 and parts[0] == "projects":
            names.add(parts[1])
        else:
            outside.append(path)
    return sorted(names), outside


def fetch_project(gh: GitHub, repo: str, sha: str, name: str, directory: pathlib.Path) -> bool:
    """Recreate projects/<name>/ as it is at commit `sha` in `directory`, so tools/validate.py can check it like a
    checkout. Return False if the pull request has no such directory (it withdraws the project)."""
    listing = f"repos/{repo}/contents/projects/{quote(name, safe='')}"
    entries = gh.find(listing, ref=sha)
    if not isinstance(entries, list):
        return False
    directory.mkdir()
    for entry in entries:
        target, limit = directory / entry["name"], PROJECT_FILES.get(entry["name"])
        if target.parent != directory:
            continue
        if entry["type"] in ("dir", "submodule"):
            target.mkdir()
        elif entry["type"] != "file":
            target.symlink_to("symlink")  # validate.py rejects whatever is not a regular file
        elif limit is None:
            target.touch()  # not a file we accept: only its name matters
        elif entry["size"] > limit:
            target.write_bytes(bytes(limit + 1))  # too large to accept, so not worth downloading
        else:
            target.write_bytes(gh.fetch(f"{listing}/{quote(entry['name'], safe='')}", accept=RAW, ref=sha)[0])
    return True


def read_config(directory: pathlib.Path) -> dict:
    """The parsed project.yaml, or {} if there is none we can use."""
    try:
        config = validate.yaml.safe_load((directory / "project.yaml").read_text(encoding="utf-8"))
    except (OSError, validate.yaml.YAMLError, UnicodeDecodeError, RecursionError):
        return {}
    return config if isinstance(config, dict) else {}


def top_contributors(gh: GitHub, slug: str, count: int) -> list[dict]:
    """The repository's top contributors. Empty for the few histories so long that GitHub refuses to list them."""
    try:
        return gh.get(f"repos/{slug}/contributors", per_page=count)
    except ApiError as error:
        if error.status != 403:
            raise
        return []


# --- one function per row of the comment ---


def scope_row(names: list[str], outside: list[str]) -> Row:
    problems = []
    if len(names) > 1:
        shown = ", ".join(code(name) for name in names[:5])
        problems.append(f"touches {len(names)} projects ({shown}); one per pull request")
    if outside:
        shown = ", ".join(code(path) for path in outside[:5]) + (" …" if len(outside) > 5 else "")
        problems.append(f"changes files outside `projects/<name>/`: {shown}")
    if problems:
        return Row(FAIL, "Pull request scope", "; ".join(problems))
    return Row(OK, "Pull request scope", "only this project's directory")


def validate_row(problems: list[str]) -> Row:
    if problems:
        return Row(FAIL, "`tools/validate.py`", "<br>".join(code(problem, 300) for problem in problems[:10]))
    return Row(OK, "`tools/validate.py`", "passes")


def checklist_row(body: str) -> Row:
    boxes = CHECKBOX.findall(body)
    unticked = [text for mark, text in boxes if mark == " "]
    if not boxes:
        return Row(WARN, "Checklist", "the pull request template's checklist is missing from the description")
    if unticked:
        shown = "; ".join(code(text, 80) for text in unticked)
        return Row(WARN, "Checklist", f"{len(unticked)} of {len(boxes)} not ticked: {shown}")
    return Row(OK, "Checklist", f"all {len(boxes)} ticked")


def popularity_row(meta: dict) -> Row:
    return Row(INFO, "Stars / forks", f"{meta['stargazers_count']:,} stars · {meta['forks_count']:,} forks")


def standing_row(meta: dict) -> Row:
    created, pushed = parse_time(meta["created_at"]), parse_time(meta["pushed_at"])
    result = f"created {ago(created)}, last push {ago(pushed)}"
    if meta["archived"]:
        return Row(FAIL, "Repository", f"archived; {result}")
    concerns = []
    if meta["fork"]:
        concerns.append("a fork of another repository")
    if months_since(created) < ESTABLISHED_MONTHS:
        concerns.append(f"under {ESTABLISHED_MONTHS} months old")
    if months_since(pushed) >= STALE_MONTHS:
        concerns.append(f"no push in {STALE_MONTHS} months")
    if concerns:
        return Row(WARN, "Repository", f"{'; '.join(concerns)} ({result})")
    return Row(OK, "Repository", result)


def license_row(gh: GitHub, slug: str, meta: dict) -> Row:
    spdx = (meta.get("license") or {}).get("spdx_id")
    if not spdx:
        return Row(FAIL, "License", "GitHub finds no license file")
    if spdx in COMMON_LICENSES:
        return Row(OK, "License", code(spdx))
    if spdx != "NOASSERTION":
        return Row(WARN, "License", f"{code(spdx)} is not on our list of common open-source licenses; check it")
    text = gh.fetch(f"repos/{slug}/license", accept=RAW)[0].decode("utf-8", "replace")
    found = next((phrase for phrase in SOURCE_AVAILABLE if phrase.lower() in text.lower()), None)
    if found:
        return Row(FAIL, "License", f"the license file mentions “{found}”: source-available, not open source")
    return Row(WARN, "License", "GitHub cannot name the license (custom, or more than one); check it")


def maintainer_row(gh: GitHub, slug: str, meta: dict, login: str) -> Row:
    """Is the person who opened the pull request an active maintainer of the repository? Only public signals: a
    role GitHub shows (owner, member, collaborator) or, failing that, having merged recent pull requests."""
    label = f"Opened by an active maintainer ({code(login)})"
    if not LOGIN.fullmatch(login):
        return Row(WARN, label, "not a user account")

    roles = []
    if meta["owner"]["login"].lower() == login.lower():
        roles.append(ASSOCIATIONS["OWNER"])
    # GitHub labels each issue and pull request with what its author is to the repository.
    latest = gh.get("search/issues", q=f"repo:{slug} author:{login}", per_page=1)["items"]
    association = latest[0]["author_association"] if latest else "NONE"
    if association in ASSOCIATIONS and not roles:
        roles.append(ASSOCIATIONS[association])
    if not roles and meta["owner"]["type"] == "Organization":
        try:
            gh.fetch(f"orgs/{quote(meta['owner']['login'], safe='')}/public_members/{login}")
            roles.append("public member of the owning organisation")
        except ApiError as error:
            if error.status != 404:
                raise

    merged = 0
    if not roles:
        # A private membership of the organisation is invisible to us, but what a maintainer does is not.
        owner, name = slug.split("/")
        merges = gh.graphql(RECENT_MERGES, owner=owner, name=name)["repository"]["pullRequests"]["nodes"]
        merged = sum(1 for pull in merges if ((pull["mergedBy"] or {}).get("login") or "").lower() == login.lower())
        if merged:
            roles.append(f"merged {merged} of the last {len(merges)} pull requests")

    # Listed, not counted: GitHub does not say how many pages a search by author has in a very large repository.
    recent = len(gh.get(f"repos/{slug}/commits", author=login, since=iso(YEAR_AGO), per_page=100))
    commits = f"{recent}+" if recent == 100 else recent
    contributors = [person.get("login", "").lower() for person in top_contributors(gh, slug, 100)]
    if login.lower() in contributors:
        rank = f"#{contributors.index(login.lower()) + 1} contributor"
    else:
        rank = "not in the top 100 contributors" if contributors else "contributor rank unavailable"
    evidence = f"{', '.join(roles) or 'no maintainer role visible'}; {commits} commits in the last 12 months; {rank}"

    if roles and (recent or merged):
        return Row(OK, label, evidence)
    if roles or recent:
        return Row(WARN, label, f"{evidence} — confirm by hand")
    return Row(FAIL, label, evidence)


def scanner_files_row(gh: GitHub, slug: str, ref: str | None, config: dict, beside: set[str]) -> Row:
    """Has the project set up .oss-scanner/ in its own repository, and are the files project.yaml names there?"""
    label = "`.oss-scanner/` in the repository"

    def in_repo(path: object) -> bool:
        if not (isinstance(path, str) and validate.REPO_PATH.fullmatch(path)):
            return False
        return gh.find(f"repos/{slug}/contents/{quote(path)}", ref=ref) is not None

    listing = gh.find(f"repos/{slug}/contents/.oss-scanner", ref=ref)
    names = [entry["name"] for entry in listing] if isinstance(listing, list) else []
    result = f"present ({', '.join(code(name) for name in names[:6])})" if names else "not present"

    threat_model = config.get("threat_model") or ".oss-scanner/threat_model.md"
    if "threat_model.md" not in beside and not in_repo(threat_model):
        result += "; no threat model (optional)"

    if "Dockerfile" in beside:
        return Row(OK if names else INFO, label, f"{result}; the Dockerfile is in this pull request")
    dockerfile = config.get("dockerfile")
    if in_repo(dockerfile):
        return Row(OK, label, f"{result}; Dockerfile at {code(dockerfile)}")
    return Row(FAIL, label, f"{result}; no Dockerfile at {code(dockerfile)}" + (f" on {code(ref)}" if ref else ""))


def criticality_signals(gh: GitHub, slug: str, meta: dict) -> dict[str, float]:
    """Collect the signals of the OpenSSF criticality score the way its reference implementation does."""
    commits = f"repos/{slug}/commits"
    created = parse_time(meta["created_at"])
    try:
        # A repository imported from elsewhere is older than its GitHub creation date: use its first commit.
        first = gh.get(commits, per_page=1, page=gh.count(commits))[0]["commit"]["author"]["date"]
        created = min(created, parse_time(first))
    except (ApiError, IndexError, ValueError):
        pass

    try:
        contributor_count = gh.count(f"repos/{slug}/contributors", anon="true")
    except ApiError as error:
        if error.status != 403:
            raise
        contributor_count = CRITICALITY_SIGNALS["contributor_count"][1]  # GitHub refuses to list very long histories

    organisations = set()
    for person in top_contributors(gh, slug, TOP_CONTRIBUTORS):
        # Bots are contributors too, and some (Copilot) have no user page at all.
        company = (gh.find(f"users/{quote(person['login'], safe='')}") or {}).get("company")
        if company:
            organisations.add(re.sub(r"inc\.|llc|@|\s", "", company.lower()).rstrip(","))

    releases = gh.get(f"repos/{slug}/releases", per_page=100)
    recent_releases = sum(1 for release in releases if parse_time(release["created_at"]) > YEAR_AGO)
    if not releases:
        # A project that tags without publishing releases: assume its tags are spread evenly over its life.
        recent_releases = round(gh.count(f"repos/{slug}/tags") / max((NOW - created).days, 1) * 365)

    window = NOW - timedelta(days=ISSUE_WINDOW_DAYS)
    # GitHub lists comments on issues and pull requests together, so the frequency is taken over both.
    updated_threads = gh.total("issues", f"repo:{slug} updated:>={window:%Y-%m-%d}")
    comments = gh.count(f"repos/{slug}/issues/comments", since=iso(window))

    return {
        "created_since": months_since(created),
        "updated_since": months_since(parse_time(meta["pushed_at"])),
        "contributor_count": contributor_count,
        "org_count": len(organisations),
        "commit_frequency": round(gh.count(commits, since=iso(YEAR_AGO)) / 52, 1),
        "recent_releases_count": recent_releases,
        "closed_issues_count": gh.total("issues", f"repo:{slug} is:issue is:closed updated:>={window:%Y-%m-%d}"),
        "updated_issues_count": gh.total("issues", f"repo:{slug} is:issue updated:>={window:%Y-%m-%d}"),
        "comment_frequency": round(comments / updated_threads, 1) if updated_threads else 0,
        # Mentions of owner/repo in commit messages anywhere on GitHub: a dependency count that works for any language.
        "dependents_count": gh.total("commits", f'"{slug}"'),
    }


def criticality_score(signals: dict[str, float]) -> float:
    """Rob Pike's formula: each signal on a log scale up to its threshold, averaged by weight. Between 0 and 1."""
    total = sum(
        weight * math.log(1 + signals[name]) / math.log(1 + max(signals[name], threshold))
        for name, (weight, threshold) in CRITICALITY_SIGNALS.items()
    )
    return round(total / sum(weight for weight, _ in CRITICALITY_SIGNALS.values()), 5)


def criticality_row(gh: GitHub, slug: str, meta: dict) -> Row:
    signals = criticality_signals(gh, slug, meta)
    score = criticality_score(signals)
    details = ", ".join(f"{name} {value:,}" for name, value in signals.items())
    result = f"**{score:.2f}** on the [OpenSSF]({CRITICALITY_SOURCE}) scale of 0 to 1"
    little_reach = meta["stargazers_count"] < FEW_STARS and score < LOW_CRITICALITY
    if little_reach:
        result += f" — below {LOW_CRITICALITY}, and under {FEW_STARS} stars: little sign of the reach we look for"
    return Row(WARN if little_reach else INFO, "Criticality score", f"{result}<br><sub>{details}</sub>")


# --- putting the comment together ---


def attempt(check: str, row, *arguments) -> Row:
    """Run one row's function. A row that cannot be worked out says so and does not cost us the others."""
    try:
        return row(*arguments)
    except ApiError as error:
        return Row(WARN, check, f"could not be checked ({error})")


def repository_rows(gh: GitHub, config: dict, beside: set[str], login: str) -> tuple[str, list[Row]]:
    """Return a Markdown description of the repository being enrolled, and the rows about it."""
    repo = config.get("repo")
    match = GITHUB_REPO.fullmatch(repo) if isinstance(repo, str) else None
    if not match:
        note = "not on github.com: stars, maintainer, license and criticality need a look by hand"
        if not repo:
            return "unknown", [Row(WARN, "Repository", "no project.yaml that names one")]
        return code(repo), [Row(WARN, "Repository", note)]

    owner, name, ref = match.groups()
    try:
        meta = gh.find(f"repos/{quote(owner, safe='')}/{quote(name, safe='')}")
    except ApiError as error:
        return code(repo), [Row(WARN, "Repository", f"could not be checked ({error})")]
    if meta is None:
        return code(repo), [Row(FAIL, "Repository", "not found on GitHub, or not public")]

    slug = meta["full_name"]  # from GitHub: the canonical name, also after a rename
    return f"[{slug}]({meta['html_url']})" + (f" at {code(ref)}" if ref else ""), [
        standing_row(meta),
        popularity_row(meta),
        attempt("Criticality score", criticality_row, gh, slug, meta),
        attempt("License", license_row, gh, slug, meta),
        attempt("Opened by an active maintainer", maintainer_row, gh, slug, meta, login),
        attempt("`.oss-scanner/` in the repository", scanner_files_row, gh, slug, ref, config, beside),
    ]


def triage(gh: GitHub, repo: str, number: int) -> str:
    """Return the comment for a pull request, or "" if it does not touch projects/."""
    pull = gh.get(f"repos/{repo}/pulls/{number}")
    names, outside = split_paths(changed_paths(gh, repo, number))
    if not names:
        return ""
    name, login = names[0], pull["user"]["login"]
    heading = f"{MARKER}\n### Enrolment triage: {code('projects/' + name)}\n\n"

    with tempfile.TemporaryDirectory() as scratch:
        directory = pathlib.Path(scratch) / name
        # A name validate.py would refuse is not fetched; check_project() reports it without reading the directory.
        if validate.NAME.fullmatch(name) and not fetch_project(gh, repo, pull["head"]["sha"], name, directory):
            return f"{heading}This pull request removes the project's directory: a withdrawal, nothing to triage.\n"
        problems, _ = validate.check_project(directory)
        config = read_config(directory)
        beside = {path.name for path in directory.glob("*")}

    described, about_repository = repository_rows(gh, config, beside, login)
    rows = [
        *about_repository,
        scope_row(names, outside),
        validate_row(problems),
        checklist_row(pull.get("body") or ""),
    ]
    table = "\n".join(f"| {row.mark} | {row.check} | {row.result} |" for row in rows)
    return (
        f"{heading}Repository: {described} · opened by {code(login)}\n\n"
        f"| | Check | Result |\n|:-:|---|---|\n{table}\n\n"
        f"<sub>Generated from public GitHub data to help reviewers. It is not a decision: enrolment is decided case "
        f"by case against the [criteria]({CRITERIA}), and a maintainer is always confirmed by hand.</sub>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True, help="the repository the pull request is in, as owner/name")
    parser.add_argument("--pr", required=True, type=int, help="the pull request's number")
    options = parser.parse_args()
    sys.stdout.write(triage(GitHub(os.environ.get("GITHUB_TOKEN")), options.repo, options.pr))
    return 0


if __name__ == "__main__":
    sys.exit(main())
