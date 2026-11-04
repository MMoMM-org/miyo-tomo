# note_meta.py — draft state of one /note draft and the stage directory listing.
# version: 0.1.1
"""Own ``tomo-tmp/note/<stem>/meta.json`` and the listing of stage directories.

``note-instructions.py`` writes the draft state (new, stage, deliver, drop);
``note-session.py start`` lists it to offer resume of failed deliveries and to
name stale stages. Both import this module so the field set, the frozen rule and
the kept/stale split exist once.

Paths are built from a base directory (the instance root, i.e. the scripts'
working directory) and a stem of the form ``YYYY-MM-DD_HHMMSS``; any other stem
raises ValueError before a path is built.

Stdlib only.

Design notes: docs/tomo/scripts/lib/note_meta.md
"""
from __future__ import annotations

import json
import os
import posixpath
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from lib.obsidian_filename import sanitize_stem

STAGE_ROOT = Path("tomo-tmp") / "note"
META_FILE = "meta.json"
STEPS = ("note", "instructions_json", "instructions_md", "source_mark")

_STEM_RE = re.compile(r"\d{4}-\d{2}-\d{2}_\d{6}")


class MetaError(Exception):
    """meta.json is missing, unreadable or not a draft state object."""


@dataclass
class NoteDraftMeta:
    stem: str
    run_id: str
    created: str
    generated: str
    template: str
    template_stem: str
    source_path: str | None
    title: str
    inbox_file: str
    destination: str
    default_destination: str
    keep_source: bool = False
    steps_done: list[str] = field(default_factory=list)
    failed_step: str = ""

    def destination_file(self) -> str:
        """Vault path the approved note moves to."""
        return self.destination + sanitize_stem(self.title) + ".md"

    def instructions_stem(self) -> str:
        """Stem of the instruction set pair in the inbox."""
        return self.stem + "_instructions"


@dataclass
class StageListing:
    kept_drafts: list[dict]
    stale_stages: list[str]


def draw_stem(now: datetime | None = None) -> str:
    """Return a new stem from the clock: ``YYYY-MM-DD_HHMMSS``."""
    return (now or datetime.now()).strftime("%Y-%m-%d_%H%M%S")


def folder(path: str) -> str:
    """Return a vault folder path with exactly one trailing slash."""
    return path.rstrip("/") + "/"


def inbox_file_for(inbox: str, stem: str, title: str) -> str:
    """Return ``<inbox>/<stem>_<sanitized title>.md``."""
    return f"{inbox.rstrip('/')}/{stem}_{sanitize_stem(title)}.md"


def new_meta(*, inbox: str, title: str, destination: str,
             default_destination: str, **fields) -> NoteDraftMeta:
    """Build a fresh draft state; ``fields`` carries the identity fields."""
    return NoteDraftMeta(
        title=title,
        inbox_file=inbox_file_for(inbox, fields["stem"], title),
        destination=folder(destination),
        default_destination=folder(default_destination),
        **fields,
    )


def stage_root(base: Path) -> Path:
    """Return ``<base>/tomo-tmp/note``."""
    return Path(base) / STAGE_ROOT


def stage_dir(base: Path, stem: str) -> Path:
    """Return the stage directory of ``stem``; ValueError on a malformed stem."""
    if not isinstance(stem, str) or not _STEM_RE.fullmatch(stem):
        raise ValueError(f"malformed stem (want YYYY-MM-DD_HHMMSS): {stem!r}")
    return stage_root(base) / stem


def read_meta(stage: Path) -> NoteDraftMeta:
    """Load meta.json from a stage directory; MetaError when unusable."""
    try:
        raw = json.loads((Path(stage) / META_FILE).read_text(encoding="utf-8"))
        return NoteDraftMeta(**raw)
    except (OSError, ValueError, TypeError) as exc:
        raise MetaError(f"{META_FILE} unusable in {Path(stage).name}: {type(exc).__name__}") from exc


def write_meta(stage: Path, meta: NoteDraftMeta) -> None:
    """Write meta.json atomically (temp file, then replace)."""
    target = Path(stage) / META_FILE
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(asdict(meta), indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)


def _check_step(step: str) -> None:
    if step not in STEPS:
        raise ValueError(f"unknown delivery step: {step!r}")


def mark_step_done(meta: NoteDraftMeta, step: str) -> None:
    """Record ``step`` as done once, in order; clears it as the failed step."""
    _check_step(step)
    if step not in meta.steps_done:
        meta.steps_done.append(step)
    if meta.failed_step == step:
        meta.failed_step = ""


def mark_step_failed(meta: NoteDraftMeta, step: str) -> None:
    """Record ``step`` as the step the delivery failed on."""
    _check_step(step)
    meta.failed_step = step


def is_frozen(meta: NoteDraftMeta) -> bool:
    """True once any delivery step is done."""
    return bool(meta.steps_done)


def is_keep_source_frozen(meta: NoteDraftMeta) -> bool:
    """True once the instruction set has landed (instructions_json done)."""
    return "instructions_json" in meta.steps_done


def apply_stage_update(meta: NoteDraftMeta, *, title: str | None = None,
                       destination: str | None = None,
                       keep_source: bool | None = None) -> bool:
    """Apply a stage update; return True (and change nothing) when refused as frozen."""
    new_title = meta.title if title is None else title
    new_dest = meta.destination if destination is None else folder(destination)
    new_keep = meta.keep_source if keep_source is None else keep_source
    names_change = new_title != meta.title or new_dest != meta.destination
    if names_change and is_frozen(meta):
        return True
    if new_keep != meta.keep_source and is_keep_source_frozen(meta):
        return True
    inbox = posixpath.dirname(meta.inbox_file)
    meta.title, meta.destination, meta.keep_source = new_title, new_dest, new_keep
    meta.inbox_file = inbox_file_for(inbox, meta.stem, new_title)
    return False


def _kept_entry(meta: NoteDraftMeta) -> dict:
    return {
        "stem": meta.stem, "title": meta.title, "template": meta.template,
        "created": meta.created, "failed_step": meta.failed_step,
    }


def list_stages(base: Path) -> StageListing:
    """Split stage directories into failed deliveries and stale stages, by stem."""
    root = stage_root(base)
    stems = sorted(p.name for p in root.iterdir()
                   if p.is_dir() and _STEM_RE.fullmatch(p.name)) if root.is_dir() else []
    kept, stale = [], []
    for stem in stems:
        try:
            meta = read_meta(root / stem)
        except MetaError:
            stale.append(stem)
            continue
        if meta.failed_step:
            kept.append(_kept_entry(meta))
        else:
            stale.append(stem)
    return StageListing(kept_drafts=kept, stale_stages=stale)


def remove_stage(base: Path, stem: str) -> bool:
    """Remove the stage directory of ``stem``; False when it did not exist."""
    stage = stage_dir(base, stem)
    if not stage.is_dir():
        return False
    shutil.rmtree(stage)
    return True
