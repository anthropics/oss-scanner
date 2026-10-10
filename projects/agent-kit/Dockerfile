# The scanner builds this image with network access, then runs its audit offline.
FROM oven/bun:1.3.14

COPY . /src
WORKDIR /src

RUN bun install --frozen-lockfile
# The demo app's Next.js build requires a live model provider key; the scanner
# builds the reusable packages without credentials.
RUN bunx nx run-many -t build --exclude=example
