# Threat model

## What this project does and where untrusted input enters
VoiceBlender is a Go voice server. It connects SIP, WebRTC, WhatsApp, WebSocket, LiveKit and MoQ call legs into mixed rooms, and adds recording, playback, TTS/STT and AI agents. It is controlled over a REST API, a WebSocket event and command channel (VSI, `/v1/vsi`), and webhooks.

There are two trust levels:

- **Network peers are untrusted.** This covers anything that can reach the SIP listeners (UDP, TCP, TLS) or the RTP/RTCP/SRTP media ports: carriers, phones, registering clients, SIPREC peers. It also covers the remote side of a call on any leg type, because the audio and signalling they send are attacker-controlled. Untrusted input includes SIP messages and headers, SDP (including multipart bodies and SIPREC metadata), digest-auth exchanges, REGISTER handling, REFER/NOTIFY, RTP/RTCP packets, SRTP keys and packets, DTMF (RFC 4733), T.140 text, and the codec bitstreams PCMU, PCMA, G.722, Opus, AMR-NB and AMR-WB.
- **HTTP callers are trusted operators.** The REST API, VSI, `/v1/legs/websocket`, `/v1/webrtc/offer` and `/metrics` have no authentication by design. Access is controlled only by the network and the `ALLOWED_IPS` allowlist. A caller who can reach them is meant to have full control: placing calls to any destination, fetching any playback URL, sending webhooks anywhere, reading recordings.

Data returned by third parties that an operator configured is semi-trusted: TTS/STT/agent providers, S3/GCS, LiveKit, and media fetched from playback URLs (WAV/MP3 parsing). A crash or memory blow-up caused by a malformed response is in scope. The operator's choice of endpoint is not.

## Components that matter most / least
- Most important: `internal/sip` (SIP engine, SDP negotiation, inbound auth, registrar, trunks, `SIP_ALLOWED_IPS` enforcement), `internal/siprec`, `internal/codec` (decoders fed from the network), `internal/jitter`, RTP/RTCP/SRTP handling in `internal/leg`, and the media pipeline from a leg's packets to the mixer (`internal/mixer`, `internal/resampler`, `internal/audiofilter`).
- Important: the WebRTC, WhatsApp, WebSocket and MoQ legs (`internal/leg`, `internal/wsmedia`, `internal/moqmedia`); the `ALLOWED_IPS` / `TRUST_PROXY_HEADERS` gate; webhook signing; credential handling (API keys, LiveKit secret, S3/GCS keys) and whether any of them leak into logs, events or API responses.
- Lower: TTS/STT/agent integrations (`internal/tts`, `internal/stt`, `internal/agent`), playback, recording and storage upload.
- Out of scope: third-party Go modules such as sipgo, pion and quic-go (report those upstream); `tests/`, `examples/`, `docs/`, and `cmd/openapi-gen` / `cmd/asyncapi-gen`.

## How to exercise it
- The image has `/usr/local/bin/voiceblender`. It starts with defaults: HTTP on `:8080`, SIP over UDP on `127.0.0.1:5060`. Configuration is environment variables, documented in `CONFIGURATION.md`. `API.md`, `openapi.yaml` and `asyncapi.yaml` describe the control surfaces.
- Unit tests: `go test ./internal/...`.
- Integration tests run two instances over loopback SIP with no external services: `go test -tags integration -timeout 30m ./tests/integration/`. The full suite takes about 12 minutes; use `-run` to pick tests. `tests/integration/call_test.go` shows how to start an instance and place a call between two instances, which is the easiest way to deliver crafted SIP/SDP/RTP to a running server.
- Interop tests (`-tags interop`) need Docker and FreeSWITCH, so they cannot run in the scanner.

## How you rate severity
- Critical: remote code execution, or reading or forging media/signalling of other calls, reachable by an unauthenticated network peer over SIP or RTP.
- High: a crash (panic, nil dereference, out-of-range index) or unbounded memory/goroutine/CPU growth that an unauthenticated SIP or RTP peer can trigger, because one process carries every call on the instance. Also high: bypassing `SIP_ALLOWED_IPS`, `ALLOWED_IPS`, inbound digest auth, SRTP `required` policy, or the inbound REGISTER decision; leaking a configured credential to a network peer.
- Medium: a crash or resource exhaustion that needs a peer already in an established call with the victim's leg, or a malformed response from a configured third-party provider; webhook signature weaknesses; credentials written to logs.
- Low: issues that need operator-level HTTP access, or that only degrade audio quality.

## Anything to leave alone
- The HTTP API being unauthenticated, and anything an HTTP caller can do with it (SSRF through playback/webhook/S3 URLs, dialling arbitrary SIP URIs, SIPREC forking a room when `SIPREC_SRC_ENABLED=true`, minting LiveKit tokens when `LIVEKIT_TOKEN_SIGNING_ENABLED=true`). These are documented operator capabilities, not vulnerabilities, unless they bypass `ALLOWED_IPS`.
- Plain RTP or SIP over UDP being unencrypted, and SRTP keys travelling in SDP. Both are documented protocol properties.
- Settings that are documented as insecure (`SIP_TLS_INSECURE_SKIP_VERIFY`, `S3_ALLOW_INSECURE_ENDPOINT`, `TRUST_PROXY_HEADERS=true` without a proxy, `SIP_INBOUND_REGISTER_DEFAULT=accept`) doing what their documentation says.
