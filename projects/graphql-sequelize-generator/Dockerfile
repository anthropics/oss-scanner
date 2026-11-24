# graphql-sequelize-generator (GSG): generates a GraphQL API (Apollo Server 4 + graphql-sequelize) from Sequelize models.
# Built and tested the way its CI (.github/workflows/nodejs.yml) does: yarn, yarn build, yarn test on Node 16
# (.nvmrc and CI pin 16.x; package.json engines say >=16.14.0).
FROM node:16-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    NODE_ENV=test \
    DEBUG=-*
# The full node image already has git, python3, make and g++, which sqlite3 needs if it must compile its binding
# from source, so no extra system packages are installed.

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install from the lockfile, as CI does. Install scripts stay enabled: sqlite3 (the test database driver) needs its
# native binding, which it fetches or builds at install time, so this must happen while the network is up.
RUN yarn install --frozen-lockfile --non-interactive --network-timeout 600000

# Compile src/*.ts to lib/ (the published entry point is lib/index.js).
RUN yarn build

# The jest suites start the example server in-process on a local port, against an in-memory SQLite database that
# they migrate and seed from src/tests/{migrations,seeders}, so they run without network access.
# A failing test should not abort the image build.
RUN yarn test || echo "WARNING: yarn test reported failures"
