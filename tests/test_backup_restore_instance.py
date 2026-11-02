"""backup-tomo.sh and restore-tomo.sh with --instance (issue #242).

Both scripts derive REPO_ROOT from their own location, and the real repo holds
a tomo-install.json for the dev instance. Every test therefore runs a copy of
the scripts inside tmp_path, with HOME and TOMO_REGISTRY_FILE pointing there,
so nothing can reach ~/.tomo or a real install.
"""

import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_SCRIPTS = REPO_ROOT / "scripts"


def _make_instance(root: Path, name: str, instance_dir: str, marker: str) -> dict:
    """Create the on-disk shape of an installed instance under root."""
    inst = root / instance_dir
    home = root / "home"
    (inst / "config").mkdir(parents=True)
    (inst / ".claude").mkdir()
    home.mkdir(parents=True)
    (inst / "config" / "vault-config.yaml").write_text(marker, encoding="utf-8")
    (inst / ".mcp.json").write_text(json.dumps({"marker": marker}), encoding="utf-8")
    (home / "auth.json").write_text(marker, encoding="utf-8")
    config = root / "tomo-install.json"
    config.write_text(
        json.dumps({
            "instanceName": name,
            "instancePath": str(inst),
            "homePath": str(home),
            "marker": marker,
        }),
        encoding="utf-8",
    )
    return {"root": root, "instance": inst, "home": home, "config": config, "name": name}


class Sandbox:
    """A fake repo with a dev instance, plus two registered instances beside it."""

    def __init__(self, tmp_path: Path):
        self.tmp = tmp_path
        self.repo = tmp_path / "repo"
        (self.repo / "scripts" / "lib").mkdir(parents=True)
        for script in ("backup-tomo.sh", "restore-tomo.sh"):
            shutil.copy(SOURCE_SCRIPTS / script, self.repo / "scripts" / script)
        shutil.copy(
            SOURCE_SCRIPTS / "lib" / "instance-registry.sh",
            self.repo / "scripts" / "lib" / "instance-registry.sh",
        )
        self.registry = tmp_path / "registry" / "instances.json"
        self.env = {
            **os.environ,
            "HOME": str(tmp_path / "fake-home"),
            "TOMO_REGISTRY_FILE": str(self.registry),
        }
        (tmp_path / "fake-home").mkdir()
        self.dev = _make_instance(self.repo, "tomo-instance", "tomo-instance", "dev")
        self.alpha = _make_instance(tmp_path / "alpha", "alpha", "instance", "alpha")
        self.beta = _make_instance(tmp_path / "beta", "beta", "instance", "beta")
        self.registry.parent.mkdir()
        self.registry.write_text(
            json.dumps({
                "schema_version": 1,
                "instances": [
                    {"name": i["name"], "path": str(i["instance"])}
                    for i in (self.alpha, self.beta)
                ],
            }),
            encoding="utf-8",
        )

    def run(self, script: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.repo / "scripts" / script), *args],
            capture_output=True,
            text=True,
            env=self.env,
            stdin=subprocess.DEVNULL,
        )

    def backup(self, *args: str) -> subprocess.CompletedProcess:
        return self.run("backup-tomo.sh", *args)

    def restore(self, *args: str) -> subprocess.CompletedProcess:
        return self.run("restore-tomo.sh", *args)

    def snapshot(self) -> dict:
        """Every file under the sandbox, by path, to prove that nothing moved."""
        return {
            str(p): p.read_bytes()
            for p in self.tmp.rglob("*")
            if p.is_file() and not p.suffix == ".pyc"
        }

    def archives(self) -> list:
        return sorted(self.tmp.rglob("*.tar.gz"))

    def backup_of(self, instance: dict) -> Path:
        res = self.backup("--instance", instance["name"])
        assert res.returncode == 0, res.stderr
        return next(iter(sorted((instance["root"] / "tomo-backups").glob("*.tar.gz"))))


@pytest.fixture
def box(tmp_path):
    return Sandbox(tmp_path)


def _read_member(archive: Path, member: str) -> str:
    with tarfile.open(archive, "r:gz") as tar:
        return tar.extractfile(f"./{member}").read().decode("utf-8")


def _break(instance: dict) -> None:
    """Change an instance so a restore has something to bring back."""
    (instance["instance"] / "config" / "vault-config.yaml").write_text("changed", encoding="utf-8")
    (instance["instance"] / ".mcp.json").write_text("changed", encoding="utf-8")
    (instance["home"] / "auth.json").write_text("changed", encoding="utf-8")
    (instance["config"]).write_text(
        instance["config"].read_text(encoding="utf-8").replace('"marker"', '"changed"'),
        encoding="utf-8",
    )


# ── backup ─────────────────────────────────────────────────


def test_backup_archives_the_named_instance_not_the_dev_instance(box):
    res = box.backup("--instance", "alpha")

    assert res.returncode == 0, res.stderr
    archives = list((box.alpha["root"] / "tomo-backups").glob("alpha-*.tar.gz"))
    assert len(archives) == 1
    archive = archives[0]
    assert _read_member(archive, "tomo-instance/config/vault-config.yaml") == "alpha"
    assert _read_member(archive, "tomo-home/auth.json") == "alpha"
    assert json.loads(_read_member(archive, "tomo-install.json"))["instanceName"] == "alpha"
    assert not (box.repo / "tomo-backups").exists()


def test_backup_unknown_instance_fails_clearly_and_writes_nothing(box):
    before = box.snapshot()

    res = box.backup("--instance", "ghost")

    assert res.returncode == 1
    assert "Unknown instance: 'ghost'" in res.stderr
    assert box.snapshot() == before
    assert box.archives() == []
    assert not (box.repo / "tomo-backups").exists()


def test_backup_registered_instance_without_config_fails_and_writes_nothing(box):
    box.beta["config"].unlink()
    before = box.snapshot()

    res = box.backup("--instance", "beta")

    assert res.returncode == 1
    assert "config missing" in res.stderr
    assert box.snapshot() == before
    assert not (box.beta["root"] / "tomo-backups").exists()


def test_backup_instance_flag_without_a_name_fails_with_a_message(box):
    res = box.backup("--instance")

    assert res.returncode == 1
    assert "--instance requires a name" in res.stderr


def test_backup_default_still_targets_the_repo_root_dev_instance(box):
    res = box.backup()

    assert res.returncode == 0, res.stderr
    archives = list((box.repo / "tomo-backups").glob("tomo-instance-*.tar.gz"))
    assert len(archives) == 1
    assert _read_member(archives[0], "tomo-instance/config/vault-config.yaml") == "dev"


def test_backup_rotation_stays_inside_the_named_instance(box):
    other = box.alpha["root"] / "tomo-backups" / "beta-keep.tar.gz"
    other.parent.mkdir()
    other.write_text("foreign", encoding="utf-8")

    res = box.backup("--instance", "alpha", "--keep", "1")

    assert res.returncode == 0, res.stderr
    assert other.exists()


# ── restore ────────────────────────────────────────────────


def test_restore_brings_the_named_instance_back_to_its_own_root(box):
    archive = box.backup_of(box.alpha)
    original_config = _read_member(archive, "tomo-install.json")
    _break(box.alpha)
    dev_config = box.dev["config"].read_bytes()
    beta_before = (box.beta["instance"] / "config" / "vault-config.yaml").read_bytes()

    res = box.restore(str(archive), "--instance", "alpha", "--force")

    assert res.returncode == 0, res.stderr
    assert (box.alpha["instance"] / "config" / "vault-config.yaml").read_text() == "alpha"
    assert json.loads((box.alpha["instance"] / ".mcp.json").read_text()) == {"marker": "alpha"}
    assert (box.alpha["home"] / "auth.json").read_text() == "alpha"
    assert box.alpha["config"].read_text() == original_config
    # The bug from the issue: the config was written back to the repo root.
    assert box.dev["config"].read_bytes() == dev_config
    assert (box.dev["instance"] / "config" / "vault-config.yaml").read_text() == "dev"
    assert (box.beta["instance"] / "config" / "vault-config.yaml").read_bytes() == beta_before


def test_restore_unknown_instance_fails_clearly_and_writes_nothing(box):
    archive = box.backup_of(box.alpha)
    before = box.snapshot()

    res = box.restore(str(archive), "--instance", "ghost", "--force")

    assert res.returncode == 1
    assert "Unknown instance: 'ghost'" in res.stderr
    assert box.snapshot() == before


def test_restore_refuses_an_archive_of_another_instance(box):
    """A foreign tomo-install.json would repoint the target at another instance."""
    archive = box.backup_of(box.alpha)
    before = box.snapshot()

    res = box.restore(str(archive), "--instance", "beta", "--force")

    assert res.returncode == 1
    assert "belongs to instance 'alpha'" in res.stderr
    assert box.snapshot() == before


def test_restore_dry_run_with_instance_writes_nothing(box):
    archive = box.backup_of(box.alpha)
    _break(box.alpha)
    before = box.snapshot()

    res = box.restore(str(archive), "--instance", "alpha", "--dry-run")

    assert res.returncode == 0, res.stderr
    assert box.snapshot() == before


def test_restore_instance_flag_without_a_name_fails_with_a_message(box):
    archive = box.backup_of(box.alpha)

    res = box.restore(str(archive), "--instance")

    assert res.returncode == 1
    assert "--instance requires a name" in res.stderr


def test_restore_default_still_targets_the_repo_root_dev_instance(box):
    assert box.backup().returncode == 0
    archive = next(iter((box.repo / "tomo-backups").glob("*.tar.gz")))
    _break(box.dev)

    res = box.restore(str(archive), "--force")

    assert res.returncode == 0, res.stderr
    assert (box.dev["instance"] / "config" / "vault-config.yaml").read_text() == "dev"
    assert (box.alpha["instance"] / "config" / "vault-config.yaml").read_text() == "alpha"


# ── help ───────────────────────────────────────────────────


@pytest.mark.parametrize("script", ["backup-tomo.sh", "restore-tomo.sh"])
def test_help_names_the_instance_flag(box, script):
    res = box.run(script, "--help")

    assert res.returncode == 0
    assert "--instance" in res.stdout
