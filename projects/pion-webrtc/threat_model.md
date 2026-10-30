# Pion WebRTC threat model

## Scope

Pion WebRTC is a Go implementation of WebRTC. Audit `main`, including experimental
code and the Pion implementations used as direct or transitive dependencies.
Dependency implementation review is explicitly in scope: inspect the resolved
`github.com/pion/*` module sources.
This includes ICE, STUN, TURN, DTLS, SRTP, RTP, RTCP, SCTP, SDP, data channels,
interceptors, and supporting Pion packages wherever used by this checkout.
Trace untrusted input across package boundaries and review both individual
protocol implementations and their integration in WebRTC.

Applications supply configuration, signaling transport, credentials, and
callbacks. Treat local application code and configuration as trusted, but remote
session descriptions, ICE candidates, network packets, media, and data-channel
messages as untrusted. Consider unauthenticated network attackers and malicious
authenticated peers, including spoofed, replayed, reordered, and truncated packets.
A finding should show a failure to enforce the configured security policy.

## Audit priorities

- **Parsing:** length checks, integer overflow, fragmentation, reassembly, and
  allocation limits in session descriptions, transport protocols, media packets,
  and data-channel messages, including the Pion dependencies that parse them.
- **Authentication and transport security:** ICE credentials and consent,
  DTLS certificate fingerprint verification, key derivation, SRTP authentication
  and replay protection, and binding negotiated identities to transports.
- **Protocol integration:** negotiation state, renegotiation, ICE restarts,
  demultiplexing, and delivery of media or data only over authorized transports.
- **Resource use:** amplification, retransmission, buffering, stream and channel
  limits, and CPU or memory exhaustion from attacker-controlled input.
- **Connection lifecycle:** panics, races, deadlocks, goroutine leaks, and resource
  cleanup during concurrent reads, writes, renegotiation, and shutdown.

## Testing

The image contains the checkout at `/src`, Go 1.27, and cached Go dependencies,
including their sources in the Go module cache (`go env GOMODCACHE`). Use those
sources for dependency review.

```sh
cd /src
export GOPROXY=off GOSUMDB=off

go build ./...
go test -count=1 -timeout=10m ./...
go test -race -count=1 -timeout=15m ./...
```

## Findings

Prioritize authentication bypasses, confidentiality or integrity failures,
key or nonce reuse, and remote process crashes. For denial of service, describe
the required access, traffic volume, resource amplification, and whether the
impact affects one connection or the whole process. Packet loss and a peer
closing its own connection are expected behavior.

