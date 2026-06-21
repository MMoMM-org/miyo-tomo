#!/usr/bin/env python3
# version: 0.12.0
"""inbox-triage.py — Deterministic inbox triage for /inbox routing.

Replaces inbox-discovery.py. Scans inbox state via Kado, reads approval
checkboxes from full doc bodies, caches doc bodies locally, computes
coverage and drift, determines action, and emits routing-plan.json.

CLI: python3 tomo/scripts/inbox-triage.py [OPTIONS]
  --inbox-path PATH     Vault-relative inbox folder (default: from vault-config.yaml)
  --force-pass1         Force suggest action
  --force-pass2         Force synthesize action
  --recover             Treat captured as fresh
  --output-dir DIR      Output directory (default: tomo-tmp)

Exit codes: 0 success, 1 Kado error, 2 schema validation failure.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.audio_constants import AUDIO_EXTS  # noqa: E402
from lib.doc_frontmatter import body_after_frontmatter  # noqa: E402
from lib.kado_client import KadoClient, KadoError  # noqa: E402
from lib.obsidian_filename import sanitize_stem  # noqa: E402

_RE_APPROVED = re.compile(r"^\s*-\s+\[x\]\s+Approved", re.MULTILINE | re.IGNORECASE)
_RE_ACCEPT = re.compile(r"^\s*-\s+\[x\]\s+Accept", re.MULTILINE | re.IGNORECASE)
_RE_FORCE_ATOMIC = re.compile(
    r"^\s*-\s+\[x\]\s+Force Atomic Note",
    re.MULTILINE | re.IGNORECASE,
)
_RE_SECTION_HEADING = re.compile(r"^### S\d+ — (.+)$", re.MULTILINE)
# Matches both **Source:** [[stem]] (SNN sections) and
# "  - Source: [[stem]]" (daily-notes-updates log entries)
_RE_SOURCE_LINK = re.compile(r"(?:\*\*)?Source:(?:\*\*)?\s+\[\[([^\]]+)\]\]")


# ---------------------------------------------------------------------------
# TriageState dataclass
# ---------------------------------------------------------------------------

@dataclass
class TriageState:
    """Holds the result of steps 1-6 of the triage algorithm."""

    inbox_path: str = ""
    all_files: list[dict] = field(default_factory=list)
    audio_files: list[dict] = field(default_factory=list)
    md_files: list[dict] = field(default_factory=list)
    pending_approval_hits: list[dict] = field(default_factory=list)
    pending_accept_hits: list[dict] = field(default_factory=list)
    captured_hits: list[dict] = field(default_factory=list)
    instructions_hits: list[dict] = field(default_factory=list)
    new_sources: list[dict] = field(default_factory=list)
    has_audio: bool = False
    approved_suggestions: list[dict] = field(default_factory=list)
    approved_fan: list[dict] = field(default_factory=list)
    approved_moc_proposals: list[dict] = field(default_factory=list)
    force_atomic_items: list[dict] = field(default_factory=list)
    pending_approval: list[dict] = field(default_factory=list)
    drift_indicators: list[dict] = field(default_factory=list)
    manifest: dict = field(default_factory=dict)

    # Terminal-state approved docs from byFrontmatter (tomo.state=approved).
    # Populated by discover() so detect_orphaned_state() can count them as
    # surviving downstream, and so --force-pass2 can re-synthesize them.
    terminal_approved_hits: list[dict] = field(default_factory=list)

    # Flags passed through for T2.2
    force_pass1: bool = False
    force_pass2: bool = False
    recover: bool = False


# ---------------------------------------------------------------------------
# Step 1: resolve inbox path
# ---------------------------------------------------------------------------

def resolve_inbox_path(cli_inbox_path: str | None) -> str:
    """Resolve inbox path from CLI arg or vault-config.yaml."""
    if cli_inbox_path:
        return cli_inbox_path.rstrip("/") + "/"

    import subprocess
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "read-config-field.py"),
            "--field", "concepts.inbox",
            "--default", "100 Inbox/",
        ],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip().rstrip("/") + "/"


# ---------------------------------------------------------------------------
# Step 2: discover all files, partition audio vs md
# ---------------------------------------------------------------------------

def discover_files(client, inbox_path: str) -> tuple[list[dict], list[dict], list[dict]]:
    """listDir inbox, partition into audio_files and md_files.

    Returns (all_files, audio_files, md_files).
    """
    all_files = client.list_dir(inbox_path, depth=1)
    audio_files = []
    md_files = []

    for item in all_files:
        if (item.get("type") or "").lower() != "file":
            continue
        path = item.get("path", "")
        suffix = Path(path).suffix.lower()
        if suffix in AUDIO_EXTS:
            audio_files.append(item)
        elif suffix == ".md":
            md_files.append(item)

    return all_files, audio_files, md_files


# ---------------------------------------------------------------------------
# Step 3: query frontmatter (4 Kado calls)
# ---------------------------------------------------------------------------

def query_frontmatter(
    client, inbox_path: str,
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """Six byFrontmatter calls for all known tomo states.

    Returns (pending_approval, pending_accept, captured, instructions,
             approved, accepted).
    """
    pending_approval = client.search_by_frontmatter(
        "tomo.state=pending-approval", path_prefix=inbox_path,
    )
    pending_accept = client.search_by_frontmatter(
        "tomo.state=pending-accept", path_prefix=inbox_path,
    )
    captured = client.search_by_frontmatter(
        "tomo.state=captured", path_prefix=inbox_path,
    )
    instructions = client.search_by_frontmatter(
        "tomo.doc_type=instructions", path_prefix=inbox_path,
    )
    approved = client.search_by_frontmatter(
        "tomo.state=approved", path_prefix=inbox_path,
    )
    accepted = client.search_by_frontmatter(
        "tomo.state=accepted", path_prefix=inbox_path,
    )
    return pending_approval, pending_accept, captured, instructions, approved, accepted


def enrich_instructions_frontmatter(
    client: KadoClient, instructions_hits: list[dict]
) -> None:
    """Populate each instructions hit's ``frontmatter`` from a real read (#74).

    Kado byFrontmatter returns ``frontmatter={}`` (see _get_doc_type), so the
    hits from query_frontmatter carry no ``tomo.sources``. compute_coverage and
    detect_drift both read ``instr_doc['frontmatter']['tomo']['sources']`` — so
    without this enrichment ``covered_paths`` is always empty: every approved doc
    reads as uncovered and ``--force-pass2`` re-synthesizes already-applied sets.
    Reads frontmatter once per instructions doc; a failed read leaves the hit's
    frontmatter empty (the doc reads as uncovered — safe-by-default).
    """
    for hit in instructions_hits:
        path = hit.get("path")
        if not path:
            continue
        try:
            fm = client.read_frontmatter(path)
        except KadoError as exc:
            print(
                f"[inbox-triage] WARNING: read_frontmatter failed for {path}: {exc}",
                file=sys.stderr,
            )
            continue
        content = fm.get("content")
        # Only overwrite when the read yields a real frontmatter dict — an empty
        # result must not clobber anything already on the hit (non-destructive).
        if isinstance(content, dict) and content:
            hit["frontmatter"] = content


# ---------------------------------------------------------------------------
# Step 4: compute new sources
# ---------------------------------------------------------------------------

def compute_new_sources(
    md_files: list[dict],
    pending_approval: list[dict],
    pending_accept: list[dict],
    captured: list[dict],
    instructions: list[dict],
    approved: list[dict] | None = None,
    accepted: list[dict] | None = None,
) -> list[dict]:
    """Files not in any frontmatter bucket are new sources."""
    known_paths = set()
    for bucket in (pending_approval, pending_accept, captured, instructions,
                   approved or [], accepted or []):
        for hit in bucket:
            known_paths.add(hit["path"])

    return [f for f in md_files if f["path"] not in known_paths]


# ---------------------------------------------------------------------------
# Step 5: check audio
# ---------------------------------------------------------------------------

def check_audio(audio_files: list[dict], md_files: list[dict]) -> bool:
    """True if uncached audio files exist (audio without sibling .md)."""
    if not audio_files:
        return False

    md_stems = set()
    for f in md_files:
        md_stems.add(Path(f["path"]).stem.lower())

    for af in audio_files:
        raw_stem = Path(af["path"]).stem
        safe_stem = sanitize_stem(raw_stem).lower()
        if safe_stem not in md_stems:
            return True

    return False


# ---------------------------------------------------------------------------
# Step 6: read approval state, cache bodies
# ---------------------------------------------------------------------------

def _get_doc_type(hit: dict) -> str:
    """Extract tomo.doc_type from a frontmatter hit.

    Kado byFrontmatter returns empty frontmatter:{}, so we fall back to
    filename-based inference using the canonical naming convention:
      *_suggestions-fan.md  → suggestions-fan
      *_suggestions.md      → suggestions
      *_moc-proposal-*.md   → moc-proposal
      *_instructions.md     → instructions
    """
    tomo = (hit.get("frontmatter") or {}).get("tomo") or {}
    doc_type = tomo.get("doc_type", "")
    if doc_type:
        return doc_type
    stem = Path(hit.get("path", "")).stem
    if stem.endswith("_suggestions-fan"):
        return "suggestions-fan"
    if stem.endswith("_suggestions"):
        return "suggestions"
    if "_moc-proposal" in stem:
        return "moc-proposal"
    if stem.endswith("_instructions"):
        return "instructions"
    return ""


def _compute_checksum(content: str) -> str:
    """Compute the sha256 checksum of a doc's BODY (frontmatter stripped).

    Hashes the body only so Tomo's own post-render frontmatter mutation
    (tomo.state → approved, updated_at) does not register as content drift on
    the next run (#78). Mirrors instruction-render._compute_sha256 exactly so
    recorded (tomo.sources[].checksum) and current checksums are comparable.
    """
    body = body_after_frontmatter(content)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _extract_fan_items(body: str, source_path: str) -> list[dict]:
    """Scan for [x] Force Atomic Note in body. Extract stem from context.

    FAN checkboxes appear in two locations:
      1. Under ### SNN — <title> sections (per-item suggestion blocks)
      2. Under ### [[date]] daily-notes-updates (log entry sub-bullets)

    For each FAN checkbox, we find the nearest preceding Source: [[stem]]
    line to determine the stem.
    """
    items = []
    lines = body.splitlines()
    last_source_stem = None

    for line in lines:
        # Track the most recent Source: [[stem]]
        source_match = _RE_SOURCE_LINK.search(line)
        if source_match:
            last_source_stem = source_match.group(1)

        # Detect FAN checkbox
        if _RE_FORCE_ATOMIC.search(line) and last_source_stem:
            items.append({
                "stem": last_source_stem,
                "source_path": source_path,
            })

    return items


def _filename_from_path(vault_path: str) -> str:
    """Extract filename from vault path."""
    return Path(vault_path).name


def read_approval_state(
    client,
    pending_approval_hits: list[dict],
    pending_accept_hits: list[dict],
    output_dir: str,
    *,
    terminal_approved_hits: list[dict] | None = None,
    force_pass2: bool = False,
) -> tuple[
    list[dict], list[dict], list[dict],
    list[dict], list[dict], list[dict], dict,
]:
    """Read full bodies for pending docs, scan approvals, cache bodies.

    When force_pass2=True, also reads and caches terminal-approved docs
    (tomo.state=approved) so they can be included in the synthesize work-list.

    Returns (approved_suggestions, approved_fan, approved_moc_proposals,
             force_atomic_items, pending_approval, drift_indicators, manifest).
    """
    approved_suggestions = []
    approved_fan = []
    approved_moc_proposals = []
    force_atomic_items = []
    pending_approval = []
    drift_indicators = []
    manifest = {}

    cache_dir = Path(output_dir) / "inbox-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    tagged_pending: list[tuple[dict, str]] = []
    for doc in pending_approval_hits:
        doc_type = _get_doc_type(doc)
        if not doc_type:
            print(
                f"[inbox-triage] WARNING: unknown doc_type for {doc.get('path', '?')}",
                file=sys.stderr,
            )
            continue
        tagged_pending.append((doc, doc_type))
    for doc in pending_accept_hits:
        doc_type = _get_doc_type(doc) or "moc-proposal"
        tagged_pending.append((doc, doc_type))

    for doc, doc_type in tagged_pending:
        vault_path = doc["path"]
        filename = _filename_from_path(vault_path)

        try:
            result = client.read_note(vault_path)
        except KadoError as exc:
            print(
                f"[inbox-triage] WARNING: kado-read failed for {vault_path}: {exc}",
                file=sys.stderr,
            )
            drift_indicators.append({
                "path": vault_path,
                "type": "missing_source",
                "detail": str(exc),
            })
            continue

        body = result.get("content", "")

        # Cache the body
        cache_path = cache_dir / filename
        cache_path.write_text(body, encoding="utf-8")

        checksum = _compute_checksum(body)
        manifest[filename] = {
            "vault_path": vault_path,
            "checksum": checksum,
            "cached_at": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
        }

        cache_path_str = str(cache_path)

        # Check approval
        approved = False
        if doc_type in ("suggestions", "suggestions-fan"):
            approved = bool(_RE_APPROVED.search(body))
            if approved:
                # Scan for FAN items
                fan_items = _extract_fan_items(body, vault_path)
                force_atomic_items.extend(fan_items)
        elif doc_type == "moc-proposal":
            approved = bool(_RE_ACCEPT.search(body))

        if approved:
            entry = {
                "path": vault_path,
                "modified": str(doc.get("modified", "")),
                "cache_path": cache_path_str,
            }
            if doc_type == "suggestions":
                approved_suggestions.append(entry)
            elif doc_type == "suggestions-fan":
                approved_fan.append(entry)
            elif doc_type == "moc-proposal":
                approved_moc_proposals.append(entry)
        else:
            pending_approval.append({
                "path": vault_path,
                "doc_type": doc_type,
                "message": f"Awaiting user approval ({doc_type})",
            })

    # When --force-pass2: read + cache terminal-approved docs so the conductor
    # can re-synthesize instructions for any that have no covering instructions doc.
    if force_pass2 and terminal_approved_hits:
        # Build set of paths already in approved buckets (from pending-approval flow)
        already_approved = {d["path"] for d in approved_suggestions + approved_fan}
        for doc in terminal_approved_hits:
            vault_path = doc["path"]
            if vault_path in already_approved:
                continue
            doc_type = _get_doc_type(doc)
            if doc_type not in ("suggestions", "suggestions-fan"):
                continue
            filename = _filename_from_path(vault_path)
            try:
                result = client.read_note(vault_path)
            except KadoError as exc:
                print(
                    f"[inbox-triage] WARNING: kado-read failed for {vault_path}: {exc}",
                    file=sys.stderr,
                )
                drift_indicators.append({
                    "path": vault_path,
                    "type": "missing_source",
                    "detail": str(exc),
                })
                continue
            body = result.get("content", "")
            cache_path = cache_dir / filename
            cache_path.write_text(body, encoding="utf-8")
            checksum = _compute_checksum(body)
            manifest[filename] = {
                "vault_path": vault_path,
                "checksum": checksum,
                "cached_at": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
            }
            entry = {
                "path": vault_path,
                "modified": str(doc.get("modified", "")),
                "cache_path": str(cache_path),
            }
            if doc_type == "suggestions":
                approved_suggestions.append(entry)
            elif doc_type == "suggestions-fan":
                approved_fan.append(entry)

    # Write manifest
    manifest_path = cache_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return (
        approved_suggestions,
        approved_fan,
        approved_moc_proposals,
        force_atomic_items,
        pending_approval,
        drift_indicators,
        manifest,
    )


# ---------------------------------------------------------------------------
# discover — main entry point for steps 1-6
# ---------------------------------------------------------------------------

def discover(
    client,
    inbox_path: str,
    *,
    output_dir: str = "tomo-tmp",
    force_pass1: bool = False,
    force_pass2: bool = False,
    recover: bool = False,
) -> TriageState:
    """Execute steps 1-6 of the triage algorithm.

    Parameters
    ----------
    client:      Initialised KadoClient (or compatible fake).
    inbox_path:  Vault-relative inbox path (e.g. "100 Inbox/").
    output_dir:  Local directory for cache files.
    force_pass1: Flag passed through to T2.2.
    force_pass2: Flag passed through to T2.2.
    recover:     Flag passed through to T2.2.

    Returns
    -------
    TriageState with all fields populated.
    """
    inbox_path = inbox_path.rstrip("/") + "/"

    # Step 2: discover files
    all_files, audio_files, md_files = discover_files(client, inbox_path)

    # Step 3: query frontmatter
    (pending_approval_hits, pending_accept_hits, captured_hits,
     instructions_hits, approved_hits, accepted_hits) = (
        query_frontmatter(client, inbox_path)
    )

    # Step 3b: enrich instructions hits with real frontmatter — byFrontmatter
    # returns {} so tomo.sources is invisible to coverage/drift otherwise (#74).
    enrich_instructions_frontmatter(client, instructions_hits)

    # Step 4: compute new sources
    new_sources = compute_new_sources(
        md_files, pending_approval_hits, pending_accept_hits,
        captured_hits, instructions_hits, approved_hits, accepted_hits,
    )

    # Step 5: check audio
    has_audio = check_audio(audio_files, md_files)

    # Step 6: read approval state and cache
    (
        approved_suggestions,
        approved_fan,
        approved_moc_proposals,
        force_atomic_items,
        pending_approval,
        drift_indicators,
        manifest,
    ) = read_approval_state(
        client, pending_approval_hits, pending_accept_hits, output_dir,
        terminal_approved_hits=approved_hits,
        force_pass2=force_pass2,
    )

    return TriageState(
        inbox_path=inbox_path,
        all_files=all_files,
        audio_files=audio_files,
        md_files=md_files,
        pending_approval_hits=pending_approval_hits,
        pending_accept_hits=pending_accept_hits,
        captured_hits=captured_hits,
        instructions_hits=instructions_hits,
        new_sources=new_sources,
        has_audio=has_audio,
        approved_suggestions=approved_suggestions,
        approved_fan=approved_fan,
        approved_moc_proposals=approved_moc_proposals,
        force_atomic_items=force_atomic_items,
        pending_approval=pending_approval,
        drift_indicators=drift_indicators,
        manifest=manifest,
        terminal_approved_hits=approved_hits,
        force_pass1=force_pass1,
        force_pass2=force_pass2,
        recover=recover,
    )


# ---------------------------------------------------------------------------
# Step 7: compute coverage
# ---------------------------------------------------------------------------

def compute_coverage(state: TriageState) -> tuple[set[str], set[str]]:
    """Determine which approved docs are already covered by instructions.

    Returns (covered_paths, to_process) where to_process = approved - covered.
    """
    covered_paths: set[str] = set()
    for instr_doc in state.instructions_hits:
        tomo = (instr_doc.get("frontmatter") or {}).get("tomo") or {}
        for source in tomo.get("sources") or []:
            if source.get("path"):
                covered_paths.add(source["path"])

    approved_paths = set()
    for bucket in (
        state.approved_suggestions,
        state.approved_fan,
        state.approved_moc_proposals,
    ):
        for doc in bucket:
            approved_paths.add(doc["path"])

    to_process = approved_paths - covered_paths
    return covered_paths, to_process


# ---------------------------------------------------------------------------
# Step 8: detect drift
# ---------------------------------------------------------------------------

def detect_drift(
    state: TriageState,
    manifest: dict,
    cache_dir: Path,
) -> list[dict]:
    """Compare cached body checksums against instructions sources[].checksum.

    Returns list of drift indicator dicts for checksum mismatches.
    """
    # Build reverse lookup: vault_path → manifest filename
    vault_to_filename: dict[str, str] = {}
    for filename, entry in manifest.items():
        vault_to_filename[entry["vault_path"]] = filename

    drift_indicators: list[dict] = []

    for instr_doc in state.instructions_hits:
        tomo = (instr_doc.get("frontmatter") or {}).get("tomo") or {}
        for source in tomo.get("sources") or []:
            source_path = source.get("path", "")
            recorded_checksum = source.get("checksum")
            if not source_path or not recorded_checksum:
                continue

            filename = vault_to_filename.get(source_path)
            if not filename:
                continue

            cached_file = cache_dir / filename
            if not cached_file.exists():
                continue

            body = cached_file.read_text(encoding="utf-8")
            current_checksum = _compute_checksum(body)

            if current_checksum != recorded_checksum:
                drift_indicators.append({
                    "path": source_path,
                    "type": "checksum_mismatch",
                    "detail": (
                        f"recorded={recorded_checksum} "
                        f"current={current_checksum}"
                    ),
                })

    return drift_indicators


# ---------------------------------------------------------------------------
# Step 8b: detect orphaned state
# ---------------------------------------------------------------------------

def detect_orphaned_state(state: TriageState) -> list[dict]:
    """Flag captured source items whose downstream docs have all vanished.

    mark-captured writes tomo.state=captured only after a suggestions doc was
    written, so captured items normally have a surviving downstream doc
    (pending-approval suggestion → approved → instructions). When captured
    items exist but every downstream bucket is empty, the suggestions/
    instructions docs were lost (e.g. deleted before approval) and the Pass-1
    analysis is stranded — triage would otherwise route to idle and the loss
    would be silent.

    Advisory only: this reuses the buckets already fetched (no extra Kado
    calls) and emits a single aggregate indicator. It cannot distinguish a
    genuinely orphaned run from a fully-applied batch that was archived while
    its captured source items still linger in the inbox (source items have a
    single terminal state and Tomo never moves them out), so the detail wording
    leaves that to the user and the indicator never changes the routed action.
    """
    downstream = (
        state.pending_approval
        + state.approved_suggestions
        + state.approved_fan
        + state.approved_moc_proposals
        + state.instructions_hits
        + state.terminal_approved_hits
    )
    if not state.captured_hits or downstream:
        return []

    n = len(state.captured_hits)
    plural = "s" if n != 1 else ""
    return [{
        "path": state.inbox_path,
        "type": "orphaned_state",
        "detail": (
            f"{n} captured source item{plural} but no surviving "
            f"suggestion/instruction docs — run /inbox --recover to reprocess "
            f"if you did not already apply and archive them"
        ),
    }]


# ---------------------------------------------------------------------------
# Step 9: determine action
# ---------------------------------------------------------------------------

def determine_action(
    state: TriageState,
    to_process: set[str],
) -> tuple[str, list[str]]:
    """Priority-ordered action determination. First match wins.

    Returns (action, idle_reasons). idle_reasons is non-empty only
    when action == 'idle'.
    """
    # 1. --force-pass1
    if state.force_pass1:
        return "suggest", []

    # 2. --force-pass2
    if state.force_pass2:
        return "synthesize", []

    # 3. has_audio
    if state.has_audio:
        return "transcribe", []

    # 4. force_atomic_items AND NOT fan_doc_exists
    fan_doc_exists = (
        len(state.approved_fan) > 0
        or any(
            d.get("doc_type") == "suggestions-fan"
            for d in state.pending_approval
        )
    )
    if state.force_atomic_items and not fan_doc_exists:
        return "fan-resolve", []

    # 5. to_process non-empty
    if to_process:
        return "synthesize", []

    # 6. --recover with captured items
    if state.recover and state.captured_hits:
        return "suggest", []

    # 7. new_sources present
    if state.new_sources:
        return "suggest", []

    # 8. idle
    idle_reasons = _build_idle_reasons(state, to_process)
    return "idle", idle_reasons


def _build_idle_reasons(
    state: TriageState, to_process: set[str],
) -> list[str]:
    """Produce human-readable reasons for why action is idle."""
    reasons: list[str] = []
    if not state.new_sources:
        reasons.append("No new source files in inbox")
    if not state.pending_approval:
        reasons.append("No pending approvals")
    if not to_process:
        reasons.append(
            "All approved items already covered by existing instructions"
        )
    return reasons


# ---------------------------------------------------------------------------
# Step 10: build routing plan
# ---------------------------------------------------------------------------

def build_routing_plan(
    state: TriageState,
    action: str,
    to_process: set[str],
    drift_indicators: list[dict],
    idle_reasons: list[str],
    metrics: dict,
) -> dict:
    """Assemble routing-plan dict matching routing-plan.schema.json."""
    # --recover treats captured items as fresh (T2.2). The decision tree flips
    # the action to "suggest" on `recover and captured_hits`, but the conductor
    # dispatches `fresh_sources[]` only — so captured items must be folded in
    # here too, or recover fires with an empty dispatch list (bug: 2026-06-09).
    # new_sources and captured_hits are disjoint by construction
    # (compute_new_sources excludes every frontmatter bucket), but dedupe by path
    # defensively so a future overlap can't double-dispatch an item.
    dispatch_sources = list(state.new_sources)
    if state.recover:
        seen = {s["path"] for s in dispatch_sources}
        dispatch_sources += [h for h in state.captured_hits if h["path"] not in seen]
    return {
        "action": action,
        "timestamp": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat().replace("+00:00", "Z"),
        "inbox_path": state.inbox_path,
        "fresh_sources": [
            {"path": s["path"], "modified": str(s.get("modified", ""))}
            for s in dispatch_sources
        ],
        "has_audio": state.has_audio,
        "approved_suggestions": state.approved_suggestions,
        "approved_fan": state.approved_fan,
        "approved_moc_proposals": state.approved_moc_proposals,
        "force_atomic_items": state.force_atomic_items,
        "pending_approval": state.pending_approval,
        "idle_reasons": idle_reasons,
        "drift_indicators": drift_indicators,
        "skip_stems": [],
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Deterministic inbox triage for /inbox routing."
    )
    p.add_argument(
        "--inbox-path", default=None,
        help="Vault-relative inbox folder (default: from vault-config.yaml)",
    )
    p.add_argument(
        "--force-pass1", action="store_true", default=False,
        help="Force suggest action",
    )
    p.add_argument(
        "--force-pass2", action="store_true", default=False,
        help="Force synthesize action",
    )
    p.add_argument(
        "--recover", action="store_true", default=False,
        help="Treat captured as fresh",
    )
    p.add_argument(
        "--output-dir", default="tomo-tmp",
        help="Output directory (default: tomo-tmp)",
    )
    return p


def _validate_routing_plan(plan: dict) -> None:
    """Validate routing plan against schema. Raises SystemExit(2) on failure."""
    import jsonschema

    schema_path = SCRIPT_DIR.parent / "schemas" / "routing-plan.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    try:
        jsonschema.validate(instance=plan, schema=schema)
    except jsonschema.ValidationError as exc:
        print(
            f"ERROR: routing-plan schema validation failed: {exc.message}",
            file=sys.stderr,
        )
        raise SystemExit(2)


def main(
    argv: list[str] | None = None,
    client_factory=None,
) -> int:
    """CLI entry point. Returns exit code.

    Parameters
    ----------
    argv:           Command-line args (default: sys.argv[1:]).
    client_factory: Callable returning a KadoClient (for testing).
    """
    args = _build_arg_parser().parse_args(argv)

    factory = client_factory or KadoClient
    try:
        client = factory()
    except KadoError as exc:
        print(f"ERROR: Kado client init failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

    inbox_path = resolve_inbox_path(args.inbox_path)
    output_dir = Path(args.output_dir)

    t_start = time.perf_counter()

    try:
        state = discover(
            client,
            inbox_path,
            output_dir=args.output_dir,
            force_pass1=args.force_pass1,
            force_pass2=args.force_pass2,
            recover=args.recover,
        )
    except KadoError as exc:
        print(f"ERROR: Triage failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

    t_discover = time.perf_counter()

    # Step 7: coverage
    covered_paths, to_process = compute_coverage(state)

    # Step 8: drift
    cache_dir = output_dir / "inbox-cache"
    new_drift = detect_drift(state, state.manifest, cache_dir)
    # Step 8b: orphaned-state consistency check (reuses already-fetched buckets)
    all_drift = state.drift_indicators + new_drift + detect_orphaned_state(state)

    # Step 9: action
    action, idle_reasons = determine_action(state, to_process)

    t_end = time.perf_counter()
    total_ms = round((t_end - t_start) * 1000, 1)
    discover_ms = round((t_discover - t_start) * 1000, 1)

    metrics = {
        "total_ms": total_ms,
        "discover_ms": discover_ms,
        "kado_calls": _count_kado_calls(state),
        "docs_cached": len(state.manifest),
    }

    # Step 10: build routing plan
    plan = build_routing_plan(
        state=state,
        action=action,
        to_process=to_process,
        drift_indicators=all_drift,
        idle_reasons=idle_reasons,
        metrics=metrics,
    )

    # Validate against schema
    _validate_routing_plan(plan)

    # Write routing-plan.json
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "routing-plan.json"
    plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Step 11: metrics on stderr
    print(
        f"[inbox-triage] {action} in {total_ms}ms — "
        f"md={len(state.md_files)} audio={len(state.audio_files)} "
        f"new={len(state.new_sources)} "
        f"to_process={len(to_process)} "
        f"approved_sugg={len(state.approved_suggestions)} "
        f"approved_fan={len(state.approved_fan)} "
        f"approved_moc={len(state.approved_moc_proposals)} "
        f"fan_items={len(state.force_atomic_items)} "
        f"pending={len(state.pending_approval)} "
        f"drift={len(all_drift)} "
        f"kado_calls={metrics['kado_calls']} "
        f"docs_cached={metrics['docs_cached']}",
        file=sys.stderr,
    )

    return 0


def _count_kado_calls(state: TriageState) -> int:
    """Estimate Kado call count from state.

    1 listDir + 4 byFrontmatter + N body reads.
    """
    body_reads = (
        len(state.approved_suggestions)
        + len(state.approved_fan)
        + len(state.approved_moc_proposals)
        + len(state.pending_approval)
    )
    return 5 + body_reads


if __name__ == "__main__":
    sys.exit(main())
