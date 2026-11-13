#!/usr/bin/env python3
# version: 0.2.2
"""review_e2e_walk.py — the driver of the /review end-to-end tests (spec 045 T6.1).

Lives in tests/, not tomo/scripts/lib/: never a production code path. Not
named `test_*`, so pytest does not collect it. Shared by test_review_e2e.py
and test_review_e2e_failures.py so each stays within the constitution's
file-size guidance.

`Walk` runs the four review scripts in-process, each called the way
tomo/dot_claude/skills/periodic-review/SKILL.md calls it (the same
subcommands, flags and file names: `tomo-tmp/review/confirmed-<kind>.json`,
`tomo-tmp/review/<stem>/proposals.json`, the writer's `--input` path), on one
`RecordingVault` — the Phase 4 deliver tests' `GuardedVault` (Kado's write
guard as production sees it) over the privacy fixture's synthetic vault. The
user's part of the flow is simulated on the fake's files directly, never
through the client: editing the document in Obsidian (`edit_document`,
`approve`), creating, moving or renaming a note, and Hashi's apply
(`hashi_apply`: the action's effect on the target per Hashi's
insertUnderMarker / replaceSection / moveNote handlers, then `applied: true`
on the action in the set JSON the way Hashi's jsonAppliedWriter writes it; the
MD peer is not touched — Hashi never ticks it).

The inbox guard (PRD KPI Quality, F1-AC10): `RecordingVault` records every
write Tomo's scripts ATTEMPT through the client — note, file and frontmatter,
before Kado's guard or an injected failure can refuse it — into the vault's
`recorded` list and into the module-level `WRITES` (test id, path). Each
test's `walk` fixture asserts after the test that every recorded path starts
with the configured inbox prefix; a sweep test in each file asserts the same
over whatever `WRITES` holds when it runs (any order, any subset), so a write
outside the inbox fails in the test that attempted it and in every sweep
that runs after it. Shared by test_review_e2e.py, test_review_e2e_failures.py
and test_review_e2e_edges.py.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import yaml

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
for entry in (str(SCRIPTS_DIR), str(TESTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from review_fake_vault import _folder_key, split_frontmatter  # noqa: E402
from review_privacy_fixture import CONFIG, DAILY, INBOX, MOCS, MONTHLY, WEEKLY, build_vault, proposals  # noqa: E402
from review_deliver_helpers import GuardedVault  # noqa: E402

TODAY = "2026-11-11"
SCRIPTS = ("review-session", "review-read", "review-doc", "review-instructions")
WRITER = SCRIPTS_DIR / "vault-config-writer.py"
WEEK, MONTH = "week", "month"
WEEK_PERIOD, MONTH_PERIOD = "2026-W13", "2026-03"
WEEK_STEM, MONTH_STEM = f"{WEEK_PERIOD}_review", f"{MONTH_PERIOD}_review"
WEEK_TARGET, MONTH_TARGET = f"{WEEKLY}{WEEK_PERIOD}.md", f"{MONTHLY}{MONTH_PERIOD}.md"
WEEK_DOC, MONTH_DOC = f"{INBOX}{WEEK_PERIOD} Review.md", f"{INBOX}{MONTH_PERIOD} Review.md"
APPROVED, TICKED = "- [ ] Approved", "- [x] Approved"
MARKER_RE = re.compile(r"^%% tomo-review \S+ %%$", re.M)
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
_FOLDERS = (DAILY, WEEKLY, MONTHLY, MOCS, INBOX)
# the week's target with the configured anchor ("In my own words") in place, no Tomo section yet
WEEK_TARGET_TEXT = ("---\njournal-start-date: 2026-03-23\n---\n# 2026-W13\n\nweek text\n\n"
                    "## Review of the Week\n### [[2026-03-23|2026-03-23 Mon]]\n- day block [[Alpha]]\n\n"
                    "## In my own words\nown words\n")

WRITES: list[tuple[str, str]] = []          # (test id, path) of every write through the client, all tests


class RecordingVault(GuardedVault):
    """The deliver tests' guarded fake with declared folders and every client write recorded."""

    def __init__(self, files: dict, folders=_FOLDERS, test_id: str = "?"):
        super().__init__(files)
        self.folders = {_folder_key(f) for f in folders}
        self.created = {p: 0 for p in self.files}
        self.recorded: list[str] = []
        self.test_id = test_id

    def _record(self, path: str) -> None:
        """Every write attempt, before the guard or an injected failure decides whether it lands."""
        self.recorded.append(path)
        WRITES.append((self.test_id, path))

    def write_note(self, path, content, expected_modified=None):
        self._record(path)
        return super().write_note(path, content, expected_modified)

    def write_file(self, path, data, expected_modified=None):
        self._record(path)
        return super().write_file(path, data, expected_modified)

    def write_frontmatter(self, path, frontmatter, mode="merge", expected_modified=None):
        self._record(path)
        return super().write_frontmatter(path, frontmatter, mode, expected_modified)

    def outside_inbox(self) -> dict:
        """Every file not under the inbox, by path: the part of the vault Tomo may never change."""
        return {p: d for p, d in self.files.items() if not p.startswith(INBOX)}


def config_without_setup() -> dict:
    """The fixture's config with no `review:` section: both kinds are `missing` at start."""
    return {k: v for k, v in CONFIG.items() if k != "review"}


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"review_e2e_{name.replace('-', '_')}",
                                                  SCRIPTS_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class Walk:
    """One instance root in `root` (cwd), the scripts loaded in-process against `vault`."""

    def __init__(self, root: Path, monkeypatch, capsys, test_id: str, *, config: dict | None = None):
        self.root, self.monkeypatch, self.capsys = root, monkeypatch, capsys
        monkeypatch.chdir(root)
        (root / "config").mkdir()
        (root / "config" / "vault-config.yaml").write_text(
            yaml.safe_dump(config if config is not None else config_without_setup()), encoding="utf-8")
        files = build_vault().files
        files[WEEK_TARGET] = WEEK_TARGET_TEXT
        self.vault = RecordingVault(files, test_id=test_id)
        self.mods = {name: _load(name) for name in SCRIPTS}
        for mod in self.mods.values():
            monkeypatch.setattr(mod, "KadoClient", self.vault)
        self.writer = _load("vault-config-writer")

    # ── running the scripts the way the skill does ──
    def run(self, script: str, *argv: str) -> dict:
        """One script call: exit 0 and one JSON object, as the skill reads it."""
        rc = self.mods[script].main(list(argv))
        out, err = self.capsys.readouterr()
        assert rc == 0, (script, argv, rc, err)
        result = json.loads(out)
        if err:                 # the one stderr line a stopped delivery prints: the step and the class, no content
            assert err == f"{script}: delivery failed at {result.get('failed_step')} (KadoError)\n", (script, argv, err)
        return result

    def start(self, request: str = "") -> dict:
        return self.run("review-session", "start", f"--args={request}", "--today", TODAY)

    def read(self, period: str, kind: str) -> dict:
        return self.run("review-read", "--period", period, "--kind", kind, "--stem", f"{period}_review")

    def write(self, stem: str, kind: str, props: dict | None = None) -> dict:
        path = self.stage(stem) / "proposals.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(props if props is not None else proposals(kind)), encoding="utf-8")
        return self.run("review-doc", "write", "--stem", stem, "--proposals", str(path), "--today", TODAY)

    def pass1(self, period: str, kind: str, props: dict | None = None) -> dict:
        """Steps 4 and 5 of the skill: read the period, propose, write the document."""
        read = self.read(period, kind)
        assert read["status"] == "ok" and read["nothing_to_review"] is False, read
        return self.write(f"{period}_review", kind, props)

    def replace(self, stem: str, *flags: str) -> dict:
        return self.run("review-doc", "replace", "--stem", stem, *flags, "--today", TODAY)

    def parse(self, stem: str) -> dict:
        return self.run("review-doc", "parse", "--stem", stem)

    def preview(self, stem: str, *flags: str) -> dict:
        return self.run("review-instructions", "preview", "--stem", stem, *flags)

    def deliver(self, stem: str, *flags: str) -> dict:
        return self.run("review-instructions", "deliver", "--stem", stem, *flags)

    def drop(self, stem: str) -> dict:
        return self.run("review-instructions", "drop", "--stem", stem)

    def status(self, stem: str) -> dict:
        return self.run("review-instructions", "status", "--stem", stem)

    def listing(self) -> list[tuple[str, str]]:
        out = self.start()
        assert out["status"] == "ok" and "notices" not in out, out
        return [(r["stem"], r["state"]) for r in out["open_reviews"]]

    # ── step 2: the setup dialogue ──
    def match(self, kind: str, *flags: str) -> dict:
        """`flags` are the answers the skill passes back, e.g. `--template <name>` after the template question."""
        return self.run("review-session", "match", "--kind", kind, *flags, "--today", TODAY)

    def setup(self, kind: str, *flags: str, **corrections) -> dict:
        """match → Confirm: confirmed-<kind>.json, setup-input, the writer, both files removed."""
        out = self.match(kind, *flags)
        assert out["status"] == "ok", out
        confirmed = self.root / "tomo-tmp" / "review" / f"confirmed-{kind}.json"
        confirmed.parent.mkdir(parents=True, exist_ok=True)
        confirmed.write_text(json.dumps({**out["proposal"], **corrections}), encoding="utf-8")
        out = self.run("review-session", "setup-input", "--kind", kind, "--confirmed", str(confirmed),
                       "--today", TODAY)
        assert out["status"] == "ok", out
        self.monkeypatch.setattr(sys, "argv", ["vault-config-writer.py", "review", "--input", out["input_path"]])
        rc = self.writer.main()
        written, err = self.capsys.readouterr()
        assert rc == 0 and err == "", (rc, err)
        confirmed.unlink()
        Path(out["input_path"]).unlink()
        return json.loads(written)

    # ── the stage ──
    def stage(self, stem: str) -> Path:
        return self.root / "tomo-tmp" / "review" / stem

    def meta(self, stem: str) -> dict:
        return json.loads((self.stage(stem) / "meta.json").read_text(encoding="utf-8"))

    # ── the user in Obsidian ──
    def doc(self, path: str) -> str:
        return self.vault.text(path)

    def edit_document(self, path: str, text: str) -> None:
        """The user saves the document: its text changes and its modified stamp moves on."""
        self.vault.files[path] = text
        self.vault.modified[path] += 1

    def approve(self, path: str) -> None:
        self.edit_document(path, self.doc(path).replace(APPROVED, TICKED, 1))

    def set_json(self, stem: str) -> dict:
        return json.loads(self.vault.text(f"{INBOX}{stem}_instructions.json"))

    def user_deletes(self, *paths: str) -> None:
        for path in paths:
            del self.vault.files[path]

    # ── Hashi ──
    def hashi_apply(self, stem: str) -> list[str]:
        """Apply every unapplied action of the stem's set as Hashi does; return the outcomes."""
        path = f"{INBOX}{stem}_instructions.json"
        doc = self.set_json(stem)
        outcomes = []
        for action in doc["actions"]:
            if action.get("applied") is True:
                outcomes.append("skipped-already")
                continue
            outcome = self._apply(action)
            outcomes.append(outcome)
            if outcome == "applied":
                action["applied"] = True
        self.vault.files[path] = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
        self.vault._bump(path)
        return outcomes

    def _apply(self, action: dict) -> str:
        kind = action["action"]
        if kind == "move_note":
            if action["destination"] in self.vault.files:
                return "failed"                                   # src ✓ dst ✓ → refused (moveNote.ts)
            self.vault.files[action["destination"]] = self.vault.files.pop(action["source"])
            return "applied"
        target = action["target_path"]
        if target not in self.vault.files:
            return "failed"
        lines = self.vault.text(target).split("\n")
        at, level = _heading(lines, action["anchor"]["value"])
        if at is None:
            return "failed"
        block = action["content"].split("\n")
        if kind == "insert_under_marker":
            assert action["placement"] == "before", action["placement"]
            lines[at:at] = block
        elif kind == "replace_section":
            lines[at + 1:_section_end(lines, at, level)] = block
        else:
            raise AssertionError(kind)
        self.vault.files[target] = "\n".join(lines)
        return "applied"


def _heading(lines: list[str], value: str) -> tuple[int | None, int]:
    for index, line in enumerate(lines):
        match = _HEADING_RE.match(line)
        if match and match.group(2).strip() == value:
            return index, len(match.group(1))
    return None, 0


def _section_end(lines: list[str], at: int, level: int) -> int:
    for index in range(at + 1, len(lines)):
        match = _HEADING_RE.match(lines[index])
        if match and len(match.group(1)) <= level:
            return index
    return len(lines)


def tomo_sections(text: str) -> int:
    """How many Tomo review sections a note holds (its markers)."""
    return len(MARKER_RE.findall(text))


def frontmatter(text: str) -> dict:
    return split_frontmatter(text)[0]
