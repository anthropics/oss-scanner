# OSS Scanner build for Waybar (https://github.com/Alexays/Waybar).
#
# Waybar is a C++20 GTK3 status bar for Wayland compositors. This builds two configurations, both with
# every optional module force-enabled (the same feature set as upstream's `build-full` CI job):
#
#   /src/build       gcc, debugoptimized, the `waybar` binary and the Catch2 unit tests.
#   /src/build-asan  gcc, ASan + UBSan + _GLIBCXX_ASSERTIONS, like upstream's `smoke` CI job.
#
# sway, grim and jq are installed so the end-to-end smoke tests in test/smoke/ can run the real
# binary inside a headless compositor.
FROM debian:sid
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential g++ meson ninja-build pkg-config cmake scdoc python3 \
      gdb valgrind file xxd jq \
      catch2 \
      gobject-introspection libgirepository1.0-dev \
      libdbusmenu-gtk3-dev libepoxy-dev libevdev-dev libfftw3-dev libfmt-dev \
      libgps-dev libgtk-3-dev libgtk-layer-shell-dev libgtkmm-3.0-dev libhowardhinnant-date-dev \
      libiniparser-dev libinput-dev libjack-jackd2-dev libjsoncpp-dev libmm-glib-dev \
      libmpdclient-dev libnl-3-dev libnl-genl-3-dev libpipewire-0.3-dev libplayerctl-dev \
      libpulse-dev libsigc++-2.0-dev libsndio-dev libspdlog-dev libsystemd-dev systemd-dev \
      libudev-dev libupower-glib-dev libwayland-dev libwireplumber-0.5-dev \
      libxkbcommon-dev libxkbregistry-dev wayland-protocols \
      sway grim imagemagick fonts-dejavu-core dbus dbus-x11 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Every optional feature forced on, so a module whose dependency is missing fails the build instead of
# being silently skipped. Meson subprojects (libcava) are downloaded here, while the network is up.
ARG WAYBAR_OPTIONS="-Dcpp_std=c++20 -Dexperimental=true -Dman-pages=disabled -Dlibcxx=false \
      -Dlibinput=enabled -Dlibnl=enabled -Dlibudev=enabled -Dlibevdev=enabled -Dpulseaudio=enabled \
      -Dupower_glib=enabled -Dpipewire=enabled -Dmpris=enabled -Dsystemd=enabled \
      -Ddbusmenu-gtk=enabled -Dmpd=enabled -Drfkill=enabled -Dsndio=enabled -Dlogind=enabled \
      -Dtests=enabled -Djack=enabled -Dwireplumber=enabled -Dcava=enabled -Dgps=enabled \
      -Dwwan=enabled -Dniri=true -Dmango=true -Dlogin-proxy=true"

# 1) Reference build: waybar and the unit tests.
RUN meson setup /src/build /src $WAYBAR_OPTIONS \
      --buildtype=debugoptimized \
      -Dcpp_args="-g -fno-omit-frame-pointer" \
    && meson compile -C /src/build -j "$(nproc)"

# 2) Sanitizer build. The subprojects fetched by the first setup are reused from subprojects/.
RUN meson setup /src/build-asan /src $WAYBAR_OPTIONS \
      --buildtype=debug \
      --wrap-mode=nodownload \
      -Db_sanitize=address,undefined \
      -Db_lundef=false \
      -Dcpp_args="-g -O1 -fno-omit-frame-pointer -fno-sanitize-recover=undefined -D_GLIBCXX_ASSERTIONS" \
    && meson compile -C /src/build-asan -j "$(nproc)"

# Run the unit tests so we know the image works, without letting a failing test abort the build.
RUN (meson test -C /src/build --print-errorlogs --suite waybar || echo "WARNING: meson test reported failures") \
    && (LSAN_OPTIONS="suppressions=/src/asan.supp" meson test -C /src/build-asan --print-errorlogs --suite waybar \
        || echo "WARNING: meson test (asan) reported failures")
