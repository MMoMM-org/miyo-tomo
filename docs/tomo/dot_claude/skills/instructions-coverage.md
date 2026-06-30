# WHY: instructions-coverage

> Rationale for decisions in `tomo/dot_claude/skills/instructions-coverage/SKILL.md`.

## Sources Array for Coverage Tracking

WHY: Before 018, there was no reliable way to determine whether an approved suggestions doc had already been consumed by the instruction pipeline. The `sources[]` array in instructions-doc frontmatter solves this: each entry records the vault path and content checksum of the upstream doc that was consumed. Coverage is a simple set-membership check — "does this suggestions doc's path appear in any instructions doc's sources?" This replaced an earlier approach that relied on state flags alone, which couldn't distinguish "consumed but instructions deleted" from "never consumed."

## Triage Pre-Computes Coverage

WHY: Coverage computation requires reading frontmatter from every existing instructions doc in the inbox folder. This is expensive (N kado-read calls) and deterministic (no LLM reasoning needed). Moving it into inbox-triage.py means the computation happens once in Python, and the routing plan's `approved_suggestions` list arrives pre-filtered — only uncovered docs appear. The skill explicitly tells conductors "do not recompute coverage" to prevent duplicate Kado calls or conflicting coverage logic.

## Drift Indicators Are Non-Blocking

WHY: Drift indicators (checksum mismatch, orphaned state, missing source) represent situations where the pipeline's assumptions about the vault state may be wrong. Making them blocking would halt the entire pipeline on vault edits that are legitimate (user edited a note after it was analyzed). Instead, they are surfaced as warnings — the conductor processes the doc but includes the drift warning in its output so the user knows something may be stale. This follows the principle that Tomo proposes, the user decides.

## Loaded by Synthesis-Conductor Only

WHY: Coverage semantics are only relevant during Pass 2 (synthesis), where the conductor decides which approved docs to transform into instructions. The suggestion-conductor (Pass 1) produces suggestions from fresh sources — it doesn't need to know about coverage because the triage script already excluded covered docs from `fresh_sources`. Loading the skill in suggestion-conductor would add unnecessary context tokens.
