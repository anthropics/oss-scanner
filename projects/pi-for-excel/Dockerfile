FROM node:24-bookworm

# The bridges can run Python, tmux commands and LibreOffice conversions.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates git openssl python3 python3-venv tmux libreoffice-calc \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: keep the checkout, dependencies and build in /src.
COPY . /src
WORKDIR /src
RUN npm ci --include=dev \
    && npm run build

# Download Chromium and its system dependencies while networking is available.
# The browser tests intercept external requests and can then run offline.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN ./node_modules/.bin/playwright install --with-deps chromium

# Run tests in the offline shell rather than hiding failures during the build.
CMD ["bash"]
