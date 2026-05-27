---
from: tomo
to: kado
date: 2026-05-20
topic: Add kado-write operation=frontmatter patch-op (no full-body rewrite)
status: done
status_note: Design accepted (merge default, arrays replace, body byte-identical, server normalises closing newline). Queued without ETA — reply: _outbox/for-tomo/2026-05-20_kado-to-tomo_kado-write-frontmatter-ack.md. Shipped-notice will follow when op lands.
priority: normal
requires_action: true
---

# Request: `kado-write operation=frontmatter` patch-op

## What Changed

Tomo is starting **F-47 Tomo Lifecycle Tags** (spec `017-tomo-lifecycle-tags/` in tomo). The refactor introduces frequent state-transitions across all Tomo-produced docs via a hierarchical lifecycle tag `#tomo/<doc-type>/<state>` plus a structured `tomo:` frontmatter block (`doc_type`, `state`, `run_id`, `updated_at`). Every state promotion is a **frontmatter-only** mutation — body content stays untouched.

The current Kado MCP surface (`tomo/scripts/lib/kado_client.py`) exposes:

| Op | Endpoint | Reads/Writes |
|---|---|---|
| `kado-read` `operation=note` | full markdown | body + frontmatter |
| `kado-read` `operation=frontmatter` | parsed YAML | frontmatter only ✅ (added pre-0.7.0) |
| `kado-write` `operation=note` | full markdown | body + frontmatter (overwrite) |
| `kado-write` `operation=file` | base64 | non-`.md` files |

**Gap**: there is no symmetric `kado-write operation=frontmatter`. Today, mutating a single frontmatter field requires a full read_note → in-memory string-edit → full write_note round-trip. `tag-captured.py:131-177` already implements this pattern via brittle regex edits on the YAML block — Tomo memory `feedback_frontmatter_newline_guard.md` flags a class of bugs this approach creates (missing trailing newline before `---`, regex collisions when the user has unusual YAML formatting, etc.).

## Why

F-47 will perform frontmatter-only state transitions on every Tomo-produced doc, multiple times per workflow cycle:

- `tag-captured.py` flips source items `pending → captured` (existing path; could migrate to new op)
- `state-promoter` (new in F-47) flips `pending-approval → approved`, `pending-accept → accepted`, etc.
- `vault-executor` flips `pending-apply → applied` when an instruction set finishes

At steady state this means ~5–15 frontmatter mutations per `/inbox` run today. With the lifecycle-tag refactor it will grow to ~15–30 mutations across all Tomo doc-types. A native `kado-write operation=frontmatter` op would:

1. **Eliminate the body-bytes round-trip** — instructions docs are 30–80 actions, ~1500–4000 tokens of body. Today every state flip moves that volume through Kado twice (read + write). Estimated saving: 60–80% of write-path Kado bandwidth on Tomo's hot path.
2. **Replace the regex-edit pattern** with a server-side parse-merge-serialize that handles edge cases (multi-line YAML values, lists, indentation, trailing newlines) correctly. Resolves `feedback_frontmatter_newline_guard.md` failure mode at the Kado layer.
3. **Reduce write-conflict surface** — narrower write target = smaller window for optimistic-concurrency rejection on busy docs.

## Impact on Kado

**Suggested API shape** (mirrors existing `kado-read operation=frontmatter`):

```http
POST /mcp  (kado-write tool)
{
  "operation": "frontmatter",
  "path": "100 Inbox/2026-05-20_1359_suggestions.md",
  "frontmatter": {
    "tomo": {
      "state": "approved",
      "updated_at": "2026-05-20T15:42:17Z"
    },
    "tags": ["#tomo/suggestions/approved", "#topic/knowledge/lyt"]
  },
  "mode": "merge",
  "expectedModified": "<iso8601 from prior read>"
}
```

**Semantics to nail down on your side**:

- `mode: "merge"` (default): deep-merge supplied keys with existing frontmatter — preserves untouched fields. `mode: "replace"`: overwrite entire frontmatter block with supplied dict.
- `tags` field: array semantics (replace) vs. `+tag`/`-tag` directives for set operations. Tomo's lifecycle is replacement-style (current `#captured` → `#active`) so simple array-replace is sufficient for our case. We can do client-side set arithmetic if needed.
- Body content (everything after the closing `---`) MUST stay byte-identical. Confirm in tests.
- Optimistic concurrency: `expectedModified` matches existing semantics on `kado-write operation=note` — reject with 409-equivalent if mtime drifted.
- Newline handling at the YAML closing fence: server-side fix is the whole point — produce a single trailing `\n` after `---` regardless of input shape.
- Error cases: file missing → 404; not `.md` → 400; frontmatter parse failure on existing file → return parsed-as-empty + supplied dict, or error? (Suggestion: error and require user to fix.)

**Compatibility**: pure additive. Existing `operation=note` callers unaffected. Old Tomo versions keep working with the full-body write.

## Action Required

1. **Decide on the API contract** (especially the `mode: merge|replace` default and the `tags` array semantics — see questions above). Reply via `_inbox/from-tomo/` or comment on this handoff.
2. **Add `operation=frontmatter` to the `kado-write` MCP tool** in the Kado plugin. Should be smaller scope than `operation=note` since you reuse the same path-ACL + capability gate + audit-log machinery.
3. **Release as Kado 0.8.0** (or whichever minor — additive feature). Once released, Tomo's `kado_client.py` will add a `write_frontmatter(path, frontmatter_dict, mode, expected_modified)` method that wraps it.
4. **Audit log entry shape**: same as `kado-write operation=note`, with a flag/marker that the body wasn't touched (helpful for users auditing which writes were content vs. metadata-only).

**Priority**: **not blocking F-47 launch**. F-47 will ship using the full read+write round-trip as fallback. This handoff is requesting the optimization that lets F-47's state-promotion path collapse from "read body + mutate string + write body" into a single targeted call — improves both performance and correctness (replaces the regex-edit class of bugs).

**Timing**: when Kado has bandwidth. F-47 implementation will land in Tomo over the next 1–2 weeks; we'll switch to the new op as soon as it's released. If you can land it within that window, F-47.P1 can use it directly; otherwise F-47 ships with the fallback and a follow-up Tomo PR swaps in `write_frontmatter` later.

## References

- Tomo spec **017-tomo-lifecycle-tags** — `docs/XDD/specs/017-tomo-lifecycle-tags/README.md` (PRD in progress; this handoff is research-phase output)
- Tomo F-47 backlog entry — `docs/XDD/backlog.md` row F-47
- Tomo memory — `feedback_frontmatter_newline_guard.md` (the brittle-regex YAML-edit failure mode this op removes)
- Today's kado-write call sites for full-body mutation that would benefit:
  - `tomo/scripts/tag-captured.py:96-184` (lifecycle tag application — regex YAML edit)
  - `tomo/scripts/lib/kado_client.py:135` (existing `read_frontmatter` op — symmetry argument)
- Symmetric existing op: `kado-read operation=frontmatter` (parsed YAML, no body) — proven pattern on the read side, same semantics on write makes the API consistent
