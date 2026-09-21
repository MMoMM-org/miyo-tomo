#!/usr/bin/env python3
# version: 0.1.1
"""test_036_delete_justification_e2e.py — spec 036 / T4.4 end-to-end validation.

Spec 036 is "a delete must not outlive the action that justified it". Its three
measured data-loss paths `[ref: PRD/Problem Statement]` are each proven at
function level already (`tests/test_036_t2_4_phase_validation.py` for P1 and
Bug A, `tests/test_036_t3_3_phase_validation.py` for Bug B). This file proves
them where the user actually meets them: in the two artifacts Pass 2 writes to
disk — `instructions.json` (what Hashi executes) and `instructions.md` (what a
user applying by hand reads).

WHY the artifact and not the functions. Both defects found in this area during
spec 035 lived between the function and the file: `instructions-diff.py` failed
the coverage audit on a legitimately withdrawn delete because it never
subtracted them, and the withheld notice was silently absent from "## Source
Deletions". Every function-level test was green for both. The written artifact
is a surface with its own defects, so it gets its own proof.

SEAM. `instruction-render.py`'s `main()` is driven IN PROCESS with a
constructed `sys.argv`. `KadoClient` — constructed inside `main()` and nowhere
else — is the ONLY stub point; it is replaced with a reader over a cloned slice
of the test vault. Everything downstream of it is the production code path:
`build_actions`, all five drop sites in their real order, the withdrawal pass,
the dangling-id audit, `render_md`, and every file write. A subprocess run would
need a live Kado and is therefore ruled out (CON-7).

Privat-Test is cloned into `tmp_path` per test; the real directory is never
mutated (per `feedback_test_scripts_must_never_touch_real_install.md`).

Run with:
  pytest tests/integration/test_036_delete_justification_e2e.py -v -m integration
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.kado_client import KadoError  # noqa: E402

from .conftest import (  # noqa: E402
    PRIVAT_TEST_ROOT,
    _load_module,
    instruction_render_mod,
    suggestions_reducer_mod,
    suggestion_parser_mod,
)

_tag_handler_group_mod = _load_module(
    "tag_handler_group", SCRIPTS_DIR / "tag-handler-group.py"
)
group_id = _tag_handler_group_mod.group_id

# ── Vault facts this file depends on ─────────────────────────────────────────

INBOX = "100 Inbox/"
NOTES = "Atlas/202 Notes/"
DAILY = "Calendar/301 Daily/"
TEMPLATER = "X/900 Support/930 Templater"

# The last daily note Privat-Test actually has. Everything after it is the gap
# that makes P2 reproducible.
LAST_REAL_DAILY = "2026-09-12"
# A date INSIDE that gap. Deliberately a fixed date, never "today" or "recent":
# a relative date silently stops testing anything the moment the calendar moves
# past whatever the vault holds. `_assert_vault_invariants` fails loudly if
# someone ever adds this daily note to Privat-Test.
MISSING_DAILY_DATE = "2026-09-15"

# Origin notes, all real files in Privat-Test's inbox.
ORIGIN_P1 = f"{INBOX}Dresden.md"
ORIGIN_P2 = f"{INBOX}Laufrunde Elbufer.md"
ORIGIN_P3 = f"{INBOX}Meissen.md"
ORIGIN_HEALTHY = f"{INBOX}Bautzen.md"

# Titles chosen so the P1 contest is a RUN collision between two claimants of
# this run, not a collision with a note the vault already holds — Privat-Test
# has an `Atlas/202 Notes/Dresden.md`, so reusing that name would conflate two
# different clash kinds.
CONTESTED_TITLE = "Elbufer Radweg"
HEALTHY_TITLE = "Bautzen Stadtbild"

# An existing note for the healthy tag-handler group to insert into.
HEALTHY_INSERT_TARGET = f"{NOTES}Atomic Notes.md"


def _assert_vault_invariants() -> None:
    """Fail loudly if the vault facts these fixtures encode have drifted.

    Every one of these is a property of Privat-Test, not of the clone: a test
    that silently stops exercising its path when the source vault changes
    proves nothing, and the failure mode is invisible (a green test asserting
    an absence that is now trivially true).
    """
    missing_daily = PRIVAT_TEST_ROOT / DAILY / f"{MISSING_DAILY_DATE}.md"
    assert not missing_daily.exists(), (
        f"{missing_daily} now exists in Privat-Test — the daily-note gap this "
        f"file's P2 case depends on has closed. Pick a later date inside the "
        f"new gap; do NOT switch to a relative date."
    )
    last_daily = PRIVAT_TEST_ROOT / DAILY / f"{LAST_REAL_DAILY}.md"
    assert last_daily.exists(), (
        f"{last_daily} is gone from Privat-Test — the healthy control's daily "
        f"note must exist, or its run is not a healthy run."
    )
    for origin in (ORIGIN_P1, ORIGIN_P2, ORIGIN_P3, ORIGIN_HEALTHY):
        assert (PRIVAT_TEST_ROOT / origin).exists(), (
            f"{origin} is gone from Privat-Test — the fixtures address real "
            f"inbox notes so the #116 missing-source guard is exercised, not "
            f"bypassed."
        )
    assert (PRIVAT_TEST_ROOT / HEALTHY_INSERT_TARGET).exists(), (
        f"{HEALTHY_INSERT_TARGET} is gone from Privat-Test — the healthy "
        f"tag-handler group needs a real insert target."
    )
    for title in (CONTESTED_TITLE, HEALTHY_TITLE):
        assert not (PRIVAT_TEST_ROOT / NOTES / f"{title}.md").exists(), (
            f"{NOTES}{title}.md now exists in Privat-Test — this run's "
            f"destination contest would no longer be a pure run collision. "
            f"Pick a title the vault does not hold."
        )


# ── The Kado seam ────────────────────────────────────────────────────────────


class _VaultBackedKado:
    """The one stubbed collaborator: a read-only Kado over a cloned vault.

    Implements exactly the five methods the render pipeline calls —
    `note_exists`, `read_note`, `search_by_name`, `list_dir`,
    `resolve_stem_to_path`. Every answer comes from real files in the clone,
    so "the daily note does not exist" is a fact about the vault rather than a
    fact about a hand-written fake's return value.
    """

    def __init__(self, root: Path):
        self.root = root

    def note_exists(self, path: str) -> bool:
        return (self.root / path).is_file()

    def read_note(self, path: str) -> dict:
        target = self.root / path
        if not target.is_file():
            raise KadoError(f"not found: {path}")
        return {"path": path, "content": target.read_text(encoding="utf-8")}

    def search_by_name(self, name: str) -> list[dict]:
        if not name.endswith(".md"):
            name += ".md"
        return [
            {"path": str(p.relative_to(self.root))}
            for p in sorted(self.root.rglob(name))
        ]

    def list_dir(self, folder: str, depth: int = 1) -> list[dict]:
        target = self.root / folder
        if not target.is_dir():
            return []
        return [
            {
                "path": str(p.relative_to(self.root)),
                "type": "file" if p.is_file() else "folder",
            }
            for p in sorted(target.iterdir())
        ]

    def resolve_stem_to_path(self, stem: str) -> str | None:
        hits = self.search_by_name(stem)
        return hits[0]["path"] if hits else None


def _clone_vault_slice(tmp_path: Path) -> Path:
    """Clone the slices of Privat-Test this file's runs actually touch.

    Deliberately NOT the whole vault: `Calendar/301 Daily/` alone is 7.8 MB of
    notes whose only relevant property here is which dates exist. Three real
    daily notes around the boundary carry that property; the gap is asserted
    against the REAL vault in `_assert_vault_invariants`, so the clone cannot
    fake a gap the vault has since closed.
    """
    vault = tmp_path / "vault"

    inbox = vault / "100 Inbox"
    inbox.mkdir(parents=True)
    for note in sorted((PRIVAT_TEST_ROOT / "100 Inbox").glob("*.md")):
        shutil.copy2(note, inbox / note.name)

    notes = vault / "Atlas" / "202 Notes"
    notes.mkdir(parents=True)
    for note in sorted((PRIVAT_TEST_ROOT / "Atlas" / "202 Notes").glob("*.md")):
        shutil.copy2(note, notes / note.name)

    shutil.copytree(
        PRIVAT_TEST_ROOT / "Atlas" / "200 Maps", vault / "Atlas" / "200 Maps"
    )

    templater = vault / TEMPLATER
    templater.mkdir(parents=True)
    for stem in ("t_note_tomo.md", "t_moc_tomo.md"):
        shutil.copy2(PRIVAT_TEST_ROOT / TEMPLATER / stem, templater / stem)

    daily = vault / DAILY
    daily.mkdir(parents=True)
    for date in ("2026-09-10", "2026-09-11", LAST_REAL_DAILY):
        shutil.copy2(
            PRIVAT_TEST_ROOT / DAILY / f"{date}.md", daily / f"{date}.md"
        )

    return vault


# ── Fixture builders ─────────────────────────────────────────────────────────


def _confirmed_atomic(
    item_id: str, item_key: str, title: str, *, destination: str = NOTES
) -> dict:
    """One approved atomic — the shape `suggestion-parser.py` emits."""
    return {
        "id": item_id,
        "source_path": item_key.rsplit("/", 1)[-1][:-3],
        "item_key": item_key,
        "audio_peer": None,
        "attachments": [],
        "approved": True,
        "keep_source": False,
        "action": "create_note",
        "title": title,
        "tags": [],
        "parent_moc": None,
        "parent_mocs": [],
        "destination": destination,
        "template": "t_note_tomo",
        "summary": "",
    }


def _confirmed_moc(item_id: str, title: str, *, destination: str = NOTES) -> dict:
    """An approved `create_moc` — the second claimant in the P1 contest."""
    return {
        "id": item_id,
        "source_path": "",
        "item_key": None,
        "attachments": [],
        "approved": True,
        "action": "create_moc",
        "title": title,
        "tags": [],
        "parent_moc": None,
        "parent_mocs": [],
        "destination": destination,
        "template": "t_moc_tomo",
        "summary": "",
        "supporting_items": None,
    }


def _daily_update(date: str, item_key: str) -> dict:
    """One accepted log entry for *item_key* — a daily-only origin.

    No matching `confirmed_items` entry, so `_build_delete_source_actions`
    site 2 emits a delete for it whose `depends_on` names this entry's action.
    `daily_note_path` is deliberately omitted: the builder derives it from
    *date* and the configured daily folder, which is how production reaches it.
    """
    return {
        "date": date,
        "trackers": [],
        "log_links": [],
        "log_entries": [
            {
                "time": None,
                "position": "after_last_line",
                "content": "Kurze Notiz zum Lauf.",
                "reason": "Short reflection, not atomic-worthy -> inline log",
                "source_stem": item_key.rsplit("/", 1)[-1][:-3],
                "source_item_key": item_key,
                "accepted": True,
                "force_atomic_note": False,
            }
        ],
    }


def _tag_handler_group(*, target_path: str | None, source_paths: list[str]) -> dict:
    """A tag-handler group result (schema: tag-handler-group.schema.json)."""
    return {
        "schema_version": "1",
        "handler": "tsukai",
        "target_path": target_path,
        "marker": "## Captures",
        "composed_block": "### 2026-09-15\n\n- Shipped X (feature)",
        "source_paths": source_paths,
        "placement": "inside",
        "compose_mode": "llm_directive",
    }


def _write_config(tmp_path: Path) -> Path:
    config = {
        "profile": "miyo",
        "concepts": {
            "inbox": INBOX,
            "asset": "Atlas/290 Assets/295 Attachments/",
            "calendar": {"granularities": {"daily": {"path": DAILY}}},
        },
        "daily_log": {"heading": "Daily Log", "heading_level": 2},
    }
    path = tmp_path / "vault-config.yaml"
    path.write_text(yaml.dump(config, allow_unicode=True), encoding="utf-8")
    return path


def _run_instruction_render(
    monkeypatch,
    tmp_path: Path,
    vault: Path,
    suggestions: dict,
    groups: list[dict],
    *,
    run_id: str,
) -> tuple[int, Path]:
    """Drive `instruction-render.py:main()` in process. Returns (exit, out_dir).

    `KadoClient` is replaced in the instruction-render module namespace — the
    one place `main()` constructs it — and `sys.argv` supplies the arguments
    the production launcher supplies. Nothing else is patched.
    """
    groups_dir = tmp_path / "tag-handler-groups"
    groups_dir.mkdir()
    for index, group in enumerate(groups):
        (groups_dir / f"group-{index}.json").write_text(
            json.dumps(group, ensure_ascii=False), encoding="utf-8"
        )

    suggestions_path = tmp_path / "parsed-suggestions.json"
    suggestions_path.write_text(
        json.dumps(suggestions, ensure_ascii=False), encoding="utf-8"
    )

    out_dir = tmp_path / "run" / "rendered"
    config_path = _write_config(tmp_path)

    monkeypatch.setattr(
        instruction_render_mod, "KadoClient", lambda: _VaultBackedKado(vault)
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "instruction-render.py",
            "--suggestions", str(suggestions_path),
            "--output-dir", str(out_dir),
            "--config", str(config_path),
            "--shared-ctx", str(tmp_path / "absent-shared-ctx.json"),
            "--upstream-type", "suggestions",
            "--run-id", run_id,
            "--tag-handler-groups-dir", str(groups_dir),
        ],
    )
    return instruction_render_mod.main(), out_dir


# ── Artifact readers ─────────────────────────────────────────────────────────


def _deletes(actions: list[dict]) -> list[dict]:
    return [a for a in actions if a.get("action") == "delete_source"]


def _delete_paths(actions: list[dict]) -> set[str]:
    return {a.get("source_path") for a in _deletes(actions)}


def _kinds(actions: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for a in actions:
        counts[a.get("action", "?")] = counts.get(a.get("action", "?"), 0) + 1
    return counts


def _assert_no_dangling(actions: list[dict]) -> None:
    surviving = {a["id"] for a in actions if a.get("id")}
    for delete in _deletes(actions):
        assert "depends_on" in delete, (
            f"a delete_source reached the wire with no depends_on key at all: "
            f"{delete}"
        )
        for dep in delete["depends_on"]:
            assert dep in surviving, (
                f"dangling dependency on the WRITTEN wire: {delete.get('id')} "
                f"names {dep!r}, absent from the emitted set"
            )


# ── Test 1 — the mixed refused run ───────────────────────────────────────────


@pytest.mark.integration
def test_all_three_data_loss_paths_in_one_run_emit_no_delete(monkeypatch, tmp_path):
    """One run, one fixture, all three measured paths at once — plus a healthy
    item beside them `[ref: PRD/Problem Statement]`.

    Mixing them is the point. Every existing 036 test drives one path in
    isolation, so nothing yet proves the three passes compose: that the
    withdrawal pass attributes two withdrawals to two DIFFERENT guards in the
    same run, that the staging-note manifest rewrite and the withdrawal pass
    do not interfere, and that a refused path does not take a healthy item's
    actions down with it.

      P1 — `create_moc` and `move_note` contest one destination.
           `validate_destinations` drops both claimants (ADR-3); the move's
           `delete_source` is then withdrawn because the id it named is gone.
      P2 — a daily-only origin whose daily note does not exist.
           `filter_missing_daily_notes` drops the log-entry action; the
           delete naming it is withdrawn.
      P3 — a tag-handler group whose `target_path` never resolved. This one is
           a GUARD, not a withdrawal: `_tag_handler_group_has_resolvable_
           target` (ADR-5) stops the insert AND the delete from being built at
           all, so there is no action for `withdraw_unjustified_deletes` to
           withdraw and none appears in the withdrawal report. Gutting the
           withdrawal pass would NOT turn P3's assertions red — they prove the
           build-time gate, and that is all they claim.

    The P3 group's id is fed in via `approved_tag_handler_group_ids` directly.
    That is the stale-replay path, and it is real: `main()` reads that list
    from a JSON file on disk, so a suggestions doc confirmed before the consent
    gate landed still carries the id. It also forces the run PAST the approval
    short-circuit, which is the only way the build-time gate is the thing under
    test rather than the approval check in front of it.
    """
    _assert_vault_invariants()
    vault = _clone_vault_slice(tmp_path)

    unresolved_group = _tag_handler_group(
        target_path=None, source_paths=[ORIGIN_P3]
    )
    unresolved_gid = group_id(unresolved_group)

    # The consent half of Feature 4, checked against the real Pass-1 chain
    # before the replay: today's reducer renders NO Approve control for this
    # group, so `parse_tag_handler_groups` cannot yield its id. The id fed to
    # the run below is therefore one no current Pass 1 would have produced —
    # which is exactly what makes the replay the right adversarial case.
    # The three assertions below deliberately restate test_036_t3_3_phase_
    # validation.py's A/C/D — they justify this fixture rather than prove new
    # ground. Dropping them would leave `unresolved_gid` looking like an
    # arbitrary id instead of a demonstrably unapprovable one.
    suggestions_reducer_mod.annotate_tag_handler_group_guards(
        [unresolved_group], None
    )
    assert unresolved_group["guard"] == "target_unresolved", (
        f"expected guard='target_unresolved' for a null target_path; got "
        f"{unresolved_group.get('guard')!r}"
    )
    rendered_block = suggestions_reducer_mod.render_tag_handler_updates_block(
        [unresolved_group]
    )
    assert "- [x] Approve" not in rendered_block, (
        f"an unresolved-target group must not render a pre-ticked Approve "
        f"control; got block:\n{rendered_block}"
    )
    assert suggestion_parser_mod.parse_tag_handler_groups(rendered_block) == [], (
        "an unresolved-target group must yield no approved id from the real "
        "render/parse chain"
    )

    suggestions = {
        "confirmed_items": [
            _confirmed_atomic("S01", ORIGIN_P1, CONTESTED_TITLE),
            _confirmed_moc("S02", CONTESTED_TITLE),
            _confirmed_atomic("S03", ORIGIN_HEALTHY, HEALTHY_TITLE),
        ],
        "daily_updates": [_daily_update(MISSING_DAILY_DATE, ORIGIN_P2)],
        "skipped": [],
        "merged_moc_proposals": [],
        "approved_tag_handler_group_ids": [unresolved_gid],
        "tag_handler_keep_source_group_ids": [],
    }

    exit_code, out_dir = _run_instruction_render(
        monkeypatch, tmp_path, vault, suggestions, [unresolved_group],
        run_id="036-T4.4-mixed",
    )
    assert exit_code == 0, "a run that withholds work is not a failed run"

    doc = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))
    actions = doc["actions"]
    md = (out_dir / "instructions.md").read_text(encoding="utf-8")
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    staged = {entry["rendered_file"] for entry in manifest}

    # ── P1 ────────────────────────────────────────────────────────────────
    assert ORIGIN_P1 not in _delete_paths(actions), (
        f"P1: the contested origin must not be deleted — Tomo just refused to "
        f"file it. Deletes on the wire: {sorted(_delete_paths(actions))}"
    )
    assert [a for a in actions if a.get("action") == "create_moc"] == [], (
        "P1: both claimants are dropped (ADR-3), so no create_moc survives"
    )
    assert (vault / ORIGIN_P1).is_file(), (
        "P1: the origin note is still in the inbox — this run instructs "
        "nothing that would remove it"
    )
    assert not any(CONTESTED_TITLE.lower().replace(" ", "-") in name for name in staged), (
        f"P1: the staging notes of both dropped claimants must be removed from "
        f"manifest.json — nothing is left to file them (T6.4c). Staged: {staged}"
    )

    # ── P2 ────────────────────────────────────────────────────────────────
    assert ORIGIN_P2 not in _delete_paths(actions), (
        f"P2: the daily-only origin must not be deleted — its content went "
        f"nowhere, the daily note for {MISSING_DAILY_DATE} does not exist. "
        f"Deletes on the wire: {sorted(_delete_paths(actions))}"
    )
    assert [a for a in actions if a.get("action") == "update_log_entry"] == [], (
        "P2: the log-entry action is dropped — Hashi never creates a daily note"
    )

    # ── P3 ────────────────────────────────────────────────────────────────
    assert [a for a in actions if a.get("action") == "insert_under_marker"] == [], (
        "P3: an unresolved-target group builds no insert_under_marker (ADR-5)"
    )
    assert ORIGIN_P3 not in _delete_paths(actions), (
        f"P3: an unresolved-target group's source must not be deleted — pre-fix "
        f"this emitted one delete per source with the target interpolated as an "
        f"empty string. Deletes on the wire: {sorted(_delete_paths(actions))}"
    )

    # ── The healthy item beside them ──────────────────────────────────────
    healthy_moves = [
        a for a in actions
        if a.get("action") == "move_note" and a.get("source_inbox_item") == ORIGIN_HEALTHY
    ]
    assert len(healthy_moves) == 1, (
        f"the healthy item's move must survive a run in which three other "
        f"paths were refused; got {healthy_moves}"
    )
    healthy_deletes = [
        d for d in _deletes(actions) if d.get("source_path") == ORIGIN_HEALTHY
    ]
    assert len(healthy_deletes) == 1, (
        f"the healthy item's delete must survive too — no cross-contamination "
        f"from the refused paths; got {healthy_deletes}"
    )
    assert healthy_deletes[0]["depends_on"] == [healthy_moves[0]["id"]], (
        f"the surviving delete must still name the move that justifies it; got "
        f"{healthy_deletes[0]}"
    )

    _assert_no_dangling(actions)

    # ── The three withdrawal reporting surfaces ───────────────────────────
    # 1. instructions.json's tomo block — the machine surface, and what
    #    instructions-diff subtracts so a withdrawn delete does not read as a
    #    coverage gap.
    withdrawals = doc["tomo"]["delete_withdrawals"]
    by_path = {w["source_path"]: w for w in withdrawals}
    assert set(by_path) == {ORIGIN_P1, ORIGIN_P2}, (
        f"exactly the two WITHDRAWN deletes belong in the report. P3 emitted no "
        f"action, so it has nothing to withdraw and must not appear here; got "
        f"{sorted(by_path)}"
    )
    assert [c["guard"] for c in by_path[ORIGIN_P1]["causes"]] == [
        "validate_destinations"
    ], f"P1's withdrawal must be attributed to the contest; got {by_path[ORIGIN_P1]}"
    assert [c["guard"] for c in by_path[ORIGIN_P2]["causes"]] == [
        "filter_missing_daily_notes"
    ], f"P2's withdrawal must be attributed to the daily filter; got {by_path[ORIGIN_P2]}"
    for record in withdrawals:
        assert set(record) == {"id", "action", "source_path", "reason", "causes"}, (
            f"Constitution L2: a withdrawal record carries ids, kinds, paths "
            f"and the builder's own reason — nothing else; got {sorted(record)}"
        )

    # 2. instructions.md — the surface a user applying by hand reads. ADR-11:
    #    plain language, no action ids, no wire action names, no guard function
    #    names. The absent delete must be visibly deliberate.
    deletions_section = md.split("## Source Deletions", 1)
    assert len(deletions_section) == 2, (
        "the document must carry a Source Deletions heading for a run that "
        "withheld two of them"
    )
    assert "⚠️ **Not deleted:** [[Dresden]] — the destination note was claimed " \
           "by another approved item" in md, (
        f"P1's withheld delete must be stated in plain language where its "
        f"absence would otherwise be silent; document:\n{md}"
    )
    assert "⚠️ **Not deleted:** [[Laufrunde Elbufer]] — its daily note does " \
           "not exist" in md, (
        f"P2's withheld delete must be stated the same way; document:\n{md}"
    )
    for leak in ("delete_source", "validate_destinations", "filter_missing_daily_notes"):
        assert leak not in md, (
            f"ADR-11: {leak!r} is an executor internal and must not appear in "
            f"the rendered document"
        )

    # 3. The run-level relay file — the only source Step 4 reads.
    relay = out_dir.parent / "withheld-deletes.md"
    assert relay.is_file(), (
        "a run that withheld two deletes must leave the relay file behind"
    )
    relay_text = relay.read_text(encoding="utf-8")
    assert "[[Dresden]]" in relay_text and "[[Laufrunde Elbufer]]" in relay_text, (
        f"both withheld deletes must reach the relay file; got:\n{relay_text}"
    )
    assert "[[Meissen]]" not in relay_text, (
        f"P3 withheld nothing — it built nothing — so it must not be relayed as "
        f"a withdrawal; got:\n{relay_text}"
    )


# ── Test 2 — the permitted control ───────────────────────────────────────────


@pytest.mark.integration
def test_healthy_run_emits_its_deletes_and_withdraws_nothing(monkeypatch, tmp_path):
    """The permitted case Constitution L1 (Testing) requires beside the three
    refusals above `[ref: SDD/CON-5]`, and the Edge Case criterion that a
    healthy run is unchanged apart from the new field `[ref: SDD/Edge Case
    Criteria]`.

    No contest, a daily note that exists, a tag-handler group whose target
    resolves. Every delete this run builds is justified and must ship — the
    failure mode a fail-closed withdrawal pass invites is withdrawing
    everything, and a spec about not deleting notes cannot prove itself by
    deleting none of them.
    """
    _assert_vault_invariants()
    vault = _clone_vault_slice(tmp_path)

    healthy_group = _tag_handler_group(
        target_path=HEALTHY_INSERT_TARGET, source_paths=[ORIGIN_P3]
    )

    suggestions = {
        "confirmed_items": [
            _confirmed_atomic("S01", ORIGIN_P1, CONTESTED_TITLE),
            _confirmed_atomic("S03", ORIGIN_HEALTHY, HEALTHY_TITLE),
        ],
        "daily_updates": [_daily_update(LAST_REAL_DAILY, ORIGIN_P2)],
        "skipped": [],
        "merged_moc_proposals": [],
        "approved_tag_handler_group_ids": [group_id(healthy_group)],
        "tag_handler_keep_source_group_ids": [],
    }

    exit_code, out_dir = _run_instruction_render(
        monkeypatch, tmp_path, vault, suggestions, [healthy_group],
        run_id="036-T4.4-healthy",
    )
    assert exit_code == 0, "a healthy run exits 0"

    doc = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))
    actions = doc["actions"]
    md = (out_dir / "instructions.md").read_text(encoding="utf-8")

    # The full action set, named rather than counted: two atomics moved, one
    # log entry written, one group inserted, and one delete per justified
    # origin (two moved origins, one daily-only origin, one group source).
    assert _kinds(actions) == {
        "move_note": 2,
        "update_log_entry": 1,
        "insert_under_marker": 1,
        "delete_source": 4,
    }, f"the healthy action set changed shape; got {_kinds(actions)}"
    assert doc["action_count"] == len(actions)

    deletes = _deletes(actions)
    assert _delete_paths(actions) == {
        ORIGIN_P1, ORIGIN_HEALTHY, ORIGIN_P2, ORIGIN_P3,
    }, f"every justified origin must still be deleted; got {_delete_paths(actions)}"

    surviving = {a["id"] for a in actions if a.get("id")}
    for delete in deletes:
        assert delete["depends_on"], (
            f"every delete in this run is conditional on a partner action, so "
            f"none may declare depends_on: [] — that asserts 'delete "
            f"unconditionally'; got {delete}"
        )
        assert set(delete["depends_on"]) <= surviving, (
            f"every declared id must be present in the same written set; got "
            f"{delete}"
        )
        # "Unchanged apart from the new field": the pre-036 delete_source
        # carried exactly these four keys plus the `applied` flag every action
        # gets. `depends_on` is the only addition.
        assert set(delete) == {
            "id", "action", "source_path", "reason", "applied", "depends_on",
        }, f"delete_source gained a field beyond depends_on; got {sorted(delete)}"

    # Nothing was withheld, so none of the three withdrawal surfaces exists.
    assert not doc.get("tomo", {}).get("delete_withdrawals"), (
        f"a healthy run withdraws nothing; got "
        f"{doc.get('tomo', {}).get('delete_withdrawals')}"
    )
    assert not (out_dir.parent / "withheld-deletes.md").exists(), (
        "a healthy run leaves no relay file — a stale one from an earlier run "
        "would be relayed to the user as this run's outcome"
    )
    for notice in ("Not deleted:", "Delete withheld:"):
        assert notice not in md, (
            f"a healthy run's document must carry no {notice!r} notice; "
            f"document:\n{md}"
        )

    _assert_no_dangling(actions)
