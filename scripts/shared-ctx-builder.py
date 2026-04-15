#!/usr/bin/env python3
# shared-ctx-builder.py — Phase A: build distilled shared context for fan-out.
# version: 0.2.0
"""
Build the per-run shared-context JSON consumed by Phase-B subagents during
/inbox fan-out. The output distills the discovery cache, profile, and user
config into the minimum a classifier needs.

Inputs (CLI):
  --cache        config/discovery-cache.yaml
  --vault-config config/vault-config.yaml
  --profiles-dir profiles/              # default: <script-dir>/../profiles
  --run-id       unique run identifier
  --output       tomo-tmp/shared-ctx.json
  --max-bytes    size budget (default 15360)

Outputs:
  File at --output matching schemas/shared-ctx.schema.json, ≤ max-bytes.
  Stdout log lines summarising counts and final size.

Exit: 0 on success, 1 on error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


# ── Helpers ──────────────────────────────────────────────────────────────────

DEWEY_CLASSIFICATION_RE = re.compile(r"^\d{4}\s*-\s*")


def is_classification_moc(title: str) -> bool:
    """Dewey-layer MOCs have titles like '2600 - Applied Sciences'."""
    return bool(DEWEY_CLASSIFICATION_RE.match(title or ""))


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


# ── Builders ─────────────────────────────────────────────────────────────────

def build_mocs(cache: dict) -> list[dict]:
    """Emit MOC list with topics fallback to title when topics empty."""
    out = []
    for entry in cache.get("map_notes") or []:
        title = (entry.get("title") or "").strip()
        path = (entry.get("path") or "").strip()
        topics = [t.strip() for t in (entry.get("topics") or []) if t and t.strip()]
        if not topics:
            topics = [title] if title else []
        if not (title and path and topics):
            continue
        out.append({
            "path": path,
            "title": title,
            "topics": topics,
            "is_classification": is_classification_moc(title),
        })
    return out


def build_tag_prefixes(cache: dict, vault_cfg: dict) -> list[dict]:
    """Intersect discovered prefixes with user's proposable list, minus exclusions."""
    sugg = ((vault_cfg.get("tomo") or {}).get("suggestions") or {})
    proposable = sugg.get("proposable_tag_prefixes") or ["topic"]
    excluded = set(sugg.get("excluded_tag_prefixes") or [
        "type", "status", "projects", "content", "mcp",
    ])

    # Discovery cache tag layout varies; support both shapes:
    # 1) vault_cfg.tags.prefixes (authoritative user config)
    # 2) cache.tag_taxonomy.prefixes (discovered)
    candidates: dict[str, dict] = {}

    user_prefixes = ((vault_cfg.get("tags") or {}).get("prefixes") or {})
    for name, data in user_prefixes.items():
        candidates[name] = {
            "name": name,
            "wildcard": bool(data.get("wildcard", True)),
            "known_values": list(data.get("known_values") or []),
        }

    cache_prefixes = ((cache.get("tag_taxonomy") or {}).get("prefixes") or {})
    for name, data in cache_prefixes.items():
        existing = candidates.get(name, {
            "name": name,
            "wildcard": bool(data.get("wildcard", True)),
            "known_values": [],
        })
        # Merge known_values
        merged = list(dict.fromkeys(
            (existing.get("known_values") or []) + list(data.get("known_values") or [])
        ))
        existing["known_values"] = merged
        candidates[name] = existing

    out = []
    for name in proposable:
        if name in excluded:
            continue
        if name not in candidates:
            # Prefix configured but not seen in vault — emit with empty values
            candidates[name] = {"name": name, "wildcard": True, "known_values": []}
        out.append(candidates[name])
    return out


def build_classification_keywords(profile: dict) -> dict[str, list[str]]:
    """Profile classification.categories → {category_label: keywords}."""
    cats = ((profile.get("classification") or {}).get("categories") or {})
    out: dict[str, list[str]] = {}
    for key, data in cats.items():
        label = f"{key} - {data.get('name') or ''}".strip().rstrip("-").strip()
        keywords = [k.strip() for k in (data.get("keywords") or []) if k and k.strip()]
        if label and keywords:
            out[label] = keywords
    return out


TYPE_MAP = {
    "boolean": "bool",
    "bool": "bool",
    "integer": "number",
    "number": "number",
    "string": "text",
    "text": "text",
    "duration": "duration",
    "time": "text",
}


def _schema_type(raw: str, scale: str | None) -> str:
    t = TYPE_MAP.get((raw or "").strip().lower(), "text")
    if t == "number" and scale and "1" in scale and "5" in scale:
        return "rating_1_5"
    return t


def _syntax_for(field_type: str, section: str) -> str:
    # Long free-text fields in "End of the Day" style sections usually live in
    # a callout body rather than as inline fields.
    if field_type == "text":
        return "callout_body"
    return "inline_field"


def _seed_keywords(name: str, extras: list[str] | None) -> list[str]:
    base = name.lower()
    # Split CamelCase into space-separated words so "WakeUpEnergy" → "wake up energy"
    split = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).lower()
    seed = {base, split}
    if extras:
        for k in extras:
            if k and k.strip():
                seed.add(k.strip().lower())
    return sorted(s for s in seed if s)


def _collect_tracker_groups(trackers_cfg: dict) -> list[tuple[str, list[dict]]]:
    """Return [(section, fields[])] pairs from the nested tracker config."""
    groups: list[tuple[str, list[dict]]] = []
    daily = trackers_cfg.get("daily_note_trackers") or {}
    section = daily.get("section") or "Habit"
    for key in ("yesterday_fields", "today_fields"):
        fields = daily.get(key) or []
        if fields:
            groups.append((section, fields))
    eod = trackers_cfg.get("end_of_day_fields") or {}
    eod_section = eod.get("section") or "End of the Day"
    eod_fields = eod.get("fields") or []
    if eod_fields:
        groups.append((eod_section, eod_fields))
    return groups


def build_tracker_fields(vault_cfg: dict) -> list[dict]:
    """Flatten vault-config `trackers:` into shared-ctx tracker_fields[]."""
    trackers_cfg = vault_cfg.get("trackers") or {}
    out: list[dict] = []
    seen_names: set[str] = set()
    for section, fields in _collect_tracker_groups(trackers_cfg):
        for f in fields:
            name = (f.get("name") or "").strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            field_type = _schema_type(f.get("type") or "", f.get("scale"))
            syntax = _syntax_for(field_type, section)
            keywords = _seed_keywords(name, f.get("keywords"))
            out.append({
                "name": name,
                "type": field_type,
                "section": section,
                "syntax": syntax,
                "keywords": keywords,
            })
    return out


def build_daily_notes(vault_cfg: dict) -> dict | None:
    """Build daily_notes block iff calendar.granularities.daily.enabled."""
    calendar = ((vault_cfg.get("concepts") or {}).get("calendar") or {})
    granularities = calendar.get("granularities") or {}
    daily = granularities.get("daily") or {}
    if not daily.get("enabled"):
        return None

    naming = (vault_cfg.get("naming") or {}).get("calendar_patterns") or {}
    daily_pattern = (naming.get("daily") or "YYYY-MM-DD").strip()
    # Defensive: vault-config values sometimes have trailing whitespace. Strip
    # everything, collapse any double-slash that results from concat.
    raw_path = (daily.get("path") or "Calendar/").strip()
    daily_path = raw_path.rstrip("/").strip() + "/"

    return {
        "enabled": True,
        "path_pattern": f"{daily_path}{daily_pattern}".replace("//", "/"),
        "date_formats": [daily_pattern, "YYYYMMDD", "DD-MM-YYYY"],
        "tracker_fields": build_tracker_fields(vault_cfg),
    }


# ── Size enforcement ─────────────────────────────────────────────────────────

def serialize(ctx: dict) -> bytes:
    return json.dumps(ctx, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def enforce_budget(ctx: dict, max_bytes: int) -> tuple[dict, int]:
    """Shorten mocs[].topics until ctx serialises within max_bytes.

    Never drops a MOC. Shortening stops once topics[] reaches length 1.
    Returns the (possibly-modified) ctx and the number of topics dropped in total.
    """
    dropped = 0
    data = serialize(ctx)
    if len(data) <= max_bytes:
        return ctx, 0

    # Build (idx, current_len) pairs and trim longest-first iteratively
    while len(data) > max_bytes:
        # Find MOC with the most topics
        victim = -1
        most = 1
        for i, moc in enumerate(ctx["mocs"]):
            topics = moc.get("topics") or []
            if len(topics) > most:
                most = len(topics)
                victim = i
        if victim < 0:
            break  # all MOCs already at 1 topic; nothing left to shorten
        ctx["mocs"][victim]["topics"].pop()
        dropped += 1
        data = serialize(ctx)
    return ctx, dropped


# ── Main ─────────────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build the per-run shared-context JSON consumed by Phase-B subagents."
    )
    p.add_argument("--cache", required=True, help="Path to discovery-cache.yaml")
    p.add_argument("--vault-config", required=True, help="Path to vault-config.yaml")
    p.add_argument(
        "--profiles-dir",
        default=str(REPO_ROOT / "profiles"),
        help="Directory containing <profile>.yaml files",
    )
    p.add_argument("--run-id", default=None, help="Unique run identifier (auto-generated if omitted)")
    p.add_argument("--output", required=True, help="Target path for shared-ctx.json")
    p.add_argument("--max-bytes", type=int, default=15360, help="Size budget (default 15 KB)")
    return p


def main() -> int:
    args = build_arg_parser().parse_args()

    cache_path = Path(args.cache)
    vault_cfg_path = Path(args.vault_config)
    profiles_dir = Path(args.profiles_dir)
    out_path = Path(args.output)

    if not cache_path.exists():
        print(f"ERROR: cache not found: {cache_path}", file=sys.stderr)
        return 1
    if not vault_cfg_path.exists():
        print(f"ERROR: vault-config not found: {vault_cfg_path}", file=sys.stderr)
        return 1

    cache = load_yaml(cache_path)
    vault_cfg = load_yaml(vault_cfg_path)
    profile_name = vault_cfg.get("profile") or "miyo"
    profile_path = profiles_dir / f"{profile_name}.yaml"
    if not profile_path.exists():
        print(f"ERROR: profile not found: {profile_path}", file=sys.stderr)
        return 1
    profile = load_yaml(profile_path)

    run_id = args.run_id or f"{uuid.uuid4().hex[:12]}"

    mocs = build_mocs(cache)
    tag_prefixes = build_tag_prefixes(cache, vault_cfg)
    classification_keywords = build_classification_keywords(profile)
    daily_notes = build_daily_notes(vault_cfg)

    ctx: dict = {
        "schema_version": "1",
        "run_id": run_id,
        "mocs": mocs,
        "tag_prefixes": tag_prefixes,
        "classification_keywords": classification_keywords,
    }
    if daily_notes is not None:
        ctx["daily_notes"] = daily_notes

    ctx, dropped = enforce_budget(ctx, args.max_bytes)
    data = serialize(ctx)

    ensure_parent(out_path)
    out_path.write_bytes(data)

    print(
        f"mocs_total={len(cache.get('map_notes') or [])} "
        f"mocs_included={len(ctx['mocs'])} "
        f"topics_dropped={dropped} "
        f"tag_prefixes_included={len(ctx['tag_prefixes'])} "
        f"classification_categories={len(ctx['classification_keywords'])} "
        f"daily_notes_enabled={bool(daily_notes)} "
        f"bytes={len(data)} "
        f"run_id={run_id}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
