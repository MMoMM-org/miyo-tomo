#!/usr/bin/env python3
# version: 0.2.0
"""Record tests/fixtures/046-t4-2-unmapped-doc-golden/{week,month}.md and .json from
the `review-doc.py write` of the source tree passed as --tree.

WHY: without a mapping the review document must stay spec 045's byte for byte
(spec 046 F1-AC10, CON-2). The golden was recorded from the branch head before
T4.2 taught `render_document` the section parts: export it with
`git archive <rev> | tar -x -C <dir>` and pass that dir. The fake vault comes
from the SAME tree (tests/review_fake_vault.py); the inputs (read.json,
proposals.json, vault config) are defined here, so the recording is what that
tree's write path produced from them.

Legitimate reasons to re-record: the inputs below were edited for an unrelated
reason, or the unmapped document changed ON PURPOSE and the change was
reviewed. Do NOT re-record from a branch to make
tests/test_046_t4_2_unmapped_doc_golden.py pass — a disagreement is the regression that
test exists to catch.

Normalisation: the `updated_at` line of the tomo: block (the clock) becomes
`updated_at: <normalised>`; everything else is the bytes the fake vault
received. The .json beside each document holds the stdout result and the
meta.json keys, `pass1_counts` and `pass1_links`.

Staging (spec 047 T2.4): a tree with ``lib/review_stage.py`` gets the read as the
stage ``review_stage.write`` leaves; an older tree (before spec 047) gets it as
``read.json``, the file its ``review-doc.py`` loads.

Usage: python3 record.py --tree <exported source tree>
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

import yaml

OUT_DIR = Path(__file__).resolve().parent
INBOX = "100 Inbox/"
DAILY = "Calendar/301 Daily/"
WEEKLY = "Calendar/302 Weekly/"
MONTHLY = "Calendar/303 Monthly/"
_UPDATED = re.compile(r"^(\s*updated_at: ).*$", re.M)


def _daily(day: str) -> str:
    return f"{DAILY}{day}.md"


def _day(day: str, **fields) -> dict:
    return {"date": day, "dailies": [_daily(day)], "sections": {"Daily Log": "x"}, "fields": fields,
            "partly_read": day == "2026-03-25", "has_content": True, "links": [], "problems": [], "tasks": [],
            "linked": []}


def _read(period: dict, days: list) -> dict:
    return {
        "period": period, "days": days, "open_tasks": [],
        "growth": {"created": [], "mocs_changed": [], "mocs_linked_by_new": []},
        "not_read": [f"{DAILY}2026-03-28 Extra.md"],
        "report": {"days": [], "growth": {"created": 0, "mocs_changed": 0, "mocs_linked_by_new": 0,
                                          "moc_folders": 1, "kado_none": []},
                   "kado_empty": [], "not_read": [], "advice": []},
    }


def _item(text: str, *sources: str) -> dict:
    return {"text": text, "sources": list(sources)}


def week_case() -> dict:
    days = [_day(f"2026-03-{d}", Sport="ja" if d != 28 else "-") for d in range(23, 30)]
    read = _read({"kind": "week", "name": "2026-W13", "start": "2026-03-23", "end": "2026-03-29"}, days)
    proposals = {"language": "de", "groups": {
        "done": [_item("Woche aufgeräumt\n# keine Überschrift\n- [ ] kein Kasten", _daily("2026-03-24"), "2026-03-26"),
                 _item("Steuer abgeschickt", "2026-03-25")],
        "open": [_item("Vermieter antworten", "2026-03-27"), _item("ohne Quelle", "2025-01-01")],
        "themes": [_item("Schlaf", "2026-03-23", "2026-03-25")],
    }}
    files = {f"{WEEKLY}2026-W13.md": "# W13\n\n## In my own words\n"}
    return {"read": read, "proposals": proposals, "files": files, "language": "de"}


def month_case() -> dict:
    days = [_day(f"2026-03-{d:02d}", Sport="ja" if d % 2 else "nein") for d in range(1, 32)]
    read = _read({"kind": "month", "name": "2026-03", "start": "2026-03-01", "end": "2026-03-31"}, days)
    read["weekly"] = [{"path": f"{WEEKLY}2026-W13.md", "week": "2026-W13", "overlap_days": 7}]
    proposals = {"language": "en", "groups": {
        "done": [_item("Tax filed", "2026-03-24")],
        "growth": [_item("New note on X", "2026-03-10")],
        "weekly_only": [_item("Only the weekly says so", f"{WEEKLY}2026-W13.md")],
        "not_in_weekly": [_item("Missing from the weekly", "2026-03-02")],
    }}
    return {"read": read, "proposals": proposals, "files": {}, "language": "en"}


CASES = {"week": week_case, "month": month_case}


def _config(language: str) -> dict:
    return {
        "concepts": {"inbox": INBOX, "calendar": {"granularities": {
            "daily": {"enabled": True, "path": DAILY},
            "weekly": {"enabled": True, "path": WEEKLY},
            "monthly": {"enabled": True, "path": MONTHLY}}}},
        "naming": {"calendar_patterns": {"weekly": "GGGG-[W]WW", "monthly": "YYYY-MM"}},
        "review": {
            "language": language,
            "week": {"first_day": "monday", "min_days_in_first_week": 4},
            "weekly": {"heading": "Tomo Review", "place": {"anchor": "In my own words", "placement": "before"},
                       "own_sections": ["In my own words"]},
            "monthly": {"heading": "Tomo Review", "place": {"anchor": "Reflections", "placement": "inside"},
                        "own_sections": ["Reflections"]},
        },
        "trackers": {"daily_note_trackers": {"today_fields": [{"name": "Sport", "type": "boolean"}]}},
    }


def _stage_read(tree: Path, stage: Path, stem: str, read: dict) -> None:
    """The read as ``tree``'s review-doc.py loads it: the stage, or ``read.json`` before spec 047."""
    if not (tree / "tomo/scripts/lib/review_stage.py").is_file():
        (stage / "read.json").write_text(json.dumps(read), encoding="utf-8")
        return
    from lib import review_stage
    from lib.period import ISO
    review_stage.write(stage, read, stem=stem, rule=ISO, sections_digest=review_stage.sections_digest(None))


def capture(tree: Path, name: str) -> dict:
    """``{doc, result}`` of one case written by ``tree``'s review-doc.py on ``tree``'s fake vault."""
    for sub in ("tomo/scripts", "tests"):
        if str(tree / sub) not in sys.path:
            sys.path.insert(0, str(tree / sub))
    from review_fake_vault import ReviewFakeVault

    spec = importlib.util.spec_from_file_location(f"review_doc_golden_{name}", tree / "tomo/scripts/review-doc.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    case = CASES[name]()
    fake = ReviewFakeVault(dict(case["files"]))
    module.KadoClient = fake
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "config").mkdir()
        (root / "profiles").mkdir()
        (root / "profiles" / "miyo.yaml").write_text(yaml.safe_dump({"concept_defaults": {}}), encoding="utf-8")
        (root / "config" / "vault-config.yaml").write_text(yaml.safe_dump(_config(case["language"])),
                                                           encoding="utf-8")
        stem = f"{case['read']['period']['name']}_review"
        stage = root / "tomo-tmp" / "review" / stem
        stage.mkdir(parents=True)
        _stage_read(tree, stage, stem, case["read"])
        (stage / "proposals.json").write_text(json.dumps(case["proposals"]), encoding="utf-8")
        os.chdir(root)
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                code = module.main(["--profiles-dir", "profiles", "write", "--stem", stem,
                                    "--proposals", str(stage / "proposals.json"), "--run-id", "r-golden",
                                    "--today", "2026-04-02"])
            meta = json.loads((stage / "meta.json").read_text(encoding="utf-8"))
        finally:
            os.chdir(cwd)
    [path] = [p for p in fake.writes if p.endswith(" Review.md")]
    result = json.loads(out.getvalue())
    return {
        "doc": _UPDATED.sub(r"\1<normalised>", fake.text(path)),
        "result": {"code": code, "stdout": result, "meta_keys": sorted(meta),
                   "pass1_counts": meta["pass1_counts"], "pass1_links": meta["pass1_links"]},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", required=True, type=Path, help="exported source tree (the pre-T4.2 head)")
    args = parser.parse_args()
    for name in CASES:
        got = capture(args.tree.resolve(), name)
        (OUT_DIR / f"{name}.md").write_text(got["doc"], encoding="utf-8")
        (OUT_DIR / f"{name}.json").write_text(json.dumps(got["result"], indent=2, sort_keys=True,
                                                         ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
