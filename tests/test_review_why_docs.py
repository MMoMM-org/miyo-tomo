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
    """The guard reads the real parsers: three scripts carry subcommands, review-read.py carries none."""
    assert set(subcommands) == {"review-session.py", "review-doc.py", "review-instructions.py"}
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


@pytest.mark.parametrize("agent", sorted(REVIEW_AGENTS))
def test_agent_mirror_names_its_frontmatter_and_reply(agent):
    text = _flat(_doc(AGENTS_DOCS / f"{agent}.md"))
    assert f"tomo/dot_claude/agents/{agent}.md" in text, "the mirror must name its runtime file"
    assert f"`{REVIEW_AGENTS[agent]}`" in text, f"the mirror must give the model `{REVIEW_AGENTS[agent]}` and why"
    assert "`tools: Read, Write`" in text and "`permissionMode: acceptEdits`" in text
    assert re.search(r"one[- ]line reply|replies (?:with )?one line", text, re.I), "the mirror must give why the reply is one line"
    assert "Kado" in text, "the mirror must give why the agent never reaches Kado or the vault"


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


# The rationale that leaves SKILL.md step 5 for review-proposer.md, and the carried / growth / input rules
# added since the plan. (label, pattern searched in the whitespace-collapsed document.)
PROPOSER_RULES = [
    ("opus-adr-7", r"`opus`.*ADR-7|ADR-7.*`opus`"),
    ("only-proposals-json", r"only `proposals\.json`"),
    ("themes-over-all-days-f1-ac3", r"F1-AC3"),
    ("open-against-later-weeks-f1-ac4", r"F1-AC4"),
    ("one-item-across-weeks-f1-ac5", r"F1-AC5"),
    ("child-marks-whole-period-f2-ac3", r"F2-AC3"),
    ("sources-a-daily-of-the-period", r"at least one (?:link to )?a? ?daily"),
    ("continuation-line", r"continuation line"),
    ("habits-computed", r"[Hh]abits are computed"),
    ("own-sections", r"user's own sections"),
    ("key-copied-unknown-section", r"`unknown-section`"),
    ("description-and-keywords", r"description and keywords"),
    ("groups-starting-point-f2-ac7", r"F2-AC7"),
    ("reminders-not-finished-text", r"[Rr]eminders, not finished text"),
    ("cap-by-merging-over-cap", r"`over-cap"),
    ("one-place-double-placement", r"`double-placement`"),
    ("analysis-rows", r"`analysis: true`"),
    ("marks-mark-not-allowed", r"`mark-not-allowed`"),
    ("quarter-marks", r"`monthly_only`"),
    ("review-language-f4-ac11", r"F4-AC11"),
    ("rewrite-fixes", r"errors verbatim"),
    ("carried-adr-6", r"ADR-6"),
    ("script-checks-marks-model-matches", r"model owns the match"),
    ("carried-marks-f4-ac2", r"F4-AC2"),
    ("theme-never-done-f4-ac3", r"F4-AC3"),
    ("placement-f4-ac4", r"F4-AC4"),
    ("off-limits-f4-ac5", r"F4-AC5"),
    ("one-item-nowhere-else-f4-ac6", r"F4-AC6"),
    ("carried-again-no-age-f4-ac8", r"F4-AC8"),
    ("same-mark-merge-f4-ac10", r"F4-AC10"),
    ("carried-false", r"`carried: false`"),
    ("growth-candidates", r"growth candidates"),
    ("growth-counts-and-moc-lists", r"growth counts and (?:the )?MOC lists"),
    ("never-manifest-json", r"never reads? `manifest\.json`"),
]


@pytest.fixture(scope="module")
def proposer_doc() -> str:
    return _flat(_doc(AGENTS_DOCS / "review-proposer.md"))


@pytest.mark.parametrize("label,pattern", PROPOSER_RULES, ids=[label for label, _p in PROPOSER_RULES])
def test_proposer_doc_holds_the_moved_rule(proposer_doc, label, pattern):
    assert re.search(pattern, proposer_doc, re.I), f"review-proposer.md has no home for {label} ({pattern!r})"


SKILL_STEP_4_5 = [
    ("plan-mention", r"`review-digest\.py plan"),
    ("check-mention", r"`review-digest\.py check"),
    ("plan-once-check-twice", r"\*\*`plan` once per run\.\*\* `plan` resets every failed unit"),
    ("failed-twice-stays-failed", r"fails twice stays failed until the next session"),
    ("read-stale", r"`read-stale`"),
    ("continued-read", r"`continued: true`"),
    ("fresh-on-start-over", r"`review-read\.py --period --kind --stem --fresh`"),
    ("pass-1-abort", r"`review-doc\.py replace --stem --abort`"),
    ("abort-exception", r"and nothing else"),
    ("agent-in-allowed-tools", r"`Agent`"),
    ("one-message-batch", r"one message"),
    ("subagent-type-general-purpose", r"`general-purpose`"),
    ("subagent-type", r"`subagent_type`"),
    ("run-in-background-false", r"`run_in_background: false`"),
    ("spec-043-backgrounded", r"backgrounded"),
    ("grep-fallback", r"`grep`"),
    ("four-self-started-helpers", r"four .{0,40}subagents.{0,80}\$2\.83|\$2\.83.{0,80}four"),
    ("never-an-agent-plan-did-not-list", r"`plan` did not list"),
    ("not-condensed-named", r"not condensed"),
    ("condense-incomplete", r"`condense-incomplete`"),
    ("nothing-condensed", r"`nothing-condensed`"),
    ("proposer-rules-moved", r"review-proposer\.md"),
]


@pytest.mark.parametrize("label,pattern", SKILL_STEP_4_5, ids=[label for label, _p in SKILL_STEP_4_5])
def test_skill_doc_holds_the_step_4_5_decision(skill_doc, label, pattern):
    assert re.search(pattern, _flat(skill_doc)), f"periodic-review.md has no WHY for {label} ({pattern!r})"


def test_skill_doc_no_longer_says_no_step_dispatches_a_subagent(skill_doc):
    assert "no step dispatches a subagent" not in _flat(skill_doc)
