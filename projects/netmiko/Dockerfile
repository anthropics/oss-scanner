FROM python:3.14-slim

RUN pip install --no-cache-dir uv

WORKDIR /src
COPY . /src

RUN uv sync --frozen
