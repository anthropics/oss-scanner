# syntax=docker/dockerfile:1
# Match the GCC 16 / Ubuntu 24.04 toolchain used by Knuth CI.
FROM kthnode/gcc16-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 python3-pip python3-venv cmake ninja-build pkg-config \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/knuth-tools
ENV PATH="/opt/knuth-tools/bin:${PATH}"
RUN python3 -m pip install --no-cache-dir "conan>=2,<3" kthbuild

# Keep sources, fixtures, dependencies and build products for offline investigation.
COPY . /src
WORKDIR /src
RUN conan profile detect --force \
    && conan config install -t dir /src/ci_utils/.conan \
    && conan remote update conancenter --url=https://center2.conan.io \
    && conan install conanfile.py --version=0.0.0 -of build --build=missing \
         -pr:b linux-ci-cd -pr:h linux-ci-cd \
         -o march_id=ZLm9Pjh -o tests=True -o consensus=False \
         -o rpc=jsonrpc -o with_websocket=True

# Production native validator, JSON-RPC, WebSocket transport and C API.
# Retain debug symbols and frame pointers without changing dependency build types.
RUN cmake --preset conan-release \
      -DGLOBAL_BUILD=ON -DENABLE_TEST=ON -DKTH_CI_TEST_SHARDS=2 \
      -DCMAKE_VERBOSE_MAKEFILE=OFF -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
      -DCMAKE_C_FLAGS_RELEASE="-O2 -g -DNDEBUG -fno-omit-frame-pointer" \
      -DCMAKE_CXX_FLAGS_RELEASE="-O2 -g -DNDEBUG -fno-omit-frame-pointer" \
    && cmake --build --preset conan-release --parallel 2 --target \
         node-exe c-api kth_infrastructure_test kth_domain_test \
         kth_network_test kth_blockchain_test kth_node_test kth_capi_test

# Prove the core suites can run with no external network during image creation.
RUN --network=none ctest --test-dir build/build/Release --output-on-failure -j1 \
      -R '^kth_(infrastructure|domain|network|blockchain|node|capi)_test[.]shard-'

CMD ["bash"]
