# Contributing

This repository takes one kind of contribution: a pull request that enrolls, edits, pauses or withdraws a project under `projects/<name>/`. We do not accept other changes, including changes to `tools/` or `templates/`.

## Contributor License Agreement

Before we can merge your first pull request, you need to sign our [Contributor License Agreement](CLA.md). A bot comments on your first pull request with instructions; you sign by replying with the sentence it gives. You only sign once.

## Enrolling a project

Follow the [README](README.md). In short:

1. Add `projects/<name>/project.yaml`, starting from `templates/project.yaml`. One project per pull request.
2. Run `tools/validate.py` and fix anything it reports.
3. Run `tools/check <name>` and make sure your project builds and its tests run in the shell that follows.
4. Open a pull request and fill in the checklist. Only a project's core maintainers can enrol it; we confirm this before merging.

The email addresses in `project.yaml` are public.

## Changing or leaving

Edit `projects/<name>/project.yaml` in a pull request to change an enrolment, set `disabled: true` to pause reports, or remove `projects/<name>/` to withdraw the project.

## Reporting a security issue

Please do not open a public issue for a vulnerability. See [SECURITY.md](SECURITY.md).

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
