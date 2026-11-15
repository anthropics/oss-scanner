# syntax=docker/dockerfile:1

# Builds the Strapi monorepo and runs the `examples/getstarted` dev sandbox.
#
#   docker build -t strapi-monorepo .
#   docker run --rm -p 1337:1337 strapi-monorepo
#
# The sandbox uses SQLite by default. Admin panel: http://localhost:1337/admin

FROM node:22-bookworm

# The full (non-slim) image has python3, make and g++, which native modules such as
# better-sqlite3 need when no prebuilt binary matches.
ENV NX_DAEMON=false \
    STRAPI_TELEMETRY_DISABLED=1

# Uses the yarn version in package.json ("packageManager"); .yarnrc.yml pins the release in .yarn/.
RUN corepack enable

WORKDIR /app
COPY . .

RUN --mount=type=cache,target=/root/.yarn/berry/cache \
    yarn install --immutable

# Code only: skips the .d.ts build, which `strapi develop` does not need.
RUN yarn build:code

WORKDIR /app/examples/getstarted

EXPOSE 1337

# Set DB=postgres or DB=mysql (plus the connection settings) to use another database.
CMD ["yarn", "develop"]
