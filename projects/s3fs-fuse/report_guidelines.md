# How we would like reports written

## Layout
Markdown, about a page, with these sections in this order:

1. **Summary** — one or two sentences: the bug and what it lets someone do.
2. **Severity** — one of the words from `threat_model.md`, and why that one.
3. **Who can trigger it** — which boundary the input crosses: control of the endpoint,
   the ability to write objects into a bucket the victim mounts, a local process using
   the mount, or the administrator's own configuration. Say which, explicitly.
4. **Affected configuration** — the commit you scanned, and the mount options needed.
   State plainly whether a default mount of a real AWS bucket is affected, or whether it
   takes a non-default option (`use_cache`, `allow_other`, `nocopyapi`, `use_xattr`, a
   `-o url=` endpoint …). A bug that needs an unusual option is still worth reporting;
   we just need to know.
5. **Reproduction** — the shortest thing that shows it. A new case in one of the
   `src/test_*.cpp` unit tests is the best form, because it runs without a mount; a
   small HTTP server with the exact reply, plus the s3fs command line, is next best.
   Include the crafted key, header or XML verbatim, and the observed output: the
   sanitizer report from `/src-asan`, the wrong bytes, the stack trace.
6. **Root cause** — the function and `file.cpp:line` where it goes wrong, and the path
   from the entry point to it. Say which of the two interfaces the entry point is on,
   the FUSE operation or the HTTP reply.
7. **Suggested fix** — see `patch_guidelines.md`.

## What every report should state
- Whether the data that reaches the bug is attacker-chosen or merely attacker-influenced.
- Whether it is reachable on all three crypto backends (OpenSSL, GnuTLS, NSS) or only
  one, when the code is in or under `*_auth.cpp`.
- Whether it depends on a server that is not AWS. s3fs is used against many
  S3-compatible stores, so "only MinIO replies like this" is useful detail, not a reason
  to skip the report.
- For a race or a deadlock: which threads and which locks, by name.

## Style
- One root cause per report. If one crafted reply trips three bugs, send three reports.
- Start the title with the file or component, then what is wrong: `s3objlist: ...`,
  `metaheader: ...`, `fdcache_page: ...`.
- Plain prose and code blocks. No tables, no CVSS vectors, no boilerplate about
  responsible disclosure.
- Quote the code you are talking about rather than describing it.
- If you are unsure whether something is reachable, say so in one sentence and send it
  anyway. We would rather judge a maybe than miss a yes.
