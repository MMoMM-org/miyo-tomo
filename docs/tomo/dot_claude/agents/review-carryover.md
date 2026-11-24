# WHY: review-carryover

> Rationale for decisions in `tomo/dot_claude/agents/review-carryover.md`.
> Spec 047 (issue #270, `docs/XDD/specs/047-review-chunked-read/`); ADR and F-AC ids refer to its
> `solution.md` and `requirements.md`. The agent takes the open items, intentions or goals, and themes of the found
> previous notes (the previous review of the same kind and of the next larger kind) into `carryover.json`. Its job is
> planned and checked by `review-digest.py` ([review-digest](../../scripts/review-digest.md)); the proposer
> ([review-proposer](review-proposer.md)) marks each item against the period.

## WHY a Separate Agent

WHY: Feature 4 follows up the previous reviews: what was open, intended or recurring last time is checked against this
period. The previous notes are other material than the period's days and arrive as `previous/<kind>-<name>.json`; one
agent reads them all at once (≤ two notes), because the same matter in both notes must become ONE carryover item with
both notes as sources (F4-AC7). It runs in the same round as the digesters, so the follow-up costs no extra wait.

## WHY `sonnet`

WHY: ADR-7. Telling an open item, an intention or a goal and a theme from free prose — the user's own text and
Tomo's earlier blocks alike, in whatever wording the user used — is a reading judgement, harder than the digester's
recording. The input is small (two previous notes, each cut at the per-day reading limit), so the stronger model
costs little. It is not `opus` because it decides nothing over the period; the matching is the proposer's.

## WHY No Setup Marker

WHY: F4-AC1. The owner rejected a setup value that marks what counts as open or as an intention: users write open
items as unticked tasks, as "next week …" lines, as a heading of their template or inside Tomo's review block, and a
marker would miss everything not written its way. So the agent reads the note's text, both the user's sections and
Tomo's blocks, and takes what reads as open, intended or recurring. Text in an off-limits section of a previous note
may still be read as a source (F4-AC5); the off-limits rule governs where items are placed, not what is read.

## WHY the Text as It Stands Now

WHY: F4-AC9. An item the user unticked or deleted in the previous review document, or removed from the note after
applying, was the user's decision not to keep it. The read takes the previous note as it is in the vault today, and the
agent carries only what that text holds; it never reconstructs earlier proposals. For the same reason nothing is
carried from the target note of the period itself or from Tomo's earlier blocks in it (F6-AC7): the read does not hand
that note to this agent.

## WHY Ids, Types and Sources

WHY: ADR-6. Each item gets an id `c<n>` (the identity the proposer cites in `carried_ids` and `lib/review_carried.py`
checks for coverage), a `type` of `open`, `intention` or `theme` (a theme is never carried as done, F4-AC3), and the
previous notes it came from as `sources`. `review-digest.py check` refuses an unknown source or a duplicate id per note
(`carry-source-unknown`, `carry-id-duplicate`); a note whose items fail after the retry is dropped and its items
removed by the script, the other note's items still carry (F6-AC2).

## WHY the Review Language

WHY: F4-AC11. A previous note may be in another language than this review; the carried item lands in this review's
document, so its text is written in the current review language from the start, and the proposer does not need to
translate.

## WHY the Cap

WHY: ADR-2. `cap_bytes` 12,288 and ≤ 30 items keep the carryover a small, fixed share of the proposer's input; over it
is `carryover-too-large`, a failed attempt.

## WHY `tools: Read, Write` and Never Kado

WHY: ADR-7, F7-AC5. The agent reads the stage files of the previous notes and writes exactly `carryover.json`; no
Bash, no MCP, no skills, no Agent, so it sees only what the read took from the vault. `permissionMode: acceptEdits`
with the unchanged `settings.json` lets the Write land under `tomo-tmp/review/<stem>/` without a prompt.

## WHY a One-Line Reply

WHY: the reply lands in the main session; quoting previous-note text there would bring journal content into the main
conversation. The reply is `<out> written` or `<out> not written: <reason word>`; `check` judges the file.
