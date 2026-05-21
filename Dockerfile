FROM debian:trixie-slim

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ansible \
        bash \
        ca-certificates \
        clang \
        curl \
        gcc \
        git \
        gnupg \
        jq \
        less \
        fd-find \
        openssh-client \
        pkg-config \
        python3 \
        python3-cryptography \
        python3-pip \
        python3-venv \
        ripgrep \
        rsync \
        sudo \
        vim \
        wget \
        xz-utils \
        zsh \
    && ln -s /usr/bin/fdfind /usr/local/bin/fd \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://antigravity.google/cli/install.sh -o /tmp/antigravity-install.sh \
    && bash /tmp/antigravity-install.sh --dir /usr/local/bin \
    && rm -f /tmp/antigravity-install.sh

RUN useradd --create-home --shell /usr/bin/zsh codex \
    && mkdir -p /workspace /nix \
    && chown -R codex:codex /workspace /nix \
    && echo "codex ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/codex \
    && chmod 0440 /etc/sudoers.d/codex

USER codex
ENV USER=codex
ENV HOME=/home/codex
ENV SHELL=/usr/bin/zsh
ENV NIX_CONF_DIR=/home/codex/.config/nix
ENV PATH=/home/codex/.nix-profile/bin:/home/codex/.local/bin:/usr/local/bin:/usr/bin:/bin
ENV NIX_PATH=nixpkgs=/home/codex/.nix-defexpr/channels/nixpkgs:nixos-unstable=/home/codex/.nix-defexpr/channels/nixos-unstable:agenix=/home/codex/.nix-defexpr/channels/agenix

RUN mkdir -p "${NIX_CONF_DIR}" \
    && printf '%s\n' \
        'experimental-features = nix-command flakes' \
        'accept-flake-config = true' \
        > "${NIX_CONF_DIR}/nix.conf" \
    && curl -fsSL https://nixos.org/nix/install | sh -s -- --no-daemon \
    && . "${HOME}/.nix-profile/etc/profile.d/nix.sh" \
    && nix-channel --add https://nixos.org/channels/nixos-unstable nixpkgs \
    && nix-channel --add https://nixos.org/channels/nixos-unstable nixos-unstable \
    && nix-channel --add https://github.com/ryantm/agenix/archive/main.tar.gz agenix \
    && nix-channel --update \
    && nix profile install \
        nixpkgs#gitleaks \
        nixpkgs#go \
        nixpkgs#nodejs_24 \
        nixpkgs#nixos-generators \
        nixpkgs#nixfmt-rfc-style \
        nixpkgs#niv \
        nixpkgs#opentofu \
        nixpkgs#pre-commit \
        nixpkgs#rustup \
        github:ryantm/agenix#agenix \
    && mkdir -p "${HOME}/.local" \
    && npm install -g --prefix "${HOME}/.local" @openai/codex@latest \
    && npm install -g --prefix "${HOME}/.local" --ignore-scripts @earendil-works/pi-coding-agent \
    && nix-collect-garbage -d

RUN printf '%s\n' \
        'export PATH="$HOME/.nix-profile/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"' \
        'export NIX_CONF_DIR="$HOME/.config/nix"' \
        'export NIX_PATH="nixpkgs=$HOME/.nix-defexpr/channels/nixpkgs:nixos-unstable=$HOME/.nix-defexpr/channels/nixos-unstable:agenix=$HOME/.nix-defexpr/channels/agenix"' \
        'export SHELL=/usr/bin/zsh' \
        'PROMPT="%n@%m:%~%# "' \
        > "${HOME}/.zshrc"

WORKDIR /workspace
ENTRYPOINT ["/usr/bin/zsh"]
