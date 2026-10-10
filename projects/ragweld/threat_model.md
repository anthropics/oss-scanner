# Ragweld security audit

Ragweld is a self-hosted retrieval and agent platform. It combines a Python
FastAPI backend, an MCP interface, and a React/TypeScript workbench. Its ingestion
and retrieval pipelines process documents and repository content. Operator
surfaces manage configuration, model routing, evaluation, training, and traces.
The Python package and many internal identifiers still use the name `tribrid`.

## Inputs and boundaries to investigate

- Treat imported documents, repository contents, filenames, metadata, retrieved
  text, model output, and incoming HTTP/MCP arguments as potentially adversarial.
- Investigate path traversal, unsafe file handling, parser bugs, injection,
  unintended subprocess execution, SSRF, and resource exhaustion across ingestion,
  retrieval, and operator APIs.
- Investigate browser rendering of imported content and model output, including
  stored XSS and unsafe links, and handling of credentials in configuration,
  diagnostics, traces, and responses.
- State the caller's required access and the deployment assumptions for every
  finding. Distinguish a trusted administrator's documented capabilities from an
  attacker using untrusted content to reach those capabilities. Do not assume
  that a corpus identifier establishes tenant isolation or that every operator
  endpoint is intended to be publicly accessible.
- Evaluate deployment and authentication assumptions against the current source
  and deployment configuration. Documentation may contain historical descriptions
  of replaced components; trace the active implementation before reporting.

## Environment and reproduction

The checkout and its Git history are at `/src`. The image includes the locked
Python runtime and development dependencies, Flyte's optional Python dependency,
Node.js 24, frontend dependencies, Chromium, and the built frontend at `web/dist`.
The Python virtual environment is `/src/.venv` and is on `PATH`.

Useful starting commands, run from `/src`:

```sh
python -m pytest -o addopts= tests/unit/test_path_match.py tests/unit/test_config_validation.py tests/unit/test_reranker_logs_path_validation.py
npm --prefix web run test:unit
npm --prefix web run build
```

This image supports source auditing and dependency-local reproduction. It does
not launch a full production stack. PostgreSQL, Qdrant, Neo4j, LiteLLM/vLLM,
Flyte, and observability backends are separate services in normal deployments.
Provider-backed generation and evaluation require external services and cannot
be exercised against a real provider in the offline scanner. Model weights and
Docling model assets are not bundled. Apple MLX execution requires Apple
hardware; GPU model execution requires suitable hardware and model assets.
Service-dependent or model-dependent tests therefore need a separately prepared
disposable fixture. Report these limitations rather than representing a partial
test run as full-stack validation.

Use only synthetic data and disposable resources for reproducers. Do not contact
the public project website, maintainer infrastructure, real model providers, or
production stores. No production credentials or private datasets are supplied.

## Reports

Include the affected commit, file and symbol, attacker-controlled input, required
access, relevant configuration, expected versus actual behavior, a minimal
reproducer, and a focused proposed patch when possible. Explain the concrete
confidentiality, integrity, or availability impact. Distinguish an observed
exploit from a hypothesis and note unavailable prerequisites.

Group duplicate manifestations of the same root cause. Prefer findings in
Ragweld's active code or its integration of dependencies. For a dependency issue,
identify the affected locked version and a reachable Ragweld call path. Send
reports privately to the configured primary contact.
