# Threat model

## What this project does and where untrusted input enters

Keystone is OpenStack's identity service. Remote clients call the public
HTTP API. Treat that input as untrusted.

## Components that matter most / least

The API and the identity backend matter most. Documentation, sample
configuration, and devstack scripts are out of scope.

## How to exercise it

Unit tests, from `/src`, with no network. `--skip-env-install` reuses
`/src/.tox/py3` and does not download packages.

```sh
/opt/venv/bin/tox -e py3 --skip-env-install
```

To start the service, run this as root from `/src`. `keystone-manage` reads
`--config-file`. The WSGI process reads `OS_KEYSTONE_CONFIG_FILES`. Both
name `$ROOT/keystone.conf`.

```sh
ROOT=/tmp/ks
mkdir -p "$ROOT/fernet" "$ROOT/cred" "$ROOT/receipt"
cat > "$ROOT/keystone.conf" <<EOF
[database]
connection = sqlite:///$ROOT/keystone.db

[fernet_tokens]
key_repository = $ROOT/fernet

[fernet_receipts]
key_repository = $ROOT/receipt

[credential]
key_repository = $ROOT/cred

[cache]
enabled = false
EOF
KM=/src/.tox/py3/bin/keystone-manage
"$KM" --config-file "$ROOT/keystone.conf" fernet_setup --keystone-user root --keystone-group root
"$KM" --config-file "$ROOT/keystone.conf" credential_setup --keystone-user root --keystone-group root
"$KM" --config-file "$ROOT/keystone.conf" db_sync
"$KM" --config-file "$ROOT/keystone.conf" bootstrap \
  --bootstrap-password secret \
  --bootstrap-username admin \
  --bootstrap-project-name admin \
  --bootstrap-role-name admin \
  --bootstrap-service-name keystone \
  --bootstrap-region-id RegionOne \
  --bootstrap-admin-url http://127.0.0.1:5000/v3 \
  --bootstrap-public-url http://127.0.0.1:5000/v3 \
  --bootstrap-internal-url http://127.0.0.1:5000/v3
export OS_KEYSTONE_CONFIG_FILES=$ROOT/keystone.conf
/src/.tox/py3/bin/uwsgi --http-socket 127.0.0.1:5000 --master \
  --processes 1 --threads 1 \
  --wsgi "keystone.server.wsgi:initialize_public_application()" &
sleep 2
curl -sS -D - -o /tmp/v3.json http://127.0.0.1:5000/v3
curl -sS -D - -o /tmp/token.json \
  -H 'Content-Type: application/json' \
  -d '{"auth":{"identity":{"methods":["password"],"password":{"user":{"name":"admin","password":"secret","domain":{"name":"Default"}}}},"scope":{"project":{"name":"admin","domain":{"name":"Default"}}}}}' \
  http://127.0.0.1:5000/v3/auth/tokens
kill %1
```

The first `curl` is `GET /v3` and returns 200. The second is
`POST /v3/auth/tokens`: user `admin` and project `admin` are both in the
domain named `Default`, password `secret`. It returns 201 and sets
`X-Subject-Token`. No other OpenStack service is required.

## How you rate severity

A failure of authentication or authorization is critical. Disclosure of
secrets is high. Denial of service is medium unless it permanently corrupts
the identity database.

## Reports

A minimal patch plus a unit test is enough. A live multi-service deployment
is not required.
