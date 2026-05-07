# squelch.py — Sidecar state helper for /moc-propose squelch registry.
# version: 0.1.0
"""Persistence and lifecycle helpers for the MOC-proposal squelch list.

The squelch list records topic clusters the user explicitly rejected during a
recent `/moc-propose` run, so the same cluster does not resurface for a
configurable number of subsequent runs.

On-disk shape (sidecar JSON file at `tomo-instance/state/moc-squelch.json`,
documented in SDD/Data Storage Changes):

    {
      "schema_version": "1",
      "last_run_id": "<UUID>",
      "rejections": [
        {
          "topic_signature": "<sha1 of normalised topic + sorted candidate stems>",
          "topic_keywords": ["zsh", "shell", "terminal"],
          "rejected_at_run_id": "<UUID>",
          "runs_remaining": 3,
          "first_seen_at": "2026-05-07T14:30:00Z"
        }
      ]
    }

In-memory shape: ``dict[str, SquelchEntry]`` keyed by ``topic_signature`` for
O(1) signature lookups during the proposal pipeline.

Failure mode (per SDD/Error-handling): missing or corrupt state file is
treated as an empty registry; a stderr warning is logged so the user can
investigate without the run crashing.

Stdlib only — no new dependencies.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA_VERSION = "1"


@dataclass
class SquelchEntry:
    """One rejected topic cluster persisted across `/moc-propose` runs."""

    topic_signature: str
    topic_keywords: list[str] = field(default_factory=list)
    rejected_at_run_id: str = ""
    runs_remaining: int = 0
    first_seen_at: str = ""

    def is_active(self) -> bool:
        """An entry counts as active while it still has runs remaining."""
        return self.runs_remaining > 0


def load_registry(path: str | os.PathLike[str]) -> dict[str, SquelchEntry]:
    """Load the squelch registry from disk.

    Missing file → empty registry, no warning (first run is the common case).
    Corrupt JSON or unexpected shape → empty registry plus a stderr warning,
    so a malformed sidecar never blocks a run.
    """
    p = Path(path)
    if not p.exists():
        return {}

    try:
        raw_text = p.read_text(encoding="utf-8")
        raw = json.loads(raw_text)
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"WARN: moc-squelch state at {p} unreadable ({exc!r}); "
            "treating as empty registry.",
            file=sys.stderr,
        )
        return {}

    if not isinstance(raw, dict):
        print(
            f"WARN: moc-squelch state at {p} is not a JSON object; "
            "treating as empty registry.",
            file=sys.stderr,
        )
        return {}

    rejections = raw.get("rejections", [])
    if not isinstance(rejections, list):
        print(
            f"WARN: moc-squelch state at {p} has non-list 'rejections'; "
            "treating as empty registry.",
            file=sys.stderr,
        )
        return {}

    registry: dict[str, SquelchEntry] = {}
    for item in rejections:
        if not isinstance(item, dict):
            continue
        signature = item.get("topic_signature")
        if not isinstance(signature, str) or not signature:
            continue
        try:
            entry = SquelchEntry(
                topic_signature=signature,
                topic_keywords=list(item.get("topic_keywords", []) or []),
                rejected_at_run_id=str(item.get("rejected_at_run_id", "")),
                runs_remaining=int(item.get("runs_remaining", 0)),
                first_seen_at=str(item.get("first_seen_at", "")),
            )
        except (TypeError, ValueError):
            # Skip individual malformed rows rather than failing the whole load.
            continue
        registry[signature] = entry

    return registry


def save_registry_atomic(
    path: str | os.PathLike[str],
    registry: dict[str, SquelchEntry],
    *,
    last_run_id: str = "",
) -> None:
    """Write the registry atomically: tmp-then-rename in the same directory.

    Same-directory ``tempfile.mkstemp`` + ``os.replace`` keeps the rename atomic
    on POSIX (single inode swap) and avoids partial writes if the process dies
    mid-write.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "last_run_id": last_run_id,
        "rejections": [asdict(entry) for entry in registry.values()],
    }
    serialised = json.dumps(payload, ensure_ascii=False, indent=2)

    fd, tmp_name = tempfile.mkstemp(
        prefix=p.name + ".",
        suffix=".tmp",
        dir=str(p.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(serialised)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, p)
    except Exception:
        # On failure, clean up the staging file rather than leaving litter.
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def decrement_all(
    registry: dict[str, SquelchEntry],
) -> dict[str, SquelchEntry]:
    """Return a new registry with every entry's ``runs_remaining`` reduced by 1.

    Entries that fall to ``0`` (or below) are dropped — they have served their
    full squelch window and must not influence future runs. The input registry
    is left untouched so callers can keep the prior state for diagnostics.
    """
    decremented: dict[str, SquelchEntry] = {}
    for signature, entry in registry.items():
        new_remaining = entry.runs_remaining - 1
        if new_remaining <= 0:
            continue
        decremented[signature] = SquelchEntry(
            topic_signature=entry.topic_signature,
            topic_keywords=list(entry.topic_keywords),
            rejected_at_run_id=entry.rejected_at_run_id,
            runs_remaining=new_remaining,
            first_seen_at=entry.first_seen_at,
        )
    return decremented


def add_or_replace(
    registry: dict[str, SquelchEntry],
    entry: SquelchEntry,
) -> dict[str, SquelchEntry]:
    """Insert ``entry`` keyed by its ``topic_signature``, replacing any prior.

    Returns a new dict so callers can choose to keep both states; the original
    registry is not mutated.
    """
    updated = dict(registry)
    updated[entry.topic_signature] = entry
    return updated


def is_active(registry: dict[str, SquelchEntry], signature: str) -> bool:
    """True iff ``signature`` is in ``registry`` with ``runs_remaining > 0``."""
    entry = registry.get(signature)
    if entry is None:
        return False
    return entry.is_active()
