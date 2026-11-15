# syntax=docker/dockerfile:1
# OSS Scanner build for CoolProp (https://github.com/CoolProp/CoolProp).
#
# One out-of-tree build of the checkout with clang and CoolProp's own "Asan" build type
# (-O2 -g -fsanitize=address -fno-omit-frame-pointer, CMakeLists.txt COOLPROP_ASAN):
#
#   /src/build-asan/CatchTestRunner    the Catch2 unit-test runner (every test in src/Tests)
#   /src/build-asan/libCoolProp.so     the C API shared library (include/CoolProp/CoolPropLib.h), the interface
#                                      the Excel, Julia, Rust, Fortran and LabVIEW wrappers call
#   /usr/local/bin/coolprop-driver     a small stdin-driven C program over that C API (source below), for
#                                      reproducers: PropsSI, HAPropsSI, AbstractState, add_fluids_as_JSON
#
# The build is -O2 rather than -O0 on purpose: several suites build dense SVD tables and crawl unoptimized.
# CMake fetches the pinned third-party dependencies (Eigen, nlohmann_json, valijson, msgpack-c, fmt, Catch2,
# IF97, REFPROP-headers, boost-headers, multicomplex) through CPM at configure time, while the network is up.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 cmake ninja-build clang libclang-rt-18-dev llvm gdb locales \
    && sed -i 's/^# *de_DE.UTF-8/de_DE.UTF-8/' /etc/locale.gen && locale-gen \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# detect_odr_violation=1, as in CoolProp's CI ASan job: at -O2 two identical internal-linkage arrays in the
# vendored externals/miniz-3.1.1/miniz.c are merged onto one address, which the level-2 ODR check misreports.
ENV ASAN_OPTIONS=detect_odr_violation=1 \
    CPM_SOURCE_CACHE=/opt/cpm-cache

RUN CC=clang CXX=clang++ cmake -S /src -B /src/build-asan -G Ninja \
      -DCMAKE_BUILD_TYPE=Asan -DCOOLPROP_ASAN=ON \
      -DCOOLPROP_CATCH_MODULE=ON -DBUILD_TESTING=ON \
      -DCOOLPROP_SHARED_LIBRARY=ON -DCOOLPROP_STATIC_LIBRARY=OFF \
      -DCOOLPROP_NO_EXAMPLES=ON -DCOOLPROP_USE_CCACHE=OFF \
    && cmake --build /src/build-asan -j"$(nproc)"

COPY <<'EOF' /opt/coolprop-driver/driver.c
/* Line-oriented driver over CoolProp's C API. One command per line on stdin, arguments separated by spaces
 * or tabs (so an argument cannot contain whitespace or be empty):
 *   props   <Output> <Name1> <Value1> <Name2> <Value2> <FluidString>
 *   haprops <Output> <Name1> <Value1> <Name2> <Value2> <Name3> <Value3>
 *   state   <Backend> <Fluids> <InputPair> <Value1> <Value2> <Output>    e.g. state HEOS Water PT_INPUTS 101325 300 Dmolar
 *   json    <Backend> <path-to-json-file>                               add_fluids_as_JSON with the file's contents
 *   config  <key> <value>                                               set_config_string
 * Prints exactly one line per command, flushed immediately: a number, "ok", or "<stage> error ...: <message>".
 * Lines longer than the buffer and commands with the wrong number of arguments are rejected, never run. */
#include "CoolPropLib.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAXTOK 9

static char *slurp(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    char *buf = NULL;
    long n;
    if (fseek(f, 0, SEEK_END) == 0 && (n = ftell(f)) >= 0 && fseek(f, 0, SEEK_SET) == 0) {
        buf = malloc((size_t)n + 1);
        if (buf && fread(buf, 1, (size_t)n, f) != (size_t)n) { free(buf); buf = NULL; }
        if (buf) buf[n] = '\0';
    }
    fclose(f);
    return buf;
}

static void print_value(double v) {
    char err[4096] = "";
    if (isfinite(v) && fabs(v) < 1e300) { printf("%.17g\n", v); return; }
    get_global_param_string("errstring", err, (int)sizeof err);
    printf("error %.17g: %s\n", v, err);
}

int main(void) {
    static char line[1 << 20];
    char msg[4096];
    setvbuf(stdout, NULL, _IOLBF, 0);
    while (fgets(line, sizeof line, stdin)) {
        size_t len = strlen(line);
        if (len == sizeof line - 1 && line[len - 1] != '\n') {
            int c;
            while ((c = getchar()) != EOF && c != '\n') {}
            printf("rejected: line longer than %zu bytes\n", sizeof line - 2);
            continue;
        }
        char *t[MAXTOK] = {0};
        int n = 0;
        for (char *p = strtok(line, " \t\r\n"); p; p = strtok(NULL, " \t\r\n")) {
            if (n == MAXTOK) { n = MAXTOK + 1; break; }
            t[n++] = p;
        }
        if (n == 0) continue;
        long err = 0;
        msg[0] = '\0';
        if (!strcmp(t[0], "props") && n == 7) {
            print_value(PropsSI(t[1], t[2], atof(t[3]), t[4], atof(t[5]), t[6]));
        } else if (!strcmp(t[0], "haprops") && n == 8) {
            print_value(HAPropsSI(t[1], t[2], atof(t[3]), t[4], atof(t[5]), t[6], atof(t[7])));
        } else if (!strcmp(t[0], "state") && n == 7) {
            long h = AbstractState_factory(t[1], t[2], &err, msg, sizeof msg);
            if (err) { printf("factory error %ld: %s\n", err, msg); continue; }
            AbstractState_update(h, get_input_pair_index(t[3]), atof(t[4]), atof(t[5]), &err, msg, sizeof msg);
            if (err) printf("update error %ld: %s\n", err, msg);
            else {
                double v = AbstractState_keyed_output(h, get_param_index(t[6]), &err, msg, sizeof msg);
                if (err) printf("output error %ld: %s\n", err, msg); else printf("%.17g\n", v);
            }
            AbstractState_free(h, &err, msg, sizeof msg);
        } else if (!strcmp(t[0], "json") && n == 3) {
            char *s = slurp(t[2]);
            if (!s) { printf("json error: cannot read %s as a regular file\n", t[2]); continue; }
            add_fluids_as_JSON(t[1], s, &err, msg, sizeof msg);
            if (err) printf("json error %ld: %s\n", err, msg); else printf("ok\n");
            free(s);
        } else if (!strcmp(t[0], "config") && n == 3) {
            set_config_string(t[1], t[2]);
            printf("ok\n");
        } else {
            printf("rejected: unknown command or wrong argument count\n");
        }
    }
    return 0;
}
EOF

# Build the driver and check its answers, not just that it runs: water at 300 K / 1 atm is ~996.56 kg/m3 and
# ~55317 mol/m3. Any error line, or a missing value, fails the build.
RUN clang -O1 -g -fno-omit-frame-pointer -fsanitize=address -Wall -Werror -DCOOLPROP_SHARED_LIBRARY_USE \
      -I/src/include/CoolProp /opt/coolprop-driver/driver.c -L/src/build-asan -lCoolProp -lm \
      -Wl,-rpath,/src/build-asan -o /usr/local/bin/coolprop-driver \
    && out="$(printf 'props D T 300 P 101325 Water\nstate HEOS Water PT_INPUTS 101325 300 Dmolar\n' | coolprop-driver)" \
    && echo "$out" \
    && echo "$out" | grep -q '^996\.5' && echo "$out" | grep -q '^5531[0-9]\.' && ! echo "$out" | grep -q error

# Run a fast slice of the suite as a health report for the maintainers' build log. It is deliberately NOT
# fatal: a red test on master should not stop the scanner from scanning. [!benchmark] tests are hidden by
# default but a positive tag filter pulls them back in, so they are excluded explicitly (their timing
# assertions are meaningless under ASan). The everyday "~[slow]" scope takes an hour or more under ASan.
RUN cd /src/build-asan && status=0; \
    timeout 900 ./CatchTestRunner "[FactoryOptions]~[!benchmark],[SchemaValidation]~[!benchmark],[json]~[!benchmark],[expression]~[!benchmark]" \
      || status=$?; \
    if [ "$status" = 124 ]; then echo "WARNING: CatchTestRunner smoke run timed out after 900 s"; \
    elif [ "$status" != 0 ]; then echo "WARNING: CatchTestRunner smoke run exited $status"; fi
