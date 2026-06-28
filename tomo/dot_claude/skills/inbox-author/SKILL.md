---
name: inbox-author
description: "Use PROACTIVELY when the user asks Tomo to CREATE a free-form artifact and save it into the vault — overview, list, summary, comparison, compiled log, a .base view, or a .canvas. Composes correct format (via obsidian-markdown/bases/canvas) and writes to the inbox. NOT for defined-type notes produced by /inbox Pass-2."
user-invocable: true
model: sonnet
effort: low
argument-hint: "what to create, e.g. 'an overview of my 2025 trips' or 'a reading-list base'"
skills:
  - kado-write-patterns
---
# Inbox Author
# version: 0.3.0

Compose a free-form artifact the user asked for and write it to the inbox folder. Use this only
for artifacts that do NOT fit a defined note type — defined types are produced by `/inbox`, never
here.

## Workflow

### 1. Determine artifact format

Determine the target format from the user's request: **md** (default), **canvas** (explicit
request for a .canvas JSON Canvas diagram), or **base** (explicit request for a .base Bases view).
Derive a short title from the request.

### 2. Resolve the template (md path only)

*Skip for .canvas and .base — they are composed directly without a template.*

Resolve `requested_type` against the known schema keys:
`atomic_note`, `map_note`, `daily`, `weekly`, `monthly`, `yearly`, `project`, `source`, `default`.

**Known key:**

```bash
python3 scripts/read-config-field.py --field templates.mapping.<requested_type> --default ""
```

If stem is non-empty, resolve the template body from the vault via `kado-read`
(operation: note; bare stem via `kado-search` byName) and save to `tomo-tmp/default-template.md`.
On empty stem or read failure: fall back to the built-in minimal default and tell the user
`"template <type> unset/missing — used built-in default"`.

**Unknown type:**

`kado-search byName` in the templates folder for a matching format. If found, save to
`tomo-tmp/default-template.md`. If not found: use built-in minimal default and tell the user
`"no type-specific template found — used the default/inbox template"`.

**Built-in minimal default** — write with the `Write` tool to `tomo-tmp/default-template.md`, verbatim:

```
---
tags:{{tags}}
---

{{body}}
```

# STRICT — the built-in fallback is materialised here, never read from a `config/templates/` path.
# Why: the built-in `t_*_tomo.md` starters live in the source repo, not the container — they are not reachable at runtime.

### 3. Compose the artifact

**For .md:**

Produce the markdown body (overview / list / summary / comparison) with whatever internal structure
fits the request. Write the tokens with the `Write` tool to `tomo-tmp/default-doc-tokens.json`:

```json
{"title": "<title>", "tags": [<tags or empty>], "body": "<composed body>"}
```

Render:

```bash
python3 scripts/token-render.py --template tomo-tmp/default-template.md \
  --tokens tomo-tmp/default-doc-tokens.json \
  --config config/vault-config.yaml > tomo-tmp/staged-artifact.md
```

# STRICT — pass tokens via the `--tokens` file, never inline `--tokens-json`.
# Why: the body is multi-line markdown; shell-quoting it inline corrupts the JSON.

Leave `tags` empty unless the user named tags — do not invent classification tags here.

**For .canvas:**

Compose the JSON Canvas content (guided by `obsidian-canvas`). Write with the `Write` tool to
`tomo-tmp/staged-artifact.canvas`, then gate:

```bash
python3 scripts/validate-json.py tomo-tmp/staged-artifact.canvas
```

If exit code is non-zero: STOP — surface the parse error and offer to recompose. Do NOT write.

**For .base:**

Compose the Obsidian Bases YAML content (guided by `obsidian-bases`). Write with the `Write` tool
to `tomo-tmp/staged-artifact.base`, then gate:

```bash
python3 scripts/validate-yaml.py tomo-tmp/staged-artifact.base
```

If exit code is non-zero: STOP — surface the parse error and offer to recompose. Do NOT write.

### 4. Write to the inbox

```bash
python3 scripts/read-config-field.py --field concepts.inbox --default "100 Inbox/"
python3 scripts/kado-write-file.py --no-overwrite \
  --local tomo-tmp/staged-artifact.<ext> \
  --vault "<inbox>/<stem>.<ext>"
```

# STRICT — build `<stem>` with `scripts/lib/obsidian_filename.sanitize_stem` from the title; append `.<ext>` separately.
# Why: raw titles contain `\ / : * ? " < > |`, which kado-write rejects; applying sanitize_stem to a name that includes the dot mangles the extension.

If exit code is 3 and stdout contains `EXISTS:<vault-path>`: warn the user and use
`AskUserQuestion` — options: overwrite / rename / cancel. On "overwrite" re-run without
`--no-overwrite`. On "rename" prompt for a new title and restart from step 3. On "cancel" stop.

### 5. Report

Tell the user the vault path the document landed at — it now sits in the inbox for later
filing via `/inbox` or by hand.

## Boundary

Write ONLY into the inbox folder. Never create defined-type notes (atomic note, MOC, daily,
project, source) — those are `/inbox` Pass-2 outputs. Never write outside the inbox.
