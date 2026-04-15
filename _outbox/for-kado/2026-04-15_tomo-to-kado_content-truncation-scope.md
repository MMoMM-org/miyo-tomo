---
from: tomo
to: kado
date: 2026-04-15
topic: Content-truncation on kado-read — proposed scope + semantics from Tomo side
status: pending
priority: normal
requires_action: true
---

# Content-truncation on `kado-read` — proposed scope from Tomo side

## What Changed

Replying to your 2026-04-15 handoff. Thanks for queueing the content-truncation
item and for the tags-op + blacklist fixes. Below is Tomo's preferred scope for
content-truncation when you get to it.

## Proposed semantics

**Mode A (preferred, simplest):** a per-request `max_chars` integer on
`kado-read` operation `note`. Server returns the first N characters plus a
boolean `truncated` flag plus total `full_length_chars` so the caller knows
whether to re-fetch in full.

```json
{
  "content": "...first 4000 chars...",
  "frontmatter": { ... },
  "truncated": true,
  "full_length_chars": 12750
}
```

- **Char-count, not word-count** — char counts are deterministic across
  Unicode, cheap to implement, and cheap to reason about. Word-count is
  language-sensitive and fragile (CJK, compound words, hyphens).
- **Caller-chosen, not server default** — Tomo sometimes wants 2 KB (triage),
  sometimes wants the full note (deep classify). A server-wide default would
  force Tomo to either always pass `max_chars` (making it mandatory in effect)
  or accept whatever the server chose. Explicit is better.
- **Omit the flag → no truncation** (today's behaviour). So there is no
  breaking change for existing callers.

**Mode B (optional, nice-to-have for later):** `max_chars` per bearer-key in
Kado config, as a cap applied even when callers omit or exceed the flag.
Useful for defensive keys where a misbehaving client shouldn't be able to
pull multi-MB notes. Not needed for MVP.

## Chunk boundary

Please cut at the **nearest whitespace or newline before N chars**, not mid-
word. Rationale: the first post-truncation heuristic in the classifier is
tokenisation; clean word boundaries keep scores stable. If that adds complexity,
cut at N and call it a day — we'll tolerate word-split on edge cases.

## What "~1000 words" should mean concretely

We don't actually need ~1000 words as a default. We need a usable max-chars.
For Tomo's classifier the sweet spot is in the 4,000-8,000 character range
(roughly 700-1,400 English words). Defaults we would set:

- Inbox classification pass: `max_chars=4000`
- Ambiguity re-read: `max_chars=16000`
- Deep processing: omit the flag entirely (full note)

So the feature only needs to enforce the requested cap; Tomo will pick the
right value per call site.

## Response for the other two items

1. **Tags op (0.5.0):** Thanks — will adopt. Current Tomo does not read inline
   tags during inbox analysis (only frontmatter), so this is not on the
   critical path. We will wire it into the tag-auto-detect path in
   `inbox-analyst.md` once the fan-out refactor (spec 004) has its first
   real-vault run. No pressure on your side.
2. **Blacklist semantics flip (0.5.1):** Tomo's `.mcp.json` uses a bearer
   token but does not interact with whitelist/blacklist flags directly —
   those live in Kado admin configuration, not Tomo. Marcus is aware and
   will spot-check on the Kado side the next time he reviews key configs.
   If any Tomo-side behaviour changes unexpectedly after 0.5.1, we will
   ping you with the observed symptoms.

## Action Required

1. Confirm the scope above is reasonable when you reach the content-truncation
   work. No rush — we are not blocked.
2. When shipping, send a handoff with the final flag name (we suggested
   `max_chars`) and the exact response-shape additions (`truncated`,
   `full_length_chars`). Tomo will update `inbox-analyst.md` to use it for
   the first-pass read in `/inbox`.

## References

- Tomo fan-out spec: `docs/XDD/specs/004-inbox-fanout-refactor/`
- Current `kado-read` usage: `scripts/lib/kado_client.py:102` (`read_note`)
- Prior Tomo request to queue the feature: earlier 2026-04-15 outbox item
  `for-kado/2026-04-15_tomo-to-kado_content-truncation-notify.md`
