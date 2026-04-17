#!/usr/bin/env python3
# version: 0.1.0
"""instruction-render.py — Render approved suggestions into note files.

Reads parsed suggestions (from suggestion-parser.py), fetches templates and
source note bodies via Kado, renders each note through token-render.py, and
writes the results to tomo-tmp/rendered/.

This is the deterministic rendering step for Pass 2. The instruction-builder
agent calls this script, then writes the rendered files to the vault via Kado
and assembles the instruction set (move/link entries only).

Usage:
  python3 scripts/instruction-render.py \\
    --suggestions tomo-tmp/parsed-suggestions.json \\
    --output-dir tomo-tmp/rendered \\
    --config config/vault-config.yaml

Exit codes:
  0 — all items rendered successfully
  1 — one or more items failed (partial output, manifest still written)
  2 — fatal error (no output)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.kado_client import KadoClient, KadoError  # noqa: E402


def slugify(text: str) -> str:
    """Convert a title to a filename-safe slug."""
    s = text.lower()
    s = re.sub(r"[äÄ]", "ae", s)
    s = re.sub(r"[öÖ]", "oe", s)
    s = re.sub(r"[üÜ]", "ue", s)
    s = re.sub(r"ß", "ss", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s[:80]  # cap length


def read_note_body(client: KadoClient, path: str) -> str:
    """Read a note via Kado and extract body (content after frontmatter)."""
    try:
        result = client.read_note(path)
        content = result.get("content", "")
    except KadoError as exc:
        print(f"  [warn] Could not read source {path}: {exc}", file=sys.stderr)
        return ""

    # Strip frontmatter (--- ... ---)
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            body = content[end + 3:].strip()
            return body
    return content.strip()


def read_template(client: KadoClient, template_path: str) -> str | None:
    """Read a template file from the vault via Kado."""
    # Ensure .md extension
    if not template_path.endswith(".md"):
        template_path += ".md"
    try:
        result = client.read_note(template_path)
        return result.get("content", "")
    except KadoError as exc:
        print(f"  [error] Could not read template {template_path}: {exc}", file=sys.stderr)
        return None


def render_via_script(template_path: str, tokens_path: str, config_path: str) -> str | None:
    """Call token-render.py and return stdout, or None on error."""
    cmd = [
        sys.executable, str(SCRIPT_DIR / "token-render.py"),
        "--template", template_path,
        "--tokens", tokens_path,
        "--config", config_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            print(f"  [error] token-render.py failed: {result.stderr.strip()}", file=sys.stderr)
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        print("  [error] token-render.py timed out", file=sys.stderr)
        return None


def main() -> int:
    p = argparse.ArgumentParser(description="Render approved suggestions into note files.")
    p.add_argument("--suggestions", required=True, help="Path to parsed suggestions JSON")
    p.add_argument("--output-dir", required=True, help="Directory for rendered files")
    p.add_argument("--config", default="config/vault-config.yaml", help="vault-config.yaml path")
    args = p.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(args.suggestions, encoding="utf-8") as f:
        suggestions = json.load(f)

    confirmed = suggestions.get("confirmed_items", [])
    if not confirmed:
        print("instruction-render: no confirmed items", file=sys.stderr)
        return 0

    try:
        client = KadoClient()
    except KadoError as exc:
        print(f"FATAL: Cannot connect to Kado: {exc}", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    date_prefix = now.strftime("%Y-%m-%d_%H%M")

    manifest: list[dict] = []
    errors = 0

    for item in confirmed:
        item_id = item.get("id", "?")
        # Render any item that has a template — that means it needs a file.
        # Items without a template (e.g. update_daily, link_to_moc) are
        # instruction-only and don't need rendering.
        if not item.get("template"):
            print(f"  [{item_id}] SKIP: no template (instruction-only)", file=sys.stderr)
            continue
        title = item.get("title") or item.get("source_path", "untitled")
        source_path = item.get("source_path", "")
        template_ref = item.get("template", "")
        tags = item.get("tags", [])
        parent_moc = item.get("parent_moc", "")
        parent_mocs = item.get("parent_mocs", [])
        destination = item.get("destination", "")
        summary = item.get("summary", "")

        print(f"  [{item_id}] Rendering: {title}", file=sys.stderr)

        # 1. Read template from vault
        if not template_ref:
            print(f"  [{item_id}] SKIP: no template specified", file=sys.stderr)
            errors += 1
            continue

        template_content = read_template(client, template_ref)
        if template_content is None:
            errors += 1
            continue

        # 2. Read source note body
        body = ""
        if source_path:
            # source_path might be just a stem — try with inbox prefix
            if "/" not in source_path:
                # Try to find it in inbox
                try:
                    from lib.kado_client import KadoNotFoundError
                except ImportError:
                    KadoNotFoundError = KadoError

                # Load inbox path from config
                inbox_path = "100 Inbox/"
                config_path = Path(args.config)
                if config_path.exists():
                    try:
                        import yaml
                        with open(config_path) as cf:
                            cfg = yaml.safe_load(cf)
                        inbox_path = cfg.get("concepts", {}).get("inbox", inbox_path)
                    except Exception:
                        pass

                full_path = f"{inbox_path}{source_path}"
                if not full_path.endswith(".md"):
                    full_path += ".md"
                body = read_note_body(client, full_path)
            else:
                if not source_path.endswith(".md"):
                    source_path += ".md"
                body = read_note_body(client, source_path)

        # 3. Prepare tokens
        up_value = ""
        if parent_moc:
            up_value = f"[[{parent_moc}]]"

        # Tags as comma-separated string for inline YAML arrays:
        # tags: [existing, {{tags}}] → tags: [existing, topic/a, topic/b]
        # If passed as a list, format_list_token() would produce YAML block
        # syntax which breaks inline arrays in templates.
        tags_str = ", ".join(tags) if isinstance(tags, list) else (tags or "")

        tokens = {
            "title": title,
            "tags": tags_str,
            "up": up_value,
            "body": body,
            "summary": summary or "",
        }

        # Write template and tokens to temp files
        tmpl_file = out_dir / f"{item_id}_template.md"
        tokens_file = out_dir / f"{item_id}_tokens.json"

        tmpl_file.write_text(template_content, encoding="utf-8")
        tokens_file.write_text(json.dumps(tokens, ensure_ascii=False), encoding="utf-8")

        # 4. Render
        rendered = render_via_script(str(tmpl_file), str(tokens_file), args.config)
        if rendered is None:
            errors += 1
            continue

        # 5. Write rendered file
        slug = slugify(title)
        filename = f"{date_prefix}_{slug}.md"
        rendered_path = out_dir / filename
        rendered_path.write_text(rendered, encoding="utf-8")

        manifest.append({
            "id": item_id,
            "action": item.get("action", "create_note"),
            "title": title,
            "source_path": source_path,
            "template": template_ref,
            "rendered_file": filename,
            "rendered_path": str(rendered_path),
            "destination": destination,
            "parent_moc": parent_moc,
            "parent_mocs": parent_mocs,
            "tags": tags,
        })

        # Clean up temp files
        tmpl_file.unlink(missing_ok=True)
        tokens_file.unlink(missing_ok=True)

        print(f"  [{item_id}] OK → {filename}", file=sys.stderr)

    # Write manifest
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        f"instruction-render: rendered={len(manifest)} errors={errors} "
        f"out={out_dir} manifest={manifest_path}",
        file=sys.stderr,
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
