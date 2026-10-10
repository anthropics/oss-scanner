# Pion DTLS threat model

## Scope

Pion DTLS is a Go library implementing DTLS 1.2 and 1.3, used mainly in WebRTC
and IoT applications. Audit both versions on `main`, including experimental code.
Applications supply configuration, credentials, trust stores, and callbacks.

Peers control incoming datagrams, handshake messages, certificates, extensions,
tickets, and encrypted records. Consider unauthenticated attackers and malicious
authenticated peers, including spoofed, replayed, reordered, and truncated UDP
packets. Assume local configuration and callbacks are trusted. A finding should
show a failure to enforce the configured security policy.

## Audit priorities

- **Parsing:** length checks, integer overflow, fragmentation, reassembly, and
  allocation limits in `pkg/protocol` and `internal/fragmentbuffer`.
- **Handshakes:** transcript integrity, certificate and Finished verification,
  downgrade protection, PSK binders, and DTLS 1.3 resumption in `internal/flight` and
  `internal/handshake`.
- **Record protection:** nonce uniqueness, epochs, sequence numbers, key updates,
  replay protection, and authentication before plaintext delivery in
  `internal/ciphersuite` and `internal/state`.
- **Resource use and routing:** cookie validation, amplification, buffering,
  retransmission, connection IDs, and validation of peer-address changes.
- **Connection lifecycle:** panics, deadlocks, goroutine leaks, and unbounded
  resource use during concurrent reads, writes, shutdown, and deadline handling.

## Testing

The image contains the checkout at `/src`, Go 1.27, cached Go dependencies.
Tests use local sockets and run without Internet access.

```sh
cd /src
export GOPROXY=off GOSUMDB=off

go build ./...
go test -count=1 -timeout=10m ./...
go test -race -count=1 -timeout=15m ./...
go test ./pkg/protocol/handshake -run='^$' \
  -fuzz='^FuzzDtlsHandshake$' -fuzztime=60s
```


## Findings

Prioritize authentication bypasses, confidentiality or integrity failures,
key or nonce reuse, and remote process crashes. For denial of service, describe
the required access, traffic volume, resource amplification, and whether the
impact affects one connection or the whole process. Packet loss and a peer
closing its own connection are expected behavior.

Include the affected protocol version and configuration, entry point, and
demonstrated impact. Provide a minimal reproducer, preferably a deterministic
Go regression test.
