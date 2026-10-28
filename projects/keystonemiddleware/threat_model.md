# Threat model

## What this project does and where untrusted input enters

keystonemiddleware is the authentication middleware other OpenStack services
use on an incoming request. Treat that request as untrusted. This
repository is not the Keystone server.

## Components that matter most / least

The middleware that authenticates a request matters most. Documentation
and examples are out of scope.

## How to exercise it

From `/src`, with no network:

```sh
/opt/venv/bin/tox -e py3 --skip-env-install
/src/.tox/py3/bin/python -m keystonemiddleware.echo
```

Echo listens on port 8000 with `auth_token`. The other paste filters are
`oauth2_token`, `oauth2_mtls_token`, `external_oauth2_token`, and `audit`.

## How you rate severity

A failure of authentication or authorization is critical. Disclosure of
secrets is high. Denial of service is medium.

## Reports

A minimal patch plus a unit test is enough.
