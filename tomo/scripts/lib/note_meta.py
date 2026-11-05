# note_meta.py — draft state of one /note draft and the stage directory listing.
# version: 0.1.8
"""Own ``tomo-tmp/note/<stem>/meta.json`` and the listing of stage directories.

``note-instructions.py`` writes the draft state (new, stage, deliver, drop);
``note-session.py start`` lists it to offer resume of started deliveries and to
name stale stages. Both import this module so the field set, the frozen rule and
the kept/stale split exist once.

Paths are built from a base directory (the instance root, i.e. the scripts'
working directory) and a stem of the form ``YYYY-MM-DD_HHMMSS``; any other stem
raises ValueError before a path is built. Error messages name the problem
class only, never a caller-supplied value or text read from meta.json.

Stdlib only.

Design notes: docs/tomo/scripts/lib/note_meta.md
"""
from __future__ import annotations

import json
import posixpath
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from lib.note_io import atomic_write_text
from lib.obsidian_filename import sanitize_stem

STAGE_ROOT = Path("tomo-tmp") / "note"
META_FILE = "meta.json"
STEPS = ("note", "instructions_json", "instructions_md", "source_mark")
# A delivery can fail before its first step: no Kado URL or token. Never a done step.
KADO_CONFIG = "kado_config"
FAILED_STEPS = (KADO_CONFIG, *STEPS)

_STEM_RE = re.compile(r"\d{4}-\d{2}-\d{2}_\d{6}")
_STR_FIELDS = ("stem", "run_id", "created", "generated", "template", "template_stem",
               "title", "inbox_file", "destination", "default_destination", "failed_step")


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
    profile: str | None = None

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


def new_meta(*, stem: str, inbox: str, title: str, destination: str,
             default_destination: str, **fields) -> NoteDraftMeta:
    """Build a fresh draft state; ``fields`` carries the other identity fields."""
    return NoteDraftMeta(
        stem=stem,
        title=title,
        inbox_file=inbox_file_for(inbox, stem, title),
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
        raise ValueError("malformed stem (want YYYY-MM-DD_HHMMSS)")
    return stage_root(base) / stem


def _steps_problem(steps: object) -> bool:
    return (not isinstance(steps, list)
            or not all(isinstance(s, str) and s in STEPS for s in steps)
            or len(set(steps)) != len(steps))


def _shape_problem(raw: dict, stem: str) -> str | None:
    """Return the problem class of a meta.json object, None when it is usable."""
    # Defaulted fields are checked only when present: absent means the dataclass default.
    if any(not isinstance(raw.get(k, ""), str) for k in _STR_FIELDS):
        return "a text field is not a string"
    # source_path, profile, keep_source and steps_done have their own shapes, so not in _STR_FIELDS.
    if raw.get("source_path") is not None and not isinstance(raw["source_path"], str):
        return "source_path is neither a string nor null"
    if raw.get("profile") is not None and not isinstance(raw["profile"], str):
        return "profile is neither a string nor null"
    if not isinstance(raw.get("keep_source", False), bool):
        return "keep_source is not a boolean"
    if _steps_problem(raw.get("steps_done", [])):
        return "steps_done is not a list of distinct known steps"
    if raw.get("failed_step") and raw["failed_step"] not in FAILED_STEPS:
        return "failed_step is not a known step"
    if raw["stem"] != stem:
        return "stem does not match the stage directory"
    return None


def read_meta(stage: Path) -> NoteDraftMeta:
    """Load meta.json from a stage directory; MetaError when unusable or mistyped."""
    try:
        raw = json.loads((Path(stage) / META_FILE).read_text(encoding="utf-8"))
        meta = NoteDraftMeta(**raw)
    except (OSError, ValueError, TypeError) as exc:
        raise MetaError(f"{META_FILE} unusable ({type(exc).__name__})") from exc
    problem = _shape_problem(raw, Path(stage).name)
    if problem:
        raise MetaError(f"{META_FILE} unusable: {problem}")
    return meta


def write_meta(stage: Path, meta: NoteDraftMeta) -> None:
    """Write meta.json atomically (temp file, then replace)."""
    atomic_write_text(Path(stage) / META_FILE, json.dumps(asdict(meta), indent=2) + "\n")


def _check_step(step: str) -> None:
    if step not in STEPS:
        raise ValueError("unknown delivery step")


def mark_step_done(meta: NoteDraftMeta, step: str) -> None:
    """Record ``step`` as done once, in order; clears it as the failed step."""
    _check_step(step)
    if step not in meta.steps_done:
        meta.steps_done.append(step)
    if meta.failed_step == step:
        meta.failed_step = ""


def mark_step_failed(meta: NoteDraftMeta, step: str) -> None:
    """Record ``step`` (a delivery step or KADO_CONFIG) as the step the delivery failed on."""
    if step not in FAILED_STEPS:
        raise ValueError("unknown delivery step")
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
        "steps_done": list(meta.steps_done),
    }


def list_stages(base: Path) -> StageListing:
    """Split stage directories into started deliveries (kept) and stale stages, by stem."""
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
        if meta.failed_step or meta.steps_done:
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
