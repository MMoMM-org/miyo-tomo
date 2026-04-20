# XDD 010 — Spike Findings

## T1.1 — fileSuggestion exit-code + stdout shape

**Date**:
**Claude Code version** (from Tomo status line):
**Tester**:

### Case A — exit 0 + three valid paths
- Typed: `@CASE_A`
- What the picker renders:
- What's inserted on selection:
- Claude Code behaviour after insertion:
- Verdict:

### Case B — exit 0 + empty stdout
- Typed: `@CASE_B`
- What the picker renders:
- Any "no results" affordance?:
- Verdict:

### Case C — exit 1 + valid paths
- Typed: `@CASE_C`
- What the picker renders:
- Fallback to Claude Code built-in picker? Error banner? Silent?:
- Verdict — should `file-suggestion.sh` always exit 0?:

### Case D — exit 0 + non-path text
- Typed: `@CASE_D`
- What the picker renders (full strings? truncated?):
- Behaviour on selection:
- Verdict — can we use non-path lines for hints (e.g. FORBIDDEN notice)?:

### Case E — exit 0 + mixed valid + non-path
- Typed: `@CASE_E`
- What renders for `(this is a hint, not a path)`:
- What happens if user picks the `... + N more` synthetic line:
- Verdict — is the "... + N more (type to filter)" F4 idea viable?:

### Overall decisions (fold into spec README Decisions Log)

- Always exit 0:
- Synthetic hint lines:
- Non-path line fate:
- Follow-up questions for T1.2 / T1.3:

---

## T1.2 — active-note suffix marker

*Pending — run `prep-t1-2.sh` when T1.1 is closed out.*

---

## T1.3 — kado-open-notes path format

*Pending — see README for the direct-curl recipe.*
