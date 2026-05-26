---
name: instructions-coverage
description: Use PROACTIVELY when synthesis-conductor needs to determine which approved docs to process. Covers sources[] field semantics, coverage computation, and drift indicator handling.
user-invocable: false
---
# Instructions Coverage
# version: 0.1.0

## Sources Field

Instructions docs carry a `sources` array in their tomo frontmatter:

```yaml
tomo:
  doc_type: instructions
  state: pending-apply
  sources:
    - path: "100 Inbox/<date>_suggestions.md"
      checksum: "sha256:<hex64>"
```

Each entry records which upstream doc was consumed to produce this instructions doc.

## Coverage Computation

A source doc is "covered" when its vault-relative path appears in any existing instructions doc's `sources[].path` field.

The triage script pre-computes coverage:
- `routing-plan.approved_suggestions` contains only UNCOVERED approved docs
- Already-covered docs are excluded before the routing plan reaches the conductor

Do not recompute coverage — trust the routing plan.

## Drift Indicators

`routing-plan.drift_indicators` entries:

```json
{"path": "...", "type": "checksum_mismatch", "detail": "..."}
```

Drift indicators are non-blocking: process the doc but surface the warning to the user.

| type | meaning |
|------|---------|
| `checksum_mismatch` | cached body hash differs from the instructions' recorded checksum |
| `orphaned_state` | frontmatter state does not match any known path |
| `missing_source` | referenced source path no longer exists in vault |
