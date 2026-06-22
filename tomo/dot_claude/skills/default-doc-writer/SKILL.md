---
name: default-doc-writer
description: Use PROACTIVELY when the user asks Tomo to CREATE a free-form document and save it into the vault — an overview, list, summary, comparison, collection, or any artifact that is NOT one of the defined note types (atomic note, MOC, daily note, project, source). Triggers: "create me an overview of X", "erstell mir eine Übersicht / Liste / Zusammenfassung von …", "make a list of Y and put it in my vault", "write up a comparison of Z", "save this as a note in my inbox". Renders the content into the configured default template and writes it to the inbox folder.
user-invocable: true
argument-hint: "what to create, e.g. 'an overview of the vacations I took and the events I attended'"
---
# Default Doc Writer
# version: 0.1.0

Compose a free-form document the user asked for, wrap it in the default template, and write it
to the inbox folder. Use this only for documents that do NOT fit a defined note type — defined
types are produced by `/inbox`, never here.

## Workflow

### 1. Compose the content

Produce the markdown the user asked for (the overview / list / summary / comparison) as the
document body, with whatever internal structure — headings, tables, bullet lists — fits the
request. Derive a short title from the request.

### 2. Resolve the default template into tomo-tmp

```bash
python3 scripts/read-config-field.py --field templates.mapping.default --default ""
```

If it returns a stem or path, resolve that template from the **vault** with `kado-read`
(operation: note; a bare stem via `kado-search` byName) and save its body to
`tomo-tmp/default-template.md`.

If it is empty OR the read fails, write the built-in minimal default to
`tomo-tmp/default-template.md` with the `Write` tool — verbatim:

```
---
tags:{{tags}}
---

{{body}}
```

# STRICT — the built-in fallback is materialised here, never read from a `config/templates/` path.
# Why: the built-in `t_*_tomo.md` starters live in the source repo, not the container — they are not reachable at runtime.

### 3. Render the template

Write the tokens with the `Write` tool to `tomo-tmp/default-doc-tokens.json`:

```json
{"title": "<title>", "tags": [<tags or empty>], "body": "<composed body>"}
```

Then render against the resolved template:

```bash
python3 scripts/token-render.py --template tomo-tmp/default-template.md \
  --tokens tomo-tmp/default-doc-tokens.json \
  --config config/vault-config.yaml > tomo-tmp/default-doc.md
```

# STRICT — pass tokens via the `--tokens` file, never inline `--tokens-json`.
# Why: the body is multi-line markdown; shell-quoting it inline corrupts the JSON.

Leave `tags` empty unless the user named tags — do not invent classification tags here.

### 4. Write to the inbox

```bash
python3 scripts/read-config-field.py --field concepts.inbox --default "100 Inbox/"
python3 scripts/kado-write-file.py --local tomo-tmp/default-doc.md --vault "<inbox>/<stem>.md"
```

# STRICT — build `<stem>` with `scripts/lib/obsidian_filename.sanitize_stem` from the title before `<stem>.md`.
# Why: raw titles contain `\ / : * ? " < > |`, which kado-write rejects.

### 5. Report

Tell the user the vault path the document landed at — it now sits in the inbox for later
filing via `/inbox` or by hand.

## Boundary

Write ONLY into the inbox folder. Never create defined-type notes (atomic note, MOC, daily,
project, source) — those are `/inbox` Pass-2 outputs. Never write outside the inbox.
