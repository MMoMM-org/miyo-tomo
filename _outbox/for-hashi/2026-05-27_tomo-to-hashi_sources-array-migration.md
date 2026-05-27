---
from: tomo
to: hashi
date: 2026-05-27
topic: "BREAKING: doc-frontmatter source_* keys replaced by sources[] array"
requires_action: true
status: pending
supersedes: 2026-05-21_tomo-to-hashi_state-driven-cleanup-schema-lock.md (Step 2 iteration contract)
---

# BREAKING: doc-frontmatter sources[] array replaces source_* keys

Shipped in 018-P1 T1.2 (commit 1246daf, 2026-05-26).

## What changed

**Old (F-47, superseded):**
```yaml
tomo:
  source_suggestions: "100 Inbox/2026-05-26_suggestions.md"
  source_moc_proposal: "100 Inbox/2026-05-27_moc-proposal-pkm-moc.md"
```
Pattern: `patternProperties: ^source_[a-z_]+$` — one string key per upstream doc type.

**New (018, current):**
```yaml
tomo:
  sources:
    - path: "100 Inbox/2026-05-26_suggestions.md"
      checksum: "sha256:abc123..."
    - path: "100 Inbox/2026-05-27_moc-proposal-pkm-moc.md"
      checksum: "sha256:def456..."
```
Typed array with `path` (required) and `checksum` (optional, `sha256:<hex64>`).

## Why

- `source_*` keys required Hashi to pattern-match frontmatter keys — fragile
- Array is easier to iterate and extend
- `checksum` enables drift detection (did the upstream doc change after synthesis?)

## Impact on Hashi

### Cleanup contract (was F-47 handoff Step 2)

**Old iteration:**
```typescript
for (const [key, path] of Object.entries(tomo)) {
  if (key.startsWith("source_")) { trash(path); }
}
```

**New iteration:**
```typescript
for (const source of tomo.sources ?? []) {
  trash(source.path);
}
```

### Checksum (optional, not required for v0.1)

If present, Hashi MAY compare `checksum` against a SHA-256 of the source doc's current content to detect drift. Drift = warn user, don't block execution.

## Schema

See `tomo/schemas/doc-frontmatter.schema.json` — sources array definition.
See `tomo/schemas/instructions.schema.json` — unchanged (instructions.json top-level has its own `source_suggestions` string, which is a different field and NOT affected by this change).
