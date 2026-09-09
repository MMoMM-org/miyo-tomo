# WHY: dot_claude/agents/voice-transcriber.md

> Rationale for decisions in `tomo/dot_claude/agents/voice-transcriber.md`.
> The agent turns inbox audio into sibling markdown transcripts. Only
> non-obvious decisions are recorded here.

## Target Composition Follows the Audio's Own Folder, Not `<inbox_path>` (spec 034 T3.3b)

WHY: spec 034 T3.2 made inbox discovery recursive — audio files in inbox
subfolders are now discovered for the first time, alongside root-level audio.
Before T3.2 this distinction did not exist: every audio file sat at the
inbox root, so "the inbox root" and "the audio's own folder" were always the
same path, and hardcoding `<inbox_path>` in both Step 3's sibling-membership
check and Step 5's `kado-write` target happened to be correct.

T3.2 broke that assumption silently. `inbox-triage.py`'s `check_audio` was
fixed for it in T3.3 (pairs by `(folder, stem)`, not stem alone — see
`docs/tomo/scripts/inbox-triage.md`), but the voice path itself — this agent
and `voice-precheck.py` — was never swept. Three sites disagreed on where a
transcript for a subfolder audio file lives:

- `inbox-triage.check_audio` — folder-aware (fixed in T3.3).
- `voice-precheck.py` — folder-aware in its sibling-path math, but listed the
  inbox with `depth=1`, so a subfolder audio file never reached the listing
  to be checked at all.
- This agent's Step 3/Step 5 — composed every target as `<inbox_path>/...`,
  the inbox ROOT, regardless of where the source audio actually sat.

The user-visible failure: a subfolder audio file with a root-level namesake
was, before T3.3, wrongly treated as already transcribed and silently
skipped. After T3.3 alone (voice path unswept) it never pairs at all — every
`/inbox` run reports it as needing transcription, dispatches this agent,
which writes the transcript to the inbox ROOT (Step 5's old composition),
where Step 3's membership check (also rooted) still won't find it beside the
audio next run. Identical dispatch, every run — the same repeated-dispatch
shape as the historical `:`-vs-`-` infinite transcribe loop (see
`docs/tomo/scripts/lib/obsidian_filename.md` if present, or the sanitize
asymmetry note below), here caused by a folder mismatch instead of a
character mismatch.

Fix: `voice-precheck.py` drops `depth=1` from its `list_dir` call — one
listDir call either way, now recursive (see the performance note below).
This agent's Step 3 composes the membership-check target from the audio
path's OWN containing folder, and Step 5 writes both the success target and
the `.transcribe-error.md` marker to that SAME folder — sourced from the
same per-file resolution Step 3 already did, paired by index (`results[i]`
corresponds to `todo[i]`; the CLI preserves input order). `<inbox_path>` is
no longer used to build any transcript path in this agent — only to seed the
Step 2 `kado-search` call.

## A Fourth Site: Step 2's Own Discovery Was Still `depth: 1` (spec 034 T3.3b follow-up)

WHY: the first pass of T3.3b fixed Step 3 (sibling-membership target) and
Step 5 (kado-write target) to compose from the audio's own containing
folder, and fixed `voice-precheck.py`'s listDir call. It missed that this
agent does its OWN discovery in Step 2, independently of `voice-precheck.py`
— and Step 2's `listDir` call was still `depth: 1`. Folder-aware composition
in Step 3/Step 5 is moot if Step 2 never hands the agent a subfolder audio
file to act on in the first place: the chain became `check_audio` (T3.3,
folder-aware) → `voice-precheck` (fixed, folder-aware, doesn't skip
dispatch) → this agent's Step 2 (`depth: 1`, never sees the file) →
`no_audio` / nothing transcribed → identical result next run. Same
repeated-dispatch shape, moved one step along rather than closed.

Step 2's `depth: 1` was justified in the runtime file as "mirrors
`inbox-orchestrator`'s call". `inbox-orchestrator.md` was deleted under spec
018 (agent-architecture-cleanup) — retired in favour of `suggestion-
conductor` + `synthesis-conductor` — and no longer exists anywhere in this
repo. The justification was stale at the moment T3.2 made discovery
recursive elsewhere (`inbox-triage.py`'s own discovery call,
`client.list_dir(inbox_path)`, already dropped its depth limit for exactly
this reason). Fix: Step 2 drops `depth: 1` entirely and no longer cites a
retired agent as its justification — CON-5 forbids rationale in the runtime
file regardless, so the corrected instruction is a bare imperative.

## Full Enumeration — Every listDir / Path Composition / Membership Check in the Voice Path

WHY: recorded once, here, so a future sweep does not have to rediscover this
by hand. As of this fix, every site in the voice path is folder-aware AND
depth-unbounded:

| File | Site | Folder-aware | Depth-unbounded |
|---|---|---|---|
| `voice-precheck.py` | `client.list_dir(inbox)` | n/a (see sibling math) | ✅ (no `depth=` kwarg since this fix; `KadoClient.list_dir` defaults to unbounded recursion) |
| `voice-precheck.py` | `_expected_md_path` (sibling path math) | ✅ uses `p.parent` | ✅ (not depth-limited by construction) |
| `voice-transcriber.md` | Step 2 `listDir` (own discovery) | n/a (listing only) | ✅ (this fix — `depth: 1` dropped) |
| `voice-transcriber.md` | Step 3 (sibling-membership target) | ✅ audio's own folder (T3.3b) | ✅ (downstream of Step 2; correct now that Step 2 is unbounded) |
| `voice-transcriber.md` | Step 5 (`kado-write` target, success + `.transcribe-error.md`) | ✅ audio's own folder (T3.3b) | ✅ (writes are not depth-limited at all — this axis never applied here) |
| `voice-transcribe.py` | none — the CLI does no discovery | n/a | n/a — it receives explicit vault-relative paths as argv and never lists a directory |
| `voice-transcribe.py` | `entry["target"] = f"{target_stem}.md"` | intentionally NOT folder-aware — a bare filename by design | n/a |

`voice-transcribe.py`'s bare-filename `target` is deliberate, not a gap: the
CLI has no opinion on vault layout, and the split described in Step 5 (the
CLI sanitises the filename; the agent — which already knows each audio
file's own folder from Step 3 — supplies the folder) is the intended
division of labour. `inbox-triage.py`'s `check_audio` (a separate file, not
part of the voice-transcriber/voice-precheck/voice-transcribe trio audited
here) was already fixed under T3.3 and remains folder-aware and
depth-unbounded.

## The `sanitize_stem` Asymmetry Is Preserved, and Is Independent of This Fix

WHY: only the derived `.md` target is sanitised (`sanitize_stem`); the source
audio filename is never touched. Obsidian already forbids
`\ / : * ? " < > |` and null in note names, while a recorder produces them
freely (e.g. a timestamp like `14:30`). Symmetrising this — sanitising the
audio side too, or dropping sanitisation entirely — previously caused an
infinite transcribe loop on exactly a raw `:` vs `-` mismatch. This fix
touches WHERE the target is composed (which folder), never WHAT the target's
filename looks like — the asymmetry is orthogonal and stays exactly as it
was, at every folder depth.

## `voice-precheck.py`'s Recursive Listing Is Still a Single Call

WHY: `voice-precheck.py` exists purely to avoid a ~17k-token agent dispatch
when there is nothing to transcribe. Dropping `depth=1` in favour of Kado's
default (`depth=None`, unbounded recursion) does not add a second listDir
call — `precheck()` still calls `client.list_dir(inbox)` exactly once; it is
the SAME call with a different depth argument, not an additional one. The
recursive listing can return more items than a flat one in a deep vault, but
comparing that single listDir round-trip against a ~17k-token agent boot is
still the same order-of-magnitude win the script was built for. If a vault's
inbox tree ever grows large enough that the recursive listDir itself becomes
the expensive step, that is a distinct concern from this fix (T3.3b only
closes the correctness gap) and would need its own measurement.
