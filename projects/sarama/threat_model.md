## Threat Model

Sarama is a client library for the Apache Kafka protocol and follows the trust assumptions of that protocol.

### Trusted

- The application using Sarama, including its configuration: broker addresses, TLS settings, SASL credentials and any custom dialer or proxy.
- The Kafka brokers the application connects to. Responses from a configured broker are treated as protocol messages from a trusted peer, not as untrusted input.
- Authenticated Kafka principals that the cluster permits to write to topics a Sarama consumer reads.

Transport security is the responsibility of the deployment. With TLS disabled, Sarama offers no protection against anyone on the network path, who can read or modify all traffic, including SASL credentials for some mechanisms.

### In scope

- Issues exploitable by a party outside the trust boundary above, for example someone on the network path when TLS is enabled with certificate verification.
- Defects in Sarama's TLS or SASL handling, such as not verifying certificates when the configuration requires it, or incorrect authentication behaviour.
- Sarama disclosing credentials or other secrets, for example in logs or error messages.

### Out of scope

- Resource exhaustion, panics or crashes caused by a configured broker, or by an authenticated producer with write access, sending malformed, oversized or highly compressible data. A misbehaving broker can already drop or modify messages and redirect clients, so these issues give it no new capability.
- Issues that require the application's configuration or environment to be compromised.
- Issues that require TLS to be disabled or certificate verification to be turned off.

Limits such as `MaxResponseSize` are robustness limits, not security boundaries against a trusted broker.

Out-of-scope issues may still be bugs worth fixing. Please report them in the same way, just as low severity hardening or informational issues.
