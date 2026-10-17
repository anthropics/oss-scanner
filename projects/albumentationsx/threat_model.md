# AlbumentationsX threat model

## Project and trust boundaries

AlbumentationsX is the maintained Python image-augmentation library in the Albumentations ecosystem. It transforms images, masks, bounding boxes, keypoints, videos, and 3D volumes in training and preprocessing pipelines. The distribution is `albumentationsx`; the Python import is `albumentations`. This enrollment covers the AlbumentationsX repository on `main`.

Applications can pass data from external datasets or user uploads: NumPy arrays, PyTorch tensors, annotations, shapes, dtypes, and metadata. An attacker may control those values without controlling the Python program that calls the library. Look for vulnerabilities that cross this boundary, including unsafe native calls, unintended file access, and resource exhaustion with a practical attacker-controlled trigger.

Pipeline parameters and JSON/YAML configurations are normally chosen by the application owner. Applications may also load configurations obtained from third parties, including the optional Hugging Face Hub integration. Review `load`, `from_dict`, `ReplayCompose`, and `HubMixin` for unsafe deserialization, unexpected class resolution, path handling, or code execution. State whether exploitation requires a third-party configuration to be loaded, an attacker-controlled dataset to be processed, or application code to be changed.

Custom Python transforms, `Lambda` callables, and application-provided reader callbacks are executable application code. AlbumentationsX does not sandbox them. Executing a callable deliberately supplied by the application is expected behavior; a way for data alone to introduce or invoke arbitrary code is a security finding.

## Components to prioritize

- `albumentations/core/`: composition and replay, serialization, validation, bounding-box and keypoint handling, Hub integration, and analytics configuration and transport.
- `albumentations/augmentations/` and `albumentations/pytorch/`: input handling and calls into NumPy, OpenCV, SciPy, PyTorch, and albucore, especially shape, dtype, stride, indexing, and allocation boundaries.
- `pyproject.toml`, package manifests, and `.github/`: package contents and release automation. Check whether untrusted pull requests or other external inputs can execute with secrets or write access, or affect published artifacts.

Third-party libraries are separate projects. Report a dependency issue here when an AlbumentationsX call path exposes it, and identify the responsible package and version. Hosted websites, commercial services, and downstream applications are outside this repository's scope.

## Build and offline tests

The Dockerfile puts the checkout at `/src` and installs its editable package, locked CI test dependencies, CPU PyTorch, headless OpenCV, and the optional Hub dependency. The virtual environment is on `PATH`. All test fixtures are in the checkout; no model weights, external datasets, credentials, or GPU are needed. Network access is disabled during scanning. Telemetry and live Hub requests are disabled by environment variables; Hub network behavior can be tested with mocks.

Run a focused set of existing tests first:

```bash
cd /src
python -m pytest -q --hypothesis-profile=ci-fast \
    tests/test_core.py tests/test_core_utils.py \
    tests/test_serialization.py tests/contracts/test_composition_serialization_contracts.py \
    tests/test_hub_mixin.py tests/test_pytorch.py tests/transforms3d/test_pytorch.py
```

The full suite is available with the same dependencies:

```bash
python -m pytest -n 2 --dist=worksteal --hypothesis-profile=ci-fast
```

Use `tests/files/`, `tests/contracts/`, `tests/property/`, and `tests/regression/` for existing fixtures and invariants. Reproducers should call the public API on small synthetic inputs wherever possible.

## Severity and reports

Rate severity from the demonstrated impact and deployment preconditions. Arbitrary code execution, arbitrary file writes, or disclosure of sensitive files or credentials through attacker-controlled data are high or critical when the exploit path supports that rating. For memory-safety issues, show the reachable call path and distinguish a crash from a controlled corruption primitive.

Resource exhaustion is relevant when a small or otherwise practical malicious input causes disproportionate CPU time or memory use in a plausible service deployment. Include input size, elapsed time, peak memory, and whether the process can recover. Ordinary allocation proportional to a caller-requested large image, validation errors, and incorrect augmentation results should not be assigned a security severity without a concrete additional impact.

Send findings privately to the primary contact. Include the source revision, dependency versions, affected public API, attacker-controlled input, exact reproduction command, observed impact, and a proposed patch and regression test when available. Keep patches focused and preserve existing API behavior, validation, and test coverage. Follow the repository's `SECURITY.md` for reporting and disclosure.
