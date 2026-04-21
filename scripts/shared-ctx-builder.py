#!/usr/bin/env python3
# shared-ctx-builder.py — Phase A: build distilled shared context for fan-out.
# version: 0.4.0
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
    """Return tag prefixes Tomo may actively propose, per the per-prefix policy.

    Reads ONLY from `vault_cfg.tags.prefixes.*`. Each entry MUST be a dict with
    the shape produced by `vault-config-writer.py tags` (and guarded by
    `vault-config-tags.schema.json`):

        <prefix_name>:
          description: <str>
          known_values: [<str>, ...]
          wildcard: <bool>      # may invent new values
          proposable: <bool>    # Tomo may actively propose this prefix
          required_for: [<concept>, ...]

    Only prefixes with `proposable: true` are emitted. Output merges observed
    values from the discovery cache (`cache.tag_taxonomy.prefixes.*.known_values`)
    into each entry's `known_values` so classifiers see both user-curated and
    freshly-observed values.

    Drift guard: if `tags.prefixes` is missing or any entry is malformed
    (e.g. a flat list of strings — the bug that blocked Pass 1 on 2026-04-21,
    or a dict entry missing `proposable`), we exit 1 with an actionable message
    pointing the user at `/explore-vault --confirm`. No silent defaults.
    """
    tags_block = vault_cfg.get("tags")
    if not isinstance(tags_block, dict) or "prefixes" not in tags_block:
        print(
            "ERROR: vault-config.yaml is missing `tags.prefixes`. "
            "Run `/explore-vault --confirm` to regenerate it via "
            "scripts/vault-config-writer.py.",
            file=sys.stderr,
        )
        sys.exit(1)

    user_prefixes = tags_block["prefixes"]
    if not isinstance(user_prefixes, dict):
        print(
            f"ERROR: `tags.prefixes` must be a dict keyed by prefix name, "
            f"got {type(user_prefixes).__name__}. The writer "
            f"(scripts/vault-config-writer.py tags) produces the correct shape; "
            f"do not hand-edit this section. "
            f"Run `/explore-vault --confirm` to regenerate it.",
            file=sys.stderr,
        )
        sys.exit(1)

    candidates: dict[str, dict] = {}
    for name, data in user_prefixes.items():
        if not isinstance(data, dict):
            print(
                f"ERROR: `tags.prefixes.{name}` must be a dict with fields "
                f"description/known_values/wildcard/proposable/required_for, "
                f"got {type(data).__name__}. "
                f"Run `/explore-vault --confirm` to regenerate.",
                file=sys.stderr,
            )
            sys.exit(1)
        for required in ("wildcard", "proposable", "known_values"):
            if required not in data:
                print(
                    f"ERROR: `tags.prefixes.{name}` is missing `{required}`. "
                    f"The schema requires description/known_values/wildcard/"
                    f"proposable/required_for. "
                    f"Run `/explore-vault --confirm` to regenerate "
                    f"(vault-config-writer.py enforces the current schema).",
                    file=sys.stderr,
                )
                sys.exit(1)
        candidates[name] = {
            "name": name,
            "wildcard": bool(data["wildcard"]),
            "proposable": bool(data["proposable"]),
            "known_values": list(data.get("known_values") or []),
        }

    # Merge in values observed by discovery-cache (optional, advisory).
    cache_prefixes = ((cache.get("tag_taxonomy") or {}).get("prefixes") or {})
    for name, data in cache_prefixes.items():
        if name not in candidates:
            continue  # cache may surface prefixes the user hasn't declared yet
        if not isinstance(data, dict):
            continue
        merged = list(dict.fromkeys(
            candidates[name]["known_values"] + list(data.get("known_values") or [])
        ))
        candidates[name]["known_values"] = merged

    # Emit only prefixes the user opted into via proposable: true. Drop the
    # proposable flag from the output — it's a policy signal, not downstream data.
    out: list[dict] = []
    for name, entry in candidates.items():
        if not entry["proposable"]:
            continue
        out.append({
            "name": entry["name"],
            "wildcard": entry["wildcard"],
            "known_values": entry["known_values"],
        })
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


def _syntax_for(field_type: str) -> str:
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
            syntax = _syntax_for(field_type)
            keywords = _seed_keywords(name, f.get("keywords"))
            description = f.get("description", "")
            if not description:
                print(f"WARN: tracker field '{name}' has no description", file=sys.stderr)
            positive_keywords = [k.strip() for k in (f.get("positive_keywords") or []) if k and k.strip()]
            negative_keywords = [k.strip() for k in (f.get("negative_keywords") or []) if k and k.strip()]
            out.append({
                "name": name,
                "type": field_type,
                "section": section,
                "syntax": syntax,
                "keywords": keywords,
                "description": description,
                "positive_keywords": positive_keywords,
                "negative_keywords": negative_keywords,
            })
    return out


_DAILY_LOG_DEFAULTS: dict = {
    "section": "Daily Log",
    "heading_level": 1,
    "time_extraction": {
        "enabled": True,
        "sources": ["content", "filename"],
        "fallback": "append_end_of_day",
    },
    "link_format": "bullet",
    "cutoff_days": 30,
    "auto_create_if_missing": {"past": False, "today": False, "future": False},
}


def build_daily_log(vault_cfg: dict) -> dict:
    """Build daily_log sub-block; forces auto_create_if_missing to false (MVP)."""
    cfg = vault_cfg.get("daily_log")
    if not cfg:
        return {k: v for k, v in _DAILY_LOG_DEFAULTS.items()}

    result: dict = {}
    for key, default in _DAILY_LOG_DEFAULTS.items():
        result[key] = cfg.get(key, default)

    acim_cfg = cfg.get("auto_create_if_missing") or {}
    forced_false = {k: False for k in ("past", "today", "future")}
    if any(acim_cfg.get(k) for k in ("past", "today", "future")):
        print("WARN: auto_create_if_missing forced to false in MVP", file=sys.stderr)
    result["auto_create_if_missing"] = forced_false
    return result


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
        "daily_log": build_daily_log(vault_cfg),
    }


# ── Size enforcement ─────────────────────────────────────────────────────────

def serialize(ctx: dict) -> bytes:
    return json.dumps(ctx, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _tracker_fields_iter(ctx: dict):
    """Yield (list_ref, index) for all tracker_fields entries across the ctx."""
    tf = (ctx.get("daily_notes") or {}).get("tracker_fields") or []
    for i in range(len(tf)):
        yield tf, i


def enforce_budget(ctx: dict, max_bytes: int) -> tuple[dict, int]:
    """Trim ctx to fit within max_bytes.

    Budget pass order:
    1. Trim each tracker description to 200 chars with ellipsis.
    2. Drop negative_keywords from each tracker.
    3. Drop positive_keywords from each tracker.
    4. Drop auto-seeded keywords from each tracker (keeps name/type/section/syntax/description).
    5. Shorten mocs[].topics (existing behaviour).

    Never drops description itself. Returns (ctx, moc_topics_dropped).
    """
    data = serialize(ctx)
    if len(data) <= max_bytes:
        return ctx, 0

    # Pass 1: trim tracker descriptions to 200 chars
    for tf, i in _tracker_fields_iter(ctx):
        desc = tf[i].get("description", "")
        if len(desc) > 200:
            tf[i]["description"] = desc[:200] + "\u2026"
    data = serialize(ctx)
    if len(data) <= max_bytes:
        return ctx, 0

    # Passes 2-4: drop keyword lists in order of importance
    for field_name in ("negative_keywords", "positive_keywords", "keywords"):
        for tf, i in _tracker_fields_iter(ctx):
            tf[i][field_name] = []
        data = serialize(ctx)
        if len(data) <= max_bytes:
            return ctx, 0

    # Pass 5: shorten mocs[].topics (original behaviour)
    dropped = 0
    while len(data) > max_bytes:
        victim = -1
        most = 1
        for i, moc in enumerate(ctx["mocs"]):
            topics = moc.get("topics") or []
            if len(topics) > most:
                most = len(topics)
                victim = i
        if victim < 0:
            break
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
