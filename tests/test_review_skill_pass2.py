#!/usr/bin/env python3
# version: 0.1.0
"""test_review_skill_pass2.py — spec 045 T5.2 / P5: the Pass 2 steps of the periodic-review skill.

Continue (`parse`), preview, deliver and drop: every refusing problem of lib/review_delivery.REFUSING
and every notice has its line, the replace-mode and heading-pick bullets stand in the order a literal
model needs, `drop`'s statuses and problem tokens are read back from the script. Split out of
tests/test_review_skill.py at Phase 5 (D8); the pins moved verbatim, their RED history is in that
file's docstring.
"""
from __future__ import annotations

import re

import pytest

from review_cli_contract import REPO, load_script
from review_skill_helpers import SKILL, _section, _text


# ── Pass 2 (F5, F6) ─────────────────────────────────────────────────────────


def test_continue_parses_the_document_and_branches_on_status_first():
    text = _section("6. Continue an open review")
    assert "python3 scripts/review-doc.py parse --stem <stem>" in text
    assert "Branch on `status` first:" in text
    assert ("- `not-found` → say the review document was not found at `doc_path` and ask `1 Start over · 2 Abort`. "
            "Start over → step 4 with the entry's `period` and `kind`. Abort → stop.") in text
    assert "report `counts` (`kept`, `unticked`, `deleted`, `added`)" in text


def test_every_parse_warning_has_a_plain_language_line():
    load_script("review-doc.py")
    from lib import review_doc_parse as rdp  # the scripts put tomo/scripts on sys.path

    warnings = {rdp.APPROVED_MISSING, rdp.UNKNOWN_GROUP, rdp.ITEM_OUTSIDE_GROUP, rdp.DUPLICATE_GROUP,
                rdp.FRONTMATTER_BROKEN}
    assert len(warnings) == 5
    text = _section("6. Continue an open review")
    lines = {
        "approved-line-missing": "- `approved-line-missing` → the Approved line is missing; restore `- [ ] Approved` at column 0 and tick it.",
        "unknown-group": "- `unknown-group` → a heading the parser does not know; its items do not land.",
        "duplicate-group": "- `duplicate-group` → the second heading of that name is ignored.",
        "frontmatter-broken": "- `frontmatter-broken` → the document's frontmatter could not be read; the period is taken from the stage.",
        "item-outside-group": "- `item-outside-group` → an item above the first heading; it is filed under an unknown group and does not land.",
    }
    assert set(lines) == warnings
    for name, line in lines.items():
        assert line in text, name


def test_an_unticked_approved_box_is_named_and_nothing_delivered():
    text = _section("6. Continue an open review")
    assert ("`approved` false → say the document is not approved yet and name the box `- [ ] Approved`; stop, "
            "nothing is delivered.") in text
    assert "`nothing_to_deliver` true → say nothing is ticked and ask `1 Start over · 2 Abort`" in text


def test_preview_prints_the_section_target_and_place_then_asks_deliver_or_abort_and_ends_the_turn():
    text = _section("7. Preview")
    assert "python3 scripts/review-instructions.py preview --stem <stem>" in text
    assert ("print `target`, `mode` (`insert`, `replace` or `new-note`), `place` (`anchor`, `placement`, `level`) "
            "and `section_md` in full, in a fenced block, copied from the Bash result") in text
    assert ("Then ask `1 Deliver · 2 Abort` and end the turn. Say in one line before it that a change is made by "
            "editing the document and running `/review` again. Deliver → step 8. Abort → stop; nothing is written, "
            "the document stays open.") in text
    assert "preview" not in text[text.index("Then ask `1 Deliver · 2 Abort`"):].replace("`preview`", "")


PREVIEW_PROBLEMS = {
    "not-approved": "- `not-approved` → name the box `- [ ] Approved`; stop.",
    "approved-line-missing": ("- `approved-line-missing` → say the Approved line is missing; restore `- [ ] Approved` "
                              "at the line start and tick it; stop."),
    "nothing-to-deliver": "- `nothing-to-deliver` → say nothing is ticked and ask `1 Start over · 2 Abort` as in step 6.",
    "replace-mode": ("- `place-missing`, `place-too-deep` or `user-heading-collision` with `mode` `replace` → say what "
                     "is wrong with the heading above the Tomo marker in the target note: there is none "
                     "(`place-missing`); it is one of the user's own sections, or an earlier heading of the same name "
                     "stands above it (`user-heading-collision`); it is too deep to replace under, the review heading "
                     "would pass level 5 (`place-too-deep`). Ask `1 Start over · 2 Abort`; Start over → step 4 with "
                     "the entry's `period` and `kind`, Abort → stop."),
    "user-heading-collision-after-pick": (
        "- `user-heading-collision` with `mode` `insert` or `new-note` after a heading pick (the rerun with "
        "`--place-anchor`) → say the target note holds a heading that clashes with the review: one named like the "
        "review heading, or the picked heading is one of the user's own sections; the user renames or removes the "
        "clashing heading in Obsidian. Ask `1 Start over · 2 Abort`; Start over → step 4 with the entry's `period` "
        "and `kind`, Abort → stop. Never print `headings` or ask for a number a second time."),
    "place-missing": ("- `place-missing` or `place-too-deep` with `mode` `insert` or `new-note` → name `place.anchor` "
                      "and `place.placement`, and say that this heading is not in the target note (`place-missing`), "
                      "or that the review heading would pass level 5 under it (`place-too-deep`); print "
                      "`headings` as a numbered list and ask: Which number, or 0 Abort? A number → rerun `preview` "
                      "with that heading as `--place-anchor`, keep it for step 8 and branch on the rerun by this "
                      "list. 0 → stop."),
    "user-heading-collision": ("- `user-heading-collision` with `mode` `insert` or `new-note` before any heading pick "
                               "→ say a heading of the user's with the same name is never replaced and the review "
                               "never lands inside one of the user's own sections; print `headings` as a numbered "
                               "list and ask: Which number, or 0 Abort? (as above)."),
    "set-exists": "- `set-exists` → say an instruction set for this review waits for Hashi and is not applied yet; nothing is delivered. Stop.",
}
PREVIEW_NOTICES = {
    "heading-renamed": "- `heading-renamed` → the marker was found under a renamed heading; the section is replaced there.",
    "target_appeared": "- `target_appeared` true → the target note was created since Pass 1; the plan targets it instead of a new note.",
    "variant_missing": ("- `variant_missing` or `templater_hint` → the template's Tomo variant is gone, or the template "
                        "holds Templater code; the readable instructions say to run Templater after the move."),
    "template_unmergeable": "- `template_unmergeable` → a plain note is built instead.",
    "unlanded-items": "- `unlanded-items` → `unlanded` kept items are under a heading the parser does not know and do not land.",
}


@pytest.mark.parametrize("problem", PREVIEW_PROBLEMS)
def test_every_refusing_preview_problem_has_its_line(problem):
    text = _section("7. Preview")
    assert PREVIEW_PROBLEMS[problem] in text, problem
    assert text.index(PREVIEW_PROBLEMS[problem]) < text.index("- `ok` with empty `problems` →"), problem


@pytest.mark.parametrize("notice", PREVIEW_NOTICES)
def test_every_preview_notice_is_one_line_and_the_question_still_follows(notice):
    text = _section("7. Preview")
    assert PREVIEW_NOTICES[notice] in text, notice
    assert text.index(PREVIEW_NOTICES[notice]) < text.index("Then ask `1 Deliver · 2 Abort`"), notice


REPLACE_MODE_LINE = "- `mode` `replace` → the note already holds Tomo's review section; it is replaced, not added to."


def test_a_replace_preview_says_the_section_is_replaced_not_added():
    """Mode `replace` (the marker found in the target) is a flag of the `ok` output, not a notice: without a line
    the user sees a `replace_section` plan and is not told their note's section goes away."""
    text = _section("7. Preview")
    at = text.index(REPLACE_MODE_LINE)
    assert text.index("- `ok` with empty `problems` →") < at < text.index("Then ask `1 Deliver · 2 Abort`")


def test_the_heading_pick_names_the_place_fields_the_refusal_carries():
    """On a refused insert or new-note plan `place` holds `anchor` and `placement` only (lib/review_actions
    assigns `level` after `_insertion` succeeds), and `headings` is texts only — so the bullet names those two."""
    source = (REPO / "tomo" / "scripts" / "lib" / "review_actions.py").read_text(encoding="utf-8")
    assert 'list(target.duplicates), {"anchor": anchor, "placement": setup.placement})' in source
    head = PREVIEW_PROBLEMS["place-missing"]
    assert "name `place.anchor` and `place.placement`" in head
    assert "`place.level`" not in head
    assert "(`place-missing`)" in head and "(`place-too-deep`)" in head


def _branch_head(bullet: str) -> str:
    """The bullet up to its arrow: the condition a literal model matches, not any later mention of the tokens."""
    return bullet[:bullet.index("→") + 1]


def _branch_at(text: str, bullet: str) -> int:
    head = _branch_head(bullet)
    assert text.count(head) == 1, head
    return text.index(head)


def test_the_replace_mode_branch_covers_all_three_problems_and_comes_before_the_heading_pick():
    """Replace mode never reads `--place-anchor` (lib/review_actions._existing_note, marker branch), so the heading
    pick would refuse forever for any of the three; the replace bullet is matched first and names all three."""
    text = _section("7. Preview")
    replace = _branch_head(PREVIEW_PROBLEMS["replace-mode"])
    for problem in ("place-missing", "place-too-deep", "user-heading-collision"):
        assert f"`{problem}`" in replace, problem
    assert "`mode` `replace`" in replace
    at = _branch_at(text, PREVIEW_PROBLEMS["replace-mode"])
    assert at < _branch_at(text, PREVIEW_PROBLEMS["place-missing"])
    assert at < _branch_at(text, PREVIEW_PROBLEMS["user-heading-collision"])


def test_a_collision_after_a_heading_pick_ends_with_start_over_or_abort_never_a_second_pick():
    """`_first(headings, setup.heading)` in lib/review_actions._existing_note refuses before `_insertion` and never
    reads `--place-anchor`, and the preview output does not tell that cause from the own-section one (same
    `problems`, `headings`, `mode` and `place`), so the pick is offered once: the after-pick bullet is matched
    before both pick bullets, offers no list, and both picks route the rerun back through the list."""
    text = _section("7. Preview")
    after = PREVIEW_PROBLEMS["user-heading-collision-after-pick"]
    assert after in text
    at = _branch_at(text, after)
    assert _branch_at(text, PREVIEW_PROBLEMS["replace-mode"]) < at
    assert at < _branch_at(text, PREVIEW_PROBLEMS["place-missing"])
    assert at < _branch_at(text, PREVIEW_PROBLEMS["user-heading-collision"])
    assert "after a heading pick" in _branch_head(after) and "`--place-anchor`" in _branch_head(after)
    assert "before any heading pick" in _branch_head(PREVIEW_PROBLEMS["user-heading-collision"])
    assert "Which number" not in after and "numbered list" not in after
    assert "`1 Start over · 2 Abort`" in after
    assert "Never print `headings` or ask for a number a second time." in after
    assert "branch on the rerun by this list" in PREVIEW_PROBLEMS["place-missing"]
    assert "(as above)" in PREVIEW_PROBLEMS["user-heading-collision"]
    assert text.count("Which number, or 0 Abort?") == 2


@pytest.mark.parametrize("pick", ["place-missing", "user-heading-collision"])
def test_the_heading_pick_branches_apply_to_insert_and_new_note_only(pick):
    head = _branch_head(PREVIEW_PROBLEMS[pick])
    assert "with `mode` `insert` or `new-note`" in head
    assert "`replace`" not in head
    assert "otherwise" not in head


def _delivery_vocabulary():
    """``(REFUSING, NOTICES)`` of lib/review_delivery and the problem constants of lib/review_actions."""
    load_script("review-instructions.py")
    from lib import review_actions as ra  # the scripts put tomo/scripts on sys.path
    from lib import review_delivery as rdl

    return rdl.REFUSING, rdl.NOTICES, ra


# Tokens a Pass 2 bullet names that are statuses, keys or modes, never a problem of the plan or of drop.
NOT_PROBLEM_TOKENS = {"ok", "problems", "stopped", "not-found", "refused", "status", "mode", "error", "headings",
                      "insert", "replace", "new-note"}


def _problem_bullets(*headings: str) -> set[str]:
    """Every token a `- `<token>`` bullet of the named sections branches on (`- `a` or `b` →` names both)."""
    bullets: set[str] = set()
    for heading in headings:
        for line in re.findall(r"- (`[^→]+`)[^→]*→", _section(heading)):
            bullets.update(re.findall(r"`([a-z]+(?:-[a-z]+)*)`", line))
    return bullets - NOT_PROBLEM_TOKENS


def test_the_refusing_set_is_derived_and_every_token_has_a_stop_line_in_pass_2():
    refusing, notices, _ = _delivery_vocabulary()
    assert not set(refusing) & set(notices)
    covered = _problem_bullets("7. Preview", "9. Drop a failed delivery")
    missing = sorted(set(refusing) - covered)
    assert not missing, f"refusing problems without a branch in the skill's Pass 2: {missing}"


def test_every_refusing_preview_problem_pinned_here_is_in_the_refusing_set():
    refusing, _, _ = _delivery_vocabulary()
    pinned = _problem_bullets("7. Preview") - set(PREVIEW_NOTICES)
    assert pinned <= set(refusing), sorted(pinned - set(refusing))
    assert {"approved-line-missing", "already-applied"} <= set(refusing)


def test_the_notice_set_is_derived():
    _, notices, _ = _delivery_vocabulary()
    expected = set(notices) | {"target_appeared"}
    assert set(PREVIEW_NOTICES) <= expected
    named = set(re.findall(r"`([a-z_-]+)`", " ".join(PREVIEW_NOTICES.values())))
    missing = sorted(expected - named)
    assert not missing, f"notices without a line pinned here: {missing}"


def test_every_problem_constant_of_review_actions_is_classified():
    refusing, notices, ra = _delivery_vocabulary()
    not_problems = {ra.INSERT, ra.REPLACE, ra.NEW_NOTE, ra.NOTE_DOC_TYPE, ra.NOTE_STATE, ra.WIRE_TYPE}
    tokens = {value for name, value in vars(ra).items()
              if name.isupper() and isinstance(value, str) and re.fullmatch(r"[a-z]+(?:-[a-z]+)+", value)}
    unclassified = sorted(tokens - not_problems - set(refusing) - set(notices))
    assert not unclassified, f"review_actions problems in neither REFUSING nor NOTICES: {unclassified}"


def test_place_anchor_goes_to_preview_and_deliver():
    assert "With a chosen heading add `--place-anchor \"<heading>\"`." in _section("7. Preview")
    assert "Add `--place-anchor \"<heading>\"` when a heading was chosen in step 7." in _section("8. Deliver")


def test_deliver_branches_on_status_then_problems_or_failed_step():
    text = _section("8. Deliver")
    assert "python3 scripts/review-instructions.py deliver --stem <stem>" in text
    assert "Branch on `status` first:" in text
    assert ("- `delivered` or `resumed` → report `target`, `place`, `paths.set_json`, `paths.set_md` and "
            "`paths.note` when set, and \"Next: review and apply the instruction set in Hashi, or by hand with the "
            "readable instructions.\"") in text
    assert ("- `refused` → `name-taken` → say a note at `exists_path` is not Tomo's and nothing was overwritten; "
            "stop. `set-exists` or `set-withdrawn` → as in step 7. Any other → the step 7 lines; nothing was written."
            ) in text
    assert ("- `stopped` → `doc-changed` → `reason` `open-unsaved` → say the document is open in Obsidian with "
            "unsaved changes (a plugin that stamps the note on edit can cause that): save it (Cmd+S) or close it, then "
            "run `/review` and choose Resume; the payloads in `paths` already written count as done. `reason` "
            "`changed-since-read` or `unknown` → say the document was edited, or is open with unsaved edits, since the "
            "preview: save it and run `/review` again; the payloads in `paths` already written count as done, and "
            "the next `/review` offers Resume or Drop. `kado-write-failed` → say Kado refused or failed at "
            "`failed_step`; nothing more was written; the next `/review` offers Resume or Drop. Stop.") in text


def test_drop_reports_withdrawn_dropped_already_applied_and_set_changed():
    text = _section("9. Drop a failed delivery")
    assert "python3 scripts/review-instructions.py drop --stem <stem>" in text
    assert ("- `withdrawn` → say the set was withdrawn (nothing for Hashi to apply) and name every file in `paths` "
            "so the user can delete them in Obsidian.") in text
    assert "- `dropped` → say only the stage was removed (`removed`); nothing was in the inbox." in text
    assert ("- `already-applied` → say Hashi already applied an action of this review, so nothing is withdrawn "
            "and nothing more is delivered; stop.") in text
    assert ("- `set-changed` → say the set changed between read and write; run `drop` once more.") in text


def test_drop_kado_write_failed_names_the_partial_withdrawal_and_reruns_once():
    text = _section("9. Drop a failed delivery")
    assert ("- `kado-write-failed` → say the withdrawal may be partly written (the set may already hold nothing "
            "for Hashi while the readable file still lists the actions) and nothing else changed; run `drop` once "
            "more. A second `kado-write-failed` → show it, say the next `/review` lists this review again and "
            "offers Drop, and stop.") in text
    assert "nothing was withdrawn; stop" not in text


def test_set_withdrawn_routes_from_the_deliver_step_into_drop():
    """P5: a drop that emptied the set but failed before the meta mark is listed again as failed-delivery;
    Resume (`deliver`) refuses `set-withdrawn` on the emptied set, and the skill offers Drop there."""
    text = _section("7. Preview")
    assert ("- `set-withdrawn` → say an earlier Drop emptied the instruction set but did not finish (its readable "
            "file may still list the actions); nothing is delivered. Ask `1 Drop · 2 Abort`; Drop → step 9 with "
            "`<stem>`, Abort → stop.") in text


# `drop` answers with these statuses (tomo/scripts/review-instructions.py, drop(), plus main's
# NotFound / Refused / Stopped handlers); the script exposes its problem tokens as constants but not
# its statuses, so the statuses are hand-listed here and the problems are read from the code.
DROP_STATUSES = ("withdrawn", "dropped", "refused", "stopped", "not-found")


def _drop_problems() -> set[str]:
    """`drop`'s own tokens plus every `Refused("<token>")` its path raises (`_setup` and `drop` bodies)."""
    script = load_script("review-instructions.py")
    from lib import review_delivery as rdl

    source = (REPO / "tomo" / "scripts" / "review-instructions.py").read_text(encoding="utf-8")
    setup_body = source[source.index("def _setup("):source.index("def _target(")]
    drop_body = source[source.index("def drop("):source.index("def status(")]
    raised = set(re.findall(r'Refused\("([a-z-]+)"', setup_body + drop_body))
    assert raised == {"setup-missing", "setup-invalid", "inbox-not-configured"}, sorted(raised)
    return {rdl.ALREADY_APPLIED, script.SET_CHANGED, script.KADO_WRITE_FAILED} | raised


def test_drop_shared_refusals_reuse_the_preview_refused_line():
    text = _section("9. Drop a failed delivery")
    assert ("- `setup-missing`, `setup-invalid` or `inbox-not-configured` → as the `refused` line of step 7: show "
            "`problems` and `errors` verbatim and stop.") in text


@pytest.mark.parametrize("status", DROP_STATUSES)
def test_every_drop_status_has_its_branch(status):
    assert f"- `{status}`" in _section("9. Drop a failed delivery"), status


def test_drop_statuses_hand_listed_here_are_the_scripts():
    # Coupled to review-instructions.py's function names (`drop`, `status`) and its `"status": "..."` literals:
    # a rename there fails this slice, not the skill.
    source = (REPO / "tomo" / "scripts" / "review-instructions.py").read_text(encoding="utf-8")
    body = source[source.index("def drop("):source.index("def status(")]
    assert set(re.findall(r'"status": "([a-z-]+)"', body)) == set(DROP_STATUSES) - {"not-found"}


def test_every_drop_problem_token_of_the_script_has_its_line():
    covered = _problem_bullets("9. Drop a failed delivery")
    missing = sorted(_drop_problems() - covered)
    assert not missing, f"drop problems without a branch: {missing}"


def test_drop_writes_the_set_before_the_readable_peer_so_a_late_failure_is_partial():
    """The skill's `kado-write-failed` wording rests on this order; a swap would make it wrong."""
    # Coupled to review-instructions.py's `drop` / `status` names and its write_file / write_note / meta call
    # text: a rename there fails this slice, not the skill.
    source = (REPO / "tomo" / "scripts" / "review-instructions.py").read_text(encoding="utf-8")
    body = source[source.index("def drop("):source.index("def status(")]
    assert body.index("write_file(paths[rdl.SET_JSON]") < body.index("write_note(paths[rdl.SET_MD]")
    assert body.index("write_note(paths[rdl.SET_MD]") < body.index('meta.data["withdrawn"] = True')


def test_status_is_never_called_by_the_skill():
    assert "review-instructions.py status" not in _text(SKILL)
