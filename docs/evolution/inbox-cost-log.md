# /inbox Cost Log

Running log of token usage and estimated cost per live `/inbox` run.
Tracks cost trajectory across implementation versions to catch regressions
and validate optimizations.

**How to add an entry**: After a live run, execute from the repo root:
```bash
python3 scripts/tomo-session-stats.py --session-latest
```
Copy the output into a new row below. Note the conductor/analyst versions
from `tomo/dot_claude/agents/*.md` headers.

**Pricing**: Sonnet 4.6 list rates ($3/$15/$3.75/$0.30 per M tokens for
input/output/cache_create/cache_read). Actual billed cost may differ
(volume discounts, batch API).

---

## Log

### 2026-05-26 — Pass 1 (suggest), 18 items, batch dispatch

| Key | Value |
|-----|-------|
| **Date** | 2026-05-26 |
| **Phase** | Pass 1 (suggest) |
| **Items** | 18 fresh sources |
| **Vault** | Privat-Test |
| **Model** | Sonnet 4.6 |
| **Versions** | suggestion-conductor v0.3.0, inbox-analyst v0.12.0, inbox-triage v0.4.0, /inbox v0.10.0 |
| **Batch size** | 5 (default) |

| Metric | Main | Subagents (18) | Total |
|--------|------|----------------|-------|
| Turns | 54 | 300 | 354 |
| Input tokens | 3,224 | 351 | 3,575 |
| Cache read | 1,749,587 | 9,783,686 | 11,533,273 |
| Cache create | 100,554 | 1,326,230 | 1,426,784 |
| Output tokens | 63,394 | 62,423 | 125,817 |
| Total context | 1,752,811 | 9,784,037 | 11,536,848 |
| Peak turn ctx | 56,320 | 47,252 | — |
| **Est. cost** | **$1.86** | **$8.85** | **$10.71** |

**Per-item average**: $0.49/item (subagent only), $0.60/item (total).

**Notes**:
- First run with the 018 architecture (triage → routing plan → conductor → batch dispatch).
- Previous architecture (opus main thread + sequential dispatch) cost ~$26 for comparable item count.
- Subagents dominate cost (83%). Next optimization: reduce per-analyst context loading.
- Shared-ctx-builder ran correctly (STRICT block enforced). Batch dispatch 5-at-a-time confirmed.

---

### 2026-05-26 — Transcription stop-gate, 2 audio files (all cached)

| Key | Value |
|-----|-------|
| **Date** | 2026-05-26 |
| **Phase** | Transcribe (stop-gate, all cached) |
| **Items** | 2 audio files, both already transcribed |
| **Model** | Sonnet 4.6 (main), Haiku 4.5 (voice-transcriber) |
| **Versions** | /inbox v0.9.0, voice-transcriber v0.4.0 |

| Metric | Main | Subagents (1) | Total |
|--------|------|---------------|-------|
| Turns | 8 | 15 | 23 |
| Context | 117,301 | 190,535 | 307,836 |
| Output | 960 | 4,296 | 5,256 |
| **Est. cost** | **$0.32** | **$0.30** | **$0.62** |

**Notes**: Minimal cost — stop-gate exits immediately when all audio is cached.
