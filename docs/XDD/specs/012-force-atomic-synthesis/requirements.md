# XDD 012 — Requirements (PRD)

## 1. User story

> As a Tomo user reviewing Pass 1 suggestions, when the analyst has only
> proposed a daily-log entry for an inbox item but I want an atomic note
> from it anyway, I tick **[ ] Force Atomic Note** under that log entry.
> I expect Tomo to respect this request — even if the analyst did not
> pre-propose an atomic section. It should generate the atomic proposal
> for me, show it to me, and proceed with rendering after I approve it.

## 2. Problem today

- Pass 2's `suggestion-parser.py` (commit `2665f81`) can PROMOTE an
  existing per-item atomic section when FAN is checked, but can't SYNTHESIZE
  one from nothing.
- When no per-item section exists, the parser prints a warning and moves on
  — the FAN tick is silently lost.
- The user learned this hard way in the 2026-04-23 run: "Furano" had FAN
  checked but the analyst judged worthiness too low to emit an atomic.
  Pass 2's warning told the user the atomic would not be created.
- Workarounds all hurt: lower the threshold and re-run Pass 1 (25+ items re-
  classified to fix one), edit the source by hand (loses Tomo's
  classification), or uncheck FAN (loses user intent).

## 3. Goals

- **G1 — Honour the FAN tick as a hard user intent.** Once ticked, Tomo
  must generate or surface an atomic proposal before rendering instructions.
- **G2 — Keep proposal-first.** Never write an atomic note to the vault
  without the user approving its title, parent MOC, tags, and
  destination. The existing `[x] Approved` UI in suggestions docs is the
  approval surface.
- **G3 — Minimal new UI.** No new checkboxes, no new commands, no new
  document types. Reuse the suggestions-doc pattern and the existing
  `/inbox` auto-detect loop.
- **G4 — Self-contained resolution.** The user should not have to re-run
  full Pass 1 to resolve a FAN. Only the affected items get re-classified.

## 4. Non-goals

- **N1** — A mechanism to set FAN from the CLI or outside the suggestions
  doc. The checkbox stays the only entry point for MVP.
- **N2** — Automatic re-try when the user unchecks the approved atomic in
  the resolve doc. Unchecked = do not render. User can re-tick FAN to
  trigger another resolve run.
- **N3** — Cross-inbox / historical item resolution. FAN only applies to
  items present in the currently-active suggestions doc.

## 5. Acceptance criteria

**A1 — Halt-on-unresolved FAN.** If Pass 2's parser finds at least one
FAN log_entry without a matching atomic section (original doc OR
companion resolve doc), the instruction-builder MUST NOT write any
instructions to the vault. It MUST emit a user-facing halt message
naming the unresolved items.

**A2 — Auto-generate resolve doc.** On halt, instruction-builder MUST
dispatch `inbox-analyst` subagents with a new `force_atomic=true` input
for each unresolved item. It MUST reduce + render a follow-up
suggestions doc at `<inbox>/<YYYY-MM-DD_HHMM>_suggestions-fan.md` via
`kado-write`. The follow-up doc MUST carry its own `[ ] Approved`
checkbox and per-atomic Approve/Skip/Delete tri-state (same format as the
regular suggestions doc).

**A3 — `force_atomic` overrides worthiness.** `inbox-analyst` with
`force_atomic=true` MUST emit a `create_atomic_note` action for the
item regardless of Step 7's worthiness score.

**A4 — Multi-doc merge.** On the next `/inbox` run after the user
approves the resolve doc, Pass 2's parser MUST read both the original
suggestions doc and the resolve doc from the inbox, merge the approved
atomic-note sections from the resolve doc into the corresponding
log_entries in the original doc (matched by `source_stem`), and emit
a single unified `parsed-suggestions.json`.

**A5 — Rendering succeeds post-merge.** `instruction-render.py` MUST
produce instructions for merged items exactly as if the analyst had
proposed the atomic in the original Pass 1 (same rendered notes, same
instruction entries, same coverage-audit result).

**A6 — Cleanup.** After a successful Pass 2 run on merged docs, the
vault-executor cleanup phase MUST handle both the original and the
resolve doc when archiving / deleting processed workflow docs. No
orphaned resolve docs remain in the inbox.

**A7 — Backwards compatibility.** Suggestions docs with FAN logs where a
matching per-item section already exists (the current happy path) MUST
continue to work unchanged. The halt and resolve flow only activates
when no section matches.

## 6. Out of scope (but noted)

- Prompting the user before triggering the resolve subflow ("3 FANs
  without section — generate resolve doc?"). MVP runs the subflow
  automatically. A future setting could gate it.
- Respecting FAN on item types other than `log_entry` (e.g. on
  daily-only items). Today FAN only appears under log_entries. If the
  checkbox pattern spreads, this design extends naturally.

## 7. Success signals

- Furano (and any future sub-worthiness item the user wants to keep)
  completes end-to-end as an atomic note in the same day, without lowering
  the global threshold.
- The `force_atomic: X items had Force Atomic Note but no per-item
  section — not rendered` warning from the parser becomes rare and, when
  it appears, is immediately followed by a resolve-doc write log line.
