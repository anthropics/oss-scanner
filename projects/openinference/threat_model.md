# Threat model — OpenInference

## What this project does and where untrusted input enters
OpenInference is a set of OpenTelemetry instrumentation libraries and semantic conventions for AI applications, in
Python (`python/`), JavaScript/TypeScript (`js/`), Java (`java/`) and Go (`go/`). Each instrumentor wraps an LLM or
agent SDK (OpenAI, Anthropic, LangChain, LlamaIndex, Bedrock, MCP, ...) inside the user's own process and turns calls,
inputs, outputs, tool calls and errors into span attributes that are exported to a tracing backend (often Phoenix).

There is no server. Untrusted input reaches the code as data flowing through the instrumented application:
- prompts, messages, tool arguments and documents from end users of the instrumented app;
- responses, streamed chunks, tool calls and errors returned by LLM providers, MCP servers and other remote services;
- context propagated in from other services (OpenTelemetry/W3C baggage and trace context, MCP request metadata).

## What we care about
- **Leaking secrets or redacted data into telemetry.** API keys, auth headers, client credentials or other secrets
  captured into spans; and the masking controls (`TraceConfig` / `OPENINFERENCE_HIDE_*` env vars, e.g. hiding inputs,
  outputs, messages, images or embeddings) failing to hide what they promise to hide.
- **Breaking or subverting the host application.** Instrumentation must be transparent: it must not change the
  result the wrapped SDK returns, swallow or alter exceptions, consume a stream the caller expects to read, or crash or
  hang the application on malformed provider responses or attacker-shaped input (e.g. unbounded recursion or memory
  while serialising deeply nested or cyclic objects).
- **Code execution or injection from data**: unsafe deserialisation, `eval`, prototype pollution in the JS packages,
  or similar paths where traced data becomes code or config.
- **Context propagation**: attacker-supplied baggage/headers or MCP metadata that can spoof session/user IDs, inject
  attributes, or cause unbounded attribute growth.

## Components that matter most / least
- Most: the shared core (`python/openinference-instrumentation`, `js/packages/openinference-core`), masking/config,
  attribute serialisation helpers, context propagation (including the MCP instrumentors), and the most widely used
  instrumentors (OpenAI, Anthropic, LangChain, LlamaIndex, Bedrock, Vercel AI SDK).
- Less: semantic-convention constant packages, examples, docs, and `spec/`.
- Out of scope: vulnerabilities in the third-party SDKs being instrumented, unless OpenInference makes them reachable
  or worse; the tracing backend that receives spans (report Phoenix issues against Phoenix).

## How to exercise it
- Python: each package under `python/` has its own `.venv` in this image with test requirements installed, e.g.
  `cd python/instrumentation/openinference-instrumentation-openai && .venv/bin/pytest tests`. Tests use recorded HTTP
  fixtures (respx/vcrpy) and an in-memory span exporter, which is the easiest way to write a reproducer.
- JavaScript: `cd js && pnpm --filter <package> test` (vitest).
- Java: `cd java && ./gradlew --offline test`. Go: `cd go/<module> && go test ./...`.

## How we rate severity
- Critical: code execution in the instrumented application from traced data.
- High: secrets (API keys, credentials, auth headers) exported in spans by default, or masking settings that silently
  fail to hide the data they are configured to hide; a crafted provider response or user input that crashes or hangs
  any application using the instrumentor.
- Medium: instrumentation altering return values/exceptions/streams in a way with security impact, spoofable session
  or user attribution, unbounded memory growth needing sustained input.
- Low: issues only reachable by the application developer configuring the library, or affecting only tests/examples.

## Anything to leave alone
- Capturing prompts and responses is the intended behaviour when masking is not configured; it is not a leak by itself.
- Dependency CVEs with no reachable path through OpenInference code.
