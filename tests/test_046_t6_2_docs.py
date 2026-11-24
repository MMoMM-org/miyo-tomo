#!/usr/bin/env python3
# version: 0.2.0
"""test_046_t6_2_docs.py — spec 046 T6.2: the documentation half of the template-sections feature.

Pins facts, not wording:

(a) PRIVACY.md names what a mapped or quarterly review reads and keeps: the quarter's monthly notes in the
    `/review` paragraph, the preview's per-section lines and a moved block's heading (the only note text the
    mapped stdout fields `sections[].lines` and `sections[].block_at.heading` carry,
    tomo/scripts/review-instructions.py docstring), and in "Where read content rests" the setup's
    `rows-<kind>.json` (review-session.py `match`); the quarter's read parts (`read-index.json`,
    `read-<YYYY-MM>.json`) are no longer named, since spec 047 stores every kind in the same stage folder
    (lib/review_stage.py; the files themselves are pinned in tests/test_review_privacy_docs.py).
(b) tomo/config/vault-example.yaml parses, and its commented review example maps sections of the quarterly
    template that the real reader (lib.review_config.review_setup, the production path) reads back as rows,
    keyed by templates.mapping.quarterly, and that lib.review_config.input_problems accepts as writer input.
(c) every managed file under tomo/ that this branch changed and that carries a `# version:` header on `main`
    carries a greater one now (CLAUDE.md: bump on every edit).
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
PRIVACY = ROOT / "PRIVACY.md"
EXAMPLE = ROOT / "tomo" / "config" / "vault-example.yaml"

sys.path.insert(0, str(ROOT / "tomo" / "scripts"))
from lib import review_config as rc  # noqa: E402

TODAY = date(2026, 11, 12)
VERSION_RE = re.compile(r"^#\s*version:\s*([0-9]+(?:\.[0-9]+)*)\s*$", re.M)


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "")).lower()


def _sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.;])\s", _plain(text))


def _one_sentence_has(text: str, *phrases: str) -> None:
    assert any(all(p.lower() in s for p in phrases) for s in _sentences(text)), \
        f"no single sentence holds all of {phrases}"


def _section(text: str, heading_pattern: str) -> str:
    m = re.search(rf"^(#+) ({heading_pattern})\s*$", text, re.M | re.I)
    assert m, f"missing heading matching {heading_pattern!r}"
    rest = text[m.end():]
    nxt = re.search(rf"^#{{1,{len(m.group(1))}}} ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _review_paragraph() -> str:
    section = _section(PRIVACY.read_text(encoding="utf-8"), r"What vault content reaches the LLM")
    m = re.search(r"^During \*\*`/review`\*\*", section, re.M)
    assert m, "PRIVACY.md needs a paragraph starting 'During **`/review`**'"
    rest = section[m.start():]
    nxt = re.search(r"^(During |#+ )", rest[1:], re.M)
    return rest[: nxt.start() + 1] if nxt else rest


def _rests() -> str:
    return _section(PRIVACY.read_text(encoding="utf-8"), r"Where read content rests")


# --- (a) PRIVACY.md ---------------------------------------------------------------------------

def test_review_paragraph_names_the_quarters_monthly_notes() -> None:
    _one_sentence_has(_review_paragraph(), "monthly notes", "quarter")


def test_review_paragraph_names_the_preview_lines_per_section() -> None:
    _one_sentence_has(_review_paragraph(), "each mapped section", "lines")


def test_review_paragraph_names_the_heading_a_moved_block_sits_under() -> None:
    _one_sentence_has(_review_paragraph(), "moved", "heading")


def test_where_read_content_rests_no_longer_names_the_quarters_read_parts() -> None:
    rests = _rests().lower()
    assert "read-index.json" not in rests and "read-<yyyy-mm>.json" not in rests


def test_where_read_content_rests_names_the_rows_file() -> None:
    _one_sentence_has(_rests(), "`rows-<kind>.json`", "headings")


# --- (b) vault-example.yaml -------------------------------------------------------------------

def _commented_review_example() -> dict:
    lines = EXAMPLE.read_text(encoding="utf-8").splitlines()
    start = lines.index("# review:")
    block = []
    for line in lines[start:]:
        if line.startswith("# ───") or not line.startswith("#"):
            break
        block.append(line[2:] if line.startswith("# ") else line[1:])
    return yaml.safe_load("\n".join(block))["review"]


def test_quarterly_example_maps_sections_the_real_reader_reads() -> None:
    config = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    config["review"] = _commented_review_example()
    config["concepts"]["calendar"]["granularities"]["quarterly"] = {"enabled": True, "path": "Calendar/Quarterly/"}
    template = config["templates"]["mapping"]["quarterly"]
    stored = config["review"]["quarterly"]
    assert set(stored.get("sections") or {}) == {template}, "the quarterly rows are keyed by the mapped template"

    setup = rc.review_setup(config, {}, "quarter", today=TODAY)
    assert setup is not None
    assert [r["id"] for r in setup.sections] == [r["id"] for r in stored["sections"][template]]

    writer_input = {"kind": "quarter", "folder": "Calendar/Quarterly/", "format": "YYYY-[Q]Q",
                    "template": template, "heading": stored["heading"], "place": stored["place"],
                    "language": "de", "sections": stored["sections"][template]}
    assert rc.input_problems(writer_input, today=TODAY) == []


# --- (c) version bumps ------------------------------------------------------------------------

def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def _merge_base() -> str:
    if _git("rev-parse", "--verify", "--quiet", "main").returncode:
        pytest.skip("no local main branch to compare against")
    base = _git("merge-base", "main", "HEAD")
    if base.returncode:
        pytest.skip("no merge base between main and HEAD")
    return base.stdout.strip()


def _changed_managed_files(base: str) -> list[str]:
    out = _git("diff", "--name-only", base, "--", "tomo/")
    return sorted(p for p in out.stdout.splitlines() if (ROOT / p).is_file())


def _version(text: str):
    m = VERSION_RE.search(text)
    return tuple(int(n) for n in m.group(1).split(".")) if m else None


def test_every_changed_managed_file_carries_a_greater_version() -> None:
    base = _merge_base()
    stale, checked = [], 0
    for path in _changed_managed_files(base):
        before = _git("show", f"{base}:{path}")
        if before.returncode:
            continue                                   # new on this branch: nothing to compare
        old = _version(before.stdout)
        if old is None:
            continue                                   # no version header at the base (e.g. JSON schemas)
        checked += 1
        new = _version((ROOT / path).read_text(encoding="utf-8"))
        if new is None or new <= old:
            stale.append(f"{path}: {old} -> {new}")
    if not checked:
        pytest.skip("no versioned managed file changed since the merge base")
    assert not stale, f"version not bumped: {stale}"
