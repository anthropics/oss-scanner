# ABOUTME: OSS Scanner build image for redash_query, a Ruby CLI and client for the Redash API.
# ABOUTME: Installs gems online so the offline audit can run the Minitest/WebMock suite.
FROM ruby:4.0.5-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Every gem the tests need must be installed here; the audit runs without network access.
RUN bundle install

# Run the suite so the image is known to work, without letting a failing test abort the build.
RUN bundle exec rake test || echo "WARNING: rake test reported failures"
