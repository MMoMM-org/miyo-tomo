"""read-shared-ctx.py — field reads for the Phase-B fan-out.

Measured over four runs and 48 subagents, `shared-ctx.json` was reached 58
times: 45 whole-file `cat`s (what the analyst contract's Step 1 prescribes),
9 inline-Python reaches for one field, and 4 whole-file Read calls. The file
is ~40 KB and `mocs` is 72% of it, so a subagent that only files a daily-note
update carries 31 KB of MOC inventory it never opens.

The inline reaches asked for `daily_notes`, `tag_prefixes`,
`placeholder_links`, `classification_keywords` and `asset_folder` — together
under 12 KB. This script is the sanctioned way to ask for exactly those, and
the reason `python3 -c` can be forbidden in the analyst contract the way it
already is in the conductor's.

Spec 040 T2.2: the fixture is no longer hand-written. It drifted from the
builder (string `placeholder_links`, `{prefix, values}` tag prefixes, no
`is_classification`), so the contract test was checking a shape no run ever
produces. It is now the builder's own output over a small cache.
"""

from __future__ import annotations

import functools
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tomo" / "scripts" / "read-shared-ctx.py"
BUILDER = REPO_ROOT / "tomo" / "scripts" / "shared-ctx-builder.py"
SCHEMA = REPO_ROOT / "tomo" / "schemas" / "shared-ctx.schema.json"
RUN_ID = "2026-09-14T14-31-06Z-311f8f"

_spec = importlib.util.spec_from_file_location("read_shared_ctx", SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

_CACHE = {
    "map_notes": [
        {"path": "Atlas/200 Maps/Running (MOC).md", "title": "Running (MOC)",
         "topics": ["laufen", "sport"], "tags": ["type/others/moc"],
         "headings": [{"text": "Training", "level": 2}],
         "editable_callouts": ["> [!blocks]- Notes"]},
        {"path": "Atlas/200 Maps/Projects.md", "title": "Projects", "topics": ["projects"]},
        {"path": "Efforts/Work/Projects.md", "title": "Projects", "topics": ["work"]},
        {"path": "Atlas/200 Maps/2600 - Applied Sciences.md",
         "title": "2600 - Applied Sciences", "topics": ["health"]},
    ],
    "placeholder_links": [
        {"target": "Weinbau (MOC)", "referenced_by": "Atlas/202 Notes/Riesling.md"},
        {"target": "Some Note", "referenced_by": "Atlas/202 Notes/Riesling.md"},
    ],
}

_VAULT_CONFIG = {
    "profile": "miyo",
    "concepts": {
        "inbox": "100 Inbox/",
        "asset": "Atlas/290 Assets/295 Attachments/",
        "map_note": {"paths": ["Atlas/200 Maps/"], "tags": ["type/others/moc"]},
        "calendar": {"granularities": {"daily": {"enabled": True, "path": "Calendar/301 Daily/"}}},
    },
    "naming": {"calendar_patterns": {"daily": "YYYY-MM-DD"}},
    "tags": {"prefixes": {"type": {
        "description": "Note type", "known_values": ["note"], "wildcard": False,
        "proposable": True, "required_for": [],
    }}},
    "trackers": {"daily_note_trackers": {"section": "Habit", "today_fields": [{
        "name": "Sport", "type": "boolean", "syntax": "inline_field",
        "description": "Did physical activity happen today?",
        "positive_keywords": ["Laufrunde"],
    }]}},
    "daily_log": {"cutoff_days": 120, "date_sources": ["content"]},
}


@functools.cache
def _built() -> str:
    """The builder's real output for _CACHE/_VAULT_CONFIG, built once per session."""
    work = Path(tempfile.mkdtemp(prefix="read-shared-ctx-fixture-"))
    (work / "cache.yaml").write_text(yaml.safe_dump(_CACHE), encoding="utf-8")
    (work / "vault-config.yaml").write_text(yaml.safe_dump(_VAULT_CONFIG), encoding="utf-8")
    out = subprocess.run([
        sys.executable, str(BUILDER),
        "--cache", str(work / "cache.yaml"), "--vault-config", str(work / "vault-config.yaml"),
        "--profiles-dir", str(REPO_ROOT / "tomo" / "profiles"),
        "--run-id", RUN_ID, "--output", str(work / "ctx.json"), "--skip-reconcile",
    ], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return (work / "ctx.json").read_text(encoding="utf-8")


def _ctx(tmp_path: Path, **overrides) -> Path:
    data = json.loads(_built())
    data.update(overrides)
    p = tmp_path / "shared-ctx.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_fixture_is_a_valid_built_context():
    import jsonschema

    jsonschema.validate(json.loads(_built()), json.loads(SCHEMA.read_text()))


def _run(capsys, *argv) -> str:
    assert _mod.main(list(argv)) == 0
    return capsys.readouterr().out.rstrip("\n")


class TestSingleField:
    def test_top_level_container_is_json(self, tmp_path, capsys):
        out = _run(capsys, "--ctx", str(_ctx(tmp_path)), "--field", "tag_prefixes")
        assert json.loads(out) == json.loads(_built())["tag_prefixes"]
        assert json.loads(out)[0]["name"] == "type"  # non-vacuity: the prefix was built

    def test_nested_scalar_prints_bare(self, tmp_path, capsys):
        """Captured straight into a shell variable — no JSON quotes around it."""
        p = str(_ctx(tmp_path))
        assert _run(capsys, "--ctx", p, "--field", "daily_notes.daily_log.cutoff_days") == "120"
        assert _run(capsys, "--ctx", p, "--field", "asset_folder") == "Atlas/290 Assets/295 Attachments/"

    def test_booleans_render_lowercase(self, tmp_path, capsys):
        """`trackers_enabled` is branched on by the analyst; Python's `True`
        would not match a shell or JSON comparison the contract might use."""
        out = _run(capsys, "--ctx", str(_ctx(tmp_path)), "--field", "daily_notes.trackers_enabled")
        assert out == "true"

    def test_null_is_distinguishable_from_absent(self, tmp_path, capsys):
        """A key holding null and a missing key mean different things to the
        contract — one is configured-off, the other is an older artifact."""
        p = _ctx(tmp_path, asset_folder=None)
        assert _run(capsys, "--ctx", str(p), "--field", "asset_folder") == "null"
        with pytest.raises(SystemExit):
            _mod.main(["--ctx", str(p), "--field", "no_such_key"])

    def test_unknown_field_names_what_is_available(self, tmp_path):
        """An agent told only 'not found' guesses again; one told the sibling
        names stops."""
        with pytest.raises(SystemExit) as exc:
            _mod.main(["--ctx", str(_ctx(tmp_path)), "--field", "daily_notes.nope"])
        msg = str(exc.value)
        assert "no such field: daily_notes.nope" in msg
        assert "'nope' not present under daily_notes" in msg
        assert "daily_log" in msg and "tracker_fields" in msg

    def test_descending_into_a_scalar_is_an_error(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            _mod.main(["--ctx", str(_ctx(tmp_path)), "--field", "asset_folder.deeper"])
        assert "no such field" in str(exc.value)


class TestOutputSize:
    """The helper must never be larger than the cat it replaces."""

    def test_containers_are_compact_by_default(self, tmp_path, capsys):
        """First version used indent=2 and measured 44 KB for `--field mocs`
        against 40 KB for catting the whole file — the tool built to shrink a
        subagent's context was inflating it."""
        out = _run(capsys, "--ctx", str(_ctx(tmp_path)), "--field", "daily_notes")
        assert "\n" not in out, "container output must be one compact line"
        assert ", " not in out and ": " not in out, "compact separators expected"

    def test_indent_is_opt_in(self, tmp_path, capsys):
        p = str(_ctx(tmp_path))
        compact = _run(capsys, "--ctx", p, "--field", "daily_notes")
        pretty = _run(capsys, "--ctx", p, "--field", "daily_notes", "--indent", "2")
        assert len(pretty) > len(compact)
        assert json.loads(pretty) == json.loads(compact)

    # Smallest tool-result spill observed in a container transcript. Above it,
    # Claude Code writes the result to a file and hands the agent a 2 KB
    # preview plus a path — which the analyst contract forbids it to parse,
    # because parsing it means inline Python.
    SPILL_FLOOR_BYTES = 37_700

    def test_step_1_batch_stays_well_under_the_spill_floor(self, tmp_path, capsys):
        """The 2026-09-15 run loaded six keys in one call: 39.8 KB, spilled,
        and three subagents reached for inline Python to read the spill file."""
        out = _run(
            capsys, "--ctx", str(_ctx(tmp_path)), "--fields",
            "daily_notes,classification_keywords,tag_prefixes,asset_folder",
        )
        assert "mocs" not in json.loads(out), "Step 1 must not carry the MOC keys"
        assert len(out) < self.SPILL_FLOOR_BYTES

    def test_moc_names_cost_less_than_the_mocs_they_name(self, tmp_path, capsys):
        """Spec 040: Step 4 reads names instead of `--field mocs`. The names
        must be a fraction of the detail, or the change bought nothing."""
        p = str(_ctx(tmp_path))
        names = _run(capsys, "--ctx", p, "--moc-names")
        detail = _run(capsys, "--ctx", p, "--field", "mocs")
        assert len(json.loads(names)) == 4
        assert len(names) < len(detail) / 3
        assert len(names) < self.SPILL_FLOOR_BYTES


class TestBatch:
    def test_fields_returns_an_object_keyed_by_the_dotted_path(self, tmp_path, capsys):
        out = _run(
            capsys, "--ctx", str(_ctx(tmp_path)),
            "--fields", "asset_folder,daily_notes.daily_log.cutoff_days",
        )
        assert json.loads(out) == {
            "asset_folder": "Atlas/290 Assets/295 Attachments/",
            "daily_notes.daily_log.cutoff_days": 120,
        }

    def test_batch_shape_is_stable_for_scalars(self, tmp_path, capsys):
        """`--field` prints a scalar bare, `--fields` always wraps in JSON —
        so a caller never has to guess which form a single-name batch gave it."""
        out = _run(capsys, "--ctx", str(_ctx(tmp_path)), "--fields", "asset_folder")
        assert json.loads(out) == {"asset_folder": "Atlas/290 Assets/295 Attachments/"}

    def test_one_unknown_name_fails_the_whole_batch(self, tmp_path):
        with pytest.raises(SystemExit):
            _mod.main(["--ctx", str(_ctx(tmp_path)), "--fields", "asset_folder,nope"])

    def test_whitespace_and_empties_are_tolerated(self, tmp_path, capsys):
        out = _run(capsys, "--ctx", str(_ctx(tmp_path)), "--fields", " asset_folder , ,run_id ")
        assert set(json.loads(out)) == {"asset_folder", "run_id"}


class TestKeys:
    def test_keys_lists_every_top_level_key_with_a_size(self, tmp_path, capsys):
        out = _run(capsys, "--ctx", str(_ctx(tmp_path)), "--keys")
        names = [line.split()[-1] for line in out.splitlines()]
        # spec 040 ADR-7: placeholder_targets replaced placeholder_links
        assert set(names) == {
            "schema_version", "run_id", "asset_folder", "tag_prefixes",
            "classification_keywords", "placeholder_targets", "mocs", "daily_notes",
        }

    def test_keys_are_ordered_largest_first(self, tmp_path, capsys):
        """The ordering is the message: it is what shows a reader that `mocs`
        dominates the payload every subagent carries."""
        out = _run(capsys, "--ctx", str(_ctx(tmp_path)), "--keys")
        sizes = [int(line.split()[0]) for line in out.splitlines()]
        assert sizes == sorted(sizes, reverse=True)


class TestFailureModes:
    def test_missing_file(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            _mod.main(["--ctx", str(tmp_path / "gone.json"), "--keys"])
        assert "no such file" in str(exc.value)

    def test_malformed_json(self, tmp_path):
        p = tmp_path / "shared-ctx.json"
        p.write_text("{not json", encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            _mod.main(["--ctx", str(p), "--keys"])
        assert "not valid JSON" in str(exc.value)

    def test_exactly_one_mode_required(self, tmp_path):
        p = str(_ctx(tmp_path))
        with pytest.raises(SystemExit):
            _mod.main(["--ctx", p])
        with pytest.raises(SystemExit):
            _mod.main(["--ctx", p, "--keys", "--field", "run_id"])


class TestAgainstTheRealContract:
    """Every dotted path `inbox-analyst.md` names must resolve on a real context."""

    # Named by the prose, never emitted by the builder, forbidden by the schema:
    # the "no log at all" branch cannot fire. Pre-existing; see docs/XDD/backlog.md
    # "analyst branches on `daily_log.enabled`". The hand-written fixture hid it.
    KNOWN_DEAD_REFERENCES = ["daily_notes.daily_log.enabled"]

    def test_every_contract_field_resolves(self, tmp_path):
        import re

        agent = (
            Path(__file__).resolve().parent.parent
            / "tomo" / "dot_claude" / "agents" / "inbox-analyst.md"
        )
        paths = {
            m.group(1)
            for m in re.finditer(r"shared_ctx\.([a-z_]+(?:\.[a-z_]+)*)", agent.read_text())
        }
        assert paths, "no shared_ctx references found — the regex or the file moved"

        ctx = _ctx(tmp_path)
        data = json.loads(ctx.read_text())
        unresolved = []
        for dotted in sorted(paths):
            try:
                _mod.resolve(data, dotted)
            except SystemExit:
                unresolved.append(dotted)
        assert unresolved == self.KNOWN_DEAD_REFERENCES, (
            f"the contract names fields a built context does not carry: {unresolved}. "
            f"Either shared-ctx-builder stopped emitting them or the prose is stale."
        )
