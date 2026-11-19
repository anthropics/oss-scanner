# Threat model

## What this project does and where untrusted input enters

S3Proxy is an HTTP server, built on Jetty, that implements the Amazon S3 REST API and keeps the
objects in a store the operator configures (`jclouds.provider`). The stores are: `transient`
(memory), `filesystem` (a directory, `jclouds.filesystem.basedir`), `sftp`, `aws-s3`,
`azureblob`, `google-cloud-storage`, and `openstack-swift`. Middlewares can wrap the store:
read-only, encryption at rest, renaming buckets or keys (alias, prefix, regex, sharded),
storage-class and user-metadata rewriting, and some testing aids. S3Proxy runs as a standalone
jar or a Docker image, and other projects also embed it as a library, mostly in their own tests.

Untrusted input enters in these ways:

- **Any request on the S3 endpoints**, before authentication. This covers `s3proxy.endpoint` and
  `s3proxy.secure-endpoint`, and the request line, path, query string and subresources. It also
  covers every header, including `Host`, which picks the bucket when `s3proxy.virtual-host` is
  set. Bodies count too: XML documents, `aws-chunked` framing with its chunk signatures and
  trailers, browser POST uploads (`multipart/form-data` with a policy), and presigned-URL query
  parameters.
- **Authenticated clients.** One identity (`s3proxy.identity` and `s3proxy.credential`) has
  access to all of its store. With `s3proxy.bucket-locator`, several identities share one proxy,
  each limited to its own buckets and store. Treat an authenticated client as a tenant: trusted
  with its own buckets, untrusted with everyone else's, and untrusted with the host.
- **Anonymous clients.** Without credentials, a client reaches only buckets and objects that an
  ACL makes public-read or public-read-write.
- **Stored content.** Keys, metadata and object bodies that one client writes are later served
  to other clients, including browsers that load them from the proxy's origin.

Trusted: the operator's properties file and command line, the keystore, the backing services and
their credentials, and the host's filesystem outside what S3Proxy is configured to manage.

## Components that matter most / least

- **Most**: `S3ProxyHandler` and `S3ProxyHandlerJetty`. They do request parsing, dispatch,
  authentication and authorization, anonymous access through ACLs, presigned URLs and POST
  policies, and authorization of the copy source. Also:
  - `auth/`: signature v2 and v4, the `Authorization` header parser, and the POST policy.
  - `checksum/` and the `aws-chunked` and trailer readers.
  - The XML mapper.
  - `BlobStoreLocator` and `GlobBlobStoreLocator`.
- **Path handling in `nio2blob/`** (the `filesystem` and `transient` stores). Keys and bucket
  names become paths under the base directory, and the store also keeps reserved names under it
  (`.s3proxy-*` sidecars, multipart stubs).
- **Middlewares that enforce a boundary**: `ReadOnlyBlobStore`, the renaming middlewares
  (`PrefixBlobStore`, `AliasBlobStore`, `RegexBlobStore`, `ShardedBlobStore`), and
  `EncryptedBlobStore` with `crypto/`. The wrappers extend `ForwardingBlobStore`. A
  `ForwardingBlobStore` method that a wrapper does not override passes straight through to the
  store, so a new method can bypass a wrapper.
- **In scope but thinner**: the adapters for remote services (`awssdk/`, `azureblob/`,
  `gcloudsdk/`, `openstackswift/`, `sftp/`). They matter where a request makes them act on a
  different bucket, key or tenant than the one authorized, or where they leak the backend's
  credentials. Where they differ from S3 without such an effect, that is a bug, not a
  vulnerability.
- **Out of scope**: test code (`src/test/`), the `s3-tests` submodule, `examples/`, `docs/`,
  and the testing middlewares (`EventualBlobStore`, `LatencyBlobStore`, `NullBlobStore`).
- **`.github/`** matters only where an untrusted pull request, issue or comment runs with a token
  that can write to the repository or with the publishing secrets.

## How to exercise it

- The image holds a built tree, and Maven runs offline. Run one test class or method with
  `mvn -B test -Dtest='CopySourceAuthorizationTest'` or `-Dtest='AwsSdkTest#testAwsV4SignatureChunkedSigned'`.
  Most tests in `src/test/java/org/gaul/s3proxy/` start a proxy on a loopback port over the
  transient store and drive it with the AWS SDK for Java v2. `TestUtils` builds the proxy from a
  config in `src/test/resources/`.
- Tests that work below the SDK use `java.net.http.HttpClient` (`UnsignedHeaderInjectionTest`,
  `AnonymousPathTest`) or a raw `Socket` when even that client would normalize the request
  (`AwsChunkedTruncationTest`, `SignedPayloadLimitTest`). A reproducer for a parsing or
  authentication problem should do the same.
- `-Ds3proxy.test.conf=s3proxy-filesystem.conf` runs the same tests against the filesystem
  store; first run `mkdir -p /tmp/blobstore`. `s3proxy-sftp.conf` runs them against an embedded
  SFTP server.
- The Azure, GCS, Swift and S3 stores need emulators (Azurite, fake-gcs-server, Swift SAIO,
  LocalStack), and the image has none of them. Their tests skip themselves without one.
- To run the server: `sed 's,^s3proxy.endpoint=.*,s3proxy.endpoint=http://127.0.0.1:8081,'
  src/test/resources/s3proxy.conf | grep -v secure-endpoint > target/s3proxy.conf`, then
  `java -jar target/s3proxy --properties target/s3proxy.conf &`. The credentials are
  `local-identity` and `local-credential`. Drive it with `curl`, or with boto3 from
  `/opt/s3-tests/bin/python`.
- s3-tests runs against that server:
  `cd s3-tests && S3TEST_CONF=/src/src/test/resources/s3-tests.conf /opt/s3-tests/bin/pytest
  --s3proxy-backend=nio2,transient 's3tests/functional/test_s3.py::test_bucket_list_empty'`.
  `src/test/resources/run-s3-tests.sh` is CI's runner, but it calls tox, which needs a network.
  It does show which tags each store deselects.

## How you rate severity

- **Critical**:
  - Reading, writing or deleting an object without valid credentials, where no ACL makes it
    public.
  - Forging or bypassing a signature check, or reusing an expired presigned URL or POST policy.
  - Reading or writing a host file outside the filesystem store's base directory.
  - Remote code execution.
- **High**:
  - An authenticated identity reaching a bucket of another identity. This includes crossing the
    boundary that a bucket locator, prefix or alias mapping draws.
  - Changing anything through a read-only proxy.
  - Recovering plaintext from the encrypting middleware without its password, or changing
    ciphertext without detection.
  - Leaking the backend's credentials, a client's SSE-C key, or a signing secret to a client or
    to logs at the default level.
  - A request that makes the proxy hold unbounded memory, threads or disk before it is
    authenticated.
- **Medium**:
  - An unauthenticated denial of service that needs sustained traffic.
  - Stored script that an anonymous reader's browser runs from the proxy's origin.
  - Telling an anonymous client whether a private object exists, or what its metadata is.
  - CORS answers that allow more than the configured rules.
- **Low**:
  - Denial of service by an authenticated client against its own buckets.
  - Hardening without a demonstrated impact.
  - Behaviour that differs from S3 with no security consequence.

## Reports and patches

- Patch against `master`. Keep Java 17 compatibility. The build runs Error Prone, NullAway,
  Checkstyle, SpotBugs and Modernizer, so `mvn -B verify -DskipTests` should still pass.
- Put a regression test under `src/test/java/` with each fix.

## Anything to leave alone

- `s3proxy.authorization=none` turns authentication off on purpose; every client is the owner.
- A public-read-write bucket is writable by anyone, as on S3. POST's `success_action_redirect`
  is an open redirect, also as on S3.
- With signature v4, a signed non-chunked body is buffered before its signature is checked, up
  to `s3proxy.v4-max-non-chunked-request-size`. This choice is deliberate: streaming would write
  part of an object before the request is known to be good.
- Configuration is the operator's choice. Examples: a base directory of `/`, a permissive regex
  mapping, CORS allow-all, metrics on a public interface, and the sample credentials in the
  example configs and the Docker image's defaults.
- The testing middlewares lose writes, delay requests or serve stale reads on purpose.
- Behaviour that only appears with a misbehaving or malicious backing service, since backing
  services are trusted.
