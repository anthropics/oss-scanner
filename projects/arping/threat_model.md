# Threat model

## What this project does and where untrusted input enters

Sends and receives raw packets on the network. Read packets are untrusted.

## Components that matter most / least

Parsing of received packets.

## How to exercise it

`tests/run` and `tests/run-rootless` contain "golden" tests from which other
tests can be derived.

## How you rate severity

RCE based on received packets is highest. Users may suid the binary, so command
line parsing or other environment based RCE are second highest.

Arping replies causing DoS could cause wider outages if arping is used to
prevent duplicate address or load balancer failover, so DoS based on untrusted
packets read off the network are higher than command line DoS is normally.

## Anything to leave alone

Any problem is in scope.
