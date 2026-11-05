#!/usr/bin/env python3
# version: 0.3.0
"""test_inbox_author_pipeline.py — Pipeline integration tests for inbox-author.

Spec 026, T4.2 (Companion Mode P1 — inbox-author format dispatch + collision).
ADR-4 (extension-routed parse-gate), ADR-5 (template mapping + fallback),
ADR-7 (--no-overwrite collision → warn branch), ADR-9 (deterministic scripts).

Test coverage (mock at orchestrator, fake Kado — not patching sub-helpers):
  (a) happy compose+write: .md artifact written via kado-write-file.py lands in concepts.inbox
  (b) parse-gate blocks: malformed .canvas (validate-json.py) / .base (validate-yaml.py) → exit 1
  (c) --no-overwrite collision: exists signal (exit 3 + EXISTS:<path>) triggers warn branch
  (d) template fallback: empty/missing mapping → read-config-field.py returns "" (fallback trigger)
  (e) inbox boundary: writes target only the concepts.inbox path
  (f) spec 044 F8: unknown-type "If found" points to /note; the not-found path, mapped
      template, built-in default and .canvas/.base steps stay byte-identical to 0.3.0
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATE_JSON = REPO_ROOT / "tomo" / "scripts" / "validate-json.py"
VALIDATE_YAML = REPO_ROOT / "tomo" / "scripts" / "validate-yaml.py"
KADO_WRITE_FILE = REPO_ROOT / "tomo" / "scripts" / "kado-write-file.py"
READ_CONFIG_FIELD = REPO_ROOT / "tomo" / "scripts" / "read-config-field.py"
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR.parent))
from lib.kado_client import KadoNotFoundError  # noqa: E402


def _load_kwf():
    """Load kado-write-file.py as a module (importlib handles the hyphen in filename)."""
    spec = importlib.util.spec_from_file_location("kado_write_file", KADO_WRITE_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Load once; individual tests patch KadoClient on this module object.
kado_write_file = _load_kwf()


def _run_kwf(monkeypatch, argv_tail: list[str], fake_client_cls) -> int:
    """Call kado-write-file main() with given CLI args and a fake KadoClient."""
    monkeypatch.setattr(sys, "argv", ["kado-write-file.py"] + argv_tail)
    monkeypatch.setattr(kado_write_file, "KadoClient", fake_client_cls)
    try:
        return kado_write_file.main()
    except SystemExit as exc:
        return exc.code if exc.code is not None else 1


def _run_gate(script: Path, target: Path) -> subprocess.CompletedProcess:
    """Run a parse-gate script against a file and return the completed process."""
    return subprocess.run(
        [sys.executable, str(script), str(target)],
        capture_output=True,
        text=True,
    )


def _run_read_config(config_path: Path, field: str, default: str = "") -> subprocess.CompletedProcess:
    """Run read-config-field.py for a single field against a given config file."""
    return subprocess.run(
        [
            sys.executable,
            str(READ_CONFIG_FIELD),
            "--config", str(config_path),
            "--field", field,
            "--default", default,
        ],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# (a) Happy .md compose + write — lands in concepts.inbox
# ---------------------------------------------------------------------------


def test_md_write_lands_in_inbox(tmp_path: Path, monkeypatch) -> None:
    """A rendered .md artifact written via kado-write-file.py must land at the inbox path."""
    inbox = "100 Inbox/"
    vault_path = f"{inbox}my-overview.md"
    local = tmp_path / "default-doc.md"
    local.write_text("---\ntags: []\n---\n\n# My Overview\n\nContent here.\n")
    write_calls: list[str] = []

    class FakeClient:
        def __init__(self):
            pass

        def read_note(self, path: str) -> dict:
            raise KadoNotFoundError("not found")  # new file → no guard

        def write_note(self, path: str, content: str, expected_modified=None) -> dict:
            write_calls.append(path)
            return {"path": path, "modified": 1}

    rc = _run_kwf(monkeypatch, ["--vault", vault_path, "--local", str(local)], FakeClient)
    assert rc == 0, f"expected exit 0, got {rc}"
    assert write_calls == [vault_path]
    assert write_calls[0].startswith(inbox)


# ---------------------------------------------------------------------------
# (b) Parse-gate blocks malformed .canvas (JSON) — validate-json.py
# ---------------------------------------------------------------------------


def test_canvas_gate_blocks_malformed_json(tmp_path: Path) -> None:
    """validate-json.py must exit 1 on malformed .canvas — blocking any vault write."""
    canvas = tmp_path / "board.canvas"
    canvas.write_text('{"nodes": [invalid}')
    result = _run_gate(VALIDATE_JSON, canvas)
    assert result.returncode == 1, (
        f"parse-gate should have exited 1 on malformed .canvas; "
        f"returncode={result.returncode}, stderr={result.stderr}"
    )


def test_canvas_gate_passes_valid_json(tmp_path: Path) -> None:
    """validate-json.py must exit 0 on valid .canvas (JSON Canvas 1.0 shape)."""
    canvas = tmp_path / "board.canvas"
    canvas.write_text('{"nodes": [], "edges": []}')
    result = _run_gate(VALIDATE_JSON, canvas)
    assert result.returncode == 0, f"stderr={result.stderr}"


# ---------------------------------------------------------------------------
# (b) Parse-gate blocks malformed .base (YAML) — validate-yaml.py
# ---------------------------------------------------------------------------


def test_base_gate_blocks_malformed_yaml(tmp_path: Path) -> None:
    """validate-yaml.py must exit 1 on malformed .base — blocking any vault write."""
    base = tmp_path / "frame.base"
    base.write_text("type: base\nfilter:\n  where: [unclosed\n")
    result = _run_gate(VALIDATE_YAML, base)
    assert result.returncode == 1, (
        f"parse-gate should have exited 1 on malformed .base; "
        f"returncode={result.returncode}, stderr={result.stderr}"
    )


def test_base_gate_passes_valid_yaml(tmp_path: Path) -> None:
    """validate-yaml.py must exit 0 on valid .base (Obsidian Bases YAML shape)."""
    base = tmp_path / "frame.base"
    base.write_text("type: base\nfilter:\n  where: tag = reading-list\n")
    result = _run_gate(VALIDATE_YAML, base)
    assert result.returncode == 0, f"stderr={result.stderr}"


# ---------------------------------------------------------------------------
# (b) Extension routing: .canvas → JSON gate, .base → YAML gate (not swapped)
# ---------------------------------------------------------------------------


def test_canvas_uses_json_gate_not_yaml_gate(tmp_path: Path) -> None:
    """validate-json.py accepts well-formed JSON Canvas content (exit 0).

    The routing-matters direction (a fixture that one gate accepts and the
    other rejects) is proven by test_base_uses_yaml_gate_not_json_gate below;
    a JSON-but-not-YAML fixture is impractical since JSON flow syntax also
    parses as YAML.
    """
    canvas = tmp_path / "canvas.canvas"
    canvas.write_text('{"nodes": [], "edges": []}')
    assert _run_gate(VALIDATE_JSON, canvas).returncode == 0


def test_base_uses_yaml_gate_not_json_gate(tmp_path: Path) -> None:
    """Valid YAML that is not valid JSON must be accepted by validate-yaml.py but rejected by JSON gate."""
    base = tmp_path / "bases.base"
    base.write_text("type: base\nname: My Reading List\n")
    yaml_result = _run_gate(VALIDATE_YAML, base)
    json_result = _run_gate(VALIDATE_JSON, base)
    assert yaml_result.returncode == 0, f"YAML gate should accept valid .base; stderr={yaml_result.stderr}"
    assert json_result.returncode == 1, "JSON gate should reject bare YAML — confirms extension routing matters"


# ---------------------------------------------------------------------------
# (c) --no-overwrite: exists → exit 3 + EXISTS signal (warn branch)
# ---------------------------------------------------------------------------


def test_collision_no_overwrite_exits_3_with_exists_signal(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """--no-overwrite when vault path already exists must exit 3 and print EXISTS:<path>."""
    local = tmp_path / "artifact.md"
    local.write_text("# Colliding note")
    vault = "100 Inbox/my-note.md"

    class FakeClient:
        def __init__(self):
            pass

        def path_exists(self, path: str) -> bool:
            return True

        def write_note(self, path: str, content: str, expected_modified=None) -> dict:
            raise AssertionError("must not write on collision — warn branch should stop execution")

    rc = _run_kwf(
        monkeypatch,
        ["--no-overwrite", "--vault", vault, "--local", str(local)],
        FakeClient,
    )
    out, _ = capsys.readouterr()
    assert rc == 3, f"expected exit 3, got {rc}"
    assert f"EXISTS:{vault}" in out, f"expected EXISTS signal in stdout; got: {out!r}"


def test_collision_no_overwrite_absent_path_writes_normally(
    tmp_path: Path, monkeypatch
) -> None:
    """--no-overwrite when vault path is absent must write normally and exit 0."""
    local = tmp_path / "new.md"
    local.write_text("# New note")
    vault = "100 Inbox/new-note.md"
    write_calls: list[str] = []

    class FakeClient:
        def __init__(self):
            pass

        def path_exists(self, path: str) -> bool:
            return False

        def read_note(self, path: str) -> dict:
            raise KadoNotFoundError("not found")  # new file → no guard

        def write_note(self, path: str, content: str, expected_modified=None) -> dict:
            write_calls.append(path)
            return {"path": path, "modified": 1}

    rc = _run_kwf(
        monkeypatch,
        ["--no-overwrite", "--vault", vault, "--local", str(local)],
        FakeClient,
    )
    assert rc == 0
    assert write_calls == [vault]


# ---------------------------------------------------------------------------
# (d) Template fallback: empty/missing mapping → read-config-field.py returns ""
# ---------------------------------------------------------------------------


def test_template_mapping_missing_returns_empty_string(tmp_path: Path) -> None:
    """read-config-field.py with no templates.mapping.default must return empty string (fallback trigger)."""
    config = tmp_path / "vault-config.yaml"
    config.write_text("concepts:\n  inbox: \"100 Inbox/\"\n")
    result = _run_read_config(config, "templates.mapping.default", default="")
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert result.stdout.strip() == "", (
        f"expected empty string (fallback trigger) when mapping absent; got {result.stdout!r}"
    )


def test_template_mapping_configured_returns_stem(tmp_path: Path) -> None:
    """read-config-field.py with templates.mapping.default configured must return the stem."""
    config = tmp_path / "vault-config.yaml"
    config.write_text(
        "concepts:\n  inbox: \"100 Inbox/\"\n"
        "templates:\n  mapping:\n    default: t_default_tomo\n"
    )
    result = _run_read_config(config, "templates.mapping.default", default="")
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert result.stdout.strip() == "t_default_tomo"


def test_template_mapping_known_type_key_resolved(tmp_path: Path) -> None:
    """Real schema keys (atomic_note, map_note, etc.) are resolved by read-config-field.py."""
    config = tmp_path / "vault-config.yaml"
    config.write_text(
        "templates:\n  mapping:\n    atomic_note: t_note_tomo\n    map_note: t_moc_tomo\n"
    )
    result = _run_read_config(config, "templates.mapping.atomic_note", default="")
    assert result.stdout.strip() == "t_note_tomo"


# ---------------------------------------------------------------------------
# (e) Inbox boundary: writes target only concepts.inbox
# ---------------------------------------------------------------------------


def test_write_targets_exact_vault_path_unmodified(tmp_path: Path, monkeypatch) -> None:
    """kado-write-file.py writes to EXACTLY the --vault path, with no relocation.

    The inbox-only boundary is a skill-level invariant: inbox-author constructs
    <inbox>/<stem>.<ext> from concepts.inbox (covered by
    test_inbox_path_resolved_from_config). This test guards the script half of
    that contract — that kado-write-file does not mangle or redirect the path it
    is handed, so the composed inbox path is the path actually written.
    """
    vault_path = "100 Inbox/artifact.md"
    local = tmp_path / "artifact.md"
    local.write_text("# Content")
    write_calls: list[str] = []

    class FakeClient:
        def __init__(self):
            pass

        def read_note(self, path: str) -> dict:
            raise KadoNotFoundError("not found")  # new file → no guard

        def write_note(self, path: str, content: str, expected_modified=None) -> dict:
            write_calls.append(path)
            return {"path": path, "modified": 1}

    rc = _run_kwf(monkeypatch, ["--vault", vault_path, "--local", str(local)], FakeClient)
    assert rc == 0
    assert write_calls == [vault_path], (
        f"script must write to the exact path given, got {write_calls!r}"
    )


def test_inbox_path_resolved_from_config(tmp_path: Path) -> None:
    """concepts.inbox resolved from vault-config.yaml is the prefix used in vault paths."""
    config = tmp_path / "vault-config.yaml"
    config.write_text("concepts:\n  inbox: \"100 Inbox/\"\n")
    result = _run_read_config(config, "concepts.inbox", default="100 Inbox/")
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert result.stdout.strip() == "100 Inbox/"


# ---------------------------------------------------------------------------
# (f) Unknown-type redirect: a found template points to /note; every other
#     path of step 2, the built-in default and the .canvas/.base steps stay
#     byte-identical to inbox-author 0.3.0.
# ---------------------------------------------------------------------------

SKILL_MD = REPO_ROOT / "tomo" / "dot_claude" / "skills" / "inbox-author" / "SKILL.md"

# Sections copied verbatim from inbox-author 0.3.0 (git show 9030a987:<SKILL_MD>).
BASELINE_SKIP_LINE = "*Skip for .canvas and .base — they are composed directly without a template.*\n"

BASELINE_KNOWN_KEY = (
    "**Known key:**\n"
    "\n"
    "```bash\n"
    "python3 scripts/read-config-field.py --field templates.mapping.<requested_type> --default \"\"\n"
    "```\n"
    "\n"
    "If stem is non-empty, resolve the template body from the vault via `kado-read`\n"
    "(operation: note; bare stem via `kado-search` byName) and save to `tomo-tmp/default-template.md`.\n"
    "On empty stem or read failure: fall back to the built-in minimal default and tell the user\n"
    "`\"template <type> unset/missing — used built-in default\"`.\n"
    "\n"
)

BASELINE_NOT_FOUND = (
    "If not found: use built-in minimal default and tell the user\n"
    "`\"no type-specific template found — used the default/inbox template\"`.\n"
)

BASELINE_BUILTIN_DEFAULT = (
    "**Built-in minimal default** — write with the `Write` tool to `tomo-tmp/default-template.md`, verbatim:\n"
    "\n"
    "```\n"
    "---\n"
    "tags:{{tags}}\n"
    "---\n"
    "\n"
    "{{body}}\n"
    "```\n"
    "\n"
    "# STRICT — the built-in fallback is materialised here, never read from a `config/templates/` path.\n"
    "# Why: the built-in `t_*_tomo.md` starters live in the source repo, not the container — they are not reachable at runtime.\n"
    "\n"
)

BASELINE_CANVAS_BASE_STEPS = (
    "**For .canvas:**\n"
    "\n"
    "Compose the JSON Canvas content (guided by `obsidian-canvas`). Write with the `Write` tool to\n"
    "`tomo-tmp/staged-artifact.canvas`, then gate:\n"
    "\n"
    "```bash\n"
    "python3 scripts/validate-json.py tomo-tmp/staged-artifact.canvas\n"
    "```\n"
    "\n"
    "If exit code is non-zero: STOP — surface the parse error and offer to recompose. Do NOT write.\n"
    "\n"
    "**For .base:**\n"
    "\n"
    "Compose the Obsidian Bases YAML content (guided by `obsidian-bases`). Write with the `Write` tool\n"
    "to `tomo-tmp/staged-artifact.base`, then gate:\n"
    "\n"
    "```bash\n"
    "python3 scripts/validate-yaml.py tomo-tmp/staged-artifact.base\n"
    "```\n"
    "\n"
    "If exit code is non-zero: STOP — surface the parse error and offer to recompose. Do NOT write.\n"
    "\n"
)


def _section(text: str, start: str, end: str) -> str:
    """Return text from the first `start` marker up to (excluding) the next `end` marker."""
    i = text.index(start)
    j = text.index(end, i + len(start))
    return text[i:j]


def _unknown_type_branch(text: str) -> str:
    return _section(text, "**Unknown type:**", "**Built-in minimal default**")


def _if_found_path(text: str) -> str:
    branch = _unknown_type_branch(text)
    return _section(branch, "If found", "If not found")


def test_unknown_type_found_path_points_to_note() -> None:
    """The unknown-type 'If found' path names /note and no longer saves the found template."""
    found = _if_found_path(SKILL_MD.read_text(encoding="utf-8"))
    assert "/note" in found, f"'If found' path must point to /note; got {found!r}"
    assert "default-template.md" not in found, (
        f"'If found' path must not save the found template; got {found!r}"
    )


def test_unknown_type_not_found_path_byte_unchanged() -> None:
    """The unknown-type 'If not found' path keeps its 0.3.0 text byte for byte."""
    branch = _unknown_type_branch(SKILL_MD.read_text(encoding="utf-8"))
    assert BASELINE_NOT_FOUND in branch
    assert branch.endswith(BASELINE_NOT_FOUND + "\n")


def test_known_key_mapped_template_byte_unchanged() -> None:
    """The mapped-template path (incl. the mapped `default` key) is byte-identical to 0.3.0."""
    text = SKILL_MD.read_text(encoding="utf-8")
    assert _section(text, "**Known key:**", "**Unknown type:**") == BASELINE_KNOWN_KEY


def test_builtin_default_byte_unchanged() -> None:
    """The built-in minimal default block and its STRICT are byte-identical to 0.3.0."""
    text = SKILL_MD.read_text(encoding="utf-8")
    assert _section(text, "**Built-in minimal default**", "### 3. Compose") == BASELINE_BUILTIN_DEFAULT


def test_canvas_and_base_steps_byte_unchanged() -> None:
    """The .canvas/.base template skip and compose+gate steps are byte-identical to 0.3.0."""
    text = SKILL_MD.read_text(encoding="utf-8")
    assert BASELINE_SKIP_LINE in _section(text, "### 2. Resolve", "**Known key:**")
    assert _section(text, "**For .canvas:**", "### 4. Write") == BASELINE_CANVAS_BASE_STEPS


def test_inbox_author_version_bumped() -> None:
    """inbox-author carries version 0.4.0 after the /note redirect."""
    assert "# version: 0.4.0\n" in SKILL_MD.read_text(encoding="utf-8")
