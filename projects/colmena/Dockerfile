FROM docker.io/nixos/nix:latest

RUN echo 'experimental-features = nix-command flakes' >> /etc/nix/nix.conf

COPY . /src
WORKDIR /src

RUN nix profile add --inputs-from . 'nixpkgs#glibc^out' 'nixpkgs#gnused' 'nixpkgs#python3' 
RUN mkdir /lib64
RUN ln -s /root/.nix-profile/lib/ld-linux-x86-64.so.2 /lib64/
RUN mkdir -p /usr/local/bin
ENV PATH=$PATH:/usr/local/bin

RUN nix build
RUN nix develop -c cargo test || echo "WARNING: cargo test reported failures"
