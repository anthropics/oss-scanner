#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Write the triage comment for an enrolment pull request, as Markdown on standard output.

    GITHUB_TOKEN=... .github/scripts/triage.py --repo anthropics/oss-scanner --pr 123

Run by .github/workflows/triage.yaml, or by hand to see what it would say. Prints nothing when the pull request
does not touch projects/.

The pull request is read as data through the GitHub API: nothing from it is checked out or executed, the only host
contacted is api.github.com, and a read-only token is enough. Text from the pull request or the enrolled repository
reaches the comment only through code(), so it cannot inject Markdown.

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
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

# tools/validate.py holds the enrolment rules (and imports PyYAML).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
import validate

API = "https://api.github.com"
RAW = "application/vnd.github.raw"
MAX_RATE_LIMIT_WAIT = 65  # seconds
# No answer we need is larger. A file we only search (a license, a security policy) is read up to the smaller limit.
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_TEXT_BYTES = 256 * 1024
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
# These two run on text anyone can write (a description, a SECURITY.md), so nothing in them is unbounded or
# crosses a line: a long run of one character must not make them slow.
CHECKBOX = re.compile(r"^[ \t]*[-*][ \t]+\[([ xX])\][ \t]+(.+)$", re.MULTILINE)
EMAIL = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){1,8}")
# A GitHub repository as OSS-Fuzz's project.yaml files name it in main_repo: any scheme, often with .git.
MAIN_REPO = re.compile(r"(?:\w+://|git@)?(?:www\.)?github\.com[/:]([^/\s]+/[^/\s#]+?)(?:\.git)?/?")
# Where GitHub looks for a repository's security policy.
SECURITY_POLICY_PATHS = ("SECURITY.md", ".github/SECURITY.md", "docs/SECURITY.md")
# The files we read from a project's directory, and the size above which validate.py refuses each.
PROJECT_FILES = dict.fromkeys(validate.FILE_KEYS, validate.MAX_FILE_BYTES)
PROJECT_FILES["project.yaml"] = validate.MAX_CONFIG_BYTES

# GitHub's author_association values that mark a maintainer rather than a contributor, and how the comment words them.
ASSOCIATIONS = {
    "OWNER": "owns the repository",
    "MEMBER": "member of the owning organisation",
    "COLLABORATOR": "collaborator on the repository",
}
# Who merged the repository's latest pull requests.
RECENT_MERGES = """query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) {
  pullRequests(states: MERGED, first: 100, orderBy: {field: UPDATED_AT, direction: DESC}) {
    nodes { mergedBy { login } } } } }"""

# SPDX ids, as GitHub reports them, of the licenses we accept without a second look. BSL-1.0 is the Boost license;
# the Business Source License is BUSL-1.1, which GitHub does not recognise and reports as "Other".
COMMON_LICENSES = {
    "0BSD", "AGPL-3.0", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "BSL-1.0", "EPL-2.0", "GPL-2.0", "GPL-3.0",
    "ISC", "LGPL-2.1", "LGPL-3.0", "MIT", "MIT-0", "MPL-2.0", "PostgreSQL", "Unlicense", "Zlib",
}
# Names of source-available licenses, looked for in the license text when GitHub cannot name it.
SOURCE_AVAILABLE = (
    "Business Source License", "Server Side Public License", "Elastic License", "Commons Clause",
    "Functional Source License", "PolyForm", "Sustainable Use License", "Fair Source License",
    "Confluent Community License", "Redis Source Available License", "Attribution-NonCommercial",
    "Innovation-Enabling Source Code License",
)
# Wording of a repository that is open source only in part, such as one with an enterprise directory.
PARTLY_OPEN = ("Enterprise License", "proprietary license", "commercial license")

CRITICALITY_SOURCE = "https://github.com/ossf/criticality_score"
# The signals of the OpenSSF criticality score (Rob Pike's formula), each with its (weight, threshold).
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
# The company each of these accounts gives on its profile. One request, where the REST API takes one per account:
# the workflow's token is allowed 1,000 requests an hour.
COMPANIES = "query($ids: [ID!]!) { nodes(ids: $ids) { ... on User { company } } }"
ISSUE_WINDOW_DAYS = 90


class ApiError(Exception):
    """A request to the GitHub API failed. `status` is the HTTP status, or 0 if there was no usable response."""

    def __init__(self, status: int, path: str, problem: str = ""):
        super().__init__(f"GitHub API: {problem or status or 'no response'} for {path}")
        self.status = status


def retry_delay(error: urllib.error.HTTPError) -> float | None:
    """Seconds to wait before asking once more, or None if the answer will not change."""
    if error.code >= 500:
        return 2
    if error.code not in (403, 429):
        return None
    # Out of requests, which GitHub says in one of two ways. The search API allows 30 a minute, so that wait is
    # short; the hourly limit is not waited for.
    if (error.headers.get("Retry-After") or "").isdigit():
        delay = int(error.headers["Retry-After"])
    elif error.headers.get("X-RateLimit-Remaining") == "0":
        delay = float(error.headers.get("X-RateLimit-Reset", 0)) - time.time() + 1
    else:
        return None
    return max(delay, 1) if delay <= MAX_RATE_LIMIT_WAIT else None


class StayOnGitHub(urllib.request.HTTPRedirectHandler):
    """Follow a redirect (a renamed repository) only within the API, so that the token is sent nowhere else."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not newurl.startswith(f"{API}/"):
            return None  # urllib then raises the redirect as an HTTPError
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class GitHub:
    """A client for api.github.com that only reads. Callers quote every path segment that comes from a pull request."""

    opener = urllib.request.build_opener(StayOnGitHub)

    def __init__(self, token: str | None):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "oss-scanner-triage",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def fetch(self, path: str, accept: str | None = None, body: dict | None = None, **params) -> tuple[bytes, str]:
        """GET a path, or POST `body` to it. Return the response's body and its Link header. Of a file asked for
        as text, only the start is read."""
        limit = MAX_TEXT_BYTES if accept == RAW else MAX_RESPONSE_BYTES
        query = urlencode({key: value for key, value in params.items() if value is not None})
        headers = {**self.headers, "Accept": accept} if accept else self.headers
        data = json.dumps(body).encode() if body else None
        request = urllib.request.Request(f"{API}/{path}{'?' + query if query else ''}", data=data, headers=headers)
        for last_try in (False, True):
            try:
                with self.opener.open(request, timeout=30) as response:
                    return response.read(limit), response.headers.get("Link") or ""
            except urllib.error.HTTPError as error:
                delay = retry_delay(error)
                if last_try or delay is None:
                    raise ApiError(error.code, path) from None
            except (OSError, http.client.HTTPException):
                delay = 2  # a dropped or cut-off connection
                if last_try:
                    raise ApiError(0, path) from None
            time.sleep(delay)

    def get(self, path: str, **params):
        """GET a path and parse its JSON. An answer with no body (204) is {}."""
        return json.loads(self.fetch(path, **params)[0] or "{}")

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
            raise ApiError(0, path, "no count")  # GitHub leaves the last page out of some expensive listings
        return int(last.group(1)) if last else len(json.loads(body))

    def total(self, kind: str, query: str) -> int:
        """How many results a search for issues or commits has."""
        return self.get(f"search/{kind}", q=query, per_page=1)["total_count"]

    def text(self, path: str, **params) -> str | None:
        """The text of a file in a repository (its first 256 KiB), or None if it is not there."""
        try:
            return self.fetch(path, accept=RAW, **params)[0].decode("utf-8", "replace")
        except ApiError as error:
            if error.status == 404:
                return None
            raise

    def graphql(self, query: str, **variables) -> dict:
        """Run a GraphQL query, for what the REST API cannot say in one request."""
        answer = json.loads(self.fetch("graphql", body={"query": query, "variables": variables})[0])
        if not answer.get("data"):
            raise ApiError(0, "graphql", "query refused")
        return answer["data"]  # with "errors" beside it when only part could be answered, such as a deleted account


def code(text: object, limit: int = 120) -> str:
    """Untrusted text as a Markdown code span that cannot end the span, the table cell or the comment. A value
    from YAML that is not a string is shown as its type: printing it could be made to take forever."""
    if not isinstance(text, str):
        text = f"<{type(text).__name__}>"
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", text).replace("`", "'").replace("|", "¦")
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


# --- reading the pull request and the repository ---


def changed_paths(gh: GitHub, repo: str, number: int) -> list[str]:
    """The paths the pull request touches, a renamed file under both its names. Only the first 100: scope_row()
    refuses a pull request that changes more."""
    files = gh.get(f"repos/{repo}/pulls/{number}/files", per_page=100)
    return [name for file in files for name in (file["filename"], file.get("previous_filename")) if name]


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
        # The name becomes a path here. Git allows none of these as a name, so this only guards against surprises.
        if "/" in entry["name"] or "\\" in entry["name"] or entry["name"] in (".", ".."):
            continue
        target, limit = directory / entry["name"], PROJECT_FILES.get(entry["name"])
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


# --- the checks: each returns the mark and the text of one row of the comment ---


def scope_row(names: list[str], outside: list[str], changed_files: int) -> tuple[str, str]:
    problems = []
    if len(names) > 1:
        shown = ", ".join(code(name) for name in names[:5])
        problems.append(f"touches {len(names)} projects ({shown}); one per pull request")
    if outside:
        shown = ", ".join(code(path) for path in outside[:5]) + (" …" if len(outside) > 5 else "")
        problems.append(f"changes files outside `projects/<name>/`: {shown}")
    if changed_files > 100:
        problems.append(f"changes {changed_files} files")
    if problems:
        return FAIL, "; ".join(problems)
    return OK, "only this project's directory"


def validate_row(problems: list[str]) -> tuple[str, str]:
    if problems:
        return FAIL, "<br>".join(code(problem, 300) for problem in problems[:10])
    return OK, "passes"


def checklist_row(body: str) -> tuple[str, str]:
    # The template marks the threat model's box as optional: left empty, it is not counted.
    boxes = [(mark, text) for mark, text in CHECKBOX.findall(body) if mark != " " or "optional" not in text]
    unticked = [text for mark, text in boxes if mark == " "]
    if not boxes:
        return WARN, "the pull request template's checklist is missing from the description"
    if unticked:
        shown = "; ".join(code(text, 80) for text in unticked[:5]) + (" …" if len(unticked) > 5 else "")
        return WARN, f"{len(unticked)} of {len(boxes)} not ticked: {shown}"
    return OK, f"all {len(boxes)} ticked"


def standing_row(meta: dict) -> tuple[str, str]:
    created, pushed = parse_time(meta["created_at"]), parse_time(meta["pushed_at"])
    result = f"created {ago(created)}, last push {ago(pushed)}"
    if meta["archived"]:
        return FAIL, f"archived; {result}"
    concerns = []
    if meta["fork"]:
        concerns.append("a fork of another repository")
    if months_since(created) < ESTABLISHED_MONTHS:
        concerns.append(f"under {ESTABLISHED_MONTHS} months old")
    if months_since(pushed) >= STALE_MONTHS:
        concerns.append(f"no push in {STALE_MONTHS} months")
    if concerns:
        return WARN, f"{'; '.join(concerns)} ({result})"
    return OK, result


def popularity_row(meta: dict) -> tuple[str, str]:
    return INFO, f"{meta['stargazers_count']:,} stars · {meta['forks_count']:,} forks"


def license_row(gh: GitHub, slug: str, meta: dict) -> tuple[str, str]:
    spdx = (meta.get("license") or {}).get("spdx_id")
    if not spdx:
        return FAIL, "GitHub finds no license file"
    if spdx in COMMON_LICENSES:
        return OK, code(spdx)
    if spdx != "NOASSERTION":
        return WARN, f"{code(spdx)} is not on our list of common open-source licenses; check it"
    text = gh.text(f"repos/{slug}/license") or ""
    found = next((name for name in SOURCE_AVAILABLE if name.lower() in text.lower()), None)
    if found:
        return FAIL, f"the license file mentions “{found}”, a source-available license"
    found = next((name for name in PARTLY_OPEN if name.lower() in text.lower()), None)
    if found:
        return WARN, f"the license file mentions “{found}”: part of the repository may not be open source"
    # GitHub also fails to name a plain license with a line added, so show the reviewer what the file says.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    says = next((line for line in lines if "licens" in line.lower()), lines[0] if lines else "nothing")
    return WARN, f"GitHub cannot name the license; its file says {code(says, 80)}"


def maintainer_row(gh: GitHub, slug: str, meta: dict, login: str) -> tuple[str, str]:
    """Is the person who opened the pull request an active maintainer of the repository? Only public signals: a
    role GitHub shows (owner, member, collaborator) or, failing that, having merged recent pull requests."""
    if not LOGIN.fullmatch(login):
        return WARN, "not a user account"

    roles = []
    if meta["owner"]["login"].lower() == login.lower():
        roles.append(ASSOCIATIONS["OWNER"])
    else:
        # GitHub labels each issue and pull request with what its author is to the repository.
        authored = gh.get("search/issues", q=f"repo:{slug} author:{login}", per_page=1)["items"]
        if authored and authored[0]["author_association"] in ASSOCIATIONS:
            roles.append(ASSOCIATIONS[authored[0]["author_association"]])
    organisation = quote(meta["owner"]["login"], safe="")
    if not roles and gh.find(f"orgs/{organisation}/public_members/{login}") is not None:
        roles.append("public member of the owning organisation")

    merged = 0
    if not roles:
        # A private member of the organisation shows no role, but merging takes write access.
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
        return OK, evidence
    return (WARN if roles or recent else FAIL), evidence


def security_policy(gh: GitHub, slug: str, owner: str) -> tuple[str, str] | None:
    """Find the security policy that applies to the repository: its own, or else the one its owner keeps for all
    their repositories in <owner>/.github. Return the policy's repository and its text, or None."""
    for repo in (slug, f"{quote(owner, safe='')}/.github"):
        for path in SECURITY_POLICY_PATHS:
            text = gh.text(f"repos/{repo}/contents/{path}")
            if text is not None:
                return repo, text
    return None


def contact_row(gh: GitHub, slug: str, meta: dict, config: dict) -> tuple[str, str]:
    """Does the repository's own security policy name the address that reports would go to?"""
    contact = config.get("primary_contact")
    if not isinstance(contact, str):
        return WARN, "project.yaml names no contact"
    policy = security_policy(gh, slug, meta["owner"]["login"])
    if policy is None:
        return INFO, f"no `SECURITY.md` to check {code(contact)} against"
    repo, text = policy
    where = "`SECURITY.md`" if repo == slug else f"`SECURITY.md` of {code(repo)}"
    # Whole addresses are compared, so that security@example.org is not found inside another address.
    given = sorted({address.lower() for address in EMAIL.findall(text)})
    if contact.lower() in given:
        return OK, f"{code(contact)} is in {where}"
    # Many policies ask for reports through GitHub and give no address at all; that is not a mismatch.
    if not given:
        return INFO, f"{where} gives no email address to check {code(contact)} against"
    shown = ", ".join(code(address) for address in given[:3]) + (" …" if len(given) > 3 else "")
    return WARN, f"{code(contact)} is not in {where}, which gives {shown}"


def oss_fuzz_projects(gh: GitHub, slug: str) -> tuple[dict[str, dict], dict[str, object], bool]:
    """Find the OSS-Fuzz projects that fuzz this repository: each one's name and project.yaml. Also return the
    main_repo of any project named after the repository or its owner that is for some other repository, and whether
    the search worked; if it did not, only projects of those two names are found."""
    owner, name = slug.lower().split("/")
    names, searched = [name, owner], True
    try:
        query = f'"github.com/{slug}" repo:google/oss-fuzz filename:project.yaml'
        hits = gh.get("search/code", q=query, per_page=5)["items"]
        names = [hit["path"].split("/")[1] for hit in hits if hit["path"].count("/") == 2] + names
    except ApiError:
        searched = False

    found, namesakes = {}, {}
    for candidate in dict.fromkeys(names):
        text = gh.text(f"repos/google/oss-fuzz/contents/projects/{quote(candidate, safe='')}/project.yaml")
        try:
            project = validate.yaml.safe_load(text or "")
        except (validate.yaml.YAMLError, RecursionError):
            continue
        # The search matches words, and a name is only a guess: main_repo is what says it is this repository.
        main_repo = project.get("main_repo") if isinstance(project, dict) else None
        match = MAIN_REPO.fullmatch(main_repo.strip()) if isinstance(main_repo, str) else None
        if match and match.group(1).lower() == slug.lower():
            found[candidate] = project
        elif isinstance(project, dict) and candidate in (name, owner):
            namesakes[candidate] = main_repo
    return found, namesakes, searched


def oss_fuzz_row(gh: GitHub, slug: str, config: dict) -> tuple[str, str]:
    """Is the repository in OSS-Fuzz, whose criteria ours follow, and does OSS-Fuzz report to the same address?"""
    projects, namesakes, searched = oss_fuzz_projects(gh, slug)
    if not projects and namesakes:
        others = "; ".join(f"{code(name)} there is for {code(main_repo)}" for name, main_repo in namesakes.items())
        return INFO, f"no OSS-Fuzz project is for this repository, but {others}"
    if not projects:
        return INFO, "not in OSS-Fuzz" if searched else "not in OSS-Fuzz under its own name (the search failed)"
    result = f"in OSS-Fuzz as {', '.join(code(name) for name in projects)}"

    contact = config.get("primary_contact")
    if not isinstance(contact, str):
        return OK, result
    primary, ccs = set(), set()
    for project in projects.values():
        if isinstance(project.get("primary_contact"), str):
            primary.add(project["primary_contact"].lower())
        for key in ("auto_ccs", "vendor_ccs"):
            listed = project.get(key)
            listed = [listed] if isinstance(listed, str) else listed if isinstance(listed, list) else []
            ccs.update(address.lower() for address in listed if isinstance(address, str))
    if contact.lower() in primary:
        return OK, f"{result}, with the same primary contact"
    theirs = ", ".join(code(address) for address in sorted(primary)) or "not given"
    if contact.lower() in ccs:
        return OK, f"{result}, which CCs {code(contact)} (its primary contact is {theirs})"
    return WARN, f"{result}, whose contacts do not include {code(contact)} (its primary contact is {theirs})"


def scanner_files_row(gh: GitHub, slug: str, ref: str | None, config: dict, beside: set[str]) -> tuple[str, str]:
    """Has the project set up .oss-scanner/ in its own repository, and are the files project.yaml names there?"""

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
        return (OK if names else INFO), f"{result}; the Dockerfile is in this pull request"
    dockerfile = config.get("dockerfile")
    if in_repo(dockerfile):
        return OK, f"{result}; Dockerfile at {code(dockerfile)}"
    return FAIL, f"{result}; no Dockerfile at {code(dockerfile)}" + (f" on {code(ref)}" if ref else "")


def criticality_signals(gh: GitHub, slug: str, meta: dict) -> dict[str, float]:
    """Collect the signals of the OpenSSF criticality score, as its reference implementation defines them."""
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
    people = [person["node_id"] for person in top_contributors(gh, slug, TOP_CONTRIBUTORS) if person.get("node_id")]
    # Bots are contributors too: they have no company, and some (Copilot) no profile at all.
    for person in gh.graphql(COMPANIES, ids=people)["nodes"] if people else []:
        company = (person or {}).get("company")
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


def criticality_row(gh: GitHub, slug: str, meta: dict) -> tuple[str, str]:
    signals = criticality_signals(gh, slug, meta)
    score = criticality_score(signals)
    result = f"**{score:.2f}** on the [OpenSSF]({CRITICALITY_SOURCE}) scale of 0 to 1"
    low = meta["stargazers_count"] < FEW_STARS and score < LOW_CRITICALITY
    if low:
        result += f": low, and the project has under {FEW_STARS} stars"
    details = ", ".join(f"{name} {value:,}" for name, value in signals.items())
    return (WARN if low else INFO), f"{result}<details><summary>signals</summary>{details}</details>"


# --- putting the comment together ---


def row(check: str, function, *arguments) -> tuple[str, str, str]:
    """One row of the table: (mark, check, result). A check that fails says so, and the others still run."""
    try:
        mark, result = function(*arguments)
    except ApiError as error:
        mark, result = WARN, f"could not be checked: {code(str(error))}"
    except Exception as error:  # an answer shaped as we did not expect: the workflow's log has the traceback
        traceback.print_exc()
        mark, result = WARN, f"could not be checked: {code(type(error).__name__)}"
    return mark, check, result


def repository_rows(gh: GitHub, config: dict, beside: set[str], login: str) -> tuple[str, list[tuple]]:
    """Return a Markdown description of the repository being enrolled, and the rows about it."""
    repo = config.get("repo")
    if not repo:
        return "unknown", [(WARN, "Repository", "no project.yaml that names one")]
    match = GITHUB_REPO.fullmatch(repo) if isinstance(repo, str) else None
    if not match:
        note = "not a github.com repository: check stars, maintainer, license and criticality by hand"
        return code(repo), [(WARN, "Repository", note)]

    owner, name, ref = match.groups()
    try:
        meta = gh.find(f"repos/{quote(owner, safe='')}/{quote(name, safe='')}")
    except ApiError as error:
        return code(repo), [(WARN, "Repository", f"could not be checked: {code(str(error))}")]
    if meta is None:
        return code(repo), [(FAIL, "Repository", "not found on GitHub, or not public")]

    slug = meta["full_name"]  # from GitHub: the canonical name, also after a rename
    return f"[{slug}]({meta['html_url']})" + (f" at {code(ref)}" if ref else ""), [
        row("Repository", standing_row, meta),
        row("Stars / forks", popularity_row, meta),
        row("Criticality score", criticality_row, gh, slug, meta),
        row("License", license_row, gh, slug, meta),
        row("Opened by an active maintainer", maintainer_row, gh, slug, meta, login),
        row("Contact in `SECURITY.md`", contact_row, gh, slug, meta, config),
        row("OSS-Fuzz", oss_fuzz_row, gh, slug, config),
        row("`.oss-scanner/` in the repository", scanner_files_row, gh, slug, ref, config, beside),
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

    described, rows = repository_rows(gh, config, beside, login)
    rows += [
        row("Pull request scope", scope_row, names, outside, pull["changed_files"]),
        row("`tools/validate.py`", validate_row, problems),
        row("Checklist", checklist_row, pull.get("body") or ""),
    ]
    table = "\n".join(f"| {mark} | {check} | {result} |" for mark, check, result in rows)
    return (
        f"{heading}Repository: {described} · opened by {code(login)}\n\n"
        f"| | Check | Result |\n|:-:|---|---|\n{table}\n\n"
        f"<sub>Automated, from public GitHub data, to help reviewers. Enrolment is decided case by case against "
        f"the [criteria]({CRITERIA}).</sub>\n"
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
