#!/usr/bin/env python3
# version: 0.4.0
"""test_garden_audit_cli_defaults.py — cwd-relative default resolution (spec 030).

Standard (docs/ai/memory/general.md 2026-06-24): runtime scripts use instance-
correct, cwd-relative path DEFAULTS so the agent calls bare `scripts/foo.py` with
no path switches; switches exist only for host/test overrides.

These tests run each agent-invoked garden-audit script from a tmp cwd laid out
like the instance (config/ + tomo-tmp/) and assert it resolves its defaults with
NO path args. garden-audit.py needs a live Kado for a full run, so its main() is
driven with the KadoClient + run_scan stubbed.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).parent.parent
_SCRIPTS = _ROOT / "tomo" / "scripts"


def _ensure_scripts_on_path() -> None:
    """Add the scripts dir to sys.path ONCE (so `lib.*` imports resolve).

    Guarded so repeated module loads across test variants don't accumulate stale
    duplicate entries.
    """
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))


def _load_script(name: str, filename: str):
    """Load a hyphen-named script module via importlib (scripts dir on path)."""
    _ensure_scripts_on_path()
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(script: str, args: list[str], cwd: Path):
    return subprocess.run(
        [sys.executable, str(_SCRIPTS / script), *args],
        capture_output=True, text=True, cwd=str(cwd),
    )


def _instance_layout(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "tomo-tmp").mkdir()
    return tmp_path


# ── garden-audit-doc fixture ──────────────────────────────────────────────────

def _doc():
    return {
        "run_id": "run-cli-001", "generated": "2026-07-21T12:00:00Z",
        "profile": "miyo", "findings": [
            {
                "id": "F01", "check": "dead_link", "tier": "integrity", "fixable": True,
                "target": {"path": "Notes/S.md", "stem": "S"},
                "detail": {"dead_target": "Missing", "count": 1},
                "decision": {"selected": True, "action": "edit_note_text"},
            }
        ],
        "skipped_checks": [], "skipped_checks_reason": "", "reappeared_exclusions": [],
    }


# ── garden-audit-render.py ────────────────────────────────────────────────────

class TestRenderDefaults:
    def test_bare_run_resolves_input_and_writes_both_artifacts(self, tmp_path):
        inst = _instance_layout(tmp_path)
        (inst / "tomo-tmp" / "garden-audit-doc.json").write_text(
            json.dumps(_doc()), encoding="utf-8"
        )
        rc = _run("garden-audit-render.py", [], inst)
        assert rc.returncode == 0, rc.stderr
        assert (inst / "tomo-tmp" / "garden-audit-report.md").is_file()
        # The wire is the STRUCTURE source — always written on a bare run.
        assert (inst / "tomo-tmp" / "garden-audit-wire.json").is_file()


# ── garden-audit-suggest.py ───────────────────────────────────────────────────

class TestSuggestDefaults:
    def test_bare_run_resolves_defaults_and_writes_in_place(self, tmp_path):
        inst = _instance_layout(tmp_path)
        # Render a report + wire into the default suggest-* paths.
        doc = _doc()
        gar = _load_script("gar_defaults", "garden-audit-render.py")
        report = "\n".join(gar.render_frontmatter(doc)) + "\n" + gar.render_report(doc)
        report = report.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
        (inst / "tomo-tmp" / "suggest-report.md").write_text(report, encoding="utf-8")
        (inst / "tomo-tmp" / "suggest-wire.json").write_text(
            json.dumps(gar.build_wire_payload(doc)), encoding="utf-8"
        )
        (inst / "config" / "moc-structure-cache.yaml").write_text(
            yaml.safe_dump({"entries": [
                {"stem": "Missing Note", "kind": "note", "path": "N/x.md", "topics": []},
            ]}), encoding="utf-8"
        )
        rc = _run("garden-audit-suggest.py", [], inst)
        assert rc.returncode == 0, rc.stderr
        # In-place: --output defaults to --report.
        out = (inst / "tomo-tmp" / "suggest-report.md").read_text(encoding="utf-8")
        assert "[[Missing Note]]" in out and "Pick one" in out


# ── garden-audit-configure.py ─────────────────────────────────────────────────

class TestConfigureDefaults:
    def test_summarize_bare_resolves_input_default(self, tmp_path):
        inst = _instance_layout(tmp_path)
        (inst / "tomo-tmp" / "garden-audit-doc.json").write_text(
            json.dumps(_doc()), encoding="utf-8"
        )
        rc = _run("garden-audit-configure.py", ["--summarize"], inst)
        assert rc.returncode == 0, rc.stderr

    def test_write_bare_resolves_output_default(self, tmp_path):
        # --write with NO --output resolves the default config path.
        inst = _instance_layout(tmp_path)
        (inst / "tomo-tmp" / "garden-audit-choices.json").write_text(
            json.dumps({"today": "2026-07-21", "exclusions": []}), encoding="utf-8"
        )
        rc = _run(
            "garden-audit-configure.py",
            ["--write", "--choices", "tomo-tmp/garden-audit-choices.json"],
            inst,
        )
        assert rc.returncode == 0, rc.stderr
        # Default --output → config/garden-audit-exclusions.yaml was written.
        written = inst / "config" / "garden-audit-exclusions.yaml"
        assert written.is_file()
        assert "configured: true" in written.read_text(encoding="utf-8")


# ── garden-audit.py (bare run resolves cwd-relative defaults; Kado stubbed) ────

def _load_scan_with_fake_kado(monkeypatch, name):
    """Load garden-audit.py with lib.kado_client.KadoClient + run_scan stubbed."""
    mod = _load_script(name, "garden-audit.py")

    class _FakeKado:
        def graph_audit(self, *a, **k):
            return {"orphans": [], "deadLinks": [], "total": {}}

        def list_dir(self, *a, **k):
            return []

    import lib.kado_client as kado_client_mod
    monkeypatch.setattr(kado_client_mod, "KadoClient", lambda *a, **k: _FakeKado())
    return mod


def _scan_instance(tmp_path, *, exclusions_configured=True):
    inst = _instance_layout(tmp_path)
    (inst / "config" / "vault-config.yaml").write_text("profile: miyo\n", encoding="utf-8")
    (inst / "config" / "moc-structure-cache.yaml").write_text(
        yaml.safe_dump({"entries": []}), encoding="utf-8"
    )
    if exclusions_configured:
        (inst / "config" / "garden-audit-exclusions.yaml").write_text(
            "configured: true\nrules: []\n", encoding="utf-8"
        )
    return inst


class TestScanDefaults:
    def test_bare_run_resolves_all_cwd_relative_defaults(self, tmp_path, monkeypatch):
        # No path args at all: config, cache, exclusions, output all resolve from
        # the instance cwd, and the doc is written to the default output path.
        mod = _load_scan_with_fake_kado(monkeypatch, "gascan_bare")
        inst = _scan_instance(tmp_path)
        captured = {}

        def _fake_run_scan(entries, **kwargs):
            captured["exclusions"] = kwargs.get("exclusions")
            return {"run_id": "r", "generated": "g", "profile": "miyo", "findings": []}

        monkeypatch.setattr(mod, "run_scan", _fake_run_scan)
        monkeypatch.chdir(inst)
        monkeypatch.setattr(sys, "argv", ["garden-audit.py"])  # bare
        assert mod.main() == 0
        # Default output path resolved.
        assert (inst / "tomo-tmp" / "garden-audit-doc.json").is_file()
        # Default exclusions path resolved + loaded (configured file present).
        assert captured["exclusions"] is not None


# ── garden-audit.py --no-exclusions skips exclusion loading ───────────────────

class TestNoExclusions:
    """--no-exclusions makes run_scan receive exclusions=None (unfiltered)."""

    def _drive(self, tmp_path, monkeypatch, name, extra_argv):
        mod = _load_scan_with_fake_kado(monkeypatch, name)
        inst = _scan_instance(tmp_path)  # a configured exclusions file EXISTS
        captured = {}

        def _fake_run_scan(entries, **kwargs):
            captured["exclusions"] = kwargs.get("exclusions")
            return {"run_id": "r", "generated": "g", "profile": "miyo", "findings": []}

        monkeypatch.setattr(mod, "run_scan", _fake_run_scan)
        monkeypatch.chdir(inst)
        monkeypatch.setattr(sys, "argv", [
            "garden-audit.py", *extra_argv,
            "--output", str(inst / "tomo-tmp" / "doc.json"),
        ])
        assert mod.main() == 0
        return captured

    def test_no_exclusions_flag_runs_unfiltered(self, tmp_path, monkeypatch):
        # A configured exclusions file exists — a normal run would load it, but
        # --no-exclusions must skip it (exclusions=None).
        captured = self._drive(tmp_path, monkeypatch, "gascan_noex", ["--no-exclusions"])
        assert captured["exclusions"] is None

    def test_default_run_loads_existing_exclusions(self, tmp_path, monkeypatch):
        captured = self._drive(tmp_path, monkeypatch, "gascan_withex", [])
        assert captured["exclusions"] is not None


class TestExclusionsExplicitVsDefault:
    """None-sentinel: a DEFAULTED-but-absent exclusions file runs unfiltered
    (exit 0); an EXPLICITLY-passed missing path is an error (exit 1)."""

    def _stub_run_scan(self, mod, monkeypatch, captured):
        def _fake_run_scan(entries, **kwargs):
            captured["exclusions"] = kwargs.get("exclusions")
            return {"run_id": "r", "generated": "g", "profile": "miyo", "findings": []}
        monkeypatch.setattr(mod, "run_scan", _fake_run_scan)

    def test_defaulted_absent_exclusions_runs_unfiltered_exit_0(self, tmp_path, monkeypatch):
        # No --exclusions passed AND no file at the default path → still exit 0 and
        # effectively unfiltered: an EMPTY GardenExclusions instance (fail-open) is
        # passed so the pushback ledger + settings defaults keep working even
        # without a wizard-written exclusions file (2026-07-23 ack-pushback).
        mod = _load_scan_with_fake_kado(monkeypatch, "gascan_default_absent")
        inst = _scan_instance(tmp_path, exclusions_configured=False)  # no exclusions file
        captured = {}
        self._stub_run_scan(mod, monkeypatch, captured)
        monkeypatch.chdir(inst)
        monkeypatch.setattr(sys, "argv", ["garden-audit.py"])  # bare — defaulted
        assert mod.main() == 0
        excl = captured["exclusions"]
        assert excl is not None
        assert excl.active_rules() == []  # no rules → unfiltered semantics
        assert excl.stale_moc_days == 90  # settings fall back to defaults

    def test_explicit_missing_exclusions_is_error_exit_1(self, tmp_path, monkeypatch):
        # An explicitly-passed missing --exclusions path is a hard error (exit 1),
        # and run_scan is never reached.
        mod = _load_scan_with_fake_kado(monkeypatch, "gascan_explicit_missing")
        inst = _scan_instance(tmp_path, exclusions_configured=False)
        captured = {}
        self._stub_run_scan(mod, monkeypatch, captured)
        monkeypatch.chdir(inst)
        monkeypatch.setattr(sys, "argv", [
            "garden-audit.py", "--exclusions", str(inst / "nope" / "missing.yaml"),
        ])
        assert mod.main() == 1
        assert "exclusions" not in captured  # run_scan never called
