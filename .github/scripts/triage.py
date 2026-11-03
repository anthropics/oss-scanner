#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Write the triage comment for an enrolment pull request, as Markdown on standard output.

    GITHUB_TOKEN=... .github/scripts/triage.py --repo anthropics/oss-scanner --pr 123

Run by .github/workflows/triage.yaml, or by hand to see what it would say. Prints nothing when the pull request
does not touch projects/.

The pull request is read as data through the GitHub API: nothing from it is checked out or executed, and a read-only
token is enough. The token goes to api.github.com alone; the only other hosts contacted are pypi.org, crates.io and
packages.ecosyste.ms (an index of the registries), which are asked about public packages, and the hosts in FORGES,
which are asked about a repository there. Text from the pull request, the enrolled repository or one of those hosts
reaches the comment only through code(), so it cannot inject Markdown. Any other repository URL gets one row saying
that none of its checks ran.

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
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

# tools/validate.py holds the enrolment rules (and imports PyYAML).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
import validate

API = "https://api.github.com"
RAW = "application/vnd.github.raw"
TEXT = "text/plain"  # Accept for a file from a host in FORGES: as with RAW, only its start is read
MAX_RATE_LIMIT_WAIT = 65  # seconds
# A larger answer is refused. A file we only search (a license, a security policy) is read up to the smaller limit.
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_TEXT_BYTES = 256 * 1024
# The workflow finds the comment to update by this first line.
MARKER = "<!-- oss-scanner-triage -->"
CRITERIA = "https://red.anthropic.com/oss-scanner"

OK, WARN, FAIL, INFO = "✅", "⚠️", "❌", "ℹ️"
NOW = datetime.now(timezone.utc)
YEAR_AGO = NOW - timedelta(days=365)
# "Established", "active" and "critical" have no published numbers. These only decide when a row gets a warning.
ESTABLISHED_MONTHS = 6
STALE_MONTHS = 12
# How many of a repository's latest issues, and of its latest pull requests, are looked at for who opened them.
RECENT_THREADS = 50
# Whoever wrote this many of the last 100 commits is part of the project, whatever role GitHub shows for them.
REGULAR_COMMITS = 5
# Fewer people than this from outside the project among those who opened the latest issues and pull requests is
# warned about. One person can open hundreds of either in a repository of their own; they cannot be other people.
FEW_OUTSIDERS = 3
# A project below both is warned about. Either alone is not: a busy young project scores well with few stars, and
# a quiet, widely used one has the stars but a middling score.
FEW_STARS = 100
LOW_CRITICALITY = 0.4

GITHUB_REPO = re.compile(r"https://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?(?:#(.+))?")
# The other hosts whose API is read, and which API each has. A fixed list, because the URL comes from a pull request
# and a host of its author's choosing could answer anything.
FORGES = {
    "gitlab.com": "gitlab",
    "codeberg.org": "gitea",  # Codeberg runs Forgejo, which has Gitea's API
}
# A repository's URL on any host; Forge.at() keeps those on a host in FORGES. GitLab nests groups in groups.
FORGE_REPO = re.compile(r"https://([a-z0-9.-]+)/((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+?)(?:\.git)?/?(?:#(.+))?")
# A license file at the top of a repository, read when its host cannot name the license or names one not on our list.
LICENSE_FILE = re.compile(r"(?:[\w.-]{1,20}[._-])?(?:LICEN[CS]E|COPYING|UNLICENSE)(?:[._-][\w.-]{1,20})?", re.I | re.A)
# GitLab's accounts for access tokens, which are bots.
GITLAB_BOT = re.compile(r"(?:project|group)_\d+_bot\w*")
LOGIN = re.compile(r"[A-Za-z0-9-]+")
# These two run on text anyone can write (a description, a SECURITY.md), so nothing in them is unbounded or
# crosses a line: a long run of one character must not make them slow.
CHECKBOX = re.compile(r"^[ \t]*[-*][ \t]+\[([ xX])\][ \t]+(.+)$", re.MULTILINE)
EMAIL = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){1,8}")
# How many OSS-Fuzz projects with a name like the repository's are read to see whether one is for it.
OSS_FUZZ_CANDIDATES = 5
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
# Who opened the repository's latest issues and pull requests, and who wrote its latest commits.
PARTICIPANTS = """query($owner: String!, $name: String!, $threads: Int!) { repository(owner: $owner, name: $name) {
  issues(first: $threads, orderBy: {field: CREATED_AT, direction: DESC}) {
    nodes { authorAssociation author { __typename login } } }
  pullRequests(first: $threads, orderBy: {field: CREATED_AT, direction: DESC}) {
    nodes { authorAssociation author { __typename login } } }
  defaultBranchRef { target { ... on Commit { history(first: 100) { nodes { author { user { login } } } } } } } } }"""

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
# How the text of each license on our list begins, for a host that does not name licenses (Codeberg). Matched in
# lower case against the first lines of a license file, joined by single spaces.
LICENSE_TITLES = (
    (r"gnu affero general public license version 3(?![.\d])", "AGPL-3.0"),
    (r"gnu lesser general public license version 2\.1(?![.\d])", "LGPL-2.1"),
    (r"gnu lesser general public license version 3(?![.\d])", "LGPL-3.0"),
    (r"gnu general public license version 2(?![.\d])", "GPL-2.0"),
    (r"gnu general public license version 3(?![.\d])", "GPL-3.0"),
    (r"apache license,? version 2\.0(?![.\d])", "Apache-2.0"),
    (r"mozilla public license,? version 2\.0(?![.\d])", "MPL-2.0"),
    (r"eclipse public license - v 2\.0(?![.\d])", "EPL-2.0"),
    (r"boost software license - version 1\.0(?![.\d])", "BSL-1.0"),
    (r"\bbsd 3-clause\b", "BSD-3-Clause"),
    (r"\bbsd 2-clause\b", "BSD-2-Clause"),
    (r"\bbsd zero clause license\b", "0BSD"),
    (r"\bmit no attribution\b", "MIT-0"),
    (r"\bmit license\b", "MIT"),
    (r"\bisc license\b", "ISC"),
    (r"\bzlib license\b", "Zlib"),
    (r"\bpostgresql licen[cs]e\b", "PostgreSQL"),
    (r"this is free and unencumbered software released into the public domain", "Unlicense"),
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
# When the repository's latest releases were made. The REST API lists every asset of every release with them: tens
# of megabytes for a project that has many of both.
RECENT_RELEASES = """query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) {
  releases(first: 100, orderBy: {field: CREATED_AT, direction: DESC}) { nodes { createdAt } } } }"""
ISSUE_WINDOW_DAYS = 90

# PyPI's most downloaded packages of the last 30 days: a list made monthly and kept in a GitHub repository.
PYPI_TOP = "repos/hugovk/top-pypi-packages/contents/top-pypi-packages.min.json"
PYPI_TOP_PAGE = "https://hugovk.github.io/top-pypi-packages/"
# How many of PyPI's packages with a name like the repository's are looked up to see whether one is from it.
PYPI_CANDIDATES = 5
# npm publishes no such list. ecosyste.ms gives npm's names in order of downloads, at most this many in an answer.
NPM_TOP = 10000
NPM_TOP_PAGE = "https://packages.ecosyste.ms/registries/npmjs.org/packages?sort=downloads&order=desc"
# crates.io lists its crates by their downloads of the last 90 days, 100 to a page: this many pages are read.
CRATES_PAGES = 10
CRATES_TOP_PAGE = "https://crates.io/crates?sort=recent-downloads"
# A GitHub repository as a package's metadata names it: any scheme, often with .git, or a page within it (its issues).
PACKAGE_REPO = re.compile(r"(?<![\w.-])github\.com[/:]([\w.-]+/[\w.-]+?)(?:\.git)?(?:[/#?]|$)", re.ASCII)


class ApiError(Exception):
    """A request to an API failed. `status` is the HTTP status, or 0 if there was no usable response."""

    def __init__(self, api: str, status: int, path: str, problem: str = ""):
        super().__init__(f"{api}: {problem or status or 'no response'} for {path}")
        self.status, self.problem = status, problem


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


class StayOnApi(urllib.request.HTTPRedirectHandler):
    """Follow a redirect (a renamed repository) only within the API, so that the token is sent nowhere else."""

    def __init__(self, base: str):
        self.base = base

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not newurl.startswith(f"{self.base}/"):
            return None  # urllib then raises the redirect as an HTTPError
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class Api:
    """A client for one API that only reads. Callers quote every path segment that comes from a pull request or
    from a list of packages."""

    def __init__(self, name: str, base: str, headers: dict[str, str] | None = None):
        self.name, self.base = name, base
        self.headers = {"User-Agent": "oss-scanner-triage", **(headers or {})}
        self.opener = urllib.request.build_opener(StayOnApi(base))

    def fetch(
        self, path: str, accept: str | None = None, body: dict | None = None, whole: bool = False, **params
    ) -> tuple[bytes, str]:
        """GET a path, or POST `body` to it. Return the response's body and its Link header. Of a file asked for
        as text, only the start is read, unless all of it is asked for with `whole`."""
        cut = accept in (RAW, TEXT) and not whole
        limit = MAX_TEXT_BYTES if cut else MAX_RESPONSE_BYTES
        query = urlencode({key: value for key, value in params.items() if value is not None})
        headers = {**self.headers, "Accept": accept} if accept else self.headers
        data = json.dumps(body).encode() if body else None
        url = f"{self.base}/{path}{'?' + query if query else ''}"
        request = urllib.request.Request(url, data=data, headers=headers)
        for last_try in (False, True):
            try:
                with self.opener.open(request, timeout=30) as response:
                    answer, length = response.read(limit + 1), response.headers.get("Content-Length")
                    # Unlike a read to the end, a read of n bytes does not notice a connection that was cut off.
                    if length and length.isdigit() and len(answer) < min(int(length), limit):
                        raise http.client.IncompleteRead(answer)
                    # The start of a text is of use, the start of a JSON answer is not: asking again will not help.
                    if len(answer) > limit and not cut:
                        raise ApiError(self.name, 0, path, "answer too large")
                    return answer[:limit], response.headers.get("Link") or ""
            except urllib.error.HTTPError as error:
                delay = retry_delay(error)
                if last_try or delay is None:
                    raise ApiError(self.name, error.code, path) from None
            except (OSError, http.client.HTTPException):
                delay = 2  # a dropped or cut-off connection
                if last_try:
                    raise ApiError(self.name, 0, path) from None
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


class GitHub(Api):
    """api.github.com: the one API that is sent the token."""

    def __init__(self, token: str | None):
        super().__init__(
            "GitHub API", API, {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        )
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

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
            raise ApiError(self.name, 0, path, "no count")  # GitHub leaves the last page out of some expensive listings
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
            raise ApiError(self.name, 0, "graphql", "query refused")
        return answer["data"]  # with "errors" beside it when only part could be answered, such as a deleted account


# Where packages are looked up: none of these is sent the token.
PYPI = Api("PyPI", "https://pypi.org")
CRATES = Api("crates.io", "https://crates.io/api/v1")
ECOSYSTEMS = Api("ecosyste.ms", "https://packages.ecosyste.ms/api/v1", {"Accept": "application/json"})


class Forge(Api):
    """The API of a host in FORGES, read without a token, and one repository on it."""

    def __init__(self, host: str, slug: str, ref: str | None):
        self.kind, self.host, self.ref, self.down = FORGES[host], host, ref, False
        self.name_as(slug)
        parts = slug.split("/")
        if self.kind == "gitlab":
            super().__init__(f"{host} API", f"https://{host}/api/v4", {"Accept": "application/json"})
            self.repo = f"projects/{quote(slug, safe='')}"
        else:
            super().__init__(f"{host} API", f"https://{host}/api/v1", {"Accept": "application/json"})
            self.repo = f"repos/{quote(parts[0], safe='')}/{quote(parts[1], safe='')}"

    def name_as(self, slug: str):
        """Show and match the repository as `slug`. Requests keep the path they were made with (self.repo)."""
        self.slug, self.url = slug, f"https://{self.host}/{slug}"
        parts = slug.split("/")
        self.short = f"{parts[0]}/{parts[-1]}"  # the owner and the name, as likeness() compares them

    @staticmethod
    def at(url: object) -> Forge | None:
        """The repository a project.yaml's repo names, if it is on a host in FORGES; None for anything else."""
        match = FORGE_REPO.fullmatch(url) if isinstance(url, str) else None
        if not match or match.group(1) not in FORGES:
            return None
        host, slug, ref = match.groups()
        parts = slug.split("/")
        # "-" starts the pages within a GitLab project (/-/tree/main), which are not a repository.
        if any(part in (".", "..", "-") for part in parts) or (FORGES[host] == "gitea" and len(parts) != 2):
            return None
        return Forge(host, slug, ref)

    def fetch(self, path: str, **kwargs) -> tuple[bytes, str]:
        """As Api.fetch, but after a request gets no answer, or a server error or rate limit that outlasts the retry,
        the host is not asked again: each request could wait a minute, and the workflow is stopped after ten."""
        if self.down:
            raise ApiError(self.name, 0, path, "skipped (the host failed an earlier request)")
        try:
            return super().fetch(path, **kwargs)
        except ApiError as error:
            # Of the errors Api.fetch raises, only "answer too large" sets problem. It says nothing of the host.
            self.down = (error.status == 0 and not error.problem) or error.status == 429 or error.status >= 500
            raise

    def meta(self) -> dict:
        """The repository's metadata under GitHub's keys, plus "project" (the host's own answer) and, on Gitea,
        "licenses". On GitLab subscribers_count is None, as is the owner of a group's project, and so are archived
        and fork when GitLab does not show them. Also calls name_as()."""
        if self.kind == "gitlab":
            # Without a login GitLab gives a short answer that leaves out whether the project is archived or a fork,
            # and whether its issues and merge requests are turned on.
            project = self.get(self.repo, license="true")
            namespace = project["namespace"]
            # Only the full (signed-in) answer has "archived"; in it, no forked_from_project means not a fork.
            full = "archived" in project
            meta = {
                "name": project["path_with_namespace"],
                # GitLab's own clock, unlike a commit's date, which its author sets. New issues and merge requests
                # also move it.
                "pushed_at": project.get("last_activity_at"),
                "archived": project.get("archived"),
                "fork": bool(project.get("forked_from_project")) if full else None,
                "stargazers_count": project.get("star_count"),
                "subscribers_count": None,
                "owner": {"login": namespace["path"] if namespace["kind"] == "user" else None},
            }
        else:
            project = self.get(self.repo)
            meta = {
                "name": project["full_name"],
                "pushed_at": project.get("updated_at"),  # the host's own clock, like GitLab's last_activity_at
                "archived": project["archived"],
                "fork": project["fork"],
                "stargazers_count": project.get("stars_count"),
                "subscribers_count": project.get("watchers_count"),
                # Gitea lists the licenses it finds. Forgejo, which Codeberg runs, may not have the field (None).
                "licenses": project.get("licenses"),
                "owner": {"login": project["owner"]["login"]},
            }
        # Use the host's spelling of the path, as the GitHub rows do: the URL may give an old name or other letter
        # case. Only a path made of the characters FORGE_REPO allows is used.
        if isinstance(meta["name"], str) and re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+", meta["name"]):
            self.name_as(meta["name"])
        return meta | {"created_at": project.get("created_at"), "forks_count": project.get("forks_count"),
                       "project": project}

    def text(self, path: str, ref: str | None = None) -> str | None:
        """The text of a file in the repository (its first 256 KiB), or None if it is not there."""
        if self.kind == "gitlab":
            where = f"{self.repo}/repository/files/{quote(path, safe='')}/raw"
            params = {"ref": ref or "HEAD"}
        else:
            where, params = f"{self.repo}/raw/{quote(path)}", {"ref": ref}
        try:
            return self.fetch(where, accept=TEXT, **params)[0].decode("utf-8", "replace")
        except ApiError as error:
            if error.status == 404:
                return None
            raise

    def listing(self, path: str = "", ref: str | None = None) -> list[str] | None:
        """The names in a directory of the repository (by default its top), a directory's ending in "/", or None if
        it is not there."""
        if self.kind == "gitlab":
            # The query is written out: find() has an argument of its own named path.
            query = urlencode({"per_page": 100, **({"path": path} if path else {}), **({"ref": ref} if ref else {})})
            entries = self.find(f"{self.repo}/repository/tree?{query}")
        else:
            entries = self.find(f"{self.repo}/contents" + (f"/{quote(path)}" if path else ""), ref=ref)
        if not isinstance(entries, list):
            return None
        return [entry["name"] + ("/" if entry.get("type") in ("tree", "dir") else "") for entry in entries]

    def openers(self, meta: dict) -> tuple[list[tuple[str, str]], list[tuple[str, int]], list[str]]:
        """Who opened each of the latest issues and merge or pull requests, as (account, name shown) in lower case:
        the name only on GitLab ("" on Gitea), and ("", "") for a deleted account or a GitLab token bot. Also how many
        of each kind were read, and which kinds could not be: turned off, members only, or on another tracker."""
        project = meta["project"]
        if self.kind == "gitlab":
            kinds = {
                "issues": (f"{self.repo}/issues", {}, project.get("issues_enabled")),
                "merge requests": (f"{self.repo}/merge_requests", {}, project.get("merge_requests_enabled")),
            }
            order, login = {"order_by": "created_at", "sort": "desc", "per_page": RECENT_THREADS}, "username"
        else:
            issues_here = project.get("has_issues") and not project.get("external_tracker")
            kinds = {
                "issues": (f"{self.repo}/issues", {"type": "issues"}, issues_here),
                "pull requests": (f"{self.repo}/issues", {"type": "pulls"}, project.get("has_pull_requests")),
            }
            order, login = {"state": "all", "limit": RECENT_THREADS}, "login"  # newest first, by default
        people, read, unread = [], [], []
        for kind, (path, params, enabled) in kinds.items():
            try:
                threads = self.find(path, **params, **order) if enabled is not False else None
            except ApiError as error:
                if error.status not in (401, 403):
                    raise
                threads = None
            if threads is None:
                unread.append(kind)
                continue
            read.append((kind, len(threads)))
            for thread in threads:
                author = thread.get("author" if self.kind == "gitlab" else "user") or {}
                person = (author.get(login) or "").lower()
                # "ghost" stands for a deleted account on both; GitLab's access tokens act through bot accounts.
                if person == "ghost" or GITLAB_BOT.fullmatch(person):
                    person = ""
                people.append((person, (author.get("name") or "").lower() if person and self.kind == "gitlab" else ""))
        return people, read, unread

    def insiders(self, meta: dict) -> tuple[set[str], str, bool]:
        """The project's own people, as accounts or names in lower case; a description of them for the row; and
        whether they are known well enough that the row need not warn about its count."""
        owner = meta["owner"]["login"]
        people = {owner.lower()} if owner else set()
        if self.kind == "gitlab":
            # Members who can push (Developer, level 30, or above), like the roles GitHub shows; also through the
            # project's groups. Only the first 100 are read. gitlab.com shows them only to a signed-in reader.
            try:
                members = self.find(f"{self.repo}/members/all", per_page=100)
            except ApiError as error:
                if error.status not in (401, 403):
                    raise
                members = None
            if isinstance(members, list):
                pushers = [m for m in members if m.get("access_level", 0) >= 30]
                people |= {m["username"].lower() for m in pushers if m.get("username")}
                complete = len(members) < 100
                return people, "members who can push" + ("" if complete else ", of the first 100 listed"), complete
            # Failing that, whoever wrote or committed many of the latest commits. A GitLab commit names no account,
            # only the names its author and committer gave, which are compared with the account and the name shown of
            # each opener. A name spelled differently there is missed, so the row still warns.
            try:
                commits = self.find(f"{self.repo}/repository/commits", per_page=100)
            except ApiError as error:
                if error.status not in (401, 403):
                    raise
                commits = None
            commits = commits if isinstance(commits, list) else []
            wrote = [fold(commit.get("author_name") or "") for commit in commits]
            committed = [c.get("committer_name") for c in commits if c.get("committer_name") != c.get("author_name")]
            wrote += [fold(name or "") for name in committed]
            verb, matched, complete = "wrote or committed", ", matched to openers by name", False
            why = f"; {self.host} lists members only to signed-in readers, so some of the project's own people may be "
            why += "counted here as outsiders"
        else:
            # Gitea shows no roles to a reader without a token, but links commits to accounts. It answers 50 at most.
            commits = self.get(f"{self.repo}/commits", limit=50, stat="false", verification="false", files="false")
            wrote = [((commit.get("author") or {}).get("login") or "").lower() for commit in commits]
            verb, matched, complete, why = "wrote", "", True, ""
        regulars = {person for person in set(wrote) if person and wrote.count(person) >= REGULAR_COMMITS}
        people |= regulars
        who = ["its owner"] if owner else []
        if regulars:
            who.append(f"whoever {verb} {REGULAR_COMMITS} or more of its last {len(commits)} commits{matched}")
        how = " and ".join(who) if regulars else ("its owner only" if owner else "none known")
        return people, how + why, complete

    def is_ours(self, url: object) -> bool:
        """Does a URL from OSS-Fuzz or a package's metadata name this repository, or a page within it?"""
        # GitLab's pages of a project are under /-/; a further name would be a project in a subgroup.
        end = r"(?:/-/|/?[#?]|/?$)" if self.kind == "gitlab" else r"(?:[/#?]|$)"
        pattern = rf"(?:[\w+.-]+://|git@)?(?:www\.)?{re.escape(self.host)}[/:]{re.escape(self.slug)}(?:\.git)?{end}"
        return isinstance(url, str) and re.match(pattern, url[:300].strip(), re.IGNORECASE) is not None


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


def ordinal(place: int) -> str:
    """A place in a list, as 1st or 2,652nd. Not as #2652: GitHub would link that to the pull request of that number."""
    suffix = "th" if 10 <= place % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(place % 10, "th")
    return f"{place:,}{suffix}"


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


def standing_row(meta: dict, activity: str = "push") -> tuple[str, str]:
    created, pushed = parse_time(meta["created_at"]), parse_time(meta["pushed_at"])
    result = f"created {ago(created)}, last {activity} {ago(pushed)}"
    if meta["archived"]:
        return FAIL, f"archived; {result}"
    concerns = []
    if meta["fork"]:
        concerns.append("a fork of another repository")
    if months_since(created) < ESTABLISHED_MONTHS:
        concerns.append(f"under {ESTABLISHED_MONTHS} months old")
    if months_since(pushed) >= STALE_MONTHS:
        concerns.append(f"no {activity} in {STALE_MONTHS} months")
    if concerns:
        return WARN, f"{'; '.join(concerns)} ({result})"
    return OK, result


def popularity_row(meta: dict) -> tuple[str, str]:
    forks, watchers = meta["forks_count"], meta["subscribers_count"]  # watchers: None where they are not counted
    result = f"{meta['stargazers_count']:,} stars · {forks:,} forks"
    result += f" · {watchers:,} watching" if watchers is not None else ""
    absent = [what for what, count in (("forks", forks), ("watchers", watchers)) if count == 0]
    if absent:
        return WARN, f"no {' and no '.join(absent)}: little sign that others use it ({result})"
    return INFO, result


def outsiders_row(gh: GitHub, slug: str, meta: dict, login: str) -> tuple[str, str]:
    """How many people from outside the project opened its latest issues and pull requests? Not counted: the
    repository's owner, whoever opened this pull request, anyone GitHub shows as a maintainer, anyone who wrote a
    good share of the latest commits, and bots."""
    owner, name = slug.split("/")
    repository = gh.graphql(PARTICIPANTS, owner=owner, name=name, threads=RECENT_THREADS)["repository"]
    threads = repository["issues"]["nodes"] + repository["pullRequests"]["nodes"]
    if not threads:
        return WARN, "the repository has no issues or pull requests"

    history = ((repository["defaultBranchRef"] or {}).get("target") or {}).get("history") or {"nodes": []}
    wrote = [((commit["author"] or {}).get("user") or {}).get("login", "").lower() for commit in history["nodes"]]
    insiders = {meta["owner"]["login"].lower(), login.lower()}
    insiders |= {person for person in set(wrote) if wrote.count(person) >= REGULAR_COMMITS}
    outsiders, theirs = set(), 0
    for thread in threads:
        author = thread["author"] or {}  # no author: a deleted account
        person = author.get("login", "").lower()
        if author.get("__typename") != "User" or thread["authorAssociation"] in ASSOCIATIONS or person in insiders:
            continue
        outsiders.add(person)
        theirs += 1

    result = f"the last {len(threads)} issues and pull requests"
    if not outsiders:
        return WARN, f"none: {result} were all opened by the project's own people or by bots"
    people = "1 person" if len(outsiders) == 1 else f"{len(outsiders)} people"
    result = f"{people} from outside the project opened {theirs} of {result}"
    return (WARN if len(outsiders) < FEW_OUTSIDERS else INFO), result


def license_row(gh: GitHub, slug: str, meta: dict) -> tuple[str, str]:
    spdx = (meta.get("license") or {}).get("spdx_id")
    return license_result("GitHub", spdx, lambda: gh.text(f"repos/{slug}/license"))


def license_result(host: str, spdx: str | None, license_text) -> tuple[str, str]:
    """Judge the license `host` names (an SPDX id, or NOASSERTION when it cannot name it); `license_text` reads the
    license file, which is only needed when the license has no name."""
    if not spdx:
        return FAIL, f"{host} finds no license file"
    if spdx in COMMON_LICENSES:
        return OK, code(spdx)
    if spdx != "NOASSERTION":
        return WARN, f"{code(spdx)} is not on our list of common open-source licenses; check it"
    text = license_text() or ""
    found = next((name for name in SOURCE_AVAILABLE if name.lower() in text.lower()), None)
    if found:
        return FAIL, f"the license file mentions “{found}”, a source-available license"
    found = next((name for name in PARTLY_OPEN if name.lower() in text.lower()), None)
    if found:
        return WARN, f"the license file mentions “{found}”: part of the repository may not be open source"
    # GitHub also fails to name a plain license with a line added, so show the reviewer what the file says.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    says = next((line for line in lines if "licens" in line.lower()), lines[0] if lines else "nothing")
    return WARN, f"{host} cannot name the license; its file says {code(says, 80)}"


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
    return contact_result(contact, security_policy(gh, slug, meta["owner"]["login"]), slug)


def contact_result(contact: str, policy: tuple[str, str] | None, slug: str) -> tuple[str, str]:
    """Does the security policy found (its repository and its text) give `contact`?"""
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


def squash(name: str) -> str:
    """A name reduced to its letters and digits, so that PcapPlusPlus and pcap-plus-plus compare equal."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def fold(name: str) -> str:
    """A person's name or account without accents, case, spaces or punctuation, so that Zdeněk Kabeláč, Zdenek
    Kabelac and zdenek.kabelac compare equal. A name with no Latin letters or digits is only put in lower case."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return squash(plain) or name.lower()


def likeness(slug: str, name: str) -> int | None:
    """How like the repository's name, or its owner's, the name of a project or a package is: 0 at best, None if
    not at all."""
    key, (owner, repo) = squash(name), (squash(part) for part in slug.split("/"))
    if key in (repo, owner):
        return 0 if key == repo else 1
    # One name inside the other, unless the inner one is so short that it is there by chance.
    for place, (inner, outer) in enumerate(((repo, key), (key, repo), (owner, key), (key, owner)), start=2):
        if len(inner) >= 4 and inner in outer:
            return place
    return None


def oss_fuzz_candidates(slug: str, names: list[str]) -> list[str]:
    """Of OSS-Fuzz's project names, the few that could be this repository's, likeliest first.

    OSS-Fuzz has no index by repository, and GitHub's code search is closed to the workflow's token. But a project
    is nearly always named after its repository or the repository's owner (bitcoin-core fuzzes bitcoin/bitcoin):
    of OSS-Fuzz's 1,252 projects on GitHub, this finds 1,183."""
    ranked = sorted((place, len(name), name) for name in names if (place := likeness(slug, name)) is not None)
    return [name for _, _, name in ranked[:OSS_FUZZ_CANDIDATES]]


def oss_fuzz_projects(gh: GitHub, slug: str, is_ours=None) -> tuple[dict[str, dict], dict[str, object]]:
    """Find the OSS-Fuzz projects that fuzz this repository: each one's name and project.yaml. Also return the
    main_repo of any project named exactly after the repository or its owner that is for some other repository.
    For a repository not on GitHub, `is_ours` says whether a main_repo names it."""
    listing = gh.get("repos/google/oss-fuzz/git/trees/HEAD:projects")["tree"]
    owner, name = (squash(part) for part in slug.split("/"))
    found, namesakes = {}, {}
    for candidate in oss_fuzz_candidates(slug, [entry["path"] for entry in listing if entry["type"] == "tree"]):
        text = gh.text(f"repos/google/oss-fuzz/contents/projects/{quote(candidate, safe='')}/project.yaml")
        try:
            project = validate.yaml.safe_load(text or "")
        except (validate.yaml.YAMLError, RecursionError):
            continue
        # A name is only a guess: main_repo is what says the project is for this repository.
        main_repo = project.get("main_repo") if isinstance(project, dict) else None
        match = MAIN_REPO.fullmatch(main_repo.strip()) if isinstance(main_repo, str) else None
        ours = is_ours(main_repo) if is_ours else bool(match) and match.group(1).lower() == slug.lower()
        if ours:
            found[candidate] = project
        elif isinstance(project, dict) and squash(candidate) in (name, owner):
            namesakes[candidate] = main_repo
    return found, namesakes


def oss_fuzz_row(gh: GitHub, slug: str, config: dict, is_ours=None) -> tuple[str, str]:
    """Is the repository in OSS-Fuzz, whose criteria ours follow, and does OSS-Fuzz report to the same address?"""
    projects, namesakes = oss_fuzz_projects(gh, slug, is_ours)
    if not projects and namesakes:
        others = "; ".join(f"{code(name)} there is for {code(main_repo)}" for name, main_repo in namesakes.items())
        return INFO, f"no OSS-Fuzz project is for this repository, but {others}"
    if not projects:
        return INFO, "not found in OSS-Fuzz"
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
    listing = gh.find(f"repos/{slug}/contents/.oss-scanner", ref=ref)
    names = [entry["name"] for entry in listing] if isinstance(listing, list) else []

    def exists(path: str) -> bool:
        return gh.find(f"repos/{slug}/contents/{quote(path)}", ref=ref) is not None

    return scanner_files_result(names, exists, ref, config, beside)


def scanner_files_result(
    names: list[str] | None, exists, ref: str | None, config: dict, beside: set[str]
) -> tuple[str, str]:
    """Judge what `.oss-scanner/` holds (`names`, None if it could not be listed), and whether `exists` finds the
    files project.yaml names."""

    def in_repo(path: object) -> bool:
        return isinstance(path, str) and bool(validate.REPO_PATH.fullmatch(path)) and exists(path)

    result = f"present ({', '.join(code(name) for name in names[:6])})" if names else "not present"
    if names is None:
        result = "its files could not be listed (check by hand)"

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

    owner, name = slug.split("/")
    releases = gh.graphql(RECENT_RELEASES, owner=owner, name=name)["repository"]["releases"]["nodes"]
    recent_releases = sum(1 for release in releases if parse_time(release["createdAt"]) > YEAR_AGO)
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
    if meta["fork"]:
        # A fork carries its parent's commits and contributors, and would be given the parent's score.
        parent = (meta.get("parent") or {}).get("full_name")
        return WARN, f"not scored: a fork of {code(parent)}, whose history it carries"
    signals = criticality_signals(gh, slug, meta)
    score = criticality_score(signals)
    result = f"**{score:.2f}** on the [OpenSSF]({CRITICALITY_SOURCE}) scale of 0 to 1"
    low = meta["stargazers_count"] < FEW_STARS and score < LOW_CRITICALITY
    if low:
        result += f": low, and the project has under {FEW_STARS} stars"
    details = ", ".join(f"{name} {value:,}" for name, value in signals.items())
    return (WARN if low else INFO), f"{result}<details><summary>signals</summary>{details}</details>"


def is_repository(url: object, slug: str) -> bool:
    """Does a URL from a package's metadata give this repository, or a page within it?"""
    match = PACKAGE_REPO.search(url[:300]) if isinstance(url, str) else None
    return bool(match) and match.group(1).lower() == slug.lower()


def pypi_rank(slug: str, names: list[str], is_ours) -> tuple[str, int] | None:
    """Of PyPI's most downloaded packages, most downloaded first, the one from the repository that is most its
    namesake, and that package's place in the list.

    The list gives names only. Like an OSS-Fuzz project, a package is nearly always named after its repository or
    the repository's owner, so the few names most like those are looked up on PyPI, which says where each
    package's source is."""
    places = enumerate(names, 1)
    ranked = sorted((like, place, name) for place, name in places if (like := likeness(slug, name)) is not None)
    for _, place, name in ranked[:PYPI_CANDIDATES]:
        info = (PYPI.find(f"pypi/{quote(name, safe='')}/json") or {}).get("info") or {}
        urls = (info.get("home_page"), *(info.get("project_urls") or {}).values())
        if any(is_ours(url) for url in urls):
            return name, place
    return None


def npm_rank(url: str) -> tuple[str, int] | None:
    """The most downloaded npm package that is from the repository, and its place among all of npm's. ecosyste.ms
    knows each package's repository, so there is nothing to guess from names."""
    order = {"sort": "downloads", "order": "desc"}
    # The first few say enough, and each comes with all that ecosyste.ms knows about the package.
    packages = ECOSYSTEMS.get("registries/npmjs.org/lookup", repository_url=url, per_page=10, **order)
    ours = {package["name"] for package in packages}
    if not ours:
        return None
    names = ECOSYSTEMS.get("registries/npmjs.org/package_names", per_page=NPM_TOP, **order)
    return next(((name, place) for place, name in enumerate(names, 1) if name in ours), None)


def crates_rank(is_ours) -> tuple[str, int] | None:
    """The most downloaded crate that is from the repository, and its place among all crates. crates.io gives each
    crate's repository in its listing, so there is nothing to guess from names."""
    for page in range(1, CRATES_PAGES + 1):
        if page > 1:
            time.sleep(1)  # crates.io asks for no more than one request a second
        crates = CRATES.get("crates", sort="recent-downloads", per_page=100, page=page)["crates"]
        for place, crate in enumerate(crates, (page - 1) * 100 + 1):
            if is_ours(crate.get("repository")):
                return crate["name"], place
    return None


def package_rank_row(gh: GitHub, slug: str) -> tuple[str, str]:
    """Where do the repository's packages stand among the most downloaded of PyPI, npm and crates.io? A registry
    is looked at only for a repository with code in one of its languages."""
    languages = gh.get(f"repos/{slug}/languages")
    return package_ranks(gh, languages, slug, lambda url: is_repository(url, slug), f"https://github.com/{slug}")


def package_ranks(gh: GitHub, languages: dict, slug: str, is_ours, url: str) -> tuple[str, str]:
    """package_rank_row() for the repository at `url`, whose languages are given. `is_ours` says whether a URL from
    a package's metadata is this repository; `slug` is its owner and name, which packages are often named after."""
    ranks = []  # (the registry, the package found and its place, how many places were looked at)
    if "Python" in languages:
        names = [row["project"] for row in json.loads(gh.fetch(PYPI_TOP, accept=RAW, whole=True)[0])["rows"]]
        ranks.append((f"[PyPI]({PYPI_TOP_PAGE})", pypi_rank(slug, names, is_ours), len(names)))
    if "JavaScript" in languages or "TypeScript" in languages:
        ranks.append((f"[npm]({NPM_TOP_PAGE})", npm_rank(url), NPM_TOP))
    if "Rust" in languages:
        ranks.append((f"[crates.io]({CRATES_TOP_PAGE})", crates_rank(is_ours), CRATES_PAGES * 100))
    if not ranks:
        return INFO, "no Python, JavaScript or Rust in the repository, so not looked for on PyPI, npm or crates.io"

    found = [f"{code(rank[0])} is {ordinal(rank[1])} on {registry}" for registry, rank, _ in ranks if rank]
    missing = [f"the top {looked_at:,} on {registry}" for registry, rank, looked_at in ranks if not rank]
    if missing:
        found.append(f"nothing from this repository found in {' or '.join(missing)}")
    return INFO, f"by downloads: {' · '.join(found)}"


# --- the same checks for a repository on a host in FORGES ---


def forge_standing_row(forge: Forge, meta: dict) -> tuple[str, str]:
    mark, result = standing_row(meta, "activity")
    unknown = [what for key, what in (("archived", "archived"), ("fork", "a fork")) if meta[key] is None]
    if not unknown:
        return mark, result
    result += f"; {forge.host} shows whether it is {' or '.join(unknown)} only to signed-in readers: check its page"
    return (WARN if mark == OK else mark), result


def forge_outsiders_row(forge: Forge, meta: dict) -> tuple[str, str]:
    """outsiders_row() for a repository on another host. Unlike on GitHub, whoever opened this pull request is
    counted like anyone else: nothing links their GitHub account to an account on the other host."""
    openers, read, unread = forge.openers(meta)
    if unread:
        why = "turned off, members only, or on another tracker"
        unread = f"{' and '.join(unread)} could not be read on {forge.host} ({why})"
    if not read:
        return WARN, unread
    unread = f"; {unread}" if unread else ""
    if not openers:
        return WARN, f"the repository has no {' or '.join(kind for kind, _ in read)}{unread}"
    # latest: "7 issues and 2 merge requests", "1 issue and no merge requests"
    latest = " and ".join(f"{n or 'no'} {kind[:-1] if n == 1 else kind}" for kind, n in read)
    if not any(account for account, _ in openers):
        bots = "bots or deleted accounts"
        return WARN, f"none from outside the project: the latest {latest}, all opened by {bots}{unread}"
    insiders, how, complete = forge.insiders(meta)
    # Folded as well as plain: a commit's "Zdenek Kabelac" is the account zdenek.kabelac, shown as Zdeněk Kabeláč.
    def is_own(account: str, name: str) -> bool:
        return bool(({account, name, fold(account), fold(name)} - {""}) & insiders)

    theirs = [account for account, name in openers if account and not is_own(account, name)]
    if not theirs:
        own = f"the project's own people ({how}), bots or deleted accounts"
        return WARN, f"none from outside the project: the latest {latest}, all opened by {own}{unread}"
    outsiders = len(set(theirs))
    people = "1 person" if outsiders == 1 else f"{outsiders} people"
    were = "was" if len(theirs) == 1 else "were"
    result = f"of the latest {latest}, {len(theirs)} {were} opened by {people} from outside the project"
    result += f" (counted as its own: {how}){unread}"
    return (WARN if outsiders < FEW_OUTSIDERS or not complete else INFO), result


def is_common(spdx: object) -> bool:
    """Is a license GitLab or Gitea names on our list? GitLab writes its ids in lower case and marks "or later" with
    a "+" ("gpl-2.0+"); Gitea's SPDX ids may end in -only or -or-later. COMMON_LICENSES lists them without these
    endings and in mixed case, so both are compared in lower case with the ending removed."""
    plain = re.sub(r"(?:\+|-only|-or-later)\Z", "", spdx.lower()) if isinstance(spdx, str) else None
    return plain in {name.lower() for name in COMMON_LICENSES}


def license_title(text: str) -> str | None:
    """The license on our list whose title heads a license file, or None. Only the title is read, not the terms
    under it, so this is weaker than a host naming the license."""
    lines = [line.strip(" \t#*=-") for line in text[:4000].splitlines()]
    head = " ".join(" ".join(line for line in lines if line).lower().split()[:60])
    return next((spdx for title, spdx in LICENSE_TITLES if re.search(title, head)), None)


def forge_license_row(forge: Forge, meta: dict) -> tuple[str, str]:
    license = None
    if forge.kind == "gitlab":
        # GitLab gives no license when it finds no license file at the top, and the key "other" when it cannot
        # name the license. Either way the files there are looked at.
        license = meta["project"].get("license")
        key = license.get("key") if license else None
        names = [key] if key and key != "other" else []
    else:
        names = meta["licenses"] or []  # Gitea names only the licenses it recognises, and Forgejo may name none
    uncommon = [name for name in names if not is_common(name)]
    if names and not uncommon:
        return OK, ", ".join(code(name) for name in names)
    named = license_result(forge.host, uncommon[0], lambda: "") if uncommon else None
    if named and named[0] != WARN:
        return named
    # A license the host cannot name, or names but is not on our list: its file may show it is source-available.
    top = [name for name in forge.listing() or [] if isinstance(name, str)]
    files = sorted((name for name in top if LICENSE_FILE.fullmatch(name)), key=len)
    if named and not files:
        return named
    if not files and "LICENSES/" in top:  # the REUSE layout: a file per license in LICENSES/
        return WARN, "the licenses are in `LICENSES/`; check them by hand"
    if not files and forge.kind == "gitlab" and license:  # found by GitLab, under a name LICENSE_FILE does not match
        return WARN, f"{forge.host} found a license file but cannot name the license; check it by hand"
    if not files:
        return FAIL, f"no license file at the top of the repository on {forge.host}"
    # Any of them may be the one with a source-available license in it.
    texts = [forge.text(name) or "" for name in files[:3]]
    text = "\n".join(texts)
    verdict = license_result(forge.host, "NOASSERTION", lambda: text)
    if named:
        return verdict if verdict[0] == FAIL else named
    # The host named nothing. If every file is headed by the title of a license on our list, and none mentions a
    # source-available or commercial one, say which: not a tick, as only the titles were read.
    titles = [license_title(each) for each in texts if each.strip()]
    flagged = any(name.lower() in text.lower() for name in (*SOURCE_AVAILABLE, *PARTLY_OPEN))
    if titles and all(titles) and not flagged:
        shown = ", ".join(code(spdx) for spdx in dict.fromkeys(titles))
        return INFO, f"{shown}, going by the title of its license file: {forge.host} does not name the license"
    return verdict


def forge_contact_row(forge: Forge, config: dict) -> tuple[str, str]:
    contact = config.get("primary_contact")
    if not isinstance(contact, str):
        return WARN, "project.yaml names no contact"
    texts = ((forge.slug, forge.text(path)) for path in SECURITY_POLICY_PATHS)
    return contact_result(contact, next((policy for policy in texts if policy[1] is not None), None), forge.slug)


def forge_package_rank_row(gh: GitHub, forge: Forge) -> tuple[str, str]:
    languages = forge.get(f"{forge.repo}/languages")
    return package_ranks(gh, languages, forge.short, forge.is_ours, forge.url)


def forge_scanner_files_row(forge: Forge, config: dict, beside: set[str]) -> tuple[str, str]:
    try:
        names = forge.listing(".oss-scanner", forge.ref) or []
    except ApiError:
        names = None  # e.g. too many files to list: the files project.yaml names are still looked for
    return scanner_files_result(names, lambda path: forge.text(path, forge.ref) is not None, forge.ref, config, beside)


def forge_rows(gh: GitHub, forge: Forge, repo: str, config: dict, beside: set[str], login: str) -> tuple[str, list]:
    """repository_rows() for a repository on a host in FORGES. The rows that need GitHub's data say so."""
    try:
        meta = forge.meta()
    except ApiError as error:
        if error.status == 404:
            return code(repo), [(FAIL, "Repository", f"not found on {forge.host}, or not public")]
        return code(repo), [(WARN, "Repository", f"could not be checked: {code(str(error))}")]
    except Exception as error:  # an answer shaped as we did not expect: the workflow's log has the traceback
        traceback.print_exc()
        return code(repo), [(WARN, "Repository", f"could not be checked: {code(type(error).__name__)}")]

    criticality = "not scored: the OpenSSF score needs GitHub's data; judge criticality by hand"
    maintainer = f"not checked: nothing links the GitHub account {code(login)} to the project's accounts on "
    maintainer += f"{forge.host}; confirm by hand that they maintain it"
    return f"[{code(forge.host + '/' + forge.slug)}]({forge.url})" + (f" at {code(forge.ref)}" if forge.ref else ""), [
        row("Repository", forge_standing_row, forge, meta),
        row("Stars / forks", popularity_row, meta),
        row("Outside participants", forge_outsiders_row, forge, meta),
        (WARN, "Criticality score", criticality),
        row("Package rank", forge_package_rank_row, gh, forge),
        row("License", forge_license_row, forge, meta),
        (WARN, "Opened by an active maintainer", maintainer),
        row("Contact in `SECURITY.md`", forge_contact_row, forge, config),
        row("OSS-Fuzz", oss_fuzz_row, gh, forge.short, config, forge.is_ours),
        row("`.oss-scanner/` in the repository", forge_scanner_files_row, forge, config, beside),
    ]


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
    forge = None if match else Forge.at(repo)
    if forge:
        return forge_rows(gh, forge, repo, config, beside, login)
    if not match:
        hosts = ["github.com", *FORGES]
        note = f"not checked: only the plain https URL of a repository on {', '.join(hosts[:-1])} or {hosts[-1]} is "
        note += "read, such as `https://gitlab.com/group/project` (no page path, port or login). Check by hand: age, "
        note += "stars, outside participants, criticality, package rank, license, maintainer, `SECURITY.md` contact, "
        note += "OSS-Fuzz, Dockerfile"
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
        row("Outside participants", outsiders_row, gh, slug, meta, login),
        row("Criticality score", criticality_row, gh, slug, meta),
        row("Package rank", package_rank_row, gh, slug),
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
        f"<sub>Automated, from public data, to help reviewers. Enrolment is decided case by case against "
        f"the [criteria]({CRITERIA}). If you think we got something wrong, please tell us in a reply.</sub>\n"
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
