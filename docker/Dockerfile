# MiYo Tomo Docker image
# Based on Kouzou secure variant — ClamAV + security hooks for vault data safety.
# version: 0.3.0
#
# Build: docker build -t miyo-tomo:latest ./docker/
#        Optional: --build-arg VOICE_ENABLED=1 for XDD 009 Whisper support.
# Run:   see begin-tomo.sh

FROM node:22-bookworm-slim AS base

# Base system dependencies — present in every image regardless of features.
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
    python3-yaml \
    ca-certificates \
    locales \
    && rm -rf /var/lib/apt/lists/*

# ── Voice transcription (XDD 009, opt-in) ───────────────────
# ffmpeg (~60 MB), python3-venv, and faster-whisper/ctranslate2 (~200 MB)
# are all installed ONLY when VOICE_ENABLED=1. Reviewer finding M3:
# ffmpeg has a long CVE history (heap overflows in demuxers); keeping it
# out of text-only images reduces attack surface. Reviewer finding M4:
# a venv under /opt/voice-venv avoids `pip install --break-system-packages`,
# which would otherwise let pip shadow distro-managed packages (certifi,
# urllib3, etc.). The drift-detection label/build-arg pattern in
# begin-tomo.sh auto-rebuilds on voice toggle, so opt-out is ergonomic.
#
# Model files are NOT baked in — they live on the host under
# $INSTANCE_PATH/voice/models/ and are bind-mounted at /tomo/voice at runtime.
ARG VOICE_ENABLED=0
RUN if [ "$VOICE_ENABLED" = "1" ]; then \
        apt-get update && apt-get install -y --no-install-recommends \
            ffmpeg \
            python3-venv \
        && rm -rf /var/lib/apt/lists/* \
        # --system-site-packages: voice-transcribe.py and other Tomo
        # scripts still need access to apt-installed python3-yaml etc.
        # The venv layers faster-whisper + ctranslate2 on top without
        # shadowing distro-managed packages.
        && python3 -m venv --system-site-packages /opt/voice-venv \
        && /opt/voice-venv/bin/pip install --no-cache-dir --upgrade pip \
        && /opt/voice-venv/bin/pip install --no-cache-dir \
            "faster-whisper>=1.1,<1.3" ; \
    fi

# Export PATH entry for the voice venv so `python3 scripts/voice-transcribe.py`
# resolves to the venv's interpreter when voice is enabled. Harmless when
# voice is disabled (the dir simply doesn't exist).
ENV PATH="/opt/voice-venv/bin:${PATH}"

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
