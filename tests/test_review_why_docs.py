"""Spec 045 T5.1 — the WHY documents of the /review command and the periodic-review skill (PRD F1-F7; ADR-1).

The two documents under ``docs/tomo/dot_claude/`` are the rationale layer of the
runtime files T5.2 writes. This test is the drift guard between those documents
and the CLI contracts of Phases 2-4: the subcommand names are read from the real
argparse parsers (``build_parser()`` of every review script and of
``vault-config-writer.py``) through ``tests/review_cli_contract.py``, never typed
by hand, so the test fails when a subcommand is added, renamed or removed and
the WHY document still names the old contract — in either direction.

Mechanisms a mutation of the parsers falsifies:
- ``test_skill_doc_names_every_subcommand_of_every_review_parser`` — a subcommand
  added to a parser (or missing from the document) fails the forward check.
- ``test_skill_doc_names_no_subcommand_the_parsers_lack`` — a subcommand removed
  from a parser while the document still names it fails the reverse check; so
  does a flag the document attaches to a subcommand that the parser does not take.
- ``test_skill_doc_names_the_review_writer_subcommand`` — the writer's ``review``
  subcommand (ADR-5) must be named with its required flags inside one mention.
- ``test_skill_doc_names_the_read_script_and_its_required_flags`` —
  ``review-read.py`` has no subcommand; its required flags must sit inside one
  ``review-read.py …`` mention, not anywhere in the document.
- ``test_every_review_script_span_is_a_contract_mention`` — a backtick span that
  names a review script but matches no mention form (wrapped, reworded) fails,
  so it cannot slip past the sweeps above silently.
- ``test_every_review_script_and_lib_has_its_why_mirror`` (spec 046 T6.2) — a
  review script or lib under ``tomo/scripts/`` without its ``docs/tomo/`` mirror
  fails; the glob is pinned to find the four libs of the T6.2 split.
- ``test_skill_doc_attaches_every_visible_flag_of_match`` — a flag added to
  ``review-session.py match`` (``--template none`` / ``--anchor``, fix round 1 of
  the Phase 6 live-walk fix) without a ``match …`` mention naming it fails; the
  suppressed test flag ``--today`` is exempt.
"""
from __future__ import annotations

import argparse
import re

import pytest

from review_cli_contract import (
    REPO,
    WRITER_SCRIPT,
    build_parsers,
    flags,
    read_mentions,
    required_flags,
    review_subcommands,
    sub_mentions,
    subparsers,
    unmatched_review_spans,
    writer_mentions,
)

DOCS_DIR = REPO / "docs" / "tomo" / "dot_claude"
COMMAND_DOC = DOCS_DIR / "commands" / "review.md"
SKILL_DOC = DOCS_DIR / "skills" / "periodic-review.md"


@pytest.fixture(scope="module")
def parsers():
    return build_parsers()


@pytest.fixture(scope="module")
def subcommands(parsers):
    return review_subcommands(parsers)


@pytest.fixture(scope="module")
def skill_doc() -> str:
    assert SKILL_DOC.is_file(), f"missing WHY document: {SKILL_DOC.relative_to(REPO)}"
    return SKILL_DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def command_doc() -> str:
    assert COMMAND_DOC.is_file(), f"missing WHY document: {COMMAND_DOC.relative_to(REPO)}"
    return COMMAND_DOC.read_text(encoding="utf-8")


def test_both_why_documents_exist():
    assert COMMAND_DOC.is_file(), f"missing WHY document: {COMMAND_DOC.relative_to(REPO)}"
    assert SKILL_DOC.is_file(), f"missing WHY document: {SKILL_DOC.relative_to(REPO)}"


REVIEW_CODE = sorted([*(REPO / "tomo" / "scripts").glob("review-*.py"),
                      *(REPO / "tomo" / "scripts" / "lib").glob("review_*.py")])


def test_the_glob_finds_the_review_scripts_and_the_spec_046_libs():
    names = {p.stem for p in REVIEW_CODE}
    assert {"review-instructions", "review_section_report", "review_kado_conflict", "review_target_read",
            "review_instructions_args"} <= names, sorted(names)


@pytest.mark.parametrize("code", REVIEW_CODE, ids=lambda p: p.name)
def test_every_review_script_and_lib_has_its_why_mirror(code):
    """Spec 046 T6.2: each runtime review file has its docs/tomo/<mirrored path>.md (CLAUDE.md, the WHY layer)."""
    mirror = REPO / "docs" / "tomo" / code.relative_to(REPO / "tomo").with_suffix(".md")
    assert mirror.is_file(), f"missing WHY document: {mirror.relative_to(REPO)}"


def test_parsers_are_the_source_of_the_subcommand_list(subcommands):
    """The guard reads the real parsers: four scripts carry subcommands, review-read.py carries none."""
    assert set(subcommands) == {"review-session.py", "review-doc.py", "review-instructions.py", "review-digest.py"}
    assert all(subcommands[script] for script in subcommands)


def test_skill_doc_names_every_subcommand_of_every_review_parser(skill_doc, subcommands):
    named = {(script, sub) for script, sub, _flags in sub_mentions(skill_doc)}
    expected = {(script, sub) for script, subs in subcommands.items() for sub in subs}
    missing = sorted(expected - named)
    assert not missing, f"the skill WHY document does not name these subcommands as `<script> <sub>`: {missing}"


def test_skill_doc_names_no_subcommand_the_parsers_lack(skill_doc, subcommands):
    mentions = sub_mentions(skill_doc)
    assert mentions, "the skill WHY document names no `<script> <sub>` at all"
    unknown = sorted({(script, sub) for script, sub, _flags in mentions if sub not in subcommands[script]})
    assert not unknown, f"the skill WHY document names subcommands the parsers do not have: {unknown}"
    bad_flags = sorted(
        (script, sub, flag)
        for script, sub, mention_flags in mentions
        for flag in mention_flags
        if flag not in flags(subcommands[script][sub])
    )
    assert not bad_flags, f"the skill WHY document attaches flags a subcommand does not take: {bad_flags}"


def test_skill_doc_attaches_every_visible_flag_of_match(skill_doc, subcommands):
    """The flags the setup dialogue passes back are the contract the WHY document explains: every flag of
    `match` with a help text must sit in some `review-session.py match …` mention of the document."""
    match_parser = subcommands["review-session.py"]["match"]
    visible = {opt for action in match_parser._actions if action.help != argparse.SUPPRESS
               for opt in action.option_strings} - {"-h", "--help"}
    attached = {flag for script, sub, mention_flags in sub_mentions(skill_doc)
                if (script, sub) == ("review-session.py", "match") for flag in mention_flags}
    assert visible <= attached, f"flags of `match` no mention of the skill WHY document attaches: {sorted(visible - attached)}"


def test_skill_doc_names_the_review_writer_subcommand(skill_doc, parsers):
    writer_subs = subparsers(parsers[WRITER_SCRIPT])
    assert "review" in writer_subs, "vault-config-writer.py lost its `review` subcommand (ADR-5)"
    mentions = writer_mentions(skill_doc)
    assert mentions, "the skill WHY document must name `vault-config-writer.py review`"
    writer_flags = flags(writer_subs["review"])
    bad_flags = sorted({flag for mention in mentions for flag in mention if flag not in writer_flags})
    assert not bad_flags, f"the skill WHY document attaches flags the writer's review subcommand does not take: {bad_flags}"
    required = required_flags(writer_subs["review"])
    assert any(required <= set(mention) for mention in mentions), (
        f"no `vault-config-writer.py review …` mention carries every required flag {sorted(required)}: {mentions}")


def test_skill_doc_names_the_read_script_and_its_required_flags(skill_doc, parsers):
    read_parser = parsers["review-read.py"]
    assert not subparsers(read_parser), "review-read.py grew subcommands; extend SUB_MENTION and this test"
    mentions = read_mentions(skill_doc)
    assert mentions, "the skill WHY document must name `review-read.py`"
    read_flags = flags(read_parser)
    bad_flags = sorted({flag for mention in mentions for flag in mention if flag not in read_flags})
    assert not bad_flags, f"the skill WHY document attaches flags review-read.py does not take: {bad_flags}"
    required = required_flags(read_parser)
    assert any(required <= set(mention) for mention in mentions), (
        f"no `review-read.py …` mention carries every required flag {sorted(required)}: {mentions}")


@pytest.mark.parametrize("doc_path", [COMMAND_DOC, SKILL_DOC], ids=["command", "skill"])
def test_every_review_script_span_is_a_contract_mention(doc_path):
    """A backtick span naming a review script must match a mention form, or the sweeps above never see it."""
    stray = unmatched_review_spans(doc_path.read_text(encoding="utf-8"))
    assert not stray, f"{doc_path.name}: spans that name a review script but match no mention form: {stray}"


def test_command_doc_is_the_shim_rationale(command_doc):
    """The command WHY names the shim contract: $ARGUMENTS verbatim into the periodic-review skill (ADR-1)."""
    assert "$ARGUMENTS" in command_doc
    assert "periodic-review" in command_doc
    assert re.search(r"`review-session\.py start`", command_doc), (
        "the command WHY must say that `start` parses the argument, not the shim")


# ── spec 047 T6.1: the WHY layer of the three review agents and the new steps 4/5 ──────────────────────────
#
# Mechanisms a mutation falsifies:
# - ``test_every_review_agent_has_its_why_mirror`` — an agent mirror deleted (or an agent added under
#   tomo/dot_claude/agents/review-*.md without one) fails; the list is fixed so the mirrors exist before the agents.
# - ``test_agent_mirror_names_its_frontmatter_and_reply`` — a mirror that drops the model, the tool pair, the
#   permission mode or the one-line reply fails.
# - ``test_skill_doc_names_every_review_digest_subcommand`` / ``..._no_digest_subcommand_the_parser_lacks`` —
#   read from review-digest.py's own parser, both directions, flags included (SDD gotcha: `plan` and `check`).
# - ``test_proposer_doc_holds_the_moved_rule`` — one row per rationale that leaves SKILL.md step 5 for the
#   proposer (plus the carried rules added since the plan); deleting the row's sentence fails its row.
# - ``test_skill_doc_holds_the_step_4_5_decision`` — one row per decision of the new step 4/5 and per STRICT's
#   observed failure mode.

AGENTS_DOCS = DOCS_DIR / "agents"
RUNTIME_AGENTS = REPO / "tomo" / "dot_claude" / "agents"
REVIEW_AGENTS = {"review-digester": "haiku", "review-carryover": "sonnet", "review-proposer": "opus"}
DIGEST_SCRIPT = "review-digest.py"
DIGEST_MENTION = re.compile(r"`(review-digest\.py) ([a-z][a-z-]*)((?: --[a-z][a-z-]*)*)`")


def _doc(path) -> str:
    assert path.is_file(), f"missing WHY document: {path.relative_to(REPO)}"
    return path.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_the_agent_list_covers_every_runtime_review_agent():
    runtime = {p.stem for p in RUNTIME_AGENTS.glob("review-*.md")}
    assert runtime <= set(REVIEW_AGENTS), f"review agents without an entry in REVIEW_AGENTS: {sorted(runtime - set(REVIEW_AGENTS))}"


@pytest.mark.parametrize("agent", sorted(REVIEW_AGENTS))
def test_every_review_agent_has_its_why_mirror(agent):
    mirror = AGENTS_DOCS / f"{agent}.md"
    assert mirror.is_file(), f"missing WHY document: {mirror.relative_to(REPO)}"


MIRROR_FACTS = [
    # (agent, label, pattern) — each anchored to the sentence that owns the fact, matched exactly once
    ("review-digester", "runtime-file", r"Rationale for decisions in `tomo/dot_claude/agents/review-digester\.md`"),
    ("review-digester", "model", r"WHY `haiku` WHY: ADR-7\. The digester records what the days say"),
    ("review-digester", "tools", r"The digester reads stage files the read already took from the vault and writes exactly its `out` path; no Bash, no MCP"),
    ("review-digester", "permission-mode", r"`permissionMode: acceptEdits` with the `Edit\(tomo-tmp/\*\)` allow rule"),
    ("review-digester", "one-line-reply", r"The reply is `<out> written` or `<out> not written: <reason word>`; whether the file is any good"),
    ("review-digester", "never-kado", r"an agent with a Kado tool could read days the read's report does not account for"),
    ("review-carryover", "runtime-file", r"Rationale for decisions in `tomo/dot_claude/agents/review-carryover\.md`"),
    ("review-carryover", "model", r"WHY `sonnet` WHY: ADR-7\. Telling an open item, an intention or a goal and a theme"),
    ("review-carryover", "tools", r"The agent reads the stage files of the previous notes and writes exactly `carryover\.json`; no Bash, no MCP"),
    ("review-carryover", "permission-mode", r"`permissionMode: acceptEdits` with the unchanged `settings\.json` lets the Write land"),
    ("review-carryover", "one-line-reply", r"quoting previous-note text there would bring journal content into the main conversation"),
    ("review-carryover", "never-kado", r"WHY `tools: Read, Write` and Never Kado WHY: ADR-7, F7-AC5\. The agent reads"),
    ("review-proposer", "runtime-file", r"Rationale for decisions in `tomo/dot_claude/agents/review-proposer\.md`"),
    ("review-proposer", "model", r"WHY `opus` \(ADR-7\) WHY: the proposer is the one judgement-heavy step"),
    ("review-proposer", "tools", r"The proposer reads stage files and writes exactly `proposals\.json`; no Bash, no MCP"),
    ("review-proposer", "permission-mode", r"`permissionMode: acceptEdits` with the unchanged `settings\.json` lets the Write land"),
    ("review-proposer", "one-line-reply", r"Its one-line reply \(`<out> written` or `<out> not written: <reason word>`\)"),
    ("review-proposer", "never-kado", r"WHY `tools: Read, Write`, Never Kado, and a One-Line Reply"),
]


@pytest.mark.parametrize("agent,label,pattern", MIRROR_FACTS, ids=[f"{a}-{lab}" for a, lab, _p in MIRROR_FACTS])
def test_agent_mirror_names_its_frontmatter_and_reply(agent, label, pattern):
    """The mirror gives the runtime file, the model and why, the tool pair, the permission mode, the one-line reply
    and the no-Kado rule, each in the one sentence that owns it."""
    found = len(re.findall(pattern, _flat(_doc(AGENTS_DOCS / f"{agent}.md"))))
    assert found == 1, f"{agent}.md: {label} ({pattern!r}) must match exactly once, matched {found}"


def test_mirror_facts_cover_every_agent():
    assert {a for a, _l, _p in MIRROR_FACTS} == set(REVIEW_AGENTS)
    for agent, model in REVIEW_AGENTS.items():
        assert any(lab == "model" and f"`{model}`" in pat for a, lab, pat in MIRROR_FACTS if a == agent), agent


@pytest.fixture(scope="module")
def digest_subcommands():
    from review_cli_contract import load_script
    return subparsers(load_script(DIGEST_SCRIPT).build_parser())


def test_skill_doc_names_every_review_digest_subcommand(skill_doc, digest_subcommands):
    assert set(digest_subcommands) == {"plan", "check"}
    named = {sub for _script, sub, _flags in DIGEST_MENTION.findall(skill_doc)}
    missing = sorted(set(digest_subcommands) - named)
    assert not missing, f"the skill WHY document does not name `review-digest.py <sub>` for: {missing}"


def test_skill_doc_names_no_digest_subcommand_the_parser_lacks(skill_doc, digest_subcommands):
    mentions = [(sub, rest.split()) for _script, sub, rest in DIGEST_MENTION.findall(skill_doc)]
    assert mentions
    unknown = sorted({sub for sub, _f in mentions if sub not in digest_subcommands})
    assert not unknown, f"the skill WHY document names subcommands review-digest.py does not have: {unknown}"
    bad = sorted((sub, flag) for sub, mention_flags in mentions if sub in digest_subcommands
                 for flag in mention_flags if flag not in flags(digest_subcommands[sub]))
    assert not bad, f"flags a review-digest.py subcommand does not take: {bad}"


# Every row below is anchored to the one sentence or bullet head that owns its rule, and must match exactly once:
# a second match would let the owning sentence be deleted while the row stays green (a hollow pin).
# (label, pattern searched in the whitespace-collapsed document.)

# The rationale that leaves SKILL.md step 5 for review-proposer.md, and the carried / growth / input rules
# added since the plan.
PROPOSER_RULES = [
    ("opus-adr-7", r"WHY `opus` \(ADR-7\)"),
    ("opus-rationale", r"WHY: the proposer is the one judgement-heavy step of `/review`"),
    ("only-proposals-json", r"WHY It Writes Only `proposals\.json` \(Spec 045 ADR-12\)"),
    ("themes-over-all-days-f1-ac3", r"\*\*Themes over all days \(F1-AC3\)\.\*\*"),
    ("open-against-later-weeks-f1-ac4", r"\*\*Open against later weeks \(F1-AC4\)\.\*\*"),
    ("one-item-across-weeks-f1-ac5", r"\*\*One item across weeks \(F1-AC5\)\.\*\*"),
    ("child-marks-whole-period-f2-ac3", r"\*\*Child marks over the whole period \(F2-AC3\)\.\*\*"),
    ("sources-a-daily-of-the-period", r"\*\*Sources\.\*\* Every item names the notes it rests on, at least one a daily"),
    ("continuation-line", r"\*\*A second line of `text`\*\* becomes a continuation line"),
    ("habits-computed", r"\*\*Habits are computed by the script; never proposed\.\*\*"),
    ("own-sections", r"\*\*The user's own sections\.\*\* The proposer never writes text"),
    ("key-copied-unknown-section", r"\*\*The key is copied, never invented\.\*\*.{0,200}refused `unknown-section`"),
    ("description-and-keywords", r"\*\*What a section receives follows its description and keywords \(046 F1-AC2\)\.\*\*"),
    ("groups-starting-point-f2-ac7", r"\*\*A row's `groups` are its starting point \(046 F2-AC7\)\.\*\*"),
    ("reminders-not-finished-text", r"\*\*Reminders, not finished text \(046 F1-AC3, F1-AC4\)\.\*\*"),
    ("cap-by-merging-over-cap", r"\*\*The cap by merging \(046 F1-AC5\)\.\*\* Over `cap` the script refuses `over-cap"),
    ("one-place-double-placement", r"\*\*One place per finding \(046 F1-AC6, F1-AC7\)\.\*\*.{0,120}`double-placement` refuses"),
    ("analysis-rows", r"\*\*Analysis rows as overviews \(046 F2-AC12\)\.\*\* A row marked `analysis: true`"),
    ("marks-mark-not-allowed", r"\*\*Marks stay on the items \(046 F1-AC9\)\.\*\*"),
    ("quarter-marks", r"a quarter's carries `monthly_only` / `not_in_monthly`"),
    ("review-language-f4-ac11", r"\*\*Item text in the review language \(F4-AC11\)\.\*\*"),
    ("rewrite-fixes", r"WHY the Rewrite Gets the Errors Verbatim"),
    ("rewrite-fix-mapping", r"so the one rewrite is aimed: `unknown-section` / `duplicate-section` → each context key once"),
    ("carried-adr-6", r"WHY the Carried Rules \(ADR-6, Feature 4\)"),
    ("script-checks-marks-model-matches", r"the model owns the match of each carried item to the days"),
    ("carried-marks-f4-ac2", r"\*\*The marks \(F4-AC2\)\.\*\* A carried open item or intention is `done`"),
    ("theme-never-done-f4-ac3", r"\*\*A theme is never done \(F4-AC3\)\.\*\*"),
    ("placement-f4-ac4", r"\*\*Placement \(F4-AC4\)\.\*\* A carried item goes into the mapped section"),
    ("off-limits-f4-ac5", r"\*\*Never under an off-limits heading \(F4-AC5\)\.\*\*"),
    ("one-item-nowhere-else-f4-ac6", r"\*\*One item, nowhere else \(F4-AC6, F4-AC7\)\.\*\*"),
    ("carried-again-no-age-f4-ac8", r"\*\*Carried again, no age \(F4-AC8\)\.\*\*"),
    ("same-mark-merge-f4-ac10", r"\*\*Same-mark merge, never across marks \(F4-AC10\)\.\*\*"),
    ("carried-false", r"\*\*`carried: false` means no carried item \(F6-AC2\)\.\*\*"),
    ("no-growth-group-f-r1-3", r"WHY It Proposes No Vault Growth Group \(T9\.3, F-R1-3\)"),
    ("growth-built-by-write", r"`review-doc\.py write` takes the created\s+notes of the read"),
    ("never-manifest-json", r"The proposer never reads `manifest\.json`"),
]


@pytest.fixture(scope="module")
def proposer_doc() -> str:
    return _flat(_doc(AGENTS_DOCS / "review-proposer.md"))


@pytest.mark.parametrize("label,pattern", PROPOSER_RULES, ids=[label for label, _p in PROPOSER_RULES])
def test_proposer_doc_holds_the_moved_rule(proposer_doc, label, pattern):
    found = len(re.findall(pattern, proposer_doc))
    assert found == 1, f"review-proposer.md: {label} ({pattern!r}) must match exactly once, matched {found}"


SKILL_STEP_4_5 = [
    ("plan-mention", r"\*\*`review-digest\.py plan --stem`\*\* lists the jobs still to run"),
    ("check-mention", r"\*\*`review-digest\.py check --stem`\*\* judges every file the agents wrote"),
    ("plan-once-check-twice", r"\*\*`plan` once per run\.\*\* `plan` resets every failed unit"),
    ("failed-twice-stays-failed", r"fails twice stays failed until the next session"),
    ("read-stale", r"\*\*`read-stale`\.\*\* `review-digest\.py plan`"),
    ("continued-read", r"prints `continued: true` with the stored `read_id` and `read_at`"),
    ("fresh-on-start-over", r"\*\*`--fresh` on every Start-over route\.\*\*"),
    ("fresh-mention", r"`review-read\.py --period --kind --stem --fresh` discards the stored material"),
    ("pass-1-abort", r"`review-doc\.py replace --stem --abort` and nothing else: the one exception to the abort rule"),
    ("abort-heading", r"WHY: the Rules say \"on Abort at any question, run no further script and write nothing\""),
    ("agent-in-allowed-tools", r"plus `Agent` since spec 047 for the three review agents"),
    ("one-message-batch", r"All jobs of a round go out as `Agent\(\)` calls in ONE message"),
    ("one-message-strict", r"\*\*One message per round\.\*\* Failure mode"),
    ("subagent-type", r"\*\*`subagent_type` on every call\.\*\* Failure mode"),
    ("subagent-type-general-purpose", r"starts a `general-purpose` agent, which has every tool"),
    ("run-in-background-false", r"\*\*`run_in_background: false`\.\*\* Failure mode"),
    ("spec-043-backgrounded", r"`claude` 2\.1\.316 backgrounded the conductor"),
    ("grep-fallback", r"fell back to `grep` over parts of the read files"),
    ("four-self-started-helpers", r"four `general-purpose` subagents it started itself \(\$2\.83"),
    ("never-an-agent-plan-did-not-list", r"never start an agent `plan` did not list; a unit without a passed digest"),
    ("not-condensed-named", r"\*\*Not condensed is named, never read instead\.\*\*"),
    ("condense-incomplete", r"\*\*`condense-incomplete`\.\*\* `write` refuses"),
    ("nothing-condensed", r"`check` answers `stopped` `nothing-condensed` naming every week"),
    ("proposer-rules-moved", r"every proposal rule now lives in \[review-proposer\]\(\.\./agents/review-proposer\.md\)"),
]


@pytest.mark.parametrize("label,pattern", SKILL_STEP_4_5, ids=[label for label, _p in SKILL_STEP_4_5])
def test_skill_doc_holds_the_step_4_5_decision(skill_doc, label, pattern):
    found = len(re.findall(pattern, _flat(skill_doc)))
    assert found == 1, f"periodic-review.md: {label} ({pattern!r}) must match exactly once, matched {found}"


def test_skill_doc_no_longer_says_no_step_dispatches_a_subagent(skill_doc):
    assert "no step dispatches a subagent" not in _flat(skill_doc)


# --- spec 047 T7.4: the mirror layer covers exactly the files that exist; carry-overs of T2.4 and T4.3 ---------

SCRIPTS_WHY = REPO / "docs" / "tomo" / "scripts"
READ_WHY = SCRIPTS_WHY / "review-read.md"


def test_the_mirror_listing_matches_the_code_listing_one_to_one():
    """The untruncated listing of review scripts and libs and the listing of their WHY documents are the same set:
    no code without a mirror (the per-file test) and no mirror without code (a deleted file's document is deleted too)."""
    code = {p.relative_to(REPO / "tomo").with_suffix(".md") for p in REVIEW_CODE}
    mirrors = {p.relative_to(REPO / "docs" / "tomo")
               for p in [*SCRIPTS_WHY.glob("review-*.md"), *(SCRIPTS_WHY / "lib").glob("review_*.md")]}
    assert mirrors == code, (sorted(mirrors - code), sorted(code - mirrors))


def test_the_deleted_review_read_parts_has_no_file_left():
    """Spec 047 T2.4 replaced lib/review_read_parts.py by review_stage.py; its history lives in review_stage.md."""
    assert not (REPO / "tomo" / "scripts" / "lib" / "review_read_parts.py").exists()
    assert not (SCRIPTS_WHY / "lib" / "review_read_parts.md").exists()
    assert not (REPO / "tests" / "test_review_read_parts.py").exists()


def test_the_contract_covers_review_digest_because_the_script_list_is_derived():
    from review_cli_contract import REVIEW_SCRIPTS, SCRIPT_NAME
    on_disk = sorted(p.name for p in (REPO / "tomo" / "scripts").glob("review-*.py"))
    assert list(REVIEW_SCRIPTS) == on_disk
    assert DIGEST_SCRIPT in REVIEW_SCRIPTS
    assert SCRIPT_NAME.search("`review-digest.py plan --stem`")


def _count(text: str, pattern: str) -> int:
    return len(re.findall(pattern, _flat(text)))


def test_skill_doc_names_the_stage_refusals_of_a_failed_load_not_a_part(skill_doc):
    """The quarter-part mechanism (`read_parts`, one `read-invalid` for a part) was removed with spec 047 T2.4; the
    document names what `review_stage.load` refuses instead, each sentence once."""
    flat = _flat(skill_doc)
    assert "A missing or broken part is `read-invalid`" not in flat
    assert _count(skill_doc, r"A stage that does not load is refused before any Kado call: no manifest is `read-missing`") == 1


def test_review_read_why_says_a_stopped_new_read_leaves_no_stage_and_no_discarded_key():
    text = READ_WHY.read_text(encoding="utf-8")
    assert _count(text, r"A new read that Kado then stops has discarded the stored read and left no stage, "
                        r"and its stop report carries no `discarded` key\.") == 1


def test_review_read_why_says_fresh_over_an_unreadable_manifest_reports_stage_invalid():
    text = READ_WHY.read_text(encoding="utf-8")
    assert _count(text, r"`--fresh` over a manifest that cannot be read reports `stage-invalid`, not `fresh`, "
                        r"because the manifest is judged before the flag\.") == 1


SEE_ALSO = {
    "review_period": {"review_day", "review_children", "review_sources"},
    "review_doc": {"review_sources", "review_carried", "review_sections", "review_doc_parse"},
    "review_sections": {"review_doc", "review_carried", "review_doc_parse"},
    "review_day": {"review_period"},
    "review_children": {"review_period", "review_sources"},
    "review_doc_parse": {"review_doc", "review_sections", "review_carried"},
    "review_sources": {"review_doc", "review_carried"},
    "review_carried": {"review_doc", "review_sections", "review_sources"},
}


@pytest.mark.parametrize("name", sorted(SEE_ALSO))
def test_the_review_lib_mirrors_link_their_neighbours_in_one_see_also_line(name):
    """The split-out libs (spec 047 T5.2, T5.3) and the modules they came from point at each other, each once."""
    lines = [ln for ln in (SCRIPTS_WHY / "lib" / f"{name}.md").read_text(encoding="utf-8").splitlines()
             if ln.startswith("See also: ")]
    assert len(lines) == 1, lines
    linked = set(re.findall(r"\[(\w+)\]\(\1\.md\)", lines[0]))
    assert linked == SEE_ALSO[name]
    assert all((SCRIPTS_WHY / "lib" / f"{n}.md").is_file() for n in linked)
