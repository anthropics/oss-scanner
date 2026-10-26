# ODF Toolkit threat model

ODF Toolkit is a Java library and collection of tools for reading, creating,
modifying, transforming and validating OpenDocument Format files. Applications
may process documents supplied by untrusted users, including on servers. Review
the current source on master; this description was checked against commit
7cf7a0ba6432268628cf3c8c066234c9ede7e624.

## Untrusted inputs and security goals

Treat ODF package bytes, ZIP entries and metadata, manifest paths, document XML,
embedded resources, RDF metadata and RDFa as attacker controlled. For applications
using the collaboration API, also treat JSON document operations as untrusted.
For the validator web application, include multipart upload bytes, supplied
filenames and request parameters.

Processing a document should not let its author read unrelated files, write
outside an application-selected destination, trigger unintended network access,
execute code, or escape application-imposed document limits. Inspect resource
consumption when small inputs can cause disproportionate memory or CPU use.
Ordinary linear resource use on a large document needs an application-specific
impact assessment.

Caller-selected filesystem locations, classpaths, parser or transformer factories,
validation configuration and XSLT stylesheets are application configuration.
Assume the caller controls them unless an exposed interface passes attacker input
into these settings. Distinguish executing a deliberately selected stylesheet
from behavior triggered solely by an untrusted ODF document. Demonstrate the
actual trust boundary crossed by each finding.

## Components to prioritize

- ODFDOM package loading, ZIP handling, path and URI resolution, manifest handling,
  XML parsing and saving: `odfdom/src/main/java/org/odftoolkit/odfdom/pkg/`, especially
  `OdfPackage.java`, `ZipHelper.java` and `OdfXMLHelper.java`.
- RDF extraction and RDFa processing, including
  `odfdom/src/main/java/org/odftoolkit/odfdom/pkg/OdfPackageDocument.java`,
  `odfdom/src/main/java/org/odftoolkit/odfdom/pkg/rdfa/` and the bundled GRDDL
  transformation resources.
- Collaboration JSON handling in
  `odfdom/src/main/java/org/odftoolkit/odfdom/changes/`, especially
  `CollabTextDocument`, `JsonOperationNormalizer` and `JsonOperationConsumer`.
- Validator stream and file entry points and XML/schema handling in
  `validator/src/main/java/org/odftoolkit/odfvalidator/`; upload handling and HTML
  output in `validator/src/main/webapp/jsp/validate.jsp`.
- XSLT Runner and package URI/entity resolution in
  `xslt-runner/src/main/java/org/odftoolkit/odfxsltrunner/`.

Check each parser and resolver independently. Some ODFDOM paths already disable
external entities or reject DOCTYPE; a finding needs a reachable reproducer that
shows the protection is absent or bypassed on the reported path.

The schema generator and taglets are build-time tooling and lower priority.
Attacks requiring replacement of trusted build templates, dependencies or the
local checkout need a separate supply-chain scenario. For dependency findings,
show reachability through ODF Toolkit rather than reporting a version match alone.
The deprecated Simple API is not in the current reactor.

## Build and exercise

The image includes a full Java 17 JDK, Maven 3.10.0, the checkout at `/src`,
the dependency cache at `/opt/maven-repository` and the built artifacts.
From `/src`, run:

```sh
mvn -B -ntp -o -Dmaven.javadoc.skip=true clean verify
```

This builds all active modules and runs the default unit and integration tests.
Use `verify` so packaged-jar tests run as well. Test fixtures are in each module's
`src/test/resources/`; test drivers are in `src/test/java/`. Do not activate the
optional performance integration-test profile for the baseline. Javadoc
generation is skipped because it uses external documentation links. Audit runs
have no Internet access; use local fixtures for file and network-access probes.

## Severity and report format

Rate severity from demonstrated impact and deployment assumptions. Unauthorized
code execution or arbitrary file writes reachable through an untrusted document
are high priority; rate them critical only when the demonstrated exposure and
impact justify it. Sensitive file disclosure, consequential server-side request
forgery, or web output injection may be high depending on reachability. A practical
small-input denial of service is generally medium, with higher severity requiring
an explained broader impact. Validation discrepancies without a security impact
are correctness findings.

Provide the affected commit, entry point, prerequisites, exact commands, a minimal
input and expected versus observed behavior. Keep probes local and use harmless
sentinel files. Include a focused regression test and a minimal proposed patch
when possible. Explain which deployment assumptions are necessary, and group
findings sharing the same root cause. These are investigation priorities, not
claims that the project contains the listed vulnerabilities.
