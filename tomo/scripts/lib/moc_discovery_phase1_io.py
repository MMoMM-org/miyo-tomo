# version: 0.1.0
"""moc_discovery_phase1_io.py — Two-pass Phase-1 file I/O of moc-discovery (`--emit-phase1` / `--phase1-input`).

Pass 1 writes the candidates with cache topics (null plus a body excerpt for
misses) for the moc-architect agent to complete; pass 2 reads the completed
file back as Candidates. `moc-discovery.py` re-exports every name.

Rationale: docs/tomo/scripts/lib/moc_discovery_phase1_io.md (issue #216).
"""
from __future__ import annotations

import json
from pathlib import Path

from lib.moc_discovery_common import ABORT_MESSAGES, Candidate, _log
from lib.moc_discovery_topics import LLM_BATCH_SIZE, _build_topics_index


def _load_phase1_input(path: Path) -> tuple[str, str, str, list[Candidate]]:
    """Load a phase1-input JSON file → (mode, trigger_arg, profile, candidates).

    Raises ValueError on malformed input. Used by the `--phase1-input` flow
    after the moc-architect agent has populated topics for cache-miss
    candidates between the `--emit-phase1` and `--phase1-input` passes.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("phase1-input must be a JSON object")
    mode = payload.get("mode")
    trigger_arg = payload.get("trigger_arg", "")
    profile = payload.get("profile")
    raw_candidates = payload.get("candidates")
    if not isinstance(mode, str) or not isinstance(profile, str):
        raise ValueError("phase1-input requires string `mode` and `profile`")
    if not isinstance(raw_candidates, list):
        raise ValueError("phase1-input requires list `candidates`")

    candidates: list[Candidate] = []
    for entry in raw_candidates:
        if not isinstance(entry, dict):
            continue
        topics_raw = entry.get("topics")
        topics = [str(t) for t in topics_raw if t] if isinstance(topics_raw, list) else []
        candidates.append(
            Candidate(
                stem=str(entry.get("stem") or ""),
                path=str(entry.get("path") or ""),
                topics=topics,
                existing_up=entry.get("existing_up"),
                classification=entry.get("classification"),
                level=int(entry.get("level") or 0),
            )
        )
    return mode, str(trigger_arg), profile, candidates


_BODY_EXCERPT_CHARS = 800  # cap per-note body included in phase1 JSON for agent extraction


def _write_phase1_emit(
    path: Path,
    mode: str,
    trigger_arg: str,
    profile_name: str,
    candidates: list[Candidate],
    cache: dict,
    moc_config,
    kado_client,
) -> str | None:
    """Write the --emit-phase1 JSON: candidates with cache-resolved topics or null.

    For each cache-miss candidate, includes a `body_excerpt` (first
    `_BODY_EXCERPT_CHARS` characters) so the moc-architect agent can extract
    topics inline without needing Kado MCP access. The agent rewrites the
    file with all topics populated, then re-invokes the script with
    `--phase1-input`.

    Enforces the cache-miss cap (CON-6: 5 batches × 10 notes = 50) here too,
    since phase 2's enforcement is skipped on the --phase1-input flow.

    Returns the abort_reason if the cap was exceeded, otherwise None.
    """
    topics_by_path = _build_topics_index(cache)
    misses_count = sum(1 for c in candidates if c.path not in topics_by_path)
    cap = getattr(moc_config, "cache_miss_max_batches", 5)
    max_misses = cap * LLM_BATCH_SIZE
    abort_reason: str | None = None
    if misses_count > max_misses:
        _log(
            f"emit-phase1: cache-miss-cap-exceeded "
            f"(misses={misses_count} > cap={max_misses})"
        )
        abort_reason = "cache-miss-cap-exceeded"

    out_candidates: list[dict] = []
    for c in candidates:
        if c.path in topics_by_path:
            out_candidates.append(
                {"stem": c.stem, "path": c.path, "topics": list(topics_by_path[c.path])}
            )
            continue
        # Cache miss — fetch body for agent-side topic extraction (unless aborting).
        body_excerpt = ""
        if abort_reason is None:
            try:
                note = kado_client.read_note(c.path)
                content = (note.get("content") if isinstance(note, dict) else "") or ""
                body_excerpt = content[:_BODY_EXCERPT_CHARS]
            except Exception as exc:  # noqa: BLE001 — kado errors are heterogeneous
                _log(f"emit-phase1: read_note failed for {c.path}: {exc}; body_excerpt empty")
        out_candidates.append(
            {
                "stem": c.stem,
                "path": c.path,
                "topics": None,
                "body_excerpt": body_excerpt,
            }
        )

    out = {
        "schema_version": "1",
        "mode": mode,
        "trigger_arg": trigger_arg,
        "profile": profile_name,
        "abort_reason": abort_reason,
        "abort_message": ABORT_MESSAGES.get(abort_reason) if abort_reason else None,
        "candidates": out_candidates,
    }
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return abort_reason
