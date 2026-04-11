# MiYo Tomo Docker image
# Based on Kouzou secure variant — ClamAV + security hooks for vault data safety.
# version: 0.1.0
#
# Build: docker build -t miyo-tomo:latest ./docker/
# Run:   see begin-tomo.sh

FROM node:22-bookworm-slim AS base

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    jq \
    zsh \
    ripgrep \
    fd-find \
    fzf \
    python3 \
    python3-yaml \
    ca-certificates \
    locales \
    && rm -rf /var/lib/apt/lists/*

# Locale — use C.UTF-8 (built-in, no locale-gen needed)
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TERM=xterm-256color

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Non-root user — remove pre-existing UID 1000 (node) to keep the 1000 convention
# for host/container UID matching on Linux hosts.
RUN (userdel -r node 2>/dev/null || true) && \
    useradd -m -s /bin/zsh -u 1000 coder
USER coder
WORKDIR /home/coder

ENTRYPOINT ["/home/coder/entrypoint.sh"]
CMD ["claude"]
