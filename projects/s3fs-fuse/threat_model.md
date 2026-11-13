# Threat model: s3fs-fuse

## What this project does

s3fs mounts an Amazon S3 bucket, or any S3-compatible object store, as a local
directory. One process (`src/s3fs`) sits between two worlds: it serves POSIX file
operations to local processes through libfuse, and it turns them into HTTP requests to
an object store with libcurl, parsing the XML replies with libxml2. It is written in
C++17 and built with `-fno-exceptions`, so an allocation failure aborts the process
rather than unwinding.

A mount is long-lived and often privileged: `/etc/fstab` entries and container setups
commonly mount as root, frequently with `allow_other`, and the mount is then used by
processes that have no idea their file system is a network client.

## Where untrusted input enters

**1. The object store and the network path to it (the main attack surface).** s3fs
believes what the endpoint tells it. Everything below crosses that boundary:

- **ListObjects/ListMultipartUploads XML** — parsed in `src/s3fs_xml.cpp` with libxml2
  and XPath, then turned into directory entries in `src/s3objlist.cpp`. Keys, common
  prefixes, sizes, ETags, `NextMarker`/`NextContinuationToken` and the namespace URL all
  come from the wire.
- **Object keys as path names.** A key becomes a path inside the mount, and under
  `use_cache` it becomes a path inside the cache directory as well
  (`src/fdcache_entity.cpp`, `src/fdcache_stat.cpp`). Anyone who can write to the bucket
  chooses these strings; they are not constrained to look like safe file names.
- **Response headers.** `x-amz-meta-mode`, `-uid`, `-gid`, `-mtime`, `-ctime`, `-atime`,
  `-permissions`, `x-amz-meta-goog-reserved-*` and the s3sync/GCS aliases are parsed in
  `src/metaheader.cpp` and become the `struct stat` a local caller sees, including the
  file type bits that make an entry a symlink, device or socket. `Content-Length`,
  `Content-Type`, `ETag`, `Last-Modified` and `x-amz-*` SSE headers are likewise trusted.
- **Symlink targets**, which are the body of the object, not a header.
- **Error and redirect handling** in `src/curl.cpp`: status codes, retry and backoff,
  `Location`, and the body of an error reply.
- **Credential endpoints.** IMDS/ECS replies are parsed by hand in
  `src/s3fs_cred.cpp` (`ParseIAMRoleFromMetaDataResponse` and the credential parser),
  and IBM IAM replies in `src/s3fs_cred_ibm.cpp`. On an EC2 instance, anything that can
  answer on the link-local address speaks to this code.

**2. Local processes using the mount.** Path names, offsets, lengths, `xattr` names and
values, `ioctl`/`fallocate` arguments and the order of operations all arrive from
callers that may be less trusted than the mounting user — that is the point of
`allow_other`. Offset and length arithmetic lives in `src/fdcache_page.cpp` and
`src/fdcache_entity.cpp`; `xattr` values are parsed in `src/s3fs_util.cpp`.

**3. Configuration.** Mount options (`src/s3fs.cpp`, `src/s3fs_help.cpp`), the
credentials file and `~/.aws/credentials` (`src/s3fs_cred.cpp`), `-o ahbe_conf`
(`src/addhead.cpp`), and `/etc/mime.types`. These are lower value: they are usually
written by the administrator. Still in scope where a parsing bug turns a config file
into memory corruption, or where a credential reaches somewhere it should not.

## Components that matter most

In roughly descending order: `s3fs_xml.cpp`, `s3objlist.cpp`, `metaheader.cpp`,
`curl.cpp` and `curl_util.cpp` (everything that handles a reply), `string_util.cpp`
(base64, hex, URL encoding, number parsing — called from all of the above),
`fdcache*.cpp` (the page and file-descriptor cache, where offset arithmetic lives),
`cache.cpp` and `cache_node.cpp` (the stat cache and its locking), `s3fs_cred*.cpp`,
the signing code in `openssl_auth.cpp`/`gnutls_auth.cpp`/`nss_auth.cpp`, and then
`s3fs.cpp` itself.

Lower value, but in scope: `s3fs_threadreqs.cpp`, `threadpoolman.cpp`, `syncfiller.cpp`,
`mpu_util.cpp`, `addhead.cpp`, `sighandlers.cpp`.

Out of scope: `test/`, `doc/`, the sample scripts (`test/mergedir.sh`,
`test/sample_delcache.sh`), and the build system.

## How to exercise it

Two builds are in the image; the Dockerfile describes them. `/src` is the reference
build, `/src-asan` the same checkout under AddressSanitizer and
UndefinedBehaviorSanitizer.

- `make check -C /src/src` runs the unit tests. They need no mount and no network, and
  they are the fastest way to reach the parsers: `test_s3objlist`, `test_metaheader`,
  `test_curl_util`, `test_string_util`, `test_cache_node`, `test_page_list`,
  `test_auth`, `test_cred_ibm`. A new case in one of these is the best reproducer for a
  parsing or arithmetic bug, and `/src-asan` will show the memory error directly.
- `make check -C /src/test` runs the integration suite against a local S3Proxy, with one
  set of mount options; `make ALL_TESTS=1 check -C /src/test` runs all thirteen sets and
  takes about an hour. Both need `/dev/fuse` and `CAP_SYS_ADMIN`, so they do not run
  during the image build, but they do run offline in a privileged container. S3Proxy and
  pjdfstest are already in `/src/test`. In a *rootless* container two of them fail for
  reasons that are not the code's: a user namespace refuses to create a block device
  node (`test_mknod`) and refuses POSIX ACLs on a FUSE mount (`test_posix_acl`).
- To drive s3fs against a server you control, start it by hand: a credentials file of
  `access:secret` with mode 600, then
  `/src/src/s3fs bucket /mnt -o url=http://127.0.0.1:8081 -o use_path_request_style -o passwd_file=... -f -o dbglevel=dbg`.
  `-f` keeps it in the foreground. A small HTTP server that returns a chosen XML listing
  or chosen headers is the most direct way to show that a malicious endpoint reaches a
  bug, and is preferred over a patched binary.

## How we rate severity

Rate by what an attacker who controls the object store, or who can write objects into a
shared bucket, can do to a client that mounts it, and assume the mount may be root's and
may be shared through `allow_other`.

- **Critical** — reading or writing outside the mount point or the cache directory
  because of a crafted object key or symlink target; remote code execution in the s3fs
  process; anything that discloses the secret key, session token or IAM credentials to a
  third party; sending requests signed with the user's credentials to a host the user did
  not configure.
- **High** — memory corruption (heap or stack overflow, use-after-free, double free,
  type confusion) reachable from a reply, a key or a local file operation, where code
  execution is not demonstrated; silent data corruption or data loss (a read that
  returns the wrong bytes, a write that is lost or misplaced, a truncate or rename that
  destroys an unrelated object); TLS verification or request signing that can be
  defeated; cache or temporary files created with permissions or in a location that let
  another local user read or replace another user's data; a privilege check in
  `s3fs.cpp` that can be bypassed.
- **Medium** — a crash, assertion or unbounded allocation caused by a malicious reply or
  a crafted key, with no corruption behind it; a deadlock or infinite loop that wedges
  the mount; credentials or signing material written to a log at a level a user would
  plausibly enable; a race in the stat or page cache that returns another file's
  metadata.
- **Low** — anything whose worst outcome is a confusing error, a leak of a few bytes, or
  a stale cache entry.

Integrity bugs count as much as memory-safety bugs here. This is a file system: if it
can be made to return wrong data or lose a write, that matters whether or not any memory
was corrupted.

## Anything to leave alone

- s3fs trusts the object store for file *contents* by design. An endpoint that serves
  different bytes than were written, or that lies about a listing in a way that only
  misleads the user, is not a vulnerability.
- Stale metadata from the stat cache is a documented trade-off, configured with
  `stat_cache_expire`; so is the cache's memory use. Do not report either as a bug
  unless a specific sequence makes the cache return another file's data.
- The credentials file format is plaintext by design; s3fs already refuses one that is
  group- or world-readable. Do not report the format itself.
- `allow_other`, `umask`, `uid`/`gid` overrides, `nonempty`, `public_bucket` and the
  other mount options are the administrator's choices. Report them only if the
  documented behaviour and the implemented behaviour differ.
- Unencrypted HTTP is available on purpose (`-o url=http://...`) for test servers and
  private networks. The absence of encryption there is not a finding.
- No reports about missing compiler hardening flags, compiler or linter warnings,
  `-fno-exceptions`, C++ style, or the age of a dependency.
