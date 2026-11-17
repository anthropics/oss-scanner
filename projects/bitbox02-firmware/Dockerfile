FROM shiftcrypto/firmware_v2:60
COPY . /src
WORKDIR /src
RUN git submodule update --init --recursive
RUN test "$(cat .containerversion)" = "60"
RUN ./scripts/bootstrap-cargo-config
RUN make -j4 unit-test
RUN make run-unit-tests
RUN cd /src/src/rust && cargo test --locked --offline --all-features -- --test-threads 1
RUN make firmware PRODUCT=bitbox02 EDITION=multi DEBUG=no
RUN make firmware PRODUCT=bitbox02 EDITION=btc-only DEBUG=no
RUN make firmware PRODUCT=bitbox02nova EDITION=multi DEBUG=no
RUN make firmware PRODUCT=bitbox02nova EDITION=btc-only DEBUG=no