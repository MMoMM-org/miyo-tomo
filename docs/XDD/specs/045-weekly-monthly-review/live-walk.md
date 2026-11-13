# Spec 045 live-walk record (/review weekly and monthly, #31)

Purpose: T6.3. The owner walked `/review` on `tomo-instance` against the test vault (`Privat-Test`) on 2026-11-12 and 2026-11-13; Claude read the transcripts, the script reports, the Kado audit log and the vault's file metadata. This file records cost, time, counts, the KPI verdicts, the model-behaviour criteria, and every defect the walk found with its fix. No journal, note or proposal text is quoted anywhere; only counts, paths, script names, field names, status values and timestamps.

## Method

- Transcripts: `tomo-home/.claude/projects/-Volumes-Moon-Coding-MiYo-Tomo-tomo-instance/<session>.jsonl`. Evidence is cited as `<session-id-prefix>:<line>`, the 1-based JSONL line; a tool call is cited at the line of the call. Timestamps in the transcripts are UTC; the Kado audit log and file times are local (UTC+1).
- Sessions in walk order: `5b959432` (2026-11-12, setup attempt), `da0eedd9` (setup, week W13 Pass 1), `68459faa` (W13 Pass 2, month Pass 1 twice, month Pass 2), `3a862c54` (2026-11-12, month rerun), `a5f4180a`, `80a4605a`, `269b1964` (2026-11-13).
- Model: `claude-sonnet-5-5` in every assistant message of every session (no other model id, no subagent or sidechain messages).
- Cost: from each assistant message's `usage`, counted once per API message id. The transcript repeats the same `usage` on every content block of one message (for example `269b1964`: 29 assistant entries, 23 message ids), so summing every entry overstates the cost. Prices used: the cost log's list rates for Sonnet, $3.00 input / $15.00 output / $3.75 cache write / $0.30 cache read per million tokens. I could not check these against a Sonnet 5.5 price sheet; they are the rates `docs/evolution/inbox-cost-log.md` states and `scripts/tomo-session-stats.py` defaults to.
- Duration: first to last `user`/`assistant` entry of the run. It includes the time the user took to answer a question inside the run, so a Pass 2 with a Deliver question carries 30 to 60 s of user time.
- A run is one `/review` invocation (a setup, a Pass 1, a Pass 2, or a bare `/review` that only reports). Where one invocation did two jobs it is split by the job and noted.
- Kado calls, retried and waited come from `review-read.py` (`report.calls`, `report.retried`, `report.waited_s`) and from `review-doc.py write` (`calls`). `review-instructions.py` reports no call count; for Pass 2 the audit log is the only source (approximate, see the table).
- Script versions at the end of the walk (HEAD `586277fa`): `review-read.py` 0.1.3, `review-session.py` 0.6.3, `review-instructions.py` 0.2.5, `review-doc.py` 0.5.1, `periodic-review/SKILL.md` 0.1.13, `commands/review.md` 0.1.0. The walk ran on earlier versions of these; each fix below says which run it was seen in.

## Runs

Counts per `review-doc.py write`: d = done, o = open, t = themes, g = growth, h = habits, w = weekly_only, n = not_in_weekly. Counts per `review-doc.py parse`: kept / unticked / deleted / added.

| Run | Evidence | What | Cost | Duration | Kado (read): calls / retried / waited | Counts |
|---|---|---|---|---|---|---|
| R1 | 5b959432:5-106 | `/review setup`, week; validator rejected the confirmed setup | $0.268 | 58 s | match only | setup not saved |
| R2 | da0eedd9:5-188 | `/review setup`, week and month; template question asked per kind, template chosen, both saved | $0.566 | 123 s | match only | setup saved (week and month) |
| R3 | da0eedd9:189-266 | Pass 1 week 2026-W13 (target exists) | **$0.469** | **48 s** | 41 / 0 / 11.7 s; write 3 | d8 o5 t5 g3 h12 |
| R4 | da0eedd9:267-400 | bare `/review`, W13 listed open, Continue; parse | $0.231 | 23 s | none | 33 / 0 / 0 / 1 (the added 1 is the Approved line read as an item, approved false) |
| R5 | 68459faa:5-108 | Pass 2 week W13: parse, preview, Deliver; then the default week 2026-W45 was read | **$0.322** | **94 s** | audit log ≈ 8 entries parse-to-deliver; W45 read 5 / 0 / 1.1 s | 33 / 0 / 0 / 0; mode insert; `delivered` |
| R6 | 68459faa:109-243 | Pass 1 month 2026-03, first (target did not exist) | **$0.909** | **161 s** | 165 / 0 / 48.4 s (read call 49.5 s wall); write 5 | d11 o9 t7 g5 h12 w1 n2 |
| R7 | 68459faa:244-279 | bare `/review`, default W45, nothing to review | $0.231 | 13 s | 5 / 0 / 1.1 s | none |
| R8 | 68459faa:280-354 | Pass 1 month 2026-03, second (the first document was no longer listed) | **$0.532** | **92 s** | 165 / 0 / 48.2 s; write refused once (`proposals-invalid`), then 5 | d11 o9 t7 g5 h12 w1 n2 |
| R9 | 68459faa:355-429 | Pass 2 month: parse, preview, Deliver; then the default W45 was read | **$0.663** | **97 s** | audit log ≈ 11 entries parse-to-deliver; W45 read 5 / 0 / 0.9 s | 46 / 1 / 0 / 0; mode new-note; `delivered` |
| R10 | 3a862c54:5-67 | bare `/review`, default W45, nothing | $0.163 | 9 s | 5 / 0 / 1.1 s | none |
| R11 | 3a862c54:68-206 | Pass 1 month, third (target exists); `write` refused `review-exists`, run ended at the Replace / Keep question, not answered | $0.869 | 155 s | 165 / 0 / 48.2 s (49.6 s wall) | no document written |
| R12 | a5f4180a:5-66 | bare `/review`, default W45, nothing | $0.182 | 9 s | 5 / 0 / 1.1 s | none |
| R13 | a5f4180a:67-195 | Pass 1 month, fourth (target exists) | $0.682 | 132 s | 165 / 0 / 48.4 s (49.5 s wall); write 3 | d9 o4 t5 g5 h12 w1 n0 |
| R14 | 80a4605a:5-99 | Pass 2 month, try 1: parse, preview; anchor heading missing in the target; user answered 0 twice | $0.244 | 89 s | audit ≈ 9 entries | 36 / 0 / 0 / 0; preview problems 1 |
| R15 | 80a4605a:100-160 | Pass 2 month, try 2: parse, preview, Deliver; stopped at `doc_mark` (`doc-changed`) | $0.227 | 30 s | audit ≈ 16 entries | 36 / 0 / 0 / 0; mode new-note; `stopped` |
| R16 | 80a4605a:161-201 | Resume 1: stopped at `doc_mark` again | $0.117 | 15 s | audit ≈ 7 entries | |
| R17 | 80a4605a:202-245 | Resume 2: completed, `status: resumed`, report named mode `replace` | $0.118 | 12 s | audit ≈ 10 entries | |
| R18 | 269b1964:5-178 | `/review setup`, week and month; the new "template has no frontmatter block" question asked, answered "Use it as it is" for both | $0.579 | 69 s | match only | setup saved, config unchanged |
| R19 | 269b1964:179-208 | bare `/review`, default W45, nothing | $0.134 | 9 s | 5 / 0 / 1.1 s | none |

Total over the seven sessions: $7.51 (a hand sum of the runs equals the per-session totals: 0.268 + 1.265 + 2.658 + 1.031 + 0.865 + 0.707 + 0.713). `scripts/tomo-session-stats.py` reports $5.41 for `68459faa` and $0.87 for `269b1964` (against $2.658 and $0.713 here) because it adds the repeated `usage`; see the open items.

Kado call figures: the weekly read made 41 calls and the monthly read 165 calls, inside the budget set on 2026-11-12 (week 45, month 170). No run retried a call; the pacer waited 11.7 s (week) and 48.2 to 48.4 s (month). No read reported `not_read`, `kado_empty` or `kado_none` entries. The weekly note W09 to W13 listing was found for the month in every run (`weekly_status` found, 6 weekly notes listed).

## KPI verdicts

| KPI | Result | Verdict |
|---|---|---|
| Weekly Pass 1 ≤ $0.50 | R3 $0.469, 48 s, in a session that had already loaded the skill during setup. A cold-session weekly Pass 1 was not measured. Fixed cost before the first script call is $0.074 in R3 against $0.119 to $0.138 in the cold sessions (3a862c54:54, a5f4180a:50, 80a4605a:54, 68459faa:53), so a cold run would sit nearer the limit; the size of that is not measured. | PASS (margin $0.031, warm) |
| Monthly Pass 1 ≤ $2.00 and ≤ 7 min | R6 $0.909 / 161 s; R8 $0.532 / 92 s; R11 $0.869 / 155 s (ended at a question); R13 $0.682 / 132 s. The read itself is 49.5 s of each. | PASS, all four |
| Pass 2 ≤ $0.20 | The two complete Pass 2 runs: R5 $0.322 and R9 $0.663. Both include the default-week read that the bare-`/review` defect added after delivery (R5 about $0.05 of the $0.322 counted from the read call; R9 about $0.14 from the deliver call on). Without it the cost at the moment `deliver` was called is already $0.270 (68459faa:86, cold session) and $0.526 (68459faa:413, warm session, the 6,978-character preview printed before it). The partial runs R16 $0.117 and R17 $0.118 are under the limit but are only resumes. | FAIL (not met) |
| ≤ 40 % of Tomo items unticked or deleted (habits excluded) | W13 delivered: 0 of 21 (8 + 5 + 5 + 3; 68459faa:64). Month first delivery: 1 of 35 (11 + 9 + 7 + 5 + 1 + 2; the one unticked is in `done`; 68459faa:388). Month rerun document: 0 of 24 (80a4605a:65). Over W13 plus the first month: 1 of 56, 1.8 %. | PASS. Caveat: the owner edited nothing (edited 0, added 0 in every parse that counted) and ticked Approved; the KPI is met but says little about the proposals' quality |
| 0 writes outside the inbox before apply | Kado: every operation in the audit-log windows of the script writes (Pass 1 write; Pass 2 deliver) is a path under `100 Inbox/`, apart from read probes of the target note and the template (`Calendar/302 Weekly/2026-W13.md`, `X/900 Support/930 Templater/t_month_privat.md`). The audit log records the operation kind (`note`, `file`) and not read or write, so this is read from the windows and from the scripts' write targets (`review-doc.py write`: the review document; `review-instructions.py deliver`: the set JSON, the set MD, the new note, the document mark), not from a write flag. Vault side, two effects outside Tomo: see below. | PASS for Tomo and Kado; NOT MET at vault level on the month new-note path |
| 0 periodic notes with two Tomo review sections | `Calendar/302 Weekly/2026-W13.md` after Hashi: 1 `## Tomo Review` heading, 1 marker line. The March monthly note no longer exists in the vault, so it could not be checked. | PASS for W13; month not checkable |
| 0 delivered proposals without a source-day link | Non-habit checkbox items without a wikilink: 0 of 21 (W13 document), 0 of 35 (first month document), 0 of 24 (month rerun document). | PASS |

Vault-side effects on the month new-note path (not written by Tomo or Kado):

1. The new note `100 Inbox/2026-03.md` built from the raw Templater template left the inbox before Hashi ran. Evidence: preview reported mode `new-note` (68459faa:394, 80a4605a:136); the month target existed in every later run (`target_exists` True in R11, R13); Hashi's run log `100 Inbox/tomo-hashi-run-log_2026-11-13T1031.md` records `I01 move_note`, outcome `skipped-already`, applied 0, failed 0.
2. 65 vault notes outside the inbox changed their modification time inside one minute at 2026-11-13 09:01:06: 31 March dailies, 30 March 5 Year Journal notes, 4 weekly notes. The month instruction set JSON landed at 09:01:04.8 (80a4605a:152; audit log). The audit log shows no Kado operation touching those notes in that minute. Cause undetermined; the pattern (a Templater monthly template reacting to the new note) fits the known raw-template defect but I did not read a template or note to confirm it.

W13 apply: Hashi run log `100 Inbox/tomo-hashi-run-log_2026-11-12T1816.md`: `I01 insert_under_marker` on the weekly note, before `Organisation`, outcome applied, applied 1, failed 0. The next `/review start` listed W13 with state `applied` (68459faa:129-133).

## Model-behaviour criteria

| Criterion | Evidence | Verdict |
|---|---|---|
| F1-AC6 (week counting asked in plain words when the weekly notes do not show it) | Not reached. `match` reported `week_rule: inferred`, `notes_checked: 8` for every weekly setup (da0eedd9:74, 269b1964:56), so the skill had no reason to ask. The month setup reports `week_rule: default` (not relevant). | not walked (the vault's weekly notes show the rule); prose pin only |
| F4-AC5 (review documents in the vault language, German here) | Setup language `de` (`proposal.language`, da0eedd9:74, 269b1964:56). All four review documents found in the vault (`100 Inbox/2026-W13 Review.md`, three month documents in `.trash`) carry 5, 7, 7 and 7 German group headings and none of the English ones; German function words outnumber English ones in each (68 to 7, 96 to 23, 96 to 23, 86 to 16). Preview headings in German (68459faa:80, 68459faa:404, 80a4605a:146). | PASS. Two notes: the chat lines of the skill are English by owner decision; 1 to 3 lines per document have three or more English function words and I did not read them, so I cannot say whether they are fixed lines or quoted journal text; the Pass 2 preview ends with one English notice about Templater code (68459faa:404, 80a4605a:146) |
| F4-AC7 (only Tomo's own section is proposed, never text for the user's own sections) | The setup lists no own sections for either kind (table value "none", da0eedd9:95, da0eedd9:154, 269b1964:70, 269b1964:130; `own_sections` empty in every `match`). | not walked (nothing to avoid on this vault); prose pin only |
| F5-AC2 (plain-text preview of the section, target note and place, then Deliver or Abort) | Week: 68459faa:80 names the target note and the place (before `Organisation`, level 2), prints the section under German group headings and ends `1 Deliver · 2 Abort`; the user answered 1 (68459faa:84) and `deliver` ran (68459faa:86). Month: 68459faa:404 (answered 1 at 408, deliver at 413) and 80a4605a:146 (answered 1 at 150, deliver at 152). | PASS, three of three |

Further model behaviour seen and recorded:

- Open review before a new request: with W13 open the skill listed it first and asked `1 Continue · 2 Start over · 3 Abort` (da0eedd9:293, 68459faa:56, 80a4605a:57, 80a4605a:124). PASS.
- Not approved: the skill said the document was not approved, named the Approved line and delivered nothing (da0eedd9:304; the cause was the done marker below).
- Anchor missing in the target: the skill said so before delivering, listed the target's headings and offered a number or `0 Abort` (80a4605a:81); Abort left everything unchanged and said how to retry (80a4605a:88, 80a4605a:95).
- An existing review document: `write` refused with `review-exists` and the skill asked Replace or Keep (3a862c54:204-206).
- Failed delivery: the skill named the step, the problem and the files already written, and offered Resume or Drop on the next run (80a4605a:157, 80a4605a:185).
- After a refused `write` caused by a re-read that reset the stem folder, the model checked the folder, wrote the proposals again and reran (68459faa:323-339). The model had called `write` straight after the re-read without writing the proposals file first.

## Defects found, in order

| # | Defect | Evidence | Fix | Seen fixed |
|---|---|---|---|---|
| 1 | Setup: `match` read the template only from `templates.mapping`, which has no weekly or monthly entry, so it proposed `template_kind: missing` and `place.anchor: null`; the setup schema rejected its own proposal and nothing was saved | 5b959432:96-100 | `7634dff5..c4d616ba` (template candidates, `needs_anchor`, `--template`, `--anchor`, `week_rule: given`, trim `none`), docs `ba82e975` | da0eedd9:74-95 (template question, anchor `Organisation`), da0eedd9:117 and :170 (setup-input `ok`) |
| 2 | The Tasks plugin's done marker on the Approved line made `parse` read the line as missing: `approved: false`, one item filed under an unknown group | da0eedd9:299-304 | `1ea36204` (marker tolerated on Approved, stripped from ticked items); test pinned to a committed fixture `97202f44` | 68459faa:64 (`approved: true`, 0 warnings) |
| 3 | A bare `/review` with an open review also started the default week (2026-W45) and read it | 68459faa:90-103 (also the listing at da0eedd9:287-293) | `867e8cbf` (`request` withheld while a review is listed) | 80a4605a:49 (`request: None`, `request_withheld: open-reviews`) |
| 4 | An empty daily listing for a period with no dailies carried `check-key-access` advice although the Kado key could read the folder | 68459faa:90 (`report.advice` 1), 68459faa:276 | `6cdbed8d` | 3a862c54:57 (`report.advice` empty for the same period) |
| 5 | `doc_mark` stopped with `doc-changed` although the document was unedited; the second resume dropped the new note from `paths`; the completed resume reported mode `replace` (a re-plan) instead of the delivered plan. Reported cause (from the coordinator, not visible in the transcripts): the `update-time-on-edit` plugin dirtied the open editor and Kado's dirty-editor guard answered CONFLICT | 80a4605a:152-157, 80a4605a:192-198, 80a4605a:233-240 | `88773c67` (`doc-changed` carries a reason; resume reports the delivered plan) | not re-walked: the fix (2026-11-13 09:41 local) is later than R17 (08:18 UTC) |
| 6 | The raw template `t_month_privat.md` opens its frontmatter only inside a Templater include and calls `tp.file.move`: the new note got two frontmatter blocks and moved to the monthly folder before Hashi applied `move_note` (Hashi: `skipped-already`); a Pass 2 preview then found the target without the anchor heading | 80a4605a:81, Hashi run log 2026-11-13T1031 | `586277fa` (setup asks once when the template has no frontmatter block at line 1) | the question appears at 269b1964:70 and :130; Pass 2 on that choice not re-walked, and both answers were "Use it as it is" (269b1964:75, :134) |

Observed polish items (no fix yet):

- 269b1964:83 and :142: after the answer `1`, the model reran `match` and told the user an internal field name ("`needs_template_ok` is no longer set") and repeated the whole proposal.
- 3a862c54:201-206: a rerun of a period whose review document still exists costs a full proposal write, then `write` refuses with `review-exists`; the Replace / Keep question comes after the model has already spent $0.87.

## Open items carried to T6.4

1. The Pass 2 cost KPI (≤ $0.20) is not met: R5 $0.322, R9 $0.663 (cost at the deliver call $0.270 / $0.526). The skill text loaded per `/review` is 21,304 to 22,784 characters and the cold start costs $0.12 to $0.14 before the first script call. Needs an owner decision: raise the KPI, or reduce the Pass 2 prompt and preview text. A Pass 2 at a clean `deliver` in a warm session was not measured.
2. A cold-session weekly Pass 1 was not measured (R3 ran warm, $0.469 against $0.50).
3. F1-AC6 and F4-AC7 were not reachable on this vault (week rule inferred, no own sections); they stay prose-pin only unless the owner walks a setup that reaches them.
4. Fixes 5 (`88773c67`) and 6 (`586277fa`) were not re-walked. The raw-template path with the answer "Use it as it is" still moves the note out of the inbox before Hashi applies; only the question is new. Whether the month's review section landed in the moved note is not known: the March monthly note no longer exists in the vault and Hashi reported `skipped-already` for the move.
5. The 65-note modification burst at 2026-11-13 09:01:06 and the Templater move are Obsidian-side effects of delivering a new note built from a Templater template; the KPI "0 writes outside the inbox before apply" holds for Tomo and Kado only. Decide how the spec states it.
6. `scripts/tomo-session-stats.py` counts the repeated `usage` of every content block, so it overstates cost (about 2x for `68459faa`). Existing cost-log rows that used it were not rechecked.
7. Why `open_reviews` was empty at 68459faa:263 and :266 after the first month document was written is not in the transcripts; its copy is in the vault `.trash`. Not determined.
8. A re-read resets the stem folder and the model wrote without rewriting the proposals (68459faa:323); the polish items above; the items carried from the Phase 5 and Phase 6 decisions (lone `%%` in item text, bare `stop`, `place.level` on a refused preview, same-named heading collision) are in the README Decisions Log.
9. 19 runs cost $7.51 (message-id counting), of which the bare default-week runs R7, R10, R12 and R19 are $0.13 to $0.23 each and end at "nothing to review": the default week has no dailies on this vault (dailies end 2026-09-12).
