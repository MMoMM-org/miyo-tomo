---
name: kado-write-patterns
description: "Use PROACTIVELY when WRITING, composing, or uploading artifacts to the vault — .md notes, .base files, .canvas files, frontmatter updates, token-rendered templates. Triggers when the task involves writing to the inbox, composing artifacts, rendering templates, or updating note frontmatter. (Read, list, and query operations → kado-discovery-patterns.)"
user-invocable: true
model: sonnet
effort: low
---
# Kado Write Patterns
# version: 0.1.0

Write-side helper catalog. Read/list/query operations are in kado-discovery-patterns.

## Write a .md Note

```bash
python3 scripts/kado-write-file.py \
  --local tomo-tmp/rendered.md \
  --vault "100 Inbox/2026-06-28_note-title.md"
```

`.md` target → `operation=note` (UTF-8 text). Stdin variant:

```bash
python3 scripts/kado-write-file.py --vault "100 Inbox/my-note.md" < tomo-tmp/rendered.md
```

## Write a Non-.md Artifact (.base / .canvas)

Run the parse gate first (exit 1 = malformed — STOP, do not write):

```bash
python3 scripts/validate-json.py tomo-tmp/staged-artifact.base
# exit 0 → proceed; exit 1 → surface error, recompose
```

Then write:

```bash
python3 scripts/kado-write-file.py \
  --local tomo-tmp/staged-artifact.base \
  --vault "100 Inbox/my-view.base"
```

Non-`.md` target → `operation=file` (base64). Same pattern for `.canvas`.

## Collision Check (--no-overwrite)

```bash
python3 scripts/kado-write-file.py --no-overwrite \
  --local tomo-tmp/staged-artifact.base \
  --vault "100 Inbox/my-view.base"
```

Exit codes:
- `0` — written successfully
- `1` — Kado error
- `2` — I/O or argument error
- `3` — vault path already exists; stdout: `EXISTS:<vault-path>`

On exit 3 → warn the user and AskUserQuestion (overwrite / rename / cancel). To overwrite, re-run without `--no-overwrite`.

## Update Note Frontmatter

Write a script to `tomo-tmp/update_fm.py` then run it:

```python
# tomo-tmp/update_fm.py
import sys
sys.path.insert(0, 'scripts')
from lib.kado_client import KadoClient, KadoConcurrencyError

client = KadoClient()
result = client.write_frontmatter(
    "100 Inbox/note.md",
    {"tomo.state": "approved"},
    mode="merge",           # deep-merge: untouched keys survive
)
print(result["modified"])   # int timestamp for concurrency guard
```

```bash
python3 tomo-tmp/update_fm.py
```

For concurrent-safe updates, pass `expected_modified=<timestamp from prior read>`:

```python
result = client.write_frontmatter(
    path,
    {"tomo.state": "done"},
    mode="merge",
    expected_modified=prior_modified,
)
```

`KadoConcurrencyError` → surface to user; retry after re-reading the note.

## Render a .md Template (token-render.py)

```bash
python3 scripts/token-render.py \
  --template tomo-tmp/template.md \
  --tokens tomo-tmp/tokens.json \
  > tomo-tmp/rendered.md
```

Tokens file is a JSON object: `{"title": "My Note", "tags": ["type/note/normal"], ...}`.

Inline tokens JSON (skip file write):

```bash
python3 scripts/token-render.py \
  --template tomo-tmp/template.md \
  --tokens-json '{"title": "My Note", "uuid": "20260628120000"}' \
  > tomo-tmp/rendered.md
```

Exit 0 = success, stdout = rendered content. Exit 1 = required token unresolvable.

## Resolve Config Fields (read-config-field.py)

Single field:

```bash
python3 scripts/read-config-field.py --field concepts.inbox
# → "100 Inbox/"

python3 scripts/read-config-field.py --field templates.mapping.default --default ""
```

Batch (saves tool calls):

```bash
python3 scripts/read-config-field.py \
  --fields concepts.inbox,profile,templates.mapping.atomic_note
# → one key=value per line

python3 scripts/read-config-field.py \
  --fields concepts.inbox,profile \
  --format json
```

Exit 1 if `--field` is used and the field is missing with no `--default`. With `--fields`, missing fields are silently omitted.

## Sanitise a Stem (obsidian_filename.py)

Apply to the **stem only** — then append the extension separately:

```bash
# CLI (for agent shell-outs):
python3 scripts/lib/obsidian_filename.py "memo 11:48:29"
# → memo 11-48-29
```

```python
# Python import (for scripts):
from lib.obsidian_filename import sanitize_stem
vault_path = sanitize_stem(raw_stem) + ".base"  # NOT sanitize_stem(raw_stem + ".base")
```

Replaces Obsidian-forbidden characters (`\ / : * ? " < > |`) with `-`. Idempotent.
