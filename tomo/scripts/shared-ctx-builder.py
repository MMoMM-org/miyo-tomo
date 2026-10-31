#!/usr/bin/env python3
# shared-ctx-builder.py — Phase A: build distilled shared context for fan-out.
# version: 1.16.0
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
  --max-bytes    per-read warning threshold in bytes (default 32768)
  --warnings-out optional; file that receives a copy of every WARN line

Outputs:
  File at --output matching schemas/shared-ctx.schema.json, every eligible MOC
  with its full detail (nothing is shed for size).
  Stderr: one WARN line per analyst read (names, step1, placeholder_targets,
  detail) whose compact JSON exceeds --max-bytes, then one summary line of
  counts and sizes. Every other WARN line (tracker fields without keywords,
  moc_proposal config) also goes to stderr.
  File at --warnings-out (only when given): every `WARN:` line printed on
  stderr during this run, exactly as printed, one per line. Rewritten on every
  run, also on an error exit; empty when the run printed no WARN line, so a
  warning from an earlier run is never carried over. Printing it (e.g. with
  `cat`) yields exactly the lines to relay to the user and nothing else.

Exit: 0 on success, 1 on error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass, fields as dc_fields
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

# Lazy import — only loaded when reconcile is enabled (skip-reconcile keeps
# shared-ctx-builder usable in offline tests without a live Kado).
try:
    sys.path.insert(0, str(SCRIPT_DIR / "lib"))
    from kado_client import KadoClient, KadoError  # type: ignore
except ImportError:
    KadoClient = None  # type: ignore
    KadoError = Exception  # type: ignore

# spec 028 T2.4: placeholder-MOC detection derives its regex from the active
# profile's MOC suffix. sys.path already carries SCRIPT_DIR/lib (inserted above).
from profile_conventions import marker_word, resolve_conventions  # type: ignore  # noqa: E402

# spec 031 Phase 5: the canonical asset-folder default lives in render_actions
# (dotted-package import — needs SCRIPT_DIR itself on sys.path, not SCRIPT_DIR/lib).
sys.path.insert(0, str(SCRIPT_DIR))
from lib.render_actions import DEFAULT_ASSET_FOLDER  # noqa: E402
from lib.moc_folders import in_moc_folders, moc_folder_prefixes  # noqa: E402
from lib.moc_tags import is_excluded_moc  # noqa: E402
from lib.vault_paths import path_key  # noqa: E402


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


# ── tomo.moc_proposal config loader (F-43) ───────────────────────────────────
#
# Backs the MOC-creation skill (`/moc-propose`). Defaults match SDD §10 / Data
# Storage Changes — the loader returns these whenever the
# `tomo.moc_proposal` block is absent or partially specified, so the skill
# works without user setup (PRD/AC-7.2). User-provided values override
# defaults per-key (PRD/AC-7.1). Unknown keys log a stderr warning and are
# dropped to keep forward-compat painless when new tunables ship.

@dataclass(frozen=True)
class MocProposalConfig:
    """Tunables for /moc-propose (spec 013)."""
    min_notes: int = 3
    confidence_threshold: float = 0.15
    max_results: int = 5
    candidate_cap: int = 500
    orphan_display_cap: int = 50
    cache_miss_max_batches: int = 5
    squelch_runs: int = 3


def load_moc_proposal_config(vault_config_path: Path | str) -> MocProposalConfig:
    """Load `tomo.moc_proposal` from vault-config.yaml, falling back to defaults.

    Behaviour:
      - Block missing → return MocProposalConfig() (all spec defaults).
      - Block present → user keys override defaults per-key; unspecified keys
        retain their default.
      - Unknown keys → emit a WARN line on stderr naming each unknown key and
        skip it. The user-facing fix is to remove the typo or update Tomo.

    Errors are intentionally non-fatal: the SDD error-handling table (line 839)
    states "missing keys → loader fallback → use defaults from spec §10. Log
    warning to run log." Crashing here would block /moc-propose for trivial
    typos, which is the wrong trade-off.
    """
    path = Path(vault_config_path)
    raw = load_yaml(path) if path.exists() else {}
    block = ((raw.get("tomo") or {}).get("moc_proposal") or {})

    if not isinstance(block, dict):
        print(
            f"WARN: vault-config.yaml::tomo.moc_proposal must be a mapping, "
            f"got {type(block).__name__}; using spec defaults.",
            file=sys.stderr,
        )
        return MocProposalConfig()

    known = {f.name for f in dc_fields(MocProposalConfig)}
    overrides: dict = {}
    unknown: list[str] = []
    for key, value in block.items():
        if key in known:
            overrides[key] = value
        else:
            unknown.append(str(key))

    if unknown:
        print(
            f"WARN: vault-config.yaml::tomo.moc_proposal has unknown key(s): "
            f"{', '.join(sorted(unknown))}. Ignoring; using spec defaults for "
            f"those slots.",
            file=sys.stderr,
        )

    return MocProposalConfig(**overrides)


# ── Cache reconcile ──────────────────────────────────────────────────────────

def reconcile_map_notes_against_vault(
    cache: dict,
    *,
    client=None,
) -> tuple[int, list[str]]:
    """Drop `cache["map_notes"]` entries whose file no longer exists in the vault.

    discovery-cache.yaml is rebuilt by `/explore-vault`, not by `/inbox`.
    Between rebuilds, MOC files get deleted/moved by the user, but the cache
    still lists them. The shared-ctx-builder fed those ghost entries into
    `ctx["mocs"]`, which inbox-analyst then offered as link targets — pointing
    at paths that no longer exist (e.g. `[[100 Inbox/2026-05-01_1008_board-games-moc]]`).

    This reconcile groups MOC paths by parent folder, issues ONE Kado
    `listDir(depth=1)` per unique parent, and keeps only paths still present.
    On Kado failure for a folder: keep all entries from that folder (fail safe
    — better to show a ghost link than to drop a live MOC).

    Mutates `cache["map_notes"]` in place. Returns (kept_count, dropped_paths).
    """
    raw = cache.get("map_notes") or []
    if not raw:
        return 0, []

    if client is None:
        if KadoClient is None:
            raise RuntimeError(
                "kado_client unavailable — pass --skip-reconcile or fix the import path"
            )
        client = KadoClient()

    by_parent: dict[str, list[dict]] = {}
    for entry in raw:
        path = (entry.get("path") or "").strip()
        if not path:
            continue
        parent = os.path.dirname(path) or "/"
        by_parent.setdefault(parent, []).append(entry)

    kept: list[dict] = []
    dropped: list[str] = []

    for parent, group in by_parent.items():
        try:
            items = client.list_dir(parent, depth=1)
        except KadoError as exc:
            print(
                f"[shared-ctx] reconcile: listDir({parent!r}) failed: {exc} — "
                f"keeping {len(group)} entr{'y' if len(group) == 1 else 'ies'} from this folder",
                file=sys.stderr,
            )
            kept.extend(group)
            continue
        existing = {
            (item.get("path") or "").lstrip("/")
            for item in items
            if isinstance(item, dict) and item.get("type") == "file"
        }
        for entry in group:
            entry_path = (entry.get("path") or "").lstrip("/")
            if entry_path in existing:
                kept.append(entry)
            else:
                dropped.append(entry_path)

    cache["map_notes"] = kept
    return len(kept), dropped


# ── Builders ─────────────────────────────────────────────────────────────────

_HEADINGS_CAP = 8  # T3.2 (spec 022): max headings per MOC in shared-ctx
_CALLOUTS_CAP = 4  # M6: max editable_callouts per MOC in shared-ctx (schema maxItems)


def build_mocs(cache: dict, moc_folders: tuple[str, ...] = ()) -> list[dict]:
    """Emit the eligible MOCs, sorted by path, each with its delivered `name`.

    Eligible = a cache MOC not tagged MiYo/Tomo/exclude/moc (spec 040 ADR-5).
    `name` follows the collision rule in `assign_names` (spec 040 ADR-1);
    `moc_folders` are the `concepts.map_note` prefixes it consults.

    Topics fall back to the title when empty.

    T3.2 (spec 022): A-trimmed inventory is copied from the cache when present:
      - headings: [{text, level}], capped at _HEADINGS_CAP (8); H2-H6 only
        (H1 is the MOC title, excluded by moc_structure.parse_headings).
      - editable_callouts: [str] — callout opening lines in editable_set.
      - Classification/Dewey MOCs (is_classification==True) carry NO inventory.
      - Entries without headings/editable_callouts in the cache omit the fields.
    """
    out = []
    for entry in cache.get("map_notes") or []:
        if is_excluded_moc(entry.get("tags")):
            continue
        title = (entry.get("title") or "").strip()
        path = (entry.get("path") or "").strip()
        topics = [t.strip() for t in (entry.get("topics") or []) if t and t.strip()]
        if not topics:
            topics = [title] if title else []
        if not (title and path and topics):
            continue
        is_classification = is_classification_moc(title)
        moc: dict = {
            "path": path,
            "title": title,
            "topics": topics,
            "is_classification": is_classification,
        }
        # T3.2: copy inventory only for non-classification MOCs
        if not is_classification:
            raw_headings = entry.get("headings")
            if raw_headings:
                moc["headings"] = raw_headings[:_HEADINGS_CAP]
            raw_callouts = entry.get("editable_callouts")
            if raw_callouts:
                moc["editable_callouts"] = list(raw_callouts)[:_CALLOUTS_CAP]
            # T2.1 (spec 023): footer presence flag passthrough
            if "has_footer" in entry:
                moc["has_footer"] = entry["has_footer"]
        out.append(moc)
    out.sort(key=lambda m: m["path"])
    assign_names(out, moc_folders)
    return out


def assign_names(mocs: list[dict], moc_folders: tuple[str, ...]) -> None:
    """Set each MOC's delivered `name` in place (spec 040 ADR-1).

    The title, unless another MOC has the same title (compared by path_key).
    Among colliding MOCs, the single one inside `moc_folders` keeps the title;
    every other one — or all of them, when zero or several lie inside —
    carries its path, which is unique in the vault.
    """
    groups: dict[str, list[dict]] = {}
    for moc in mocs:
        groups.setdefault(path_key(moc["title"]), []).append(moc)
    for group in groups.values():
        if len(group) == 1:
            group[0]["name"] = group[0]["title"]
            continue
        inside = [m for m in group if in_moc_folders(m["path"], moc_folders)]
        keeper = inside[0] if len(inside) == 1 else None
        for moc in group:
            moc["name"] = moc["title"] if moc is keeper else moc["path"]


# A placeholder link is a missing MOC only when its target follows the vault's
# MOC naming convention: a trailing `(MOC)` parenthetical OR a trailing ` MOC`
# word (case-insensitive, word-boundary so mid-word "...MOC" never matches).
# spec 028 T2.4: the marker word is derived from the active profile's suffix
# (miyo " (MOC)" → "MOC"); an empty suffix (lyt) detects nothing. Condition C
# offers MOC *creation*, so a placeholder link to a missing regular note (no MOC
# marker) must not reach it — that was the bulk of the unfiltered list (158 of
# 196 on the real vault, 2026-06-09).
_DEFAULT_SUFFIX = " (MOC)"


def _moc_name_re(suffix: str):
    """Build the placeholder-MOC detection regex from a profile suffix.

    Matches the parenthesised `(MOC)` form OR the bare word ` MOC` at end of
    string (case-insensitive), keyed off the suffix's alphanumeric core
    (`marker_word`, F-55 S1). An empty suffix yields ``None`` — detect nothing.
    """
    word = marker_word(suffix)
    if not word:
        return None
    return re.compile(
        rf"(\({re.escape(word)}\)|\b{re.escape(word)})\s*$", re.IGNORECASE
    )


# Legacy default (miyo) suffix used when no profile suffix is threaded (standalone
# smoke test / older callers). The active pipeline passes the resolved regex.
_MOC_NAME_RE = _moc_name_re(_DEFAULT_SUFFIX)


def _is_missing_moc_target(target: str, moc_re=_MOC_NAME_RE) -> bool:
    """True if a placeholder target names a MOC (the profile's `(MOC)`/` MOC` convention)."""
    if moc_re is None:
        return False
    return bool(moc_re.search(target))


def build_placeholder_links(cache: dict, moc_re=_MOC_NAME_RE) -> list[dict]:
    """Filter cache.placeholder_links[] to the ones that name a missing MOC.

    Source: `moc-tree-builder.py` detects every dead wikilink in MOC bodies and
    `cache-builder.py` lifts them onto `cache.placeholder_links` as
    `{"target": str, "referenced_by": str}`. Those are *placeholder links* in
    the general sense — a dead link may point to a missing MOC OR a missing
    regular note. `inbox-analyst` Condition C uses this list to offer MOC
    *creation* (Tier-3 New MOC Proposal §2.C), so only links whose target
    follows the MOC naming convention (`(MOC)` / ` MOC`) belong here — a missing
    regular note is not a missing MOC. Filtering at this feed (not in the cache)
    keeps the cache a complete dead-link record while keeping the shared-ctx
    envelope lean (M6) and stopping Condition C from proposing MOCs for non-MOCs.

    Drift guard: drop entries that don't have both fields. Older caches
    written before F-35 may lack the field — return [] silently. The schema
    treats `placeholder_links` as optional, so absence is fine downstream.
    """
    raw = cache.get("placeholder_links") or []
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        target = (entry.get("target") or "").strip()
        referenced_by = (entry.get("referenced_by") or "").strip()
        if not (target and referenced_by):
            continue
        if not _is_missing_moc_target(target, moc_re):
            continue
        out.append({"target": target, "referenced_by": referenced_by})
    return out


def build_placeholder_targets(cache: dict, moc_re=_MOC_NAME_RE) -> list[str]:
    """The missing-MOC names the analyst checks, each once, sorted (spec 040 ADR-7).

    The analyst compares only `target`; `referenced_by` stays in the discovery
    cache. Always a list — empty when the vault has no placeholder MOCs — so
    the analyst's read of this field never fails for its absence.
    """
    return sorted({p["target"] for p in build_placeholder_links(cache, moc_re)})


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


def _field_syntax(field: dict, field_type: str) -> str:
    """The configured `syntax` wins; the type-derived guess is the fallback.

    `syntax` is a declared property of a tracker field — the schema calls it
    "How the field is serialised in the daily note" — and only the config knows
    it, because it describes the shape of the user's daily-note template rather
    than anything about the value. Deriving it from the type reads a `text`
    field as a callout, which is wrong for any vault writing `- Field:: value`
    under a heading.
    """
    configured = (field.get("syntax") or "").strip()
    return configured or _syntax_for(field_type)


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
            syntax = _field_syntax(f, field_type)
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
                # Absent means active, so a config written before the switch
                # existed keeps every field switched on.
                "active": bool(f.get("active", True)),
            })
    return out


_DAILY_LOG_DEFAULTS: dict = {
    "enabled": True,
    "section": "Daily Log",
    "heading_level": 1,
    "date_sources": ["content", "frontmatter", "filename"],
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


def build_asset_folder(vault_cfg: dict) -> str:
    """Return the configured attachment-filing destination (concepts.asset).

    Falls back to DEFAULT_ASSET_FOLDER when the key is absent or blank so
    the field is always a usable, non-empty path — never None. Normalised
    with the same rstrip("/") + "/" shape `_asset_dest_join`
    (lib/render_actions.py) uses when it actually places a file, so the
    preamble line always names the exact string the destination is built
    from — never a value differing only by a trailing slash.
    """
    raw = (vault_cfg.get("concepts") or {}).get("asset")
    folder = (raw or "").strip()
    if not folder:
        return DEFAULT_ASSET_FOLDER
    return folder.rstrip("/") + "/"


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
        # Patterns Step 8 of inbox-analyst uses to detect dates in
        # filename/frontmatter/content. `daily_pattern` drives daily-note filename matching;
        # the rest cover natural-language date mentions in German / European notes:
        #   "2026-03-30", "20260330", "30-03-2026" (existing)
        #   "30.03.2026", "30.03.26", "30.03." — German short forms, year-less OK (→ current year)
        #   "30/03/2026" — European slash form
        # The LLM in inbox-analyst is expected to match these literally, so narrow and
        # explicit patterns here are better than generic regex.
        "date_formats": [
            daily_pattern, "YYYYMMDD", "DD-MM-YYYY",
            "DD.MM.YYYY", "DD.MM.YY", "DD.MM.",
            "D.M.YYYY", "D.M.",
            "DD/MM/YYYY", "DD/MM",
        ],
        # Absent means enabled: an existing config that predates the switch
        # must keep behaving exactly as it did.
        "trackers_enabled": bool(
            (vault_cfg.get("trackers") or {}).get("enabled", True)
        ),
        "tracker_fields": build_tracker_fields(vault_cfg),
        "daily_log": build_daily_log(vault_cfg),
    }


# ── Size enforcement ─────────────────────────────────────────────────────────

def serialize(ctx: dict) -> bytes:
    return json.dumps(ctx, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def warn_unusable_trackers(ctx: dict) -> list[str]:
    """Report active tracker fields with no keywords, on stderr.

    A tracker with no `positive_keywords` falls back to the analyst's
    description path, which the agent definition specifies as a word-split of
    the English `description` against the note body — no overlap at all for a
    German vault. In practice the analyst matches semantically instead and
    does fire, but at a flat 0.5 confidence with no negative-keyword
    suppression, so false positives are never caught. The gap is silent at
    every layer: the schema does not require keywords, the config validates,
    and the analyst reports a match either way.

    Keys on `positive_keywords` ALONE, deliberately. The `keywords` field is
    seeded from the field name by `_seed_keywords` and is therefore never
    empty — but the analyst's matching rule reads `positive_keywords` and
    nothing else, so a field with seeded keywords and no positive_keywords is
    just as inert. Checking `keywords` too would silence this warning on
    exactly the configuration it exists to report.

    Returns the names it warned about, so callers can assert on them.
    """
    daily = ctx.get("daily_notes") or {}
    if daily.get("trackers_enabled") is False:
        return []
    unusable = [
        f.get("name", "?")
        for f in (daily.get("tracker_fields") or [])
        if isinstance(f, dict)
        and f.get("active", True)
        and not f.get("positive_keywords")
    ]
    if unusable:
        print(
            f"WARN: {len(unusable)} active tracker field(s) have no keywords; "
            f"matching falls back to guesswork and cannot suppress false "
            f"positives: {', '.join(unusable)}. "
            f"Run /tomo-setup trackers to fill them, or set active: false on the "
            f"ones you do not use.",
            file=sys.stderr,
        )
    return unusable


_STEP1_FIELDS = ("daily_notes", "classification_keywords", "tag_prefixes", "asset_folder")
_DETAIL_CAP = 20  # read-shared-ctx.py --mocs-from resolves at most this many


def _compact_len(value) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def read_sizes(ctx: dict) -> dict[str, int]:
    """Bytes of each analyst read, serialised as read-shared-ctx.py prints it."""
    mocs = ctx.get("mocs") or []
    return {
        "names": _compact_len([m.get("name") for m in mocs]),
        "step1": _compact_len({k: ctx[k] for k in _STEP1_FIELDS if k in ctx}),
        "placeholder_targets": _compact_len(ctx.get("placeholder_targets") or []),
        "detail": _DETAIL_CAP * max((_compact_len(m) for m in mocs), default=0),
    }


def size_guards(ctx: dict, max_bytes: int) -> list[str]:
    """WARN lines for every analyst read over max_bytes. Never alters ctx."""
    return [
        f"WARN: shared-ctx read '{read}' is {size} bytes, over --max-bytes "
        f"{max_bytes}. Every analyst performs this read once per item; above "
        f"~37 KB the result reaches it as a 2 KB preview."
        for read, size in read_sizes(ctx).items()
        if size > max_bytes
    ]


def count_collisions(mocs: list[dict]) -> int:
    """Distinct titles held by two or more eligible MOCs (compared by path_key)."""
    seen: dict[str, int] = {}
    for moc in mocs:
        key = path_key(moc["title"])
        seen[key] = seen.get(key, 0) + 1
    return sum(1 for n in seen.values() if n > 1)


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
    p.add_argument(
        "--max-bytes",
        type=int,
        default=32768,
        help="Per-read warning threshold in bytes (default 32768); nothing is shed",
    )
    p.add_argument(
        "--skip-reconcile",
        action="store_true",
        help="Skip the listDir-vs-cache MOC reconcile step (offline / test mode)",
    )
    p.add_argument(
        "--warnings-out",
        default=None,
        help="Also write every WARN line printed on stderr to this file (rewritten each run)",
    )
    return p


class _WarnRecorder:
    """Pass-through stderr that keeps a copy of every line starting with WARN:."""

    def __init__(self, stream):
        self._stream = stream
        self._partial = ""
        self.warnings: list[str] = []

    def write(self, text: str) -> int:
        self._stream.write(text)
        self._partial += text
        *complete, self._partial = self._partial.split("\n")
        self.warnings.extend(line for line in complete if line.startswith("WARN:"))
        return len(text)

    def flush(self) -> None:
        self._stream.flush()

    def finish(self) -> list[str]:
        if self._partial.startswith("WARN:"):
            self.warnings.append(self._partial)
        self._partial = ""
        return self.warnings


def main() -> int:
    args = build_arg_parser().parse_args()
    if not args.warnings_out:
        return build(args)
    original_stderr = sys.stderr
    recorder = _WarnRecorder(original_stderr)
    sys.stderr = recorder
    try:
        return build(args)
    finally:
        sys.stderr = original_stderr
        warnings_path = Path(args.warnings_out)
        ensure_parent(warnings_path)
        warnings_path.write_text(
            "".join(line + "\n" for line in recorder.finish()), encoding="utf-8"
        )


def build(args: argparse.Namespace) -> int:
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

    # Reconcile cache against live vault (drops ghost MOCs from stale cache).
    map_notes_total_before = len(cache.get("map_notes") or [])
    reconcile_dropped: list[str] = []
    if args.skip_reconcile:
        print("[shared-ctx] reconcile skipped (--skip-reconcile)", file=sys.stderr)
    else:
        try:
            _, reconcile_dropped = reconcile_map_notes_against_vault(cache)
            if reconcile_dropped:
                print(
                    f"[shared-ctx] reconcile: dropped {len(reconcile_dropped)} ghost MOC(s) "
                    f"from cache (paths no longer in vault):",
                    file=sys.stderr,
                )
                for p in reconcile_dropped[:10]:
                    print(f"  - {p}", file=sys.stderr)
                if len(reconcile_dropped) > 10:
                    print(f"  ... and {len(reconcile_dropped) - 10} more", file=sys.stderr)
            else:
                print(
                    f"[shared-ctx] reconcile: cache clean "
                    f"({map_notes_total_before} MOC(s) verified)",
                    file=sys.stderr,
                )
        except (RuntimeError, KadoError) as exc:
            # Don't fail the build if reconcile blows up — log loudly and
            # continue with the full (potentially stale) cache.
            print(
                f"[shared-ctx] reconcile FAILED: {exc} — proceeding with unfiltered cache "
                f"(may include ghost MOCs)",
                file=sys.stderr,
            )

    conventions = resolve_conventions(
        profile_dict=profile, profiles_dir=profiles_dir
    )

    mocs = build_mocs(cache, moc_folder_prefixes(vault_cfg))
    tag_prefixes = build_tag_prefixes(cache, vault_cfg)
    classification_keywords = build_classification_keywords(profile)
    daily_notes = build_daily_notes(vault_cfg)
    asset_folder = build_asset_folder(vault_cfg)
    placeholder_targets = build_placeholder_targets(cache, _moc_name_re(conventions.moc_suffix))

    ctx: dict = {
        "schema_version": "1",
        "run_id": run_id,
        "mocs": mocs,
        "tag_prefixes": tag_prefixes,
        "classification_keywords": classification_keywords,
        "asset_folder": asset_folder,
        "placeholder_targets": placeholder_targets,
    }
    if daily_notes is not None:
        ctx["daily_notes"] = daily_notes

    warn_unusable_trackers(ctx)

    for line in size_guards(ctx, args.max_bytes):
        print(line, file=sys.stderr)
    data = serialize(ctx)
    sizes = read_sizes(ctx)
    excluded = sum(1 for e in cache.get("map_notes") or [] if is_excluded_moc(e.get("tags")))

    ensure_parent(out_path)
    out_path.write_bytes(data)

    print(
        f"mocs_total={map_notes_total_before} "
        f"mocs_after_reconcile={len(cache.get('map_notes') or [])} "
        f"mocs_reconcile_dropped={len(reconcile_dropped)} "
        f"eligible={len(ctx['mocs'])} "
        f"excluded={excluded} "
        f"collisions={count_collisions(ctx['mocs'])} "
        f"names_bytes={sizes['names']} "
        f"detail_bytes={_compact_len(ctx['mocs'])} "
        f"tag_prefixes_included={len(ctx['tag_prefixes'])} "
        f"classification_categories={len(ctx['classification_keywords'])} "
        f"placeholder_targets={len(placeholder_targets)} "
        f"daily_notes_enabled={bool(daily_notes)} "
        f"asset_folder={ctx['asset_folder']} "
        f"bytes={len(data)} "
        f"run_id={run_id}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
