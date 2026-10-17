FROM rocker/r2u:noble

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-dev build-essential git curl ca-certificates \
      r-cran-jsonlite r-cran-dplyr r-cran-rlang r-cran-plm r-cran-lmtest \
      r-cran-sandwich r-cran-aer r-cran-car r-cran-broom r-cran-forecast \
      r-cran-vars r-cran-urca r-cran-tseries r-cran-cluster r-cran-rpart \
      r-cran-randomforest r-cran-ggplot2 r-cran-gridextra r-cran-readxl \
      r-cran-openxlsx r-cran-base64enc r-cran-reshape2 r-cran-knitr \
      r-cran-nortest r-cran-testthat r-cran-styler r-cran-lintr \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /uvx /bin/

COPY . /src
WORKDIR /src
RUN uv sync --frozen --group dev --all-extras --python /usr/bin/python3 \
    && rmcp --version \
    && Rscript -e 'stopifnot(requireNamespace("jsonlite"), requireNamespace("ggplot2"), requireNamespace("forecast"))'

CMD ["bash"]
