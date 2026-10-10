FROM node:lts-trixie

WORKDIR /src
COPY . .

# Generic tools
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates make git wget tar curl && \
    rm -rf /var/lib/apt/lists/*

# Pnpm
RUN npm install -g pnpm@11.1.2

# Go
RUN wget https://go.dev/dl/go1.27.2.linux-amd64.tar.gz
RUN rm -rf /usr/local/go && tar -C /usr/local -xzf go1.27.2.linux-amd64.tar.gz
RUN rm -rf go1.27.2.linux-amd64.tar.gz
ENV PATH=$PATH:/usr/local/go/bin
RUN go version

# Deps
RUN make deps

# Test to ensure build is working
RUN make webui
RUN make test
RUN make clean-webui
