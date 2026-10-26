# Threat model

## What this project does and where untrusted input enters

keystoneauth is the client library other projects use to authenticate to
OpenStack. Treat data received over the network as untrusted. This
repository is not the Keystone server.

## Components that matter most / least

The authentication plugins matter most. Documentation is out of scope.

## How to exercise it

Unit tests, from `/src`, with no network. `--skip-env-install` reuses
`/src/.tox/py3` and does not download packages.

```sh
/opt/venv/bin/tox -e py3 --skip-env-install
```

This repository is a library. It has no service to start, and the tests do
not need a running Keystone.

## How you rate severity

A failure of authentication or authorization is critical. Disclosure of
secrets is high. Denial of service is medium.

## Reports

A minimal patch plus a unit test is enough.
