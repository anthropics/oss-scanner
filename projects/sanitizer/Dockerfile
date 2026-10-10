FROM php:8.5-cli-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git curl unzip python3 python3-selenium \
      chromium chromium-driver libonig-dev \
    && docker-php-ext-install -j"$(nproc)" mbstring \
    && echo 'memory_limit=1G' > /usr/local/etc/php/conf.d/oss-scanner.ini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Scanner contract: build with the Sanitizer checkout as context, at /src.
COPY . /src
WORKDIR /src

# Install development tools and the legacy HTML5 parser while online.
RUN composer update --no-interaction --prefer-dist --no-progress

# Run the repository's browser harness and check its result, including its
# unsanitized execution controls. The browser and all dependencies are local.
RUN <<'SH'
set -eu
cat > /usr/local/bin/scanner-browser <<'SCRIPT'
#!/bin/sh
set -eu
cd /src
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT HUP INT TERM
php tests/browser.php > "$work/input.html"
timeout 180s python3 - "$work/input.html" <<'PY'
import json
import sys
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

options = webdriver.ChromeOptions()
options.binary_location = '/usr/bin/chromium'
for flag in ('--headless', '--no-sandbox', '--disable-dev-shm-usage',
             '--no-first-run', '--no-default-browser-check'):
    options.add_argument(flag)
with webdriver.Chrome(service=Service('/usr/bin/chromedriver'), options=options) as browser:
    browser.get(Path(sys.argv[1]).resolve().as_uri())
    result = WebDriverWait(browser, 120).until(lambda driver: driver.execute_script(
        "const text = document.getElementById('result')?.textContent;"
        "return text && text !== 'Running' ? text : null;"
    ))
    data = json.loads(result)
print(json.dumps(data))
sys.exit(0 if data.get('passed') is True else 1)
PY
SCRIPT
chmod +x /usr/local/bin/scanner-browser
SH

# Preserve the environment for investigation if a project check fails.
RUN vendor/bin/phpunit || echo 'WARNING: PHPUnit reported failures'
RUN vendor/bin/phpstan analyze --no-progress --debug || echo 'WARNING: PHPStan reported failures'
RUN scanner-browser || echo 'WARNING: browser checks reported failures'
