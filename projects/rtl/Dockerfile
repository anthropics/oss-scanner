# syntax=docker/dockerfile:1
FROM node:22.23.4-bookworm

ENV NG_CLI_ANALYTICS=false \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_AUDIT=false

COPY . /src
WORKDIR /src

# --legacy-peer-deps is required: plain `npm ci` fails on an ERESOLVE conflict from
# @fortawesome/angular-fontawesome. Dev dependencies are kept so TypeScript, the Angular
# toolchain and the test runners are available offline.
RUN npm ci --legacy-peer-deps

# Compile server/ (TypeScript) into backend/, which is what rtl.js and the backend tests load.
RUN npm run buildbackend

# Backend regression tests (node:test, no network, no browser). Report failures without
# failing the build.
RUN npm run testbackend || echo "WARNING: backend tests reported failures"
