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
