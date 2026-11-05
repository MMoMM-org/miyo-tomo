"""Spec 044 T3.1: the WHY mirrors for /note exist and name each decision the
runtime text will bake in, so no rationale has to live in the runtime files.

Assertions are on specific decision statements (a heading plus a distinguishing
phrase), not on a word that appears anywhere in the file.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs" / "tomo" / "dot_claude"
CMD = DOCS / "commands" / "note.md"
SKILL = DOCS / "skills" / "note-from-template.md"
AUTHOR = DOCS / "skills" / "inbox-author.md"

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _text(path: Path) -> str:
    assert path.is_file(), f"{path.relative_to(REPO)} is missing"
    return path.read_text()


def _section(text: str, heading_part: str) -> str:
    """Heading and body of the one '## ' section whose heading contains heading_part.

    A key matching several headings would silently test the first one, so it fails.
    """
    parts = re.split(r"^## ", text, flags=re.M)
    matches = []
    for part in parts[1:]:
        head, _, body = part.partition("\n")
        if heading_part.lower() in head.lower():
            matches.append(head + "\n" + body)
    assert matches, f"no '## ' heading containing {heading_part!r}"
    assert len(matches) == 1, (
        f"{len(matches)} '## ' headings contain {heading_part!r}; use a longer key"
    )
    return matches[0]


def _assert_needles(section: str, needles: list[str], label: str) -> None:
    body = re.sub(r"\s+", " ", section).lower()
    for needle in needles:
        assert needle.lower() in body, f"{label} lacks {needle!r}"


def test_mirrors_start_with_why_title():
    assert _text(CMD).startswith("# WHY: note (command)")
    assert _text(SKILL).startswith("# WHY: note-from-template (skill)")


def test_command_is_thin_shim_and_main_session():
    body = _section(_text(CMD), "Thin Shim")
    assert "note-from-template" in body
    assert "$ARGUMENTS" in body
    main = _section(_text(CMD), "Main Session")
    assert "AskUserQuestion" in main
    assert "subagent" in main.lower()
    assert "cannot" in main.lower()


@pytest.mark.parametrize(
    "heading, needles",
    [
        ("Main Session", ["AskUserQuestion", "subagent", "Agent tool"]),
        ("Printed Before", ["print", "before", "AskUserQuestion", "note.md", "draft.md"]),
        ("Abort", ["note-instructions.py drop", "note_include", "stays saved"]),
        ("Exit 2 Means", ["exit 2", "another value", "nothing is staged"]),
        ("Resume-or-Drop", ["steps_done", "never a silent drop", "frozen"]),
        ("Model Fills", ["ADR-1", "scripts check"]),
        ("Delivery Is One Script", ["ADR-2", "deliver", "exit 3", "withdrawn", "nothing is written"]),
        ("Exit 3 Branches", ["steps_done", "is_frozen", "deliver", "output"]),
        ("Source That Moves", ["source_marked", "not marked", "source_mark", "resume", "retries"]),
        ("No Candidate Fitting", ["folder_listed", "adjust patterns", "inbox-author", "abort", "F2-AC3"]),
        ("Runtime Details", ["Templater", "F3-AC7", "F3-AC8", "headings", "previews"]),
        ("Session Start", ["ADR-6", "note-session.py", "argparse"]),
        ("Shared Parser", ["ADR-4", "template_syntax", "outline"]),
        ("Draft State", ["ADR-7", "tomo-tmp/note/", "reset-tomo-tmp.sh"]),
        ("note_include", ["ADR-5", "templates-include", "comments"]),
        ("Question Budget", ["four", "required", "Skipped, left empty"]),
        ("Template Unreadable", ["folder_listed", "never says that no template exists"]),
        ("STRICT", ["observed", "Why:"]),
        ("Eval", ["ADR-8", "not in the CLAUDE.md eval gate"]),
        ("Separate Mode", ["--process", "decline", "note-process.py"]),
    ],
)
def test_skill_mirror_names_decision(heading, needles):
    _assert_needles(_section(_text(SKILL), heading), needles, f"{heading!r} section")


def _sentences(text: str) -> list[str]:
    flat = re.sub(r"\s+", " ", text)
    return [s for s in re.split(r"(?<=[.:;])\s+", flat) if s]


def test_frozen_title_is_always_qualified_by_steps_done():
    """SKILL.md step 6 and is_frozen freeze title/destination only once steps_done
    is non-empty; an unqualified 'during a resume ... frozen' contradicts that."""
    unqualified = [
        s
        for s in _sentences(_text(SKILL))
        if re.search(r"\bfr(?:oz|eez)", s, re.I)
        and "title" in s.lower()
        and "steps_done" not in s
        and "once a step is done" not in s
    ]
    assert not unqualified, f"frozen title without the steps_done condition: {unqualified}"


@pytest.mark.parametrize(
    "stale",
    [
        # Exit 3 branches on steps_done (Rename/Abort vs Keep/Drop), not rename-or-abort alone.
        "rename or abort, never overwrite",
        # The skill writes three local files, not draft.md alone (SKILL.md intro).
        "writes `draft.md` and nothing else",
        # Exit 1 of deliver with an empty step is the filled-note check, not a Kado error.
        "Exit 1 is a Kado or system error",
        # deliver re-runs the filled-note check and can report it failing (exit 1, empty step).
        "`deliver` never runs on a failing check",
        # kept_drafts and every deliver output carry steps_done now.
        "`kept_drafts` entries do not carry it",
        "reads `steps_done` from `meta.json`",
        # Signal 2 is a skipped point filled through Change something, not an answered re-asked point.
        "an answered re-asked point",
        # Several fits: three candidates plus Abort, never four options plus Abort.
        "asks with up to four options",
    ],
)
def test_skill_mirror_has_no_stale_statement(stale):
    flat = re.sub(r"\s+", " ", _text(SKILL))
    assert stale.lower() not in flat.lower()


def test_inbox_author_has_note_redirect_entry():
    body = _section(_text(AUTHOR), "/note")
    assert "/note" in body
    assert "If found" in body
    assert "unknown" in body.lower()
    assert "built-in default" in body
    assert "note-from-template" in body


@pytest.mark.parametrize("path", [CMD, SKILL, AUTHOR])
def test_relative_links_resolve(path):
    broken = []
    for target in LINK.findall(_text(path)):
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            continue
        rel = target.split("#", 1)[0]
        if rel and not (path.parent / rel).exists():
            broken.append(target)
    assert not broken, f"{path.name}: unresolved links {broken}"


SCRIPTS = REPO / "docs" / "tomo" / "scripts"
NOTE_INSTRUCTIONS = SCRIPTS / "note-instructions.md"
NOTE_META = SCRIPTS / "lib" / "note_meta.md"


@pytest.mark.parametrize(
    "heading, needles",
    [
        # A1: one frozen message for the title/destination and the keep-source refusal.
        ("Frozen Message", ["apply_stage_update", "is_frozen", "is_keep_source_frozen",
                            "instructions_json", "delete", "misreport"]),
        # A2: exit 1 is branched on status; withdrawn is not a draft problem.
        ("Exit 1 Branches on status", ["status", "withdrawn", "empty step",
                                       "no draft edit", "rename", "steps_done"]),
        # A3: the empty-step branch names the stamp, because stage reports check.ok true then.
        ("Exit 1 Branches on status", ["frontmatter stamp", "check.ok", "true"]),
        # A4: a missing Kado config is a named failed step.
        ("Exit 1 Branches on status", ["kado_config", "the draft stays"]),
    ],
)
def test_skill_mirror_names_exit_1_and_frozen_decisions(heading, needles):
    _assert_needles(_section(_text(SKILL), heading), needles, f"{heading!r} section")


@pytest.mark.parametrize(
    "path, heading, needles",
    [
        (NOTE_INSTRUCTIONS, "kado_config",
         ["URL or a token", "opens no connection", "fails at the first step", "failed_step", "stale stage", "steps_done", "kept draft", "whole delivery",
          "records nothing", "reruns first", "leftover", "harmless"]),
        (NOTE_META, "FAILED_STEPS",
         ["STEPS", "stop point", "never in `steps_done`", "INBOX_STEPS", "SOURCE_MARK",
          "freeze"]),
    ],
)
def test_script_mirror_names_kado_config_decision(path, heading, needles):
    _assert_needles(_section(_text(path), heading), needles, f"{path.name} {heading!r}")


@pytest.mark.parametrize(
    "stale",
    [
        # Exit 1 with an empty step is also the stamp or a withdrawn guard, not the check alone.
        "Exit 1 with an empty `step` is the filled-note check failing",
        "a failure there (exit 1, empty `step`) sends the skill back",
    ],
)
def test_skill_mirror_has_no_stale_exit_1_statement(stale):
    flat = re.sub(r"\s+", " ", _text(SKILL))
    assert stale.lower() not in flat.lower()


@pytest.mark.parametrize(
    "heading, needles",
    [
        # 1. The source delete is disclosed before approval; the line and the option follow keep_source.
        ("Source Delete Is Named", ["before", "approves", "delete_source", "keep_source",
                                    "no source", "nothing is deleted", "--keep-source",
                                    "[[", "is_keep_source_frozen"]),
        # 2. deliver exit 2 is a bad invocation, config or stage: no other value cures it.
        ("deliver Exit 2", ["no title staged", "unknown stem", "meta.json", "vault-config.yaml",
                            "no other value", "the draft stays", "inbox_file",
                            "destination_file", "sanitize_stem"]),
        # 3. new exit 1 stages nothing; template-outline.py exit 2 is refused input no retry cures.
        ("new Exit 1", ["sourceerror", "before the stage", "nothing to drop",
                        "another source", "exit 2", "no retry", "drop the stem",
                        "unusable stage"]),
        # 4. deliver stamps tomo:, so a draft-supplied key clashes with the stamp.
        ("tomo: Key", ["_checked_note", "stamp", "rendered-note", "pending-move",
                       "no_user_tomo_key", "clash", "frontmatterMergeError"]),
        # 5. One fit continues without asking; several get a numbered list under the four-option cap.
        ("Template Choice", ["one candidate fits", "without asking", "numbered list",
                             "four-option cap", "another number"]),
        # 6. Script errors are verbatim: they name the problem class only and are written for the user.
        ("Verbatim", ["problem class", "written for the user", "paraphras", "hide the cause"]),
        # Sweep: draft keeps {{source_link}}; stage resolves it from keep_source.
        ("source_link", ["{{source_link}}", "keep_source", "rewrite"]),
        # Sweep: "none" answers a required point.
        ("Question Budget", ["\"none\"", "deliberate"]),
        # Sweep: another template needs a new stem.
        ("Another Template", ["meta.json", "template", "new stem"]),
        # Sweep: the save path re-outlines because a delivery removed the stage.
        ("Process Offer Re-Outlines", ["removes the stage", "process-outline.json",
                                       "rejected_required"]),
        # Sweep: the header names both file names; the report points to Hashi.
        ("Header Names Both", ["inbox_file", "destination_file", "Hashi", "inbox"]),
        # Fix 1: exit 3 reads steps_done from deliver's own output.
        ("Exit 3 Branches", ["stdout", "the run ended"]),
        # Fix 2: a kept-draft drop names what landed by kind and never promises nothing landed.
        ("Kept Draft Drop", ["kept_drafts", "steps_done", "by kind", "no path", "in flight",
                             "may already be in the inbox", "<stem>_"]),
        # Fix 3: exit 2 of new/stage splits on the option the error names.
        ("Exit 2 Means", ["note-instructions: --title", "--destination", "--source",
                          "vault-config.yaml", "local I/O", "unknown stem", "meta.json",
                          "verbatim", "stop"]),
        # Fix 4: Default omits --destination; keep current needs a stored destination.
        ("Default Destination", ["omit", "--destination", "atomic_note", "keep current",
                                 "exists", "replaces"]),
        # Fix 5: both process paths branch on template-outline.py exits.
        ("Process Paths Branch", ["exit 1", "F2-AC4", "exit 2", "rm -f", "write nothing"]),
        # Fix 6: a resume never ran read this session.
        ("Resume Gets No Process Offer", ["read", "resume", "default_destination", "skip"]),
        # Fix 7: the hand-off names the default type so inbox-author cannot bounce back.
        ("No Candidate Fitting", ["byName", "`default`", "loop", "known key", "Skill"]),
        # Fix 9: signal 2 is a skipped point filled through Change something.
        ("Separate Mode", ["Skipped, left empty:", "Change something", "could never fire"]),
        # Fix 10: three candidates plus Abort keeps the four-option cap.
        ("Template Choice", ["three candidates plus abort", "four"]),
        # Sweep: after setup start reruns; kept drafts come first.
        ("Setup Reruns start", ["candidates", "note_include", "kept draft"]),
    ],
)
def test_skill_mirror_names_remaining_decisions(heading, needles):
    _assert_needles(_section(_text(SKILL), heading), needles, f"{heading!r} section")


def test_deliver_exit_2_scopes_what_reached_the_vault():
    """_record and _fail (note-instructions.py) write meta.json after Kado was asked, so a
    failed write exits 2 with the note or the instruction set possibly in the inbox and
    the landed step missing from steps_done. Only the causes raised before Kado is asked
    (bad or unknown stem, unreadable meta.json, no title staged) leave the vault
    untouched: a "nothing ... vault" sentence must name them, and the section must name
    the write case and what the next /note does with it (identical text, stale_stages)."""
    section = _section(_text(SKILL), "deliver Exit 2")
    unscoped = [
        s
        for s in _sentences(section)
        if re.search(r"\bnothing\b.*\bvault\b", s, re.I)
        and not all(cause in s.lower() for cause in ("unknown stem", "no title staged"))
    ]
    assert not unscoped, f"'nothing reached the vault' without its causes: {unscoped}"
    body = re.sub(r"\s+", " ", section).lower()
    for needle in ("`_record`", "`_fail`", "landed", "steps_done", "_instructions",
                   "stale_stages", "identical"):
        assert needle in body, f"'deliver Exit 2' section lacks {needle!r}"
