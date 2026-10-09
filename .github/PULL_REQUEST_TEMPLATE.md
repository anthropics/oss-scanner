## Enrol `projects/<name>`

I have verified each of the following before submitting this project:

- [ ] I am a core maintainer of this project.
- [ ] I accept the [OSS Scanner terms](https://red.anthropic.com/oss-scanner/terms/).
- [ ] `project.yaml` follows the README (one project per PR; `tools/validate.py` passes locally).
- [ ] `tools/check <name>` builds the project, and its tests run in the shell that follows.
- [ ] `primary_contact` must be the email address of the primary security contact.
- [ ] There is a `Dockerfile` that builds the project (required) in one of two places: in the project's repository at the path `dockerfile:` names, or next to `project.yaml` in this repo.
- [ ] `threat_model.md` is written for this project (recommended but optional), placed in the same way: in the repository at the path `threat_model:` names, or next to `project.yaml` in this repo.

To change an enrolment, edit `project.yaml`; to pause reports, set `disabled: true`; to withdraw the project, remove `projects/<name>/`.

Context (optional): if you believe it is not obvious why your project qualifies for our inclusion criteria, you may write a brief note here to explain why you feel it does.
