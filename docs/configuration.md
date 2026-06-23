# Configuration

Documents Tomo's configuration surface: where settings live, what each one controls, how to change a setting safely, and which defaults to leave alone.

## Where settings live

Tomo's configuration lives almost entirely inside your instance directory — the Docker bind-mount that holds agents, scripts, and config. Each instance is self-contained under a parent you chose at install (default `~/MiYo/Tomo/`), laid out as `<parent>/<name>/{begin-tomo.sh, tomo-install.json, instance/, home/}`. The config files described below live under that instance's `instance/` directory (shown as `tomo-instance/` in the paths below).

Two pieces sit at the instance root, one level above `instance/`: `tomo-install.json` (install state, written before the container exists) and `begin-tomo.sh` (the launcher). One more lives in your home directory: the instance registry `~/.tomo/instances.json` (see [tomo-install.json and the instance registry](#tomo-installjson--host-side-install-state)).

Files split into four groups by who manages them.

### User-edited config

These are the files you change to shape Tomo's behaviour:

- **`tomo-instance/config/vault-config.yaml`** — vault structure, concept-to-folder mappings, frontmatter schema, tag taxonomy, callout policy, relationship markers, daily-log rules, tracker definitions. The installer writes a minimal version (profile + concepts); `/explore-vault` enriches it on first run. The complete schema is documented in `tomo/config/vault-example.yaml`.
- **`tomo-instance/config/user-rules/*.md`** — natural-language behavioural rules that don't fit YAML (tagging precedence, destination overrides, template selection). The installer creates only `README.md`; you author topic files like `tagging.md`, `destinations.md`, `templates.md` as your conventions emerge. Files are lazy-loaded by agents when relevant and referenced descriptively from the instance `CLAUDE.md`.
- **`tomo-instance/config/kado-config.md`** — human-readable record of your Kado host, port, and protocol. The bearer token is **not** stored here.

### Installer-managed (regenerated on re-install)

These are written by `install-tomo.sh` / `update-tomo.sh`. Edit the source under `tomo/` rather than the instance copy:

- **`tomo-instance/.mcp.json`** — Kado MCP server URL and bearer token. Gitignored. Re-run the installer to regenerate.
- **`tomo-instance/voice/config.json`** — voice-transcription settings, mirrored from `tomo-install.json` so in-container agents can read them. Always present (empty `{}` when voice is disabled).
- **`tomo-instance/CLAUDE.md`**, plus agents, commands, and skills under `tomo-instance/.claude/` — synced from `tomo/`.

### Framework data (read-only)

- **`tomo-instance/profiles/<name>.yaml`** — framework profiles (`miyo`, `lyt`). Copied verbatim from `tomo/profiles/`. Acts as the L2 default layer; vault-config.yaml (L3) overrides any field per the precedence rule (see [Override mechanism](#override-mechanism)).

### Generated runtime state (not config)

These live alongside config but aren't user-edited:

- **`tomo-instance/config/discovery-cache.yaml`** — output of `/explore-vault`. Acts as the L4 advisory layer; agents may consult it for hints but never use it as ground truth.
- **`<parent>/<name>/tomo-install.json`** — install state, host-side, at the instance root (next to `begin-tomo.sh`). Holds instance/launcher paths, the source repo path, vault path, profile name, Kado connection (host/port/protocol; no token), and the voice block.

## Settings reference

This is the top-level surface — one row per top-level setting per file. For vault-config.yaml the canonical leaf-field reference (every nested key, every frontmatter entry, every tracker keyword) is [`tomo/config/vault-example.yaml`](../tomo/config/vault-example.yaml) — point there rather than duplicating the schema.

### vault-config.yaml — vault structure and conventions

| Field | Default | What it controls |
|---|---|---|
| `schema_version` | `1` | Schema migration version. Tomo refuses to start if it expects a newer schema; you'll see a migration diff first. |
| `profile` | set by installer (`miyo`, `lyt`, or `custom`) | Which profile loads as the L2 baseline. Fields you omit fall back to the profile. |
| `profile_version` | matches the chosen profile | Trip-wire for profile-schema migrations. |
| `concepts` | from profile | Concept-to-folder mappings: inbox, atomic_note, map_note, calendar, project, area, source, template, asset. Override only the entries that differ. |
| `naming` | from profile | Display labels Tomo uses in proposals (`labels`) and Moment.js filename patterns per calendar granularity (`calendar_patterns`). |
| `templates` | from profile | Template file mappings per concept (`base_path` + `mapping`); optional `custom_tokens`. Tomo verifies each file exists at session start. |
| `frontmatter` | from profile | `strict` flag plus `required` / `optional` field lists. Each entry binds a YAML key to a template token, type, and default. |
| `relationships` | from profile | Parent/peer markers (e.g. `up::`, `related::`) with write rules: format, position, multi/separator. |
| `tags.prefixes` | from profile + discovery | Per-prefix tag taxonomy. Each entry has four axes: `description`, `known_values`, `wildcard`, `proposable`, `required_for`. |
| `callouts` | `enabled: true`; categories from profile | Classification of Obsidian callouts into `editable`, `protected`, `ignore`. Unlisted callouts are treated as protected. |
| `protected_patterns` | ` ```dataviewjs `, ` ```dataview `, ` ```folder-overview ` | Code-block fences Tomo never modifies. |
| `tomo.suggestions.parallel` | `5` | Maximum concurrent Phase-B subagents during `/inbox` fan-out. Range 1–5. |
| `trackers.daily_note_trackers` | empty unless authored | Tracker fields Tomo reads and proposes updates for in daily notes. Two buckets: `today_fields` and `end_of_day_fields.fields`. Each entry gives `name`, `type`, `syntax`, `description`, `positive_keywords`, `negative_keywords`. |
| `daily_log` | enabled, section `"Daily Log"` | Daily-log append rules: section heading, heading level, date-source priority, time-extraction policy, link format, cutoff days, auto-create flags. |

JSON-Schema definitions for the structured sub-sections live in `tomo/schemas/vault-config-{tags,callouts,relationships,trackers}.schema.json`.

### kado-config.md — Kado connection record

| Field | Default | What it controls |
|---|---|---|
| `Host` | from installer (Docker default: `host.docker.internal`) | Hostname Tomo uses to reach Kado. |
| `Port` | `23026` (Kado's default bind) | Port Kado is listening on. |
| `Protocol` | `http` | HTTP scheme (`http` or `https`). |

The bearer token is **not** stored here — it lives in `.mcp.json`.

### .mcp.json — MCP server registration (gitignored)

| Field | Default | What it controls |
|---|---|---|
| `mcpServers.kado.type` | `"http"` | Transport type for the MCP server. |
| `mcpServers.kado.url` | `${PROTOCOL}://${HOST}:${PORT}/mcp` | Endpoint Claude Code calls for vault operations. |
| `mcpServers.kado.headers.Authorization` | `Bearer ${KADO_TOKEN}` | Your Kado bearer token. |

Regenerated by every `install-tomo.sh` run from the values you provide.

### voice/config.json — voice transcription (mirrored from install state)

| Field | Default | What it controls |
|---|---|---|
| `enabled` | `false` | Whether the voice-transcriber agent is active. |
| `model` | `""` | Faster-whisper model directory (downloaded by `download-whisper-model.sh`). |
| `language` | `""` | Whisper language hint (ISO 639-1 code; empty = auto-detect). |
| `schema_version` | set by installer | Voice-block schema version. |

Edit the values in `tomo-install.json` (host side) and re-run `install-tomo.sh` or `update-tomo.sh` to refresh this file.

### tomo-install.json — host-side install state

Lives at the instance root, `<parent>/<name>/tomo-install.json` (next to `begin-tomo.sh`), **outside** the container. Each instance has its own.

| Field | Default | What it controls |
|---|---|---|
| `version`, `tomoVersion` | current Tomo version | Trip-wire for installer-script changes. `tomoVersion` is what the launcher compares against the source repo to decide whether to offer an update. |
| `instanceName`, `instanceLocation`, `instancePath`, `launcherPath`, `homePath` | from installer | Where the instance, launcher, and Docker home dir live on disk. `instanceLocation` is the parent dir; `instancePath` is `<parent>/<name>/instance`. |
| `repoPath` | from installer | Absolute path of the Tomo source repo this instance was installed from. Makes the instance self-describing for updates — the launcher and `update-tomo.sh --instance` resolve the source from here. |
| `vaultPath` | from installer | Absolute host path of your Obsidian vault. |
| `profile`, `profileVersion` | from installer | Profile selected at install; mirrors into `vault-config.yaml`. |
| `kado.host`, `kado.port`, `kado.protocol` | from installer | Kado connection metadata; the bearer token lives only in `.mcp.json`. |
| `voice` | `{}` | Voice block (schema_version, enabled, model, language); mirrored into `voice/config.json`. |
| `ide_bridge` | `{}` | Tomo Context block (schema_version, enabled, auth_token, port) for the Hashi IDE Bridge; drives the IDE lock file (`tomo-home/.claude/ide/<port>.lock`) and the container `socat` proxy. |
| `installedAt` | ISO 8601 UTC timestamp | When the instance was last (re-)installed. |

### instances.json — the instance registry

Lives at `~/.tomo/instances.json` (override with `TOMO_REGISTRY_FILE` for tests). It is a single index of every instance the installer has created, so install/update runs can list and resolve instances by name. It is **rebuildable**: if it's deleted, your instances still launch via their own `begin-tomo.sh`, and the next install or update re-creates the entry. A registry write failure never aborts an install or update.

```json
{
  "schema_version": 1,
  "instances": [
    {
      "name": "privat",
      "path": "/Users/you/MiYo/Tomo/privat/instance",
      "repo": "/path/to/miyo-tomo",
      "version": "0.13.0",
      "updatedAt": "2026-05-31T14:00:00Z"
    }
  ]
}
```

| Field | What it holds |
|---|---|
| `schema_version` | Registry schema version (`1`). |
| `instances[].name` | Unique instance name (the key install/update resolve against). |
| `instances[].path` | The instance's `instance/` directory; its parent is the instance root holding `tomo-install.json`. |
| `instances[].repo` | Source repo the instance was installed from. |
| `instances[].version` | Installed Tomo version, refreshed on every install/update. |
| `instances[].updatedAt` | ISO 8601 UTC timestamp of the last install/update. |

You don't edit this file by hand — install and update maintain it. Entries whose `path` directory has gone missing are flagged `[stale]` in the installer's selection menu.

### config/tag-handlers/ — tag-handler framework

| What | Detail |
|---|---|
| **Location** | `tomo-instance/config/tag-handlers/<feature>.json` — one file per handler. |
| **Who manages it** | You (via the **tomo-tag-handler-wizard** — see below). Do not hand-edit the JSON. |
| **What it does** | Tomo recognizes inbox notes that carry a registered `MiYo/<Feature>/…` tag and handles them as a group: it reads the declared frontmatter fields, merges all captures for the same target into **one** suggestion, and surfaces that suggestion in the normal Pass-1 suggestions doc for you to approve. The approved action is then applied like any other inbox action. |
| **Effect if the folder is empty** | None — a run with no registered handlers is identical to a run without the framework. |

#### What a handler controls

Each handler file declares:

- **Which tag prefix to match** — e.g. `MiYo/Tsukai/` — and which path segments after the prefix carry meaningful values (e.g. the repo name).
- **Which frontmatter fields to read** from the matched note (e.g. `category`).
- **A target note** — resolved from the captured segment values via a mapping you supply (e.g. repo name → dev-log note path).
- **A marker heading** in that target note under which the composed content is inserted.
- **A compose directive** — either a free-text instruction to the model (which synthesises all captures in the batch into one logical update) or a mechanical field list (no model call).

#### Tsukai reference handler

Tomo ships a reference handler for [Tomo Tsukai](https://github.com/MMoMM-org/miyo-tomo-tsukai) at `config/tag-handlers/tsukai.json`. It recognises `MiYo/Tsukai/<repo>` tags and routes each batch's captures to the note you map to that repo. The handler works out of the box once you fill in the repo-to-note mapping via the wizard.

#### Authoring and editing handlers

Use the **tomo-tag-handler-wizard** slash command:

```
/tomo-tag-handler-wizard
```

The wizard walks you through every field with guided questions, validates the result, and writes the handler file atomically. No manual JSON editing, no skill authoring. Run the same command again on an existing handler's tag prefix to edit it.

After adding or editing a handler, restart Claude Code in the container so agents load the updated registry.

### profiles/<name>.yaml — framework profiles (read-only)

You don't hand-edit these — choose one via `vault-config.yaml`'s `profile` field. The shipped profiles are `miyo` and `lyt` under `tomo-instance/profiles/`. Each profile defines `concept_defaults`, `classification`, and other framework defaults that act as the L2 layer beneath your vault-config.

To create a custom profile, copy an existing file, adjust, and reference it via `profile: "custom"` in vault-config.yaml.

## Override mechanism

Tomo composes its effective configuration from four layers. Higher layers win.

| Layer | Source | When to edit | Effect on lower layers |
|---|---|---|---|
| **L3 — User config** | `tomo-instance/config/vault-config.yaml`, `user-rules/*.md` | Anytime; this is your editable surface. | Wins over profile defaults. Fields you omit fall back to L2. |
| **L2 — Profile** | `tomo-instance/profiles/<name>.yaml` (`miyo`, `lyt`, or custom) | Switch via `profile:` in vault-config.yaml; or copy + edit a profile to make a custom one. | Wins over universal defaults. Vault-config (L3) overrides any field. |
| **L1 — Universal PKM concepts** | Built into Tomo's skills and agents | Not user-editable. | Lowest-level fallbacks (concept names, MOC matching, lifecycle states). |
| **L4 — Discovery cache** | `tomo-instance/config/discovery-cache.yaml` | Refreshed by `/explore-vault`. Advisory only — never used as ground truth. | Hints to agents (e.g. "this folder usually holds notes") but does not override L3/L2/L1. |

`null` in vault-config.yaml is **not** the same as omitting the field — `null` explicitly disables a setting and prevents fallback to the profile.

### How to change a setting

The edit workflow depends on which file holds the setting:

- **Vault structure or behaviour** (concepts, frontmatter, tags, callouts, trackers, daily_log, etc.) — edit `tomo-instance/config/vault-config.yaml` directly. Changes take effect at the next session start; no installer re-run needed.
- **Behavioural rules that don't fit YAML** (tagging precedence, destination overrides, template selection) — add or edit a markdown file under `tomo-instance/config/user-rules/`, then reference it descriptively from `tomo-instance/CLAUDE.md` so agents know it exists.
- **Kado connection** (host, port, protocol, bearer token) — re-run `install-tomo.sh`. Hand-editing `kado-config.md` does **not** update `.mcp.json`, and `.mcp.json` is what Claude Code actually reads.
- **Voice transcription** (enabled, model, language) — re-run `install-tomo.sh` or `update-tomo.sh`; both re-run the voice wizard and re-mirror the voice block from `tomo-install.json` into `voice/config.json`.
- **Tomo Context** (Hashi IDE Bridge — enabled, auth token, port) — re-run `install-tomo.sh` or `update-tomo.sh`; both re-run the Tomo Context wizard, rewrite the IDE lock file, and re-deliver the launcher + entrypoint that spawn the proxy. The configured port must match the port Hashi listens on.
- **Profile choice** — change the `profile` field in vault-config.yaml. The installer's profile prompt only sets the initial value; subsequent changes are file edits.
- **Managed runtime files** (agents, commands, skills, the instance `CLAUDE.md`) — don't hand-edit the instance copies; they are overwritten by `update-tomo.sh`. Edit the source under `tomo/`, bump the file's `# version:` comment, then run `update-tomo.sh`.

After any edit to vault-config.yaml or user-rules, restart Claude Code in the container so agents reload their context.

## Defaults and safe values

Tomo's defaults are tuned for the MiYo profile but most are safe across vault layouts. This section calls out what to change and what to leave alone.

### Safe to leave at the default

- **`schema_version`, `profile_version`** — Tomo manages these. You only see them when migrating.
- **`frontmatter.strict: true`** — keep on; Tomo warns when a note is missing a required field rather than silently writing malformed YAML.
- **`callouts.enabled: true`** with the profile's editable/protected/ignore split. Unlisted callouts default to protected (Tomo won't touch them).
- **`protected_patterns`** — already covers DataviewJS, Dataview, and folder-overview blocks. Add an entry only if your vault has other code-block fences Tomo must not modify.
- **`tomo.suggestions.parallel: 5`** — only lower this if your machine is constrained or you hit API rate limits.
- **`naming.calendar_patterns`** — `YYYY-MM-DD` etc. are Moment.js standard and align with the common calendar-plugin defaults.
- **`relationships.parent` (`up::`) / `relationships.peer` (`related::`)** — LYT conventions; change only if your vault uses different markers.

### You probably need to change

- **`concepts.*` folder paths** — must match your vault's actual folder structure. Profiles ship with their author's paths; run `/explore-vault` to align with what's actually in your vault.
- **`frontmatter.required` / `frontmatter.optional`** — must match the fields your note templates produce. Mismatch causes strict-mode warnings on every note write.
- **`templates.base_path` / `templates.mapping`** — must point at your real template filenames.
- **`tags.prefixes`** — populated incrementally by `/explore-vault`. Edit to mark prefixes non-`proposable` (e.g. external tags like Raindrop, Readwise).
- **`daily_log.section` / `heading_level`** — must match the heading used in your daily-note template (e.g. `# Daily Log` vs. `## Log`).

### Required — no safe default

- **Kado bearer token** (`.mcp.json`) — must match your Kado plugin's API key. The installer prompts for it.
- **`kado.host` / `kado.port`** — `host.docker.internal:23026` works for the common Docker-on-host setup; change only if Kado runs elsewhere.
- **`vaultPath`** (in `tomo-install.json`) — absolute host path of your Obsidian vault.

### Off by default — opt in deliberately

- **`voice.enabled: false`** — leave off unless you transcribe voice memos. Enabling needs `model` + `language` plus a downloaded faster-whisper model.
- **`ide_bridge.enabled: false`** — Tomo Context (live Obsidian editor context via the Hashi IDE Bridge) stays off until you enable it in the install/update wizard. Enabling needs a `hashi_<uuid>` token from Hashi and a port matching Hashi's (default `23027`). See [Setup → Tomo Context](setup.md#tomo-context--live-editor-context-optional).
- **`trackers.daily_note_trackers`** — empty unless you author tracker definitions.
- **`daily_log.auto_create_if_missing.*`** — all `false` in MVP. Leave alone unless you specifically want Tomo creating daily notes for you.

### What breaks when you get this wrong

| Misconfiguration | Symptom |
|---|---|
| Wrong vault path | Every Kado call returns a permission error; Tomo stalls at session start. |
| Wrong Kado token | MCP connection fails with 401; Claude Code reports the kado server unhealthy. |
| Concept path doesn't exist | Tomo refuses to file inbox items because the destination folder is missing. |
| `frontmatter.required` mismatch | Strict mode warns on every note write; non-strict produces malformed frontmatter silently. |
| `null` instead of omitting a field | Disables fallback to the profile — you get an unset value where a default was expected. |
