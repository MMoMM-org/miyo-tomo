#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t5_2_destination_clash_proposal.py — spec 034 T5.2.

The destination folder is flat, so two notes named `Dresden` cannot both
live in it. `_dest_join` builds the destination from the title with no
collision check, and `_disambiguate_filename` guards only the intermediate
rendered file within one render run — never the vault destination. Pass 1
therefore proposed two identical destinations and said nothing.

This file pins the Pass-1 half of PRD Feature 7. A clash is BOTH halves:
two items in the run claiming one destination, and an item claiming a
destination where a note already lives.

  1. Two items, one destination -> the second gets a distinct proposed name.
  2. A destination already occupied in the vault -> the same treatment, and
     the reason is surfaced in the document (PRD: "surfaced there too" — a
     proposal the user can accept unchanged beats a warning they must act
     on).
  3. Kado absent, unreachable, or skipped (`--fan-resolve`) -> the vault
     half silently does not run and the document renders as it does today.
     Not an error, not a fabricated collision. ADR-4 makes Pass 1 advisory
     and T5.3 the binding guard, so a check that cannot run costs a
     convenience, not a safety property. This case is non-vacuous against
     defensive bugs (a null-check, an unchecked attribute access) and
     deliberately vacuous against the collision logic itself.
  4. The proposed name is an ORDINARY suggested name — same field, same
     shape as any other, carrying no marker. T5.3 depends on this: it must
     be able to honour the user's edit without knowing the name was ever
     adjusted.
  5. A run with no clash is untouched. Byte-identity of the whole document
     is owned by `tests/test_034_t3_4_phase3_gate.py`, which asserts the
     flat golden rendered by the real pipeline at `ee44cb3` (before Phase
     1). Minting a fresh golden after this change would be circular — the
     local half only is asserted here.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.item_key import to_filename  # noqa: E402
from lib.obsidian_filename import is_obsidian_safe  # noqa: E402

NOTES = "Atlas/202 Notes/"
DRESDEN_PLACES = "100 Inbox/Places/Dresden.md"
DRESDEN_REISE = "100 Inbox/Reise/Dresden.md"
ROOT_NOTE = "100 Inbox/Root Note.md"

RE_SUGGESTED_NAME = re.compile(r"^\*\*Suggested name:\*\* (.+)$", re.MULTILINE)
RE_CLASH = re.compile(r"^\*\*Name clash:\*\* (.+)$", re.MULTILINE)


def _load_reducer():
    spec = importlib.util.spec_from_file_location(
        "suggestions_reducer_t5_2", SCRIPTS_DIR / "suggestions-reducer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["suggestions_reducer_t5_2"] = mod
    spec.loader.exec_module(mod)
    return mod


REDUCER = _load_reducer()


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"{cmd[1]} failed (exit {result.returncode})\n"
        f"stderr:\n{result.stderr}\nstdout:\n{result.stdout[:2000]}"
    )
    return result


def _atomic_result(
    stem: str,
    item_key: str,
    title: str,
    *,
    location: str = NOTES,
    force_atomic: bool = False,
) -> dict:
    return {
        "schema_version": "1",
        "stem": stem,
        "item_key": item_key,
        "path": item_key,
        "type": "fleeting_note",
        "type_confidence": 0.9,
        "issues": [],
        "force_atomic": force_atomic,
        "actions": [
            {
                "kind": "create_atomic_note",
                "source_stem": stem,
                "suggested_title": title,
                "template": "Atomic Note.md",
                "location": location,
                "candidate_mocs": [],
                "tags_to_add": [],
                "atomic_note_worthiness": 0.85,
                "classification": None,
                "force_atomic": force_atomic,
            },
        ],
    }


class FakeKado:
    """The reducer's Kado client, reduced to what Pass 1 asks of it.

    `occupied` is the set of vault paths that already hold a note; `list_dir`
    serves them the way Kado does, as entries under a folder. `raises` turns
    every call into a transport failure, which is the unreachable-Kado shape
    (the constructor succeeding and the calls failing) — distinct from a
    missing config, where the constructor itself raises.
    """

    def __init__(self, occupied: set[str] | None = None, raises: bool = False):
        self.occupied = occupied or set()
        self.raises = raises
        self.probed: list[str] = []

    def list_dir(self, path: str, *, depth: int | None = None, limit: int = 500) -> list:
        self.probed.append(path)
        if self.raises:
            raise RuntimeError("kado unreachable")
        prefix = path.rstrip("/") + "/"
        return [
            {"path": p, "type": "file", "modified": 1716300000000, "size": 100}
            for p in sorted(self.occupied)
            if p.startswith(prefix) and "/" not in p[len(prefix):]
        ]


def _reduce(
    work: Path,
    results: dict[str, dict],
    run_id: str,
    *,
    kado: FakeKado | None = None,
    fan_resolve: bool = False,
) -> str:
    """Drive the real reducer + renderer and return the markdown document.

    The reducer runs in-process so `KadoClient` can be swapped for a fake;
    `kado=None` means the flag `--no-kado`, i.e. the degraded run.
    """
    items_dir = work / "items"
    items_dir.mkdir(exist_ok=True)
    state_path = work / "inbox-state.jsonl"

    for item_key, result in results.items():
        for status in ("pending", "running", "done"):
            _run([
                sys.executable, str(SCRIPTS_DIR / "state-update.py"),
                "--state", str(state_path),
                "--item-key", item_key,
                "--stem", result["stem"],
                "--path", item_key,
                "--status", status,
                "--run-id", run_id,
            ])
        (items_dir / to_filename(item_key)).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    doc_path = work / "suggestions-doc.json"
    argv = [
        "suggestions-reducer.py",
        "--state", str(state_path), "--items-dir", str(items_dir),
        "--run-id", run_id, "--profile", "miyo", "--output", str(doc_path),
        "--shared-ctx", str(work / "absent-shared-ctx.json"),
        "--resolved-attachments", str(work / "absent-resolved.json"),
        "--tag-handler-groups-dir", str(work / "absent-thg"),
        "--threshold", "1",
    ]
    if fan_resolve:
        argv.append("--fan-resolve")
    if kado is None and not fan_resolve:
        argv.append("--no-kado")

    real_client = REDUCER.KadoClient
    real_argv = sys.argv
    try:
        sys.argv = argv
        if kado is not None:
            REDUCER.KadoClient = lambda *a, **k: kado
        assert REDUCER.main() == 0
    finally:
        REDUCER.KadoClient = real_client
        sys.argv = real_argv

    md_path = work / "suggestions.md"
    _run([
        sys.executable, str(SCRIPTS_DIR / "suggestions-render.py"),
        "--input", str(doc_path), "--output", str(md_path),
        "--json-output", str(work / "suggestions-wire.json"),
    ])
    return md_path.read_text(encoding="utf-8")


# Both namesakes propose the SAME name into the SAME folder — one destination,
# two claimants. The stems already differ by subfolder, so nothing but the
# proposed name can tell the two destinations apart.
CLASHING_RUN = {
    DRESDEN_PLACES: _atomic_result("Dresden", DRESDEN_PLACES, "Dresden"),
    DRESDEN_REISE: _atomic_result("Dresden", DRESDEN_REISE, "Dresden"),
    ROOT_NOTE: _atomic_result("Root Note", ROOT_NOTE, "Root note takeaway"),
}

# One item whose proposed destination is occupied in the vault; nothing in the
# run collides with anything else, so the run-internal half must stay silent.
VAULT_RUN = {
    DRESDEN_PLACES: _atomic_result("Dresden", DRESDEN_PLACES, "Dresden"),
    ROOT_NOTE: _atomic_result("Root Note", ROOT_NOTE, "Root note takeaway"),
}
OCCUPIED = {f"{NOTES}Dresden.md"}


# ---------------------------------------------------------------------------
# 1. Two items, one destination
# ---------------------------------------------------------------------------

def test_second_claimant_on_one_destination_gets_a_distinct_name(tmp_path):
    doc = _reduce(tmp_path, CLASHING_RUN, "t5-2-run-clash")
    names = RE_SUGGESTED_NAME.findall(doc)
    assert len(names) == 3, f"expected three proposals, got {names}"
    assert len(set(names)) == 3, (
        f"two proposals still claim one destination: {names}"
    )
    assert names.count("Dresden") == 1, (
        f"the first claimant must keep its name, exactly one of them: {names}"
    )


def test_the_run_internal_clash_states_its_reason(tmp_path):
    doc = _reduce(tmp_path, CLASHING_RUN, "t5-2-run-reason")
    reasons = RE_CLASH.findall(doc)
    assert len(reasons) == 1, (
        f"exactly one adjusted proposal, so exactly one reason: {reasons}"
    )
    assert "run" in reasons[0].lower(), (
        f"the reason must say the other claimant is in THIS run: {reasons[0]!r}"
    )


# ---------------------------------------------------------------------------
# 2. A destination already occupied in the vault
# ---------------------------------------------------------------------------

def test_a_destination_occupied_in_the_vault_is_renamed(tmp_path):
    kado = FakeKado(occupied=OCCUPIED)
    doc = _reduce(tmp_path, VAULT_RUN, "t5-2-vault", kado=kado)
    names = RE_SUGGESTED_NAME.findall(doc)
    assert "Dresden" not in names, (
        f"a note already lives at {sorted(OCCUPIED)[0]} — the proposal must "
        f"not target it: {names}"
    )
    assert NOTES in kado.probed, (
        f"the destination folder was never listed: {kado.probed}"
    )


def test_the_vault_clash_surfaces_the_occupied_path(tmp_path):
    doc = _reduce(tmp_path, VAULT_RUN, "t5-2-vault-reason", kado=FakeKado(OCCUPIED))
    reasons = RE_CLASH.findall(doc)
    assert len(reasons) == 1, f"expected one reason, got {reasons}"
    assert f"{NOTES}Dresden.md" in reasons[0], (
        f"the reason must name the note already in the way: {reasons[0]!r}"
    )


# ---------------------------------------------------------------------------
# 3. Kado absent / unreachable / skipped — the vault half degrades quietly
# ---------------------------------------------------------------------------

def test_no_kado_renders_the_document_exactly_as_today(tmp_path):
    doc = _reduce(tmp_path, VAULT_RUN, "t5-2-no-kado")
    assert RE_SUGGESTED_NAME.findall(doc) == ["Dresden", "Root note takeaway"], (
        "with no Kado the vault half cannot run, so nothing may be renamed"
    )
    assert RE_CLASH.findall(doc) == [], (
        "a collision Pass 1 could not observe must not be reported"
    )


def test_fan_resolve_skips_the_vault_half(tmp_path):
    run = {
        key: _atomic_result(
            r["stem"], key, r["actions"][0]["suggested_title"], force_atomic=True
        )
        for key, r in VAULT_RUN.items()
    }
    doc = _reduce(tmp_path, run, "t5-2-fan", fan_resolve=True)
    assert RE_SUGGESTED_NAME.findall(doc) == ["Dresden", "Root note takeaway"]
    assert RE_CLASH.findall(doc) == []


def test_fan_resolve_still_runs_the_run_internal_half(tmp_path):
    """Only the VAULT half degrades without Kado. The run-internal comparison
    needs nothing but the run itself, so it must survive `--fan-resolve` —
    otherwise the resolve doc can propose two notes into one file."""
    run = {
        key: _atomic_result(
            r["stem"], key, r["actions"][0]["suggested_title"], force_atomic=True
        )
        for key, r in CLASHING_RUN.items()
    }
    doc = _reduce(tmp_path, run, "t5-2-fan-clash", fan_resolve=True)
    names = RE_SUGGESTED_NAME.findall(doc)
    assert len(set(names)) == len(names) == 3, (
        f"two resolve-doc proposals still claim one destination: {names}"
    )
    reasons = RE_CLASH.findall(doc)
    assert len(reasons) == 1 and "run" in reasons[0].lower(), reasons


def test_an_unreachable_kado_never_fabricates_a_collision(tmp_path):
    kado = FakeKado(occupied=OCCUPIED, raises=True)
    doc = _reduce(tmp_path, VAULT_RUN, "t5-2-unreachable", kado=kado)
    assert RE_SUGGESTED_NAME.findall(doc) == ["Dresden", "Root note takeaway"], (
        "a failing probe must fail OPEN — an error is not a collision"
    )
    assert RE_CLASH.findall(doc) == []
    assert kado.probed, "the probe must have been attempted, not skipped"


# ---------------------------------------------------------------------------
# 3b. Two names differing only in case are one destination (CON-6)
# ---------------------------------------------------------------------------
# Folding is the fail-safe direction, not a claim about the filesystem: not
# folding on a folding filesystem loses a note silently and unrecoverably,
# folding on a case-sensitive one costs a rename the user can undo. CON-7
# forbids measuring which filesystem is underneath, so the assumption taken is
# the one that survives being wrong.

CASE_RUN = {
    DRESDEN_PLACES: _atomic_result("Dresden", DRESDEN_PLACES, "Dresden"),
    DRESDEN_REISE: _atomic_result("Dresden", DRESDEN_REISE, "dresden"),
    ROOT_NOTE: _atomic_result("Root Note", ROOT_NOTE, "Root note takeaway"),
}


def test_two_run_items_differing_only_in_case_are_one_destination(tmp_path):
    doc = _reduce(tmp_path, CASE_RUN, "t5-2-case-run")
    names = RE_SUGGESTED_NAME.findall(doc)
    assert "Dresden" in names, "the first claimant keeps its name"
    assert "dresden" not in names, (
        f"`Dresden` and `dresden` are one file on a folding filesystem: {names}"
    )


def test_a_case_only_run_clash_says_the_names_differ_only_in_case(tmp_path):
    doc = _reduce(tmp_path, CASE_RUN, "t5-2-case-run-reason")
    reasons = RE_CLASH.findall(doc)
    assert len(reasons) == 1, f"expected one reason, got {reasons}"
    assert "only in case" in reasons[0], (
        "on a case-sensitive filesystem these are two visibly different names — "
        f"a bare collision notice would read as a Tomo bug: {reasons[0]!r}"
    )
    # Both casings, as their authors wrote them.
    assert f"`{NOTES}Dresden.md`" in reasons[0], reasons[0]
    assert f"`{NOTES}dresden.md`" in reasons[0], reasons[0]


def test_a_vault_note_differing_only_in_case_is_a_clash(tmp_path):
    # The user proposes `dresden`; the vault already spells it `Dresden`.
    run = {
        DRESDEN_PLACES: _atomic_result("Dresden", DRESDEN_PLACES, "dresden"),
        ROOT_NOTE: _atomic_result("Root Note", ROOT_NOTE, "Root note takeaway"),
    }
    doc = _reduce(tmp_path, run, "t5-2-case-vault", kado=FakeKado(occupied=OCCUPIED))
    assert "dresden" not in RE_SUGGESTED_NAME.findall(doc), (
        f"{sorted(OCCUPIED)[0]} already holds that file: "
        f"{RE_SUGGESTED_NAME.findall(doc)}"
    )
    reasons = RE_CLASH.findall(doc)
    assert len(reasons) == 1, f"expected one reason, got {reasons}"
    assert "only in case" in reasons[0], reasons[0]
    # The vault's own spelling, not the folded key or the user's casing.
    assert f"`{NOTES}Dresden.md`" in reasons[0], reasons[0]
    assert f"`{NOTES}dresden.md`" in reasons[0], reasons[0]


# ---------------------------------------------------------------------------
# 3c. One listing per destination folder (F9 — runs do not get more expensive)
# ---------------------------------------------------------------------------

def test_one_listing_per_folder_however_the_location_is_spelled(tmp_path):
    """`Atlas/202 Notes` and `Atlas/202 Notes/` name one folder.

    A raw-string cache key would list it twice — and the cost is a doubled
    Kado call and nothing else, so it fails silently rather than erroring.
    The assertion is on the client's own record of the calls it received,
    not on the cache: the observed call is what F9 measures.
    """
    kado = FakeKado(occupied=OCCUPIED)
    run = {
        DRESDEN_PLACES: _atomic_result(
            "Dresden", DRESDEN_PLACES, "Elbe", location=NOTES
        ),
        ROOT_NOTE: _atomic_result(
            "Root Note", ROOT_NOTE, "Root note takeaway", location=NOTES.rstrip("/")
        ),
    }
    _reduce(tmp_path, run, "t5-2-cache-key", kado=kado)
    assert len(kado.probed) == 1, (
        f"one folder, one listing — got {kado.probed}"
    )


# ---------------------------------------------------------------------------
# 4. The proposed name is an ordinary suggested name
# ---------------------------------------------------------------------------

def test_the_adjusted_name_is_an_ordinary_editable_field(tmp_path):
    doc = _reduce(tmp_path, CLASHING_RUN, "t5-2-editable")
    doc_json = json.loads(
        (tmp_path / "suggestions-doc.json").read_text(encoding="utf-8")
    )
    adjusted = [n for n in RE_SUGGESTED_NAME.findall(doc) if n.startswith("Dresden")]
    adjusted = [n for n in adjusted if n != "Dresden"]
    assert len(adjusted) == 1, f"expected one adjusted name, got {adjusted}"
    name = adjusted[0]

    # The name the user reads carries no marker of its own history. Brackets,
    # backticks and emphasis would all be markup a reader has to strip before
    # editing; the vocabulary check catches a name that narrates the rename.
    # Parentheses are NOT markup here — the profile's own MOC suffix is
    # ` (MOC)`, so a parenthesised qualifier is an ordinary Obsidian name.
    assert not re.search(r"[*_`\[\]<>]|clash|auto|adjust|renamed", name, re.IGNORECASE), (
        f"the proposed name must be a plain name a user would type: {name!r}"
    )
    assert is_obsidian_safe(name), f"the proposed name must be filable: {name!r}"

    # And it travels in the same field as any other title, with no extra key.
    items = [
        a["item"]
        for section in doc_json["sections"]
        for a in section["actions"]
        if a.get("item")
    ]
    titles = [i["title"] for i in items]
    assert name in titles, f"the adjusted name never reached `item.title`: {titles}"
    shapes = {tuple(sorted(i.keys())) for i in items}
    assert len(shapes) == 1, (
        f"the adjusted item carries a different set of fields: {shapes}"
    )


# ---------------------------------------------------------------------------
# 5. A run with no clash is untouched
# ---------------------------------------------------------------------------

def test_a_run_without_a_clash_is_untouched(tmp_path):
    run = {
        DRESDEN_PLACES: _atomic_result(
            "Dresden", DRESDEN_PLACES, "Dresden - Frauenkirche"
        ),
        DRESDEN_REISE: _atomic_result(
            "Dresden", DRESDEN_REISE, "Dresden - a different note"
        ),
        ROOT_NOTE: _atomic_result("Root Note", ROOT_NOTE, "Root note takeaway"),
    }
    doc = _reduce(tmp_path, run, "t5-2-clean", kado=FakeKado(occupied=set()))
    assert RE_SUGGESTED_NAME.findall(doc) == [
        "Dresden - Frauenkirche",
        "Dresden - a different note",
        "Root note takeaway",
    ], "no clash — every proposed name must survive verbatim"
    assert "**Name clash:**" not in doc


def test_whole_document_byte_identity_is_owned_by_the_phase_3_gate():
    """The no-clash regression is the flat golden, not a fixture minted here.

    `tests/fixtures/034-t3-4-flat-golden/suggestions.md` was rendered by the
    real pipeline at `ee44cb3`, the commit before Phase 1, and
    `test_034_t3_4_phase3_gate.py` asserts it as a whole string. Re-recording
    it after this change would assert only that the change is what it is.
    """
    golden = TESTS_DIR / "fixtures" / "034-t3-4-flat-golden" / "suggestions.md"
    assert golden.is_file(), f"the no-clash baseline is missing: {golden}"
    assert "**Name clash:**" not in golden.read_text(encoding="utf-8")


def test_both_parser_paths_read_the_adjusted_name_as_an_ordinary_title(tmp_path):
    """T5.3 must be able to honour the user's edit without knowing the name
    was ever adjusted — which is only true if nothing marks it.

    Both Pass-2 entry points are checked: `build_from_wire` (the ADR-026 JSON
    path) and the markdown path `synthesis-conductor.md` actually invokes. The
    `**Name clash:**` line is informational; neither path may lose a field to
    it or carry it into a title.
    """
    doc = _reduce(tmp_path, CLASHING_RUN, "t5-2-parser")
    assert "**Name clash:**" in doc, "fixture no longer produces a clash"

    parser = importlib.util.spec_from_file_location(
        "suggestion_parser_t5_2", SCRIPTS_DIR / "suggestion-parser.py"
    )
    mod = importlib.util.module_from_spec(parser)
    sys.modules["suggestion_parser_t5_2"] = mod
    parser.loader.exec_module(mod)

    wire = json.loads((tmp_path / "suggestions-wire.json").read_text(encoding="utf-8"))
    from_wire = mod.build_from_wire(wire, moc_template="MOC.md")

    approved = tmp_path / "suggestions-approved.md"
    approved.write_text(doc.replace("- [ ] Approved", "- [x] Approved", 1), encoding="utf-8")
    from_md = json.loads(_run([
        sys.executable, str(SCRIPTS_DIR / "suggestion-parser.py"),
        "--file", str(approved),
    ]).stdout)

    expected = sorted(RE_SUGGESTED_NAME.findall(doc))
    for label, parsed in (("wire", from_wire), ("markdown", from_md)):
        titles = sorted(i["title"] for i in parsed["confirmed_items"])
        assert titles == expected, (
            f"the {label} path did not read the proposed names back: {titles}"
        )
        assert not any("clash" in json.dumps(i).lower() for i in parsed["confirmed_items"]), (
            f"the {label} path carried the clash notice into a confirmed item"
        )
