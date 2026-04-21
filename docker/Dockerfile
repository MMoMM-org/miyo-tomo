# MiYo Tomo Docker image
# Based on Kouzou secure variant — ClamAV + security hooks for vault data safety.
# version: 0.2.0
#
# Build: docker build -t miyo-tomo:latest ./docker/
#        Optional: --build-arg VOICE_ENABLED=1 for XDD 009 Whisper support.
# Run:   see begin-tomo.sh

FROM node:22-bookworm-slim AS base

# System dependencies
# - ffmpeg: always installed; needed by faster-whisper for decoding audio
#   (m4a/mp3/ogg/opus/aac/flac). ~60 MB footprint is acceptable overhead
#   for the voice feature opt-in path to stay ergonomic.
# - python3-pip: only strictly required by the conditional faster-whisper
#   install below, but small enough to always include.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    jq \
    zsh \
    ripgrep \
    fd-find \
    fzf \
    # jq + fzf are required by .claude/scripts/file-suggestion.sh (XDD 010)
    python3 \
    python3-pip \
    python3-yaml \
    ffmpeg \
    ca-certificates \
    locales \
    && rm -rf /var/lib/apt/lists/*

# ── Voice transcription (XDD 009) ───────────────────────────
# faster-whisper + ctranslate2 are a ~200 MB runtime; install only when
# VOICE_ENABLED=1 is passed as a build arg. When disabled (default), the
# pip step is a no-op and the image stays lean. Model files are NOT baked
# in — they live on the host under $INSTANCE_PATH/voice/models/ and are
# bind-mounted at /tomo/voice at runtime.
ARG VOICE_ENABLED=0
RUN if [ "$VOICE_ENABLED" = "1" ]; then \
      pip install --break-system-packages --no-cache-dir \
        "faster-whisper>=1.0,<2" ; \
    fi
VOLUME ["/tomo/voice"]

# Locale — use C.UTF-8 (built-in, no locale-gen needed)
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TERM=xterm-256color

# Suppress Claude Code's "switched to native install" prompt,
# skip auto-update checks, and disable the autoupdater entirely.
# npm is the only install method in Docker — native installer doesn't apply.
ENV DISABLE_INSTALLATION_CHECKS=1 \
    DISABLE_AUTOUPDATER=1

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Pin to the new init flow so the CLI doesn't nag about migration.
ENV CLAUDE_CODE_NEW_INIT=true

# Non-root user — remove pre-existing UID 1000 (node) to keep the 1000 convention
# for host/container UID matching on Linux hosts.
RUN (userdel -r node 2>/dev/null || true) && \
    useradd -m -s /bin/zsh -u 1000 coder
USER coder
WORKDIR /home/coder

ENTRYPOINT ["/home/coder/entrypoint.sh"]
CMD ["claude"]
