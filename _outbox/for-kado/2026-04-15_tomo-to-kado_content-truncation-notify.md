---
from: tomo
to: kado
date: 2026-04-15
topic: Please notify Tomo when kado-read content truncation ships
status: pending
priority: low
requires_action: true
---

# Please notify Tomo when `kado-read` content truncation ships

## What Changed

Tomo's `/inbox` pipeline now fans out per-item classification to parallel
`inbox-analyst` subagents (spec 004, shipped 2026-04-15, commit `be7a4b8`).

Each subagent reads one inbox note via `mcp__kado__kado-read` (operation:
`note`). Current per-item context sits at ~18 KB tokens, comfortably under
the 80 KB target.

For very long inbox items (>5,000 words), the full-note read inflates context.
Marcus mentioned that Kado has a future feature on the roadmap: partial /
truncated reads (something like `max_chars` or `first_n_words` on
`kado-read`).

## Why

Truncated reads would let Tomo:
- Read only the first N characters or first section of large notes during
  classification
- Drop per-subagent context by another 3-5 KB in the long-tail case
- Classify large notes without forcing a full download through SSE

## Impact on Kado

None — this is a follow-up request on an already-scheduled Kado feature.

## Action Required

When the content-truncation feature ships in Kado:
1. **Send Tomo a handoff** (`_outbox/for-tomo/`) with the new flag name, the
   semantics (character count? word count? first section?), and any caveats.
2. Tomo will update `inbox-analyst.md` to use the flag for the initial pass
   (full read only when classification is ambiguous and more context helps).

No action needed right now — this is a watchlist entry so Kado knows Tomo
is a downstream consumer that will adopt the feature promptly.

## References

- Tomo fan-out spec: `docs/XDD/specs/004-inbox-fanout-refactor/solution.md`
- Current `kado-read` usage: `scripts/lib/kado_client.py:102` (read_note)
