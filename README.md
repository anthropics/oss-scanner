# OSS Scanner

OSS Scanner is a service by Anthropic to scan critical open-source repositories for security vulnerabilities. Learn more about the service at [red.anthropic.com/oss-scanner](https://red.anthropic.com/oss-scanner).

Note, use of this tool is subject to the terms and conditions outlined in the [OSS Scanner terms](https://red.anthropic.com/oss-scanner/terms).

## How to sign up

Enroll an open-source project by opening a pull request that adds one directory:

```
projects/<name>
```

Our security scanner builds your project in an isolated VM, then analyses it with no Internet access and emails what it finds to `primary_contact` (and any CCs), each with a reproducer and a proposed patch where available. Reports are model-generated and are not reviewed by a human. Because of this we do not place a 90-day disclosure period on these findings and will not make them public. Project owners should provide `project.yaml` (to configure the scanner), a `Dockerfile` (stating how to build the project), and optionally a `threat_model.md` (providing project-specific threat modeling).

### project.yaml

Start from `templates/project.yaml`:

```
repo: https://github.com/example/project    # required: the git repository to scan; add #branch to pin one
primary_contact: security@example.org       # required: reports and build problems go here (one address)
auto_ccs:                                   # optional: more addresses on every mail
  - maintainer@example.org
homepage: https://example.org               # optional
disabled: false                             # optional: true pauses reports without removing the enrolment
dockerfile: .oss-scanner/Dockerfile         # required unless a Dockerfile sits in this repo next to your project.yaml
threat_model: .oss-scanner/threat_model.md  # optional; also supports placing the file in this repository
```

`repo` and `primary_contact` are always required. `dockerfile` is required unless you keep your Dockerfile next to `project.yaml` (see below). Others are optional.

The email addresses in `project.yaml` are public. Use addresses you are happy to see published, such as a security alias.

To receive reports encrypted, add your armored OpenPGP public key. Reports then go to `primary_contact` only; pgp cannot be combined with `auto_ccs`:
```
pgp: |
  -----BEGIN PGP PUBLIC KEY BLOCK-----
  mQINBF...
  -----END PGP PUBLIC KEY BLOCK-----
```

You must provide a Dockerfile, in exactly one of two places:

* **in your own repository**: set `dockerfile:` to its path (we suggest at some location like `.oss-scanner/Dockerfile`). This is the preferred option because it allows you to update the build without a pull request here; or,  
* **here**, next to `project.yaml`, as `projects/<name>/Dockerfile`, with no `Dockerfile:` key set in the `project.yaml`. If you would rather not add files to your repository, put it here and the scanner builds it exactly as it would an in-repo copy.

(The threat model works the same way. Set the `threat_model` field for its location in your repository, or place it here at `projects/<name>/threat_model.md`.)

The purpose of the `Dockerfile` is to set up your environment, install every dependency, and build the project. Initial project setup runs with network access enabled, but the security audit after it runs without Internet access. Anything the build or the tests need must be fetched during the initial Dockerfile setup. We recommend checking that your tests pass inside the built image.

The `threat_model.md` (optional but strongly recommended) file allows you to provide the scanner with documentation on your intended security goals. We have found it is most useful to provide guidance for how you rate the severity of reports (e.g., do you consider post-auth SQLi high or critical? are buffer overflows without demonstrated exploits capped at high? when is stored XSS medium, high, and critical?) This file can also state what the project does, where untrusted input enters, which components matter and which are out of scope, how you would like reports and patches to look, or anything else you think important or useful.

We suggest you run two commands before opening a pull request:

* `tools/validate.py` checks `projects/<name>/` against the rules above.
* `tools/check <name>` builds your project the way our scanner will, and opens a shell in the finished image with no network. If your tests pass in this container, our scanner will likely work with your project. `tools/check --qemu <name>` does the same inside virtual machines laid out like the scanner's.

These tools need your host to have installed git, Docker, and Python 3 with PyYAML (`pip install pyyaml`); `--qemu` needs Linux on x86-64 with QEMU instead of Docker.

## What happens after the merge

1. The scanner imports the project, builds it online in an isolated VM, then moves the VM to a network with no Internet access for scanning. If the build fails, we will email `primary_contact` with an error message.  
2. We scan the project for vulnerabilities.
3. Findings are emailed to `primary_contact` and any additional CCs with reproduction steps and a proposed patch where available.

You can edit your project at any time with a PR. To unenroll your project, set the disabled field to true to pause reports or remove `projects/\<name\>/` to withdraw the project entirely.

## Security considerations

* `tools/check` runs your project's Dockerfile with network access, as `docker build` would. With `--qemu` the build runs inside a virtual machine, which keeps it off your files, but it can still reach services on your computer and your local network. Only check projects you trust, or use a machine with nothing to lose.
* `tools/check` installs Claude Code into the image it builds (as the scanner does). Claude Code is covered by its own terms.

## Learn more

Please visit [red.anthropic.com/oss-scanner](https://red.anthropic.com/oss-scanner). 

---

**Maintenance status:** this repository is actively maintained by Anthropic. We review and merge enrollment pull requests (changes under `projects/<name>/`) only; we do not accept other contributions, including changes to `tools/` or `templates/`. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to enroll, [SECURITY.md](SECURITY.md) to report a vulnerability in this repository, and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
