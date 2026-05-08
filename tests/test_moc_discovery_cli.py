#!/usr/bin/env python3
# version: 0.1.1
"""test_moc_discovery_cli.py — CLI scaffolding + mode routing for moc-discovery.py.

F-43 Phase 2 T2.1: covers `route_input(args)` mode dispatch (PRD/AC-1.1-1.7),
the `--dry-run` short-circuit (no Kado calls, JSON DiscoveryReport on stdout),
and the exit-code 2 fatal path when profile resolution fails.

Phase stubs (`phase1_select_candidates`, etc.) are NotImplementedError in this
slice — those land in T2.2-T2.7. These tests intentionally exercise only the
pieces shipped by T2.1.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
PROFILES_DIR = REPO_ROOT / "tomo" / "profiles"
SCRIPT_PATH = SCRIPTS_DIR / "moc-discovery.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load moc-discovery.py as a module for direct route_input() / main() access.
_spec = importlib.util.spec_from_file_location("moc_discovery", SCRIPT_PATH)
moc_discovery = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["moc_discovery"] = moc_discovery
_spec.loader.exec_module(moc_discovery)


def _ns(**overrides) -> Namespace:
    """Build an argparse.Namespace mirroring moc-discovery.py's parser shape."""
    base = dict(
        tag=None,
        folder=None,
        klass=None,  # `class` is reserved → argparse `dest="klass"`
        title=None,
        free_text=None,
        config=None,
        profile=None,
        cache=None,
        dry_run=False,
        candidate_cap=None,
    )
    base.update(overrides)
    return Namespace(**base)


# ── route_input() — PRD/AC-1.1 through AC-1.7 ──────────────────────────────


def test_route_tag_mode():
    """AC-1.1: --tag <prefix> → ('tag', '<prefix>')."""
    args = _ns(tag="topic/applied/zsh")
    assert moc_discovery.route_input(args) == ("tag", "topic/applied/zsh")


def test_route_folder_mode():
    """AC-1.2: --folder <path> → ('folder', '<path>')."""
    args = _ns(folder="Atlas/202 Notes/2611 Code Snippets/")
    assert moc_discovery.route_input(args) == (
        "folder",
        "Atlas/202 Notes/2611 Code Snippets/",
    )


def test_route_class_mode():
    """AC-1.3: --class <NNNN> → ('class', '<NNNN>')."""
    args = _ns(klass="2600")
    assert moc_discovery.route_input(args) == ("class", "2600")


def test_route_title_mode():
    """AC-1.4: --title <text> → ('title', '<text>')."""
    args = _ns(title="Shell & Terminal")
    assert moc_discovery.route_input(args) == ("title", "Shell & Terminal")


def test_route_freetext_when_unknown_prefix():
    """AC-1.7: free-text positional with `:` is NOT reinterpreted as a flag.

    `foo:bar` lands as positional → ('free-text', 'foo:bar'). Disambiguates
    against titles like "Shell: A Survey" (PRD/AC-1.7).
    """
    args = _ns(free_text="foo:bar")
    assert moc_discovery.route_input(args) == ("free-text", "foo:bar")


def test_route_no_args():
    """AC-1.6: no args → whole-vault density scan ('scan', '')."""
    args = _ns()
    assert moc_discovery.route_input(args) == ("scan", "")


def test_route_input_rejects_empty_string():
    """An accidental `--tag ""` must raise ValueError, not silently scan.

    Empty-string flag values were previously falsy → fell through every guard
    and routed to scan mode silently. route_input now uses `is not None` and
    rejects empty strings explicitly so misrouting is impossible.
    """
    with pytest.raises(ValueError, match="non-empty"):
        moc_discovery.route_input(_ns(tag=""))


# ── --dry-run + exit-code paths ────────────────────────────────────────────


def test_dry_run_emits_json_to_stdout_and_skips_kado(tmp_path):
    """`--dry-run` writes a minimal DiscoveryReport JSON and skips Kado.

    The Kado client must not be instantiated on the dry-run path — we point
    KADO_API_BASE_URL at an unreachable address; if main() did call Kado the
    subprocess would either hang or surface a connection error in stderr.
    """
    # Minimal vault-config so profile resolution succeeds.
    config_path = tmp_path / "vault-config.yaml"
    config_path.write_text("profile: miyo\n", encoding="utf-8")

    cache_path = tmp_path / "discovery-cache.yaml"
    cache_path.write_text("map_notes: []\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--dry-run",
            "--config",
            str(config_path),
            "--cache",
            str(cache_path),
            "--tag",
            "topic/test",
        ],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            # Forbid Kado access. If the dry-run path leaks to KadoClient,
            # the connection refusal will land in stderr / non-zero exit.
            "KADO_API_BASE_URL": "http://127.0.0.1:1",
            "KADO_API_KEY": "dry-run-must-not-call",
        },
        timeout=15,
    )

    assert result.returncode == 0, (
        f"dry-run exited {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )

    report = json.loads(result.stdout)
    assert report["schema_version"] == "1"
    assert report["mode"] == "tag"
    assert report["trigger_arg"] == "topic/test"
    assert report["profile"] == "miyo"
    # Defaults for un-implemented phases.
    assert report["candidates"] == []
    assert report["topic_clusters"] == []
    assert report["candidates_total"] == 0
    assert report["candidates_capped"] is False
    assert report["abort_reason"] is None
    # No "Kado" / connection error in stderr (dry-run must not touch network).
    assert "ConnectionRefused" not in result.stderr
    assert "kado" not in result.stderr.lower()


def test_exit_code_2_on_missing_profile(tmp_path):
    """SDD §Error Handling: profile unresolved → fatal exit 2.

    `vault-config.yaml::profile` names a profile YAML that does not exist on
    disk → loader cannot resolve → exit 2 with a stderr message.
    """
    config_path = tmp_path / "vault-config.yaml"
    config_path.write_text("profile: nonexistent-profile-xyz\n", encoding="utf-8")

    cache_path = tmp_path / "discovery-cache.yaml"
    cache_path.write_text("map_notes: []\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--dry-run",
            "--config",
            str(config_path),
            "--cache",
            str(cache_path),
        ],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
        timeout=15,
    )

    assert result.returncode == 2, (
        f"expected exit 2 on missing profile, got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "profile" in result.stderr.lower()
