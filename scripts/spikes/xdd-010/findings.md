# XDD 010 — Spike Findings

## T1.1 — fileSuggestion exit-code + stdout shape

**Date**: 2026-04-20
**Claude Code version** (from Tomo status line): current Tomo Docker session
**Tester**: Marcus

### Case A — exit 0 + three valid paths
- Typed: `@CASE_A`
- What the picker renders:
  - README.md
  - CLAUDE.md
  - docs/XDD/README.md
- What's inserted on selection: `@README.md`
- Claude Code behaviour after insertion: tries to read README.md (file resolution succeeds)
- **Verdict**: Happy path. Picker inserts exactly the emitted path, prefixed with `@`, and Claude Code resolves it as a file reference. No prefix/suffix mangling of valid paths.

### Case B — exit 0 + empty stdout
- Typed: `@CASE_B`
- What the picker renders: nothing
- Any "no results" affordance?: none — picker simply doesn't appear
- **Verdict**: exit 0 + empty = silent no-op. Acceptable graceful-degrade state; use for scopes where Kado returns FORBIDDEN or UNAUTHORIZED without surfacing an error to the user.

### Case C — exit 1 + valid paths
- Typed: `@CASE_C`
- What the picker renders: nothing
- Fallback to Claude Code built-in picker? Error banner? Silent?: silent — no fallback, no banner, no picker. Non-zero exit = picker invisible, stdout discarded.
- **Verdict**: Claude Code does **not** fall back to its built-in picker on non-zero exit. It just shows nothing. No user-visible signal of failure. **Rule confirmed: `file-suggestion.sh` must always exit 0** — non-zero is strictly worse than exit 0 + empty (same outcome, no recovery opportunity).

### Case D — exit 0 + non-path text
- Typed: `@CASE_D`
- What the picker renders (full strings? truncated?):
  - this is not a real path
  - neither is this
  - nor this

  (all three rendered verbatim)
- Behaviour on selection: inserted as `@"this is not a real path"` — wrapped in double quotes as a string literal
- **Verdict**: Non-path text **is** selectable and renders as-is. On selection, Claude Code wraps it in double quotes and does **not** attempt file resolution. This makes non-path lines usable for synthetic hint lines (FORBIDDEN notices, "no open notes" messages), with two caveats:
  1. User **can** accidentally pick a hint → result is a quoted literal in their prompt that Claude then has to interpret; Claude will treat it as a verbatim string, not a file request.
  2. Place hints at the **bottom** of the result list to minimize accidental picks.

### Case E — exit 0 + mixed valid + non-path
- Typed: `@CASE_E`
- What renders for `(this is a hint, not a path)`:
  - README.md
  - (this is a hint, not a path)
  - CLAUDE.md
  - ... + 42 more (type to filter)

  (paths + hint + synthetic overflow line all render)
- What happens if user picks the `... + N more` synthetic line: inserted as `@"... + 42 more (type to filter)"` — quoted literal, no resolution
- **Verdict**: F4 "... + N more" synthetic line is **viable visually** but not great UX — it's selectable and inserts as a quoted literal if picked. Mitigation options:
  - Put the "... + N more" line last; users unlikely to arrow past real results intentionally.
  - Drop the synthetic line entirely and silently truncate to 15 real results; user types more to filter. Simpler, less surprising.
  - **Decision deferred to Phase 2** — both paths are viable after T1.1.

### Overall decisions (fold into spec README Decisions Log)

- **Always exit 0**: CONFIRMED. Non-zero hides the picker with no fallback and no error signal. Exit 0 + empty stdout achieves the same "hide picker" effect, but leaves room for the script to emit best-effort partial results on recoverable errors.
- **Synthetic hint lines**: VIABLE. Non-path strings render verbatim and insert as `@"..."` quoted literals (no resolution attempt). Safe for FORBIDDEN/UNAUTHORIZED user-visible notices. Must be placed at the bottom of the result list because they ARE selectable.
- **Non-path line fate**: Selection inserts `@"<verbatim-text>"`. Claude sees a literal string, not a file request. No silent failure mode — if the user picks a hint by mistake, their prompt contains a visible quoted string they can see and correct.
- **F4 "... + N more" affordance**: Technically works; decide placement + whether to ship it in Phase 2 or defer. Strong candidate for deferral — truncation-without-affordance is simpler and doesn't add a selectable non-path line.
- **Follow-up questions for T1.2 / T1.3**:
  - T1.2 prior signal (from Case D): non-path text is always quoted-literal-inserted. `path.md (active)` contains a valid path followed by a non-path suffix. Likely outcome: picker renders with suffix, insert = `@"path.md (active)"`, file resolution **fails**. T1.2 should still run to confirm and see whether Claude Code does any prefix-matching tolerance. Expected outcome: **suffix-hack rejected → position-only marker**.
  - T1.3 still required: confirm `kado-open-notes` `notes[].path` format matches what Claude Code expects for `@`-resolution (vault-relative? absolute?). No prior signal from T1.1.

---

## T1.2 — active-note suffix marker

**Date**: 2026-04-20
**Resolution**: decided without spike.

**Decision**: **Suffix-hack rejected. Position-only marker is final.**

**Evidence chain**:
- T1.1 Case D proved non-path text inserts as `@"<text>"` quoted literal.
- `path.md (active)` is a valid path followed by a non-path suffix.
- On selection, Claude Code would insert `@"path.md (active)"` — a
  quoted string literal, not a file reference.
- Consequently, Claude would not resolve the file content; the user
  would see a weird quoted literal in their prompt.

**Alternative considered**: run the spike anyway to check for prefix-
matching tolerance (Claude Code might strip the suffix before resolving).
Rejected because:
- Evidence is already consistent across Cases A + D.
- A second prep/restart cycle is costly in user time.
- Even if suffix-hack worked, it would be fragile (any Claude Code
  upgrade could silently break it).

**Consequence for Phase 2**:
- `handle_open_notes()` emits active note at stdout position 0,
  followed by other open notes in Kado's returned order.
- No in-text marker of any kind.
- UX: users infer "active" from ordering. Documentation in Tomo's
  help should state this convention explicitly.

---

## T1.3 — kado-open-notes path format

*Pending — see README for the direct-curl recipe. Run from inside the Tomo container; Kado is not reachable from the host sandbox.*
