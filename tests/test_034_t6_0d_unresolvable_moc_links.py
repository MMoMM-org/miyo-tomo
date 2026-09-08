#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t6_0d_unresolvable_moc_links.py — spec 034 T6.0d.

A `link_to_moc` whose `target_moc_path` resolves through neither tier used to
render as an ordinary `- [ ] Applied` checkbox: only the `- **Path:**` line was
suppressed, and the anchor's unresolved branch told the user to *open the MOC*
and find an editable callout — for a MOC that will never exist. It validated
clean, passed the dryrun, and the coverage audit counted it `[OK]`. Under CON-2
the user approves on what the document says, so that is a document that asks
for a thing it knows cannot be done.

`resolve_target_moc_paths`' tier 2 returns None for **three** reasons and only
one of them means the MOC does not exist:

  - `absent`       — Kado answered and there is no such note
  - `unchecked`    — there was no Kado client; nothing was asked
  - `probe-failed` — the Kado call raised and the exception was swallowed

Withholding on a bare null would conflate all three and tell the user that an
offline run's MOCs will never exist, which is false and worse than the defect
being repaired. Each cause is therefore recorded where it is known and carried
through to the user in its own sentence.

What each block pins:

  1. An unresolvable link is not rendered as an appliable instruction, and the
     user is told why, per cause.
  2. A link that DOES resolve is untouched — path line, anchor and all.
  3. The three causes reach the rendered document as three different
     sentences, asserted through `instruction-render.main()` rather than
     through the resolver.
  4. The coverage audit subtracts what the renderer withheld, and reports one
     aggregated note per cause carrying the count — never one note per link.
  5. The marker the resolver writes never reaches the wire.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import build_actions  # noqa: E402

NOTES = "Atlas/202 Notes/"
INBOX = "100 Inbox/"

CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
}

# The MOC Kado answers for. Every other target below is one Kado either denies
# or is never asked about.
LIVE_MOC = "Rivers (MOC)"
LIVE_MOC_PATH = "Atlas/201 MOCs/Rivers (MOC).md"
# Two links share this target, so an aggregating report and a per-link one
# cannot render the same count.
ABSENT_MOC = "Ghosts (MOC)"
FAILING_MOC = "Storms (MOC)"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeKado:
    """The three tier-2 outcomes, chosen per MOC stem.

    A MagicMock cannot stand in here: `search_by_name` returning a Mock is
    truthy, so the resolver would walk into it and the cause under test would
    never be produced.
    """

    def __init__(self, hits: dict[str, list[dict]], raising: set[str]):
        self._hits = hits
        self._raising = raising

    def search_by_name(self, stem: str) -> list[dict]:
        if stem in self._raising:
            raise RuntimeError("kado unreachable")
        return self._hits.get(stem, [])

    def read_note(self, path: str) -> dict:
        return {"content": ""}

    def note_exists(self, path: str) -> bool:
        return True

    def list_dir(self, *_a, **_kw) -> list[dict]:
        return []


def _atomic(item_key: str, title: str, *, idx: int, parents: list[str]):
    stem = item_key.rsplit("/", 1)[-1][:-3]
    manifest = {
        "action": "create_atomic_note",
        "title": title,
        "rendered_file": f"2026-09-08_10{idx:02d}_{title.lower()}.md",
        "destination": NOTES,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": list(parents),
        "tags": [],
        "attachments": [],
    }
    confirmed = {
        "id": f"S{idx:02d}",
        "title": title,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": list(parents),
        "candidate_mocs": [],
        "tags": [],
        "attachments": [],
    }
    return manifest, confirmed


# One item per link so every withholding is attributable, and two items under
# each of the two causes a single run can produce.
PAIRS = [
    _atomic(f"{INBOX}Rivers/Elbe.md", "Elbe", idx=1, parents=[LIVE_MOC]),
    _atomic(f"{INBOX}Rivers/Rhein.md", "Rhein", idx=2, parents=[ABSENT_MOC]),
    _atomic(f"{INBOX}Rivers/Donau.md", "Donau", idx=3, parents=[ABSENT_MOC]),
    _atomic(f"{INBOX}Wetter/Sturm.md", "Sturm", idx=4, parents=[FAILING_MOC]),
    _atomic(f"{INBOX}Wetter/Regen.md", "Regen", idx=5, parents=[FAILING_MOC]),
]


def _built():
    return build_actions(
        [m for m, _ in PAIRS], [c for _, c in PAIRS], [], [], CFG, kado_client=None,
    )


def _parsed_suggestions() -> dict:
    return {
        "confirmed_items": [dict(c) for _, c in PAIRS],
        "daily_updates": [],
        "skipped": [],
    }


def _drive_render(monkeypatch, tmp_path, *, with_client: bool) -> Path:
    """Drive the real `instruction-render.main()` end to end.

    The resolver is NOT monkeypatched: the whole point is that the cause a null
    target carries has to survive every pass between the resolver and the
    rendered markdown. A unit test on the resolver passes while the cause never
    reaches the Skipped section.

    `with_client=False` reproduces the production path where `client` is None —
    `main()` only constructs a KadoClient when there are confirmed items — so
    the `unchecked` cause is reached the way a real run reaches it, not by
    patching the resolver's argument.
    """
    ir = _load("instruction_render_t6_0d", "instruction-render.py")
    built = _built()

    suggestions_file = tmp_path / "suggestions.json"
    suggestions_file.write_text(json.dumps({
        "confirmed_items": ([{
            "id": "S01", "action": None, "title": "placeholder",
            "source_path": "", "tags": [], "parent_mocs": [], "candidate_mocs": [],
        }] if with_client else []),
        # With no confirmed items the run needs some other reason to proceed,
        # and a daily update is the cheapest one that leaves `client` None.
        "daily_updates": ([] if with_client else [{"date": "2026-09-08"}]),
        "skipped": [],
    }), encoding="utf-8")
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    fake = FakeKado(
        hits={LIVE_MOC: [{"path": LIVE_MOC_PATH}]}, raising={FAILING_MOC},
    )
    monkeypatch.setattr(ir, "load_config", lambda _p: {
        "concepts.inbox": INBOX, "profile": "miyo", "callouts.editable": ["NOTE"],
    })
    monkeypatch.setattr(ir, "KadoClient", lambda: fake)
    monkeypatch.setattr(
        ir, "build_actions",
        lambda *_a, **_kw: ([dict(a) for a in built[0]], [dict(s) for s in built[1]]),
    )
    monkeypatch.setattr(ir, "_validate_action_paths", lambda _a: [])

    out_dir = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        "instruction-render.py", "--suggestions", str(suggestions_file),
        "--output-dir", str(out_dir), "--config", str(cfg_file),
    ])
    assert isinstance(ir.main(), int)
    return out_dir


def _md(out_dir: Path) -> str:
    return (out_dir / "instructions.md").read_text(encoding="utf-8")


def _doc(out_dir: Path) -> dict:
    return json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))


def _links(doc: dict) -> list[dict]:
    return [a for a in doc["actions"] if a["action"] == "link_to_moc"]


# ---------------------------------------------------------------------------
# 1. The unresolvable link is not an appliable instruction
# ---------------------------------------------------------------------------

def test_a_link_to_a_moc_kado_says_is_absent_is_not_emitted(monkeypatch, tmp_path):
    doc = _doc(_drive_render(monkeypatch, tmp_path, with_client=True))
    targets = [a["target_moc"] for a in _links(doc)]
    assert ABSENT_MOC not in targets, (
        f"Kado answered that {ABSENT_MOC!r} does not exist, yet the run still "
        f"emitted a link into it: {targets}"
    )


def test_no_tickable_checkbox_names_a_moc_the_run_could_not_confirm(
    monkeypatch, tmp_path,
):
    md = _md(_drive_render(monkeypatch, tmp_path, with_client=True))
    body = md.split("## Skipped", 1)[0]
    for moc in (ABSENT_MOC, FAILING_MOC):
        assert f"Add link to [[{moc}]]" not in body, (
            f"an `- [ ] Applied` instruction still asks the user to open "
            f"{moc!r} — a MOC this run could not confirm exists:\n{body}"
        )


# ---------------------------------------------------------------------------
# 2. The resolving link is untouched
# ---------------------------------------------------------------------------

def test_a_link_that_resolves_is_unaffected(monkeypatch, tmp_path):
    out_dir = _drive_render(monkeypatch, tmp_path, with_client=True)
    doc, md = _doc(out_dir), _md(out_dir)
    live = [a for a in _links(doc) if a["target_moc"] == LIVE_MOC]
    assert len(live) == 1, f"the one resolvable link was lost: {_links(doc)}"
    assert live[0]["target_moc_path"] == LIVE_MOC_PATH
    assert f"Add link to [[{LIVE_MOC}]] — Elbe" in md
    assert f"- **Path:** `{LIVE_MOC_PATH}`" in md


# ---------------------------------------------------------------------------
# 3. Three causes, three sentences, through the rendered document
# ---------------------------------------------------------------------------

def test_the_absent_moc_is_reported_as_confirmed_absent(monkeypatch, tmp_path):
    md = _md(_drive_render(monkeypatch, tmp_path, with_client=True))
    assert "MOC not found" in md, md
    assert ABSENT_MOC in md.split("## Skipped", 1)[1], md


def test_a_failed_kado_probe_is_not_reported_as_a_missing_moc(
    monkeypatch, tmp_path,
):
    md = _md(_drive_render(monkeypatch, tmp_path, with_client=True))
    skipped = md.split("## Skipped", 1)[1]
    assert "MOC could not be checked" in skipped, skipped
    # The two causes must not share one sentence: a swallowed Kado error means
    # nothing was learned about the MOC, and telling the user it is missing
    # invites them to re-create a MOC that is already there.
    absent_line = next(
        line for line in skipped.splitlines() if ABSENT_MOC in line
    )
    failing_line = next(
        line for line in skipped.splitlines() if FAILING_MOC in line
    )
    assert absent_line != failing_line
    assert "not found" in absent_line and "not found" not in failing_line, (
        f"the two causes render the same sentence:\n{absent_line}\n{failing_line}"
    )


def test_an_offline_run_withholds_without_claiming_the_mocs_are_gone(
    monkeypatch, tmp_path,
):
    out_dir = _drive_render(monkeypatch, tmp_path, with_client=False)
    doc, md = _doc(out_dir), _md(out_dir)
    assert _links(doc) == [], (
        "with no Kado client nothing was checked, so no MOC link can be "
        f"offered as appliable: {_links(doc)}"
    )
    skipped = md.split("## Skipped", 1)[1]
    assert "Kado was not available" in skipped, skipped
    assert "not found" not in skipped, (
        "an offline run must never tell the user a MOC does not exist — it "
        f"asked nobody:\n{skipped}"
    )


# ---------------------------------------------------------------------------
# 4. The audit agrees, one aggregated note per cause
# ---------------------------------------------------------------------------

def _run_diff(out_dir: Path):
    diff = _load("instructions_diff_t6_0d", "instructions-diff.py")
    return diff.run_diff(_parsed_suggestions(), _doc(out_dir))


def test_the_audit_completes_clean_when_kado_confirmed_the_moc_absent(
    monkeypatch, tmp_path, capsys,
):
    rc, observations = _run_diff(_drive_render(monkeypatch, tmp_path, with_client=True))
    out = capsys.readouterr().out
    assert rc == 0, (
        "a deliberate withholding is not drift; a hard fail here misdiagnoses "
        f"the guard as a coverage gap:\n{out}"
    )
    absent_notes = [o for o in observations if "confirmed absent" in o]
    assert len(absent_notes) == 1, (
        f"one aggregated note per cause, never one per link: {observations}"
    )
    assert "2 MOC link(s)" in absent_notes[0], (
        "the note must carry the count it aggregated — with a single link an "
        f"aggregating and a per-link implementation look identical: {absent_notes}"
    )


def test_the_two_unchecked_causes_are_two_aggregated_observations(
    monkeypatch, tmp_path,
):
    rc, observations = _run_diff(_drive_render(monkeypatch, tmp_path, with_client=True))
    assert rc == 0
    unchecked = [o for o in observations if "could not be checked" in o]
    assert len(unchecked) == 1 and "2 MOC link(s)" in unchecked[0], (
        f"the swallowed-probe cause owes exactly one aggregated note: {observations}"
    )

    rc2, observations2 = _run_diff(
        _drive_render(monkeypatch, tmp_path / "offline", with_client=False)
    )
    assert rc2 == 0
    offline = [o for o in observations2 if "Kado was not available" in o]
    assert len(offline) == 1 and "5 MOC link(s)" in offline[0], (
        f"the offline cause owes its own aggregated note: {observations2}"
    )
    assert not [o for o in observations2 if "confirmed absent" in o], (
        f"an offline run confirmed nothing absent: {observations2}"
    )


# ---------------------------------------------------------------------------
# 5. The marker never reaches the wire
# ---------------------------------------------------------------------------

def test_the_cause_marker_never_reaches_an_emitted_action(monkeypatch, tmp_path):
    doc = _doc(_drive_render(monkeypatch, tmp_path, with_client=True))
    leaked = [a for a in doc["actions"] if "unresolved_moc" in a]
    assert leaked == [], (
        "Hashi's link_to_moc schema is additionalProperties:false — a "
        f"Tomo-internal marker on the wire makes it reject the set: {leaked}"
    )
