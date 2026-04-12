#!/usr/bin/env python3
# version: 0.2.0
"""test-kado.py — Verify Kado connectivity and API key permissions.

Reads .mcp.json (for URL + bearer token) and vault-config.yaml (for
concept paths), then runs a battery of checks against the Kado MCP
server:

  1. Connectivity — can we reach Kado at all?
  2. Auth — is the bearer token accepted?
  3. Per-concept read access — listDir on each concept path
  4. Tag listing — listTags (vault-wide read)
  5. Frontmatter read — read one note to verify kado-read works

Optional (--write-test): writes a small test file to the inbox folder
to verify write permission, then immediately deletes it.

Usage:
    python3 scripts/test-kado.py                    # run from instance dir
    python3 scripts/test-kado.py --verbose          # show file counts
    python3 scripts/test-kado.py --write-test       # also test write
    python3 scripts/test-kado.py --instance /path   # point at instance

Exit codes:
    0  — all checks passed
    1  — one or more checks failed
    2  — configuration error (missing .mcp.json or vault-config.yaml)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Allow running the script from anywhere as long as lib/ is adjacent
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

try:
    from lib.kado_client import (  # noqa: E402
        KadoAuthError,
        KadoClient,
        KadoConnectionError,
        KadoError,
        KadoNotFoundError,
        KadoToolError,
    )
except ImportError as e:
    print(f"Error importing kado_client: {e}", file=sys.stderr)
    print(f"Expected at: {_SCRIPT_DIR}/lib/kado_client.py", file=sys.stderr)
    sys.exit(2)


# ── Colors ────────────────────────────────────────────────

if sys.stdout.isatty():
    C_RESET = "\033[0m"
    C_BOLD = "\033[1m"
    C_GREEN = "\033[32m"
    C_RED = "\033[31m"
    C_YELLOW = "\033[33m"
    C_CYAN = "\033[36m"
    C_DIM = "\033[2m"
else:
    C_RESET = C_BOLD = C_GREEN = C_RED = C_YELLOW = C_CYAN = C_DIM = ""


def step(msg: str) -> None:
    print(f"\n{C_BOLD}{C_CYAN}▸ {msg}{C_RESET}")


def ok(msg: str) -> None:
    print(f"  {C_GREEN}✓{C_RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {C_RED}✗{C_RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {C_YELLOW}⚠{C_RESET} {msg}")


def info(msg: str) -> None:
    print(f"    {C_DIM}{msg}{C_RESET}")


# ── Instance discovery ────────────────────────────────────

def resolve_instance(explicit: str | None) -> Path:
    """Resolve the instance path (where .mcp.json and config/ live)."""
    if explicit:
        p = Path(explicit).resolve()
        if not p.is_dir():
            raise SystemExit(f"Instance path does not exist: {p}")
        return p

    cwd = Path.cwd()
    # Walk up looking for .mcp.json
    for candidate in [cwd, *cwd.parents]:
        if (candidate / ".mcp.json").is_file():
            return candidate

    # Fall back to cwd even if .mcp.json is missing — the KadoClient will
    # report a clearer error.
    return cwd


# ── vault-config parsing ──────────────────────────────────

def load_vault_config(path: Path) -> dict:
    """Load vault-config.yaml — prefers PyYAML, falls back to minimal parser."""
    if not path.is_file():
        return {}
    try:
        import yaml  # type: ignore

        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        return _parse_vault_config_minimal(path)


def _parse_vault_config_minimal(path: Path) -> dict:
    """Stdlib-only fallback parser — extracts concept paths only."""
    cfg: dict = {"concepts": {}}
    in_concepts = False
    current_concept: str | None = None

    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue

            if line.startswith("concepts:"):
                in_concepts = True
                continue
            if not in_concepts:
                continue
            if not line.startswith((" ", "\t")):
                break  # Left the concepts block

            indent = len(line) - len(line.lstrip())
            stripped = line.strip()

            if indent <= 2 and stripped.endswith(":"):
                current_concept = stripped[:-1].strip()
                cfg["concepts"].setdefault(current_concept, {})
                continue

            if indent <= 2 and ":" in stripped:
                # Simple concept line like: '  inbox: "100 Inbox/"'
                key, _, rest = stripped.partition(":")
                val = rest.strip().strip('"').strip("'")
                if val:
                    cfg["concepts"][key.strip()] = val
                continue

            if current_concept and ":" in stripped:
                key, _, rest = stripped.partition(":")
                val = rest.strip().strip('"').strip("'")
                if key.strip() == "base_path" and val:
                    cfg["concepts"][current_concept] = {"base_path": val}
                elif key.strip() == "paths":
                    # Next line will be "- path"; handled loosely below
                    pass
                continue

            if current_concept and stripped.startswith("- "):
                val = stripped[2:].strip().strip('"').strip("'")
                existing = cfg["concepts"].get(current_concept, {})
                if isinstance(existing, dict):
                    existing.setdefault("paths", []).append(val)
                    cfg["concepts"][current_concept] = existing

    return cfg


def concept_paths(vault_cfg: dict) -> list[tuple[str, str]]:
    """Return [(label, path), ...] for each concept defined in the config."""
    paths: list[tuple[str, str]] = []
    concepts = vault_cfg.get("concepts", {})

    for name, val in concepts.items():
        if isinstance(val, str) and val:
            paths.append((name, val.rstrip("/")))
        elif isinstance(val, dict):
            if "base_path" in val and val["base_path"]:
                paths.append((f"{name}.base_path", val["base_path"].rstrip("/")))
            if "paths" in val and isinstance(val["paths"], list):
                for i, p in enumerate(val["paths"]):
                    if p:
                        suffix = f"[{i}]" if len(val["paths"]) > 1 else ""
                        paths.append((f"{name}.paths{suffix}", p.rstrip("/")))

    return paths


# ── Individual test helpers ───────────────────────────────

def test_connectivity(client: KadoClient) -> tuple[bool, str | None]:
    """Test 1+2: Can we reach Kado and does the bearer token work?"""
    step("Connectivity & authentication")
    try:
        items = client.list_dir("/", depth=1, limit=1)
        ok(f"Kado reachable; vault root returned {len(items)} item(s) (page 1)")
        return True, None
    except KadoConnectionError as e:
        fail(f"Cannot reach Kado: {e}")
        info("Check: is Kado running on the host? curl the URL from .mcp.json to verify.")
        return False, "connection"
    except KadoAuthError as e:
        fail(f"Authentication failed: {e}")
        info("Check: the bearer token in .mcp.json must match Kado's configured API key.")
        return False, "auth"
    except KadoError as e:
        fail(f"Kado error: {e}")
        return False, "other"


def test_concept_read(
    client: KadoClient, label: str, path: str, verbose: bool
) -> bool:
    """Test: does listDir work on the given concept path?"""
    try:
        if verbose:
            items = client.list_dir(path, limit=500)
            n_files = sum(1 for i in items if i.get("type") != "folder")
            n_notes = sum(
                1
                for i in items
                if i.get("type") != "folder"
                and (i.get("name", "").endswith(".md") or i.get("path", "").endswith(".md"))
            )
            n_folders = sum(1 for i in items if i.get("type") == "folder")
            ok(
                f"{label}: {path}/ — {n_files} file(s), {n_notes} note(s), "
                f"{n_folders} folder(s)"
            )
        else:
            client.list_dir(path, limit=1)
            ok(f"{label}: {path}/")
        return True
    except KadoNotFoundError:
        warn(f"{label}: {path}/ — not found (OK for new setups)")
        return True  # Not a permission failure
    except KadoAuthError:
        fail(f"{label}: {path}/ — permission denied")
        info("API key is missing read access for this path.")
        return False
    except KadoError as e:
        fail(f"{label}: {path}/ — {e}")
        return False


def test_list_tags(client: KadoClient) -> bool:
    """Test: vault-wide tag listing."""
    step("Tag listing (vault-wide read)")
    try:
        tags = client.list_tags(limit=500)
        ok(f"listTags works — {len(tags)} unique tag(s) found")
        return True
    except KadoAuthError:
        fail("listTags denied — API key missing kado-search/listTags permission")
        return False
    except KadoError as e:
        fail(f"listTags error: {e}")
        return False


def test_read_frontmatter(client: KadoClient, concept_paths_list: list[tuple[str, str]]) -> bool:
    """Test: read one file's frontmatter (verifies kado-read permission)."""
    step("Frontmatter read")

    for label, path in concept_paths_list:
        try:
            items = client.list_dir(path, limit=20)
        except KadoError:
            continue
        for item in items:
            if item.get("type") == "folder":
                continue
            name = item.get("name", "")
            item_path = item.get("path", "")
            if name.endswith(".md") or item_path.endswith(".md"):
                # Prefer the full vault-relative path returned by Kado,
                # fall back to base/name if it's missing
                file_path = item_path or f"{path.rstrip('/')}/{name}"
                try:
                    client.read_frontmatter(file_path)
                    ok(f"read_frontmatter works — tested on {file_path}")
                    return True
                except KadoAuthError:
                    fail(f"read_frontmatter denied on {file_path}")
                    info("API key is missing kado-read/frontmatter permission.")
                    return False
                except KadoNotFoundError:
                    continue
                except KadoError as e:
                    fail(f"read_frontmatter failed: {e}")
                    return False

    warn("No .md files found in any concept path — skipped read_frontmatter check")
    return True  # Not a failure; new vault may be empty


def test_write(client: KadoClient, inbox_path: str) -> bool:
    """Test: write a tiny test file to inbox, then delete it.

    Note: KadoClient doesn't expose delete, so this leaves a file behind
    named .tomo-kado-test-<timestamp>.md that the user can clean up.
    """
    step("Write test (inbox)")
    if not inbox_path:
        warn("No inbox path configured — skipped write test")
        return True

    filename = f".tomo-kado-test-{int(time.time())}.md"
    target = f"{inbox_path.rstrip('/')}/{filename}"
    content = (
        "---\n"
        "title: Tomo Kado write test\n"
        "tags:\n"
        "  - tomo/test\n"
        "---\n\n"
        "This file was created by `scripts/test-kado.py` to verify write access.\n"
        "It is safe to delete.\n"
    )
    try:
        client.write_note(target, content)
        ok(f"Write works — test file created at {target}")
        warn(f"Remove manually: {target}")
        return True
    except KadoAuthError:
        fail(f"Write denied on {target}")
        info("API key is missing kado-write/note permission for inbox.")
        return False
    except KadoError as e:
        fail(f"Write failed: {e}")
        return False


# ── Main ──────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test Kado connectivity and API key permissions for this Tomo instance.",
    )
    parser.add_argument(
        "--instance",
        default=None,
        help="Path to the Tomo instance (default: walk up from cwd looking for .mcp.json)",
    )
    parser.add_argument(
        "--config",
        default="config/vault-config.yaml",
        help="Relative or absolute path to vault-config.yaml",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show file counts per concept"
    )
    parser.add_argument(
        "--write-test",
        action="store_true",
        help="Also test write access by creating a small file in the inbox",
    )
    parser.add_argument("--url", default=None, help="Override Kado URL")
    parser.add_argument("--token", default=None, help="Override Kado bearer token")
    args = parser.parse_args()

    print(f"{C_BOLD}Kado Configuration Test{C_RESET}")

    # Resolve instance dir
    try:
        instance = resolve_instance(args.instance)
    except SystemExit as e:
        print(f"  {C_RED}✗{C_RESET} {e}", file=sys.stderr)
        return 2

    info(f"Instance: {instance}")

    # Load vault-config.yaml
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = instance / cfg_path
    vault_cfg = load_vault_config(cfg_path)
    if not vault_cfg:
        fail(f"Could not load {cfg_path}")
        info("Pass --config or run from the instance directory.")
        return 2
    info(f"Config:   {cfg_path}")

    # Create client — chdir so .mcp.json auto-discovery picks the right file
    original_cwd = Path.cwd()
    try:
        os.chdir(instance)
        try:
            client = KadoClient(base_url=args.url, token=args.token)
        except KadoError as e:
            fail(f"Configuration error: {e}")
            info(f"Check: {instance}/.mcp.json exists and has kado.url + token")
            return 2
    finally:
        os.chdir(original_cwd)

    all_pass = True

    # Test 1+2: Connectivity and auth
    ok_conn, err_kind = test_connectivity(client)
    if not ok_conn:
        return 1  # Stop early

    # Test 3: Per-concept read
    step("Per-concept read access")
    cp_list = concept_paths(vault_cfg)
    if not cp_list:
        warn("No concept paths found in vault-config.yaml")
    else:
        for label, path in cp_list:
            if not test_concept_read(client, label, path, verbose=args.verbose):
                all_pass = False

    # Test 4: Tag listing
    if not test_list_tags(client):
        all_pass = False

    # Test 5: Read frontmatter
    if not test_read_frontmatter(client, cp_list):
        all_pass = False

    # Test 6 (optional): Write
    if args.write_test:
        inbox = vault_cfg.get("concepts", {}).get("inbox", "")
        if isinstance(inbox, str):
            if not test_write(client, inbox):
                all_pass = False
        else:
            warn("Inbox path is not a simple string — skipped write test")

    # Summary
    print()
    if all_pass:
        print(f"{C_BOLD}{C_GREEN}━━━ All Kado checks passed ━━━{C_RESET}")
        print(f"  {C_DIM}Your API key has the permissions Tomo needs.{C_RESET}")
        return 0
    else:
        print(f"{C_BOLD}{C_RED}━━━ Some Kado checks failed ━━━{C_RESET}")
        print(f"  {C_DIM}See .claude/rules/kado-config.md for configuration details.{C_RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
