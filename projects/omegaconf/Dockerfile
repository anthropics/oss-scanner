FROM python:3.12-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      default-jre-headless git jq \
    && rm -rf /var/lib/apt/lists/*

# Java and the repository's ANTLR jar generate the parser during installation.
COPY . /src
WORKDIR /src
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r requirements/dev.txt -e . \
    && python -m pip check

# Run after building: docker run --rm --network none IMAGE python -m pytest -q
CMD ["bash"]
