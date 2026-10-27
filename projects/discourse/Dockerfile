FROM discourse/discourse_test:release

ENV LOAD_PLUGINS=1 \
    PLAYWRIGHT_BROWSERS_PATH=/home/discourse/.cache/ms-playwright

COPY . /src
WORKDIR /src

RUN bundle config set --local path /var/www/discourse/vendor/bundle \
    && bundle config set --local deployment true \
    && bundle config set --local without development \
    && bundle install \
    && CI=1 pnpm install --frozen-lockfile \
    && pnpm playwright install --no-shell chromium ffmpeg

RUN SKIP_DB_AND_REDIS=1 bin/rake plugin:install_all_gems \
    && script/assemble_ember_build.rb
