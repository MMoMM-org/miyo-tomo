"""note_stub_kit.py — run the /note stubs and the real /note scripts side by side
(spec 044 T4.1).

The eval case `note-draft-before-approval` grades the note-from-template skill
against the stubs of `evals/_lib/note-stubs.sh`. tests/test_stub_contract.py
uses this module to stage two workspaces with that kit (same config, same
fixture vault), run a stub in one and the real script in the other on the same
argv, and compare exit code, stdout, stderr and the files the skill reads.

Real scripts run in a subprocess with cwd = the workspace. Kado is never
reached: REAL_LAUNCHER loads the script as a module, replaces its KadoClient
with tests/note_fake_vault.NoteFakeVault filled from the kit's fixture file
(`scripts/note-fixture.json`), freezes its clock and run id to the kit's
constants, and calls its main(). Nothing is written outside tmp_path.

Not named `test_*`, so pytest does not collect it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KIT = REPO / "evals" / "_lib" / "note-stubs.sh"
SCRIPTS = REPO / "tomo" / "scripts"
TESTS = Path(__file__).resolve().parent

STEM = "2026-11-05_100000"
RUN_ID = "2026-11-05T10-00-00Z-c0ffee"
TEMPLATE = "X/Templates/t_meeting_tomo.md"
SOURCE = "100 Inbox/Meeting with Dana.md"

# argv[1] = scenario JSON file, argv[2] = real script, argv[3:] = its argv.
REAL_LAUNCHER = r"""
import importlib.util, json, os, sys
from datetime import datetime, timezone

scenario_file, script = sys.argv[1], sys.argv[2]
scenario = json.load(open(scenario_file, encoding="utf-8"))
sys.path.insert(0, os.path.dirname(script))
sys.path.insert(0, scenario["tests_dir"])
import lib.kado_client as kc
from note_fake_vault import NoteFakeVault

FROZEN = datetime(2026, 11, 5, 10, 0, 0, tzinfo=timezone.utc)


class Frozen(datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN.astimezone(tz) if tz else FROZEN.replace(tzinfo=None)


vault = NoteFakeVault(files=scenario["files"])
for method, path, exc in scenario.get("fail", []):
    vault.fail[(method, path)] = getattr(kc, exc)(exc)
sys.argv = [script] + sys.argv[3:]
spec = importlib.util.spec_from_file_location("under_test", script)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
if scenario.get("kado") != "unconfigured" and hasattr(mod, "KadoClient"):
    mod.KadoClient = vault
if hasattr(mod, "datetime"):
    mod.datetime = Frozen
if hasattr(mod, "run_id_lib"):
    mod.run_id_lib.generate = lambda: scenario["run_id"]
if hasattr(mod, "_now"):
    mod._now = lambda: FROZEN
if scenario.get("withdraw"):
    mod.withdraw_unjustified_deletes = lambda kept: (kept[:-1], kept[-1:])
sys.exit(mod.main(sys.argv[1:]))
"""


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("KADO_")}
    env.update(PYTHONDONTWRITEBYTECODE="1", TZ="UTC")
    return env


def stage(ws: Path, drafts: str = "none", deliver: str = "delivered") -> Path:
    """Source the kit the way the case scaffold does, with cwd = ws."""
    ws.mkdir(parents=True, exist_ok=True)
    script = f"set -e\nNOTE_DRAFTS={drafts}\nNOTE_DELIVER={deliver}\n. '{KIT}'\nstage_note_instance\n"
    subprocess.run(["/bin/bash", "-c", script], cwd=ws, check=True, capture_output=True, text=True,
                   env=_env())
    return ws


def fixture(ws: Path) -> dict:
    return json.loads((ws / "scripts" / "note-fixture.json").read_text(encoding="utf-8"))


def vault_files(ws: Path, extra: dict | None = None, drop: tuple = ()) -> dict:
    files = {**fixture(ws)["vault"], **(extra or {})}
    return {p: t for p, t in files.items() if p not in drop}


def run_stub(ws: Path, script: str, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(["python3", f"scripts/{script}", *argv], cwd=ws, capture_output=True,
                          text=True, env=_env(), timeout=60, check=False)


def run_real(ws: Path, script: str, *argv: str, files: dict | None = None, fail=(),
             kado: str = "fake", withdraw: bool = False) -> subprocess.CompletedProcess:
    scenario = {"tests_dir": str(TESTS), "run_id": RUN_ID,
                "files": vault_files(ws) if files is None else files,
                "fail": [list(f) for f in fail], "kado": kado, "withdraw": withdraw}
    scenario_file = ws.parent / f"{ws.name}.scenario.json"
    scenario_file.write_text(json.dumps(scenario), encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-c", REAL_LAUNCHER, str(scenario_file), str(SCRIPTS / script), *argv],
        cwd=ws, capture_output=True, text=True, env=_env(), timeout=60, check=False,
    )


def pair(tmp_path: Path, drafts: str = "none", deliver: str = "delivered") -> tuple[Path, Path]:
    """Two workspaces staged alike: (stub workspace, real workspace)."""
    return (stage(tmp_path / "stub", drafts, deliver), stage(tmp_path / "real", drafts, deliver))


def outputs(proc: subprocess.CompletedProcess) -> tuple[int, str, str]:
    return proc.returncode, proc.stdout, proc.stderr
