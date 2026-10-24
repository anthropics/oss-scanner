FROM python:3.12-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      default-jre-headless git expect fish zsh \
    && rm -rf /var/lib/apt/lists/*

# The scanner supplies the public project checkout as the build context.
COPY . /src
WORKDIR /src
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r requirements/dev.txt -e . \
    && python -m pip check

# Core tests need no external service. Optional plugins have separate environments.
# Run after building: docker run --rm --network none IMAGE python -m pytest -q
CMD ["bash"]
