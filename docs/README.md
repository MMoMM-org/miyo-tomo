# Documentation

Tomo is an AI-assisted PKM workflow runner for Obsidian. It runs inside a Docker container, talks to your vault through [MiYo Kado](https://github.com/MMoMM-org/miyo-kado)'s MCP server, and proposes every change for you to review before any vault file changes. This site covers installation, configuration, day-to-day usage, and troubleshooting.

## Overview

Tomo is for Obsidian users who want AI assistance with inbox triage, MOC linking, frontmatter, and daily-log entries — without giving an AI direct write access to their vault. The container is the sandbox; Kado is the gatekeeper; you remain the one who applies changes.

The documentation is organised around the user journey:

- **First-time install** → start with [Installation](installation.md), then walk through the [Setup Guide](setup.md).
- **Running more than one instance** → each instance is self-contained under `~/MiYo/Tomo/<name>/`; see [Installation → Multiple instances](installation.md#multiple-instances) and [Setup → Create new vs. update an existing instance](setup.md#create-new-vs-update-an-existing-instance).
- **Configuring your vault** → see [Configuration](configuration.md) for the four-layer config model and what each setting controls.
- **Running Tomo day-to-day** → see [Usage](usage.md) for `/inbox`, `/explore-vault`, `/execute`, and the launcher reference.
- **Stuck or seeing errors** → [Troubleshooting](troubleshooting.md) covers common failure modes.

## Documentation map

- [Installation](installation.md) — prerequisites, install command, verify, update
- [Setup Guide](setup.md) — interactive walkthrough, launcher, post-install ops
- [Configuration](configuration.md) — where settings live; per-file reference; layer precedence; safe defaults
- [Usage](usage.md) — starting a session; common workflows; what Tomo does and doesn't change; launcher flag and slash command reference
- [Troubleshooting](troubleshooting.md) — common errors and recovery

## Quick links

- **Install for the first time** → [Installation](installation.md)
- **Stand up a second instance** → re-run `bash scripts/install-tomo.sh` and pick *create new* ([Setup](setup.md#create-new-vs-update-an-existing-instance))
- **Update an instance** → `bash scripts/update-tomo.sh --instance <name>` ([Setup → Updating an Instance](setup.md#updating-an-instance))
- **Look up what a config field does** → [Configuration → Settings reference](configuration.md#settings-reference)
- **Process my inbox** → [Usage → Process inbox items](usage.md#process-inbox-items)
- **Apply an instruction set** → run `/execute` in-session ([Usage](usage.md#common-workflows))
- **Re-authenticate Claude Code** → run `claude login` inside the container ([Setup → Authentication](setup.md#authentication))
