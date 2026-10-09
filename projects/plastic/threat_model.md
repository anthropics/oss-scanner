# plastic: security audit scope

plastic is a Python/PyTorch research sandbox with a FastAPI service, a React
dashboard, persistent model/session artifacts, and a restricted Hugging Face
demo deployment. It is an early research project; no broad downstream adoption
or demonstrated general safety efficacy is claimed.

The repository's LICENSE is "MIT License with Commercial Use Restriction".
This submission preserves that license and asks the program to determine
eligibility; it does not represent the project as OSI-approved open source.

## Boundaries and useful targets

- Treat HTTP paths, query parameters, JSON bodies, chat input and rendered model
  output as attacker-controlled. Review `plastic/api/`, `dashboard/`, and
  `deploy/huggingface/app.py` for request validation, path traversal, file access,
  injection, denial of service and bypasses of the public deployment's controls.
- The local research API is a trusted-operator tool without per-user authentication.
  The hosted demo uses a separate middleware allowlist and resource limits.
  Evaluate each deployment in its actual configuration; an unauthenticated local
  API alone is not a bypass of the hosted demo's restrictions. Browser-to-local
  attacks remain relevant if their prerequisites and impact are demonstrated.
- Public demo sessions are intentionally shared. Reading or resetting an allowed
  shared session is expected; access to other artifacts, disallowed operations or
  unbounded work is not. Check malformed/encoded paths, request bodies, concurrent
  operations, disconnects and exception cleanup at the middleware/service boundary.
- Review `plastic/store.py`, `plastic/session/`, and `plastic/api/sleep_jobs.py` for
  corruption, races, unsafe deserialization, path escapes and subprocess argument
  handling. Checkpoints and artifact-store files are operator-provided trusted
  inputs by default. For findings that require a malicious checkpoint or local
  file, show how an attacker crosses a real trust boundary to supply it.
- Concrete violations of implemented transaction/state contracts are useful:
  writes or decay during freeze, rejected updates retained, incompatible state
  loaded, nonfinite state persisted, or accepted changes exceeding a budget.
  Keep these separate from claims about factual correctness or model alignment.
  Prompt-induced wrong answers or a probe failing to cover arbitrary behavior
  alone do not establish a software vulnerability or safety-method failure.

Do not target the live Hugging Face Space, third-party services, other users'
data or real credentials. Reproduce against the container and disposable
artifact stores. GPU timing, model-quality benchmarking and training new large
checkpoints are outside this enrollment's audit environment.

## Offline environment and checks

The checkout is at `/src`. Python 3.12, CPU PyTorch, the project's dev/pretrained/
Jev dependencies, Node 22, the dashboard dependencies and its production build
are installed. Python is installed editable, so candidate patches take effect.
All network dependencies must be available before the scan; no credentials are
provided, and external grading services cannot be called offline.

Run from `/src`:

```sh
python -m pytest tests deploy/huggingface/test_space.py
npm --prefix dashboard test -- --maxWorkers=2 --minWorkers=1
npm --prefix dashboard run build
plastic --help
```

`tests/test_api.py` creates tiny models/tokenizers in disposable directories and
exercises the API without external weights. `deploy/huggingface/test_space.py`
checks the public middleware and deployment contracts with local fixtures.
The large Qwen and TTT checkpoints are not bundled; their checkpoint-dependent
integration tests use the repository's existing skip conditions. These skips
must be reported rather than treated as evidence of backend coverage. No datasets
or private session state are bundled. Prefer tiny locally generated fixtures for
reproducers. Use a fresh `/tmp` artifact store for each destructive test.

## Reports

Send reports privately to the configured primary contact. Include the source
commit, affected deployment/configuration, attacker prerequisites, exact input,
minimal offline reproducer, expected/actual result and demonstrated impact.
Provide a minimal patch and regression test where possible. Deduplicate reports
by root cause, retaining distinct reachable entry points in the same report.

Prioritize arbitrary code execution, arbitrary file access or mutation, and
bypasses of hosted controls. Severity should follow demonstrated attacker reach
and impact; distinguish trusted-local prerequisites from unauthenticated remote
reachability, and explain resource assumptions for denial-of-service findings.
