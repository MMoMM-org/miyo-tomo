#!/usr/bin/env python3
# version: 0.2.0
"""test_040_analyst_prose.py — spec 040 T4.2: the analyst's prose contract.

`inbox-analyst.md` is LLM-loaded runtime prose, so the contract is asserted on
the text: Step 4 reads names (never the full MOC list), nominates by meaning,
scores by meaning with the existing thresholds and a four-row decision table;
a new Step 7.5b derives the result filename, writes the nominated names to a
file and fetches their detail once; Step 10.3 reuses the filename; any reader
failure fails the item.

RED on `main`: Step 4 there reads `--field mocs` and `placeholder_links`, and
there is no Step 7.5b.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT = REPO_ROOT / "tomo" / "dot_claude" / "agents" / "inbox-analyst.md"


def _text() -> str:
    return AGENT.read_text(encoding="utf-8")


def _section(start: str, end: str) -> str:
    text = _text()
    i = text.index(start)
    j = text.index(end, i + len(start))
    return text[i:j]


def _bash_blocks(text: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)```", text, re.DOTALL)


def _reader_calls(text: str) -> list[str]:
    return [b for b in _bash_blocks(text) if "read-shared-ctx.py" in b]


# ── no full MOC list, anywhere ───────────────────────────────────────────────

def test_the_full_moc_list_is_never_read():
    text = _text()
    assert "--field mocs" not in text
    assert "shared_ctx.mocs" not in text
    assert "placeholder_links" not in text
    for call in _reader_calls(text):
        assert not re.search(r"--fields?\s+\S*\bmocs\b", call), call


def test_every_reader_call_checks_the_run_id():
    calls = _reader_calls(_text())
    assert len(calls) >= 4, calls  # Step 1, two in Step 4, one in Step 7.5b
    for call in calls:
        assert '--run-id "<run_id>"' in call, call


def test_step_1_strict_forbids_the_mocs_key():
    step1 = _section("### Step 1 ", "### Step 2 ")
    assert "STRICT — NEVER pass `mocs` to `--field` or `--fields`" in step1


# ── Step 4 ───────────────────────────────────────────────────────────────────

def _step4() -> str:
    return _section("### Step 4", "### Step 5")


def test_step_4_reads_names_and_placeholder_targets():
    calls = _reader_calls(_step4())
    assert any("--moc-names" in c for c in calls)
    assert any("--field placeholder_targets" in c for c in calls)


def test_step_4_nominates_by_meaning_with_the_cap():
    step4 = _step4()
    assert "at most 6" in step4
    assert "by meaning" in step4
    assert "0.15" in step4 and "0.5" in step4
    assert "Keep the top 3 with `score ≥ 0.15`" in step4  # F2-AC1: up to three become candidates
    assert "W_TITLE" not in step4 and "overlap_ratio" not in step4  # the formula no longer decides


def test_step_4_decision_table_rows_in_order():
    step4 = _step4()
    rows = [ln for ln in step4.splitlines() if re.match(r"\|\s*[1-4]\s*\|", ln)]
    assert [ln.split("|")[1].strip() for ln in rows] == ["1", "2", "3", "4"]
    assert "placeholder" in rows[0].lower()
    assert "thematic" in rows[1].lower() and "name" in rows[1].lower()
    assert "0.15" in rows[2] and "classification" in rows[2].lower()
    assert "otherwise" in rows[3].lower()


def test_step_4_keeps_the_guard_and_placeholder_rules():
    step4 = _step4()
    for phrase in ("Classification Guard", "is_classification", "needs_new_moc",
                   "Placeholder link trigger", "verbatim", "casing", "takes precedence",
                   "placeholder_targets"):
        assert phrase in step4, phrase


def test_step_4_anchors_read_the_fetched_detail():
    step4 = _step4()
    anchors = step4[step4.index("Anchor emission"):]
    assert "Step 7.5b" in anchors


def test_step_4_placement_fallback_tiers_are_kept():
    """F2-AC3: a fetched MOC without headings or callouts falls back as before."""
    anchors = _step4()[_step4().index("Anchor emission"):]
    tier3 = anchors[anchors.index("TIER-3 — Editable callout fallback"):anchors.index("TIER-4")]
    tier4 = anchors[anchors.index("TIER-4 — H1 title last-resort"):]
    assert "`moc.headings` is absent or empty AND `moc.editable_callouts` is\n  non-empty" in tier3
    assert "absent/empty AND `moc.editable_callouts` is\n  absent/empty, use `moc.title`" in tier4
    assert "fall back to the first body line" in tier4


# ── Step 7.5b ────────────────────────────────────────────────────────────────

def _step75b() -> str:
    return _section("### Step 7.5b", "### Step 8 ")


def test_step_75b_sits_between_7_5_and_8():
    text = _text()
    assert text.index("### Step 7.5 ") < text.index("### Step 7.5b") < text.index("### Step 8 ")


def test_step_75b_derives_the_filename_before_writing_names():
    s = _step75b()
    assert s.index("item-result-filename.py") < s.index(".moc-names.txt")
    assert "<items_dir>/<result_stem>.moc-names.txt" in s
    assert "at most 20" in s and "thread order" in s


def test_step_75b_fetches_detail_once_or_skips():
    s = _step75b()
    calls = _reader_calls(s)
    assert len(calls) == 1 and "--mocs-from" in calls[0]
    assert "nothing was nominated" in s


def test_step_75b_drops_unresolved_names_with_an_issue():
    s = _step75b()
    assert "unresolved" in s and "issues" in s


def test_a_failing_reader_fails_the_item():
    text = _text()
    for heading in ("### Step 1 ", "### Step 4", "### Step 7.5b"):
        section = text[text.index(heading):]
        section = section[: section.index("\n### ", 4)]
        assert "non-zero" in section and "Step 11" in section, heading
    assert "shared_ctx_unavailable" in _section("### Step 11", "### Step 12")


def test_no_new_state_update_blocks():
    """test_034_t2_2 counts exactly four state-update blocks; Step 7.5b adds none."""
    assert "state-update.py" not in "".join(_bash_blocks(_step75b()))


# ── Step 10.3 reuses the filename ────────────────────────────────────────────

def test_step_10_3_reuses_the_captured_filename():
    step10 = _section("### Step 10 ", "### Step 10b")
    assert "item-result-filename.py" not in "".join(_bash_blocks(step10))
    assert "Step 7.5b" in step10


def test_version_bumped():
    m = re.search(r"# version: (\d+)\.(\d+)\.(\d+)", _text())
    assert tuple(map(int, m.groups())) >= (0, 27, 0)
