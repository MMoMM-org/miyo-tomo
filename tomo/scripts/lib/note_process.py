# note_process.py — process files of /note: read, write, decline, required points.
# version: 0.1.2
"""Own ``config/note-processes/<template-stem>.md``.

A process file carries optional YAML frontmatter (``destination``: a relative
vault folder by lib/note_paths.vault_folder, which also normalises it to one
trailing "/" on read and write; ``required`` list of point
names, ``offer: never``) and a body of free guidance. ``offer: never`` with no
other field and no body is a decline marker; with any other field or a body the
file reads as a normal process with ``declined`` false.

``note-process.py`` (read, write, decline) and ``note-instructions.py new``
import this module. ``read_process`` never raises on a broken file: it returns
``exists: true`` with ``error`` naming the problem class, never the file text.
``write_process`` writes nothing when a required point is absent from the
template outline and raises DestinationError for a destination vault_folder
refuses; a stored destination it refuses makes read report ``error``.
``check_outline`` raises OutlineError for an outline of the wrong shape.
Functions take the process directory explicitly; a template stem that could
leave it raises TemplateStemError. All three errors subclass ValueError. No
message carries the stem, a value or file text.

Frontmatter is serialised with yaml.safe_dump and the whole file is replaced
atomically. Schema (documentation): tomo/schemas/note-process.schema.json.

Design notes: docs/tomo/scripts/lib/note_process.md
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from lib.note_paths import vault_folder

PROCESS_DIR = Path("config") / "note-processes"
DECLINE_VALUE = "never"
_FENCE = "---"
OUTLINE_LISTS = ("frontmatter", "headings", "tokens")


class ProcessFileError(Exception):
    """A process file is present but cannot be used; message has no file text."""


class TemplateStemError(ValueError):
    """The template stem could leave the process directory; fixed message."""


class DestinationError(ValueError):
    """A destination to write is not a relative vault folder; fixed message."""


class OutlineError(ValueError):
    """An outline is not the template-outline.py shape; message names the field only."""


def check_outline(data: object) -> dict:
    """Return data when it is an object whose outline lists are lists of objects."""
    if not isinstance(data, dict):
        raise OutlineError("outline is not a JSON object")
    for key in OUTLINE_LISTS:
        value = data.get(key)
        if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
            raise OutlineError(f"outline {key} is not a list of objects")
    return data


def _items(outline: dict, key: str) -> list[dict]:
    value = outline.get(key)
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def outline_points(outline: dict) -> list[str]:
    """Return the outline's points: frontmatter keys, headings, open tokens."""
    names = [f.get("key", "") for f in _items(outline, "frontmatter")]
    names += [h.get("text", "") for h in _items(outline, "headings")]
    names += [t.get("name", "") for t in _items(outline, "tokens") if not t.get("prefilled")]
    seen: list[str] = []
    for name in (n.strip() for n in names if isinstance(n, str)):
        if name and name not in seen:
            seen.append(name)
    return seen


def process_path(process_dir: Path, template_stem: str) -> Path:
    """Return the process file path; TemplateStemError when the stem could leave the dir."""
    stem = template_stem if isinstance(template_stem, str) else ""
    if not stem.strip() or "/" in stem or "\\" in stem or stem.startswith("."):
        raise TemplateStemError("malformed template stem")
    return Path(process_dir) / f"{stem}.md"


def _empty(exists: bool, error: str = "", declined: bool = False) -> dict:
    return {
        "exists": exists, "declined": declined, "destination": "", "required": [],
        "guidance": "", "missing_required": [], "error": error,
    }


def _split(text: str) -> tuple[dict, str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != _FENCE:
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == _FENCE:
            return _load_frontmatter("".join(lines[1:i])), "".join(lines[i + 1:])
    raise ProcessFileError("frontmatter fence is not closed")


def _load_frontmatter(block: str) -> dict:
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        raise ProcessFileError(f"frontmatter is not valid YAML ({type(exc).__name__})") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ProcessFileError("frontmatter is not a key/value mapping")
    return data


def _validate(fm: dict) -> None:
    if "destination" in fm and vault_folder(fm["destination"]) is None:
        raise ProcessFileError("destination is not a relative vault folder")
    req = fm.get("required")
    if req is not None and (not isinstance(req, list)
                            or not all(isinstance(r, str) and r.strip() for r in req)):
        raise ProcessFileError("required must be a list of point names")
    if "offer" in fm and fm["offer"] != DECLINE_VALUE:
        raise ProcessFileError("offer must be 'never' when present")


def _parsed(fm: dict, body: str, outline: dict | None) -> dict:
    guidance = body.strip()
    if fm.get("offer") == DECLINE_VALUE and not guidance and not (set(fm) - {"offer"}):
        return _empty(True, declined=True)
    result = _empty(True)
    result["destination"] = vault_folder(fm["destination"]) if "destination" in fm else ""
    result["required"] = [r.strip() for r in fm.get("required") or []]
    result["guidance"] = guidance
    if outline is not None:
        points = outline_points(outline)
        result["missing_required"] = [r for r in result["required"] if r not in points]
    return result


def read_process(process_dir: Path, template_stem: str, outline: dict | None = None) -> dict:
    """Read a process file; never raises for a missing or broken file."""
    path = process_path(process_dir, template_stem)
    if not path.is_file():
        return _empty(False)
    try:
        fm, body = _split(path.read_text(encoding="utf-8"))
        _validate(fm)
    except ProcessFileError as exc:
        return _empty(True, error=str(exc))
    except (OSError, UnicodeDecodeError) as exc:
        return _empty(True, error=f"process file unreadable ({type(exc).__name__})")
    return _parsed(fm, body, outline)


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _render(fm: dict, guidance: str) -> str:
    head = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False) if fm else ""
    body = guidance.strip()
    return f"{_FENCE}\n{head}{_FENCE}\n" + (f"{body}\n" if body else "")


def _destination_to_write(destination: str | None) -> str | None:
    """Return the vault_folder form, None when absent; DestinationError when refused."""
    if destination is None:
        return None
    folder = vault_folder(destination)
    if folder is None:
        raise DestinationError("destination is not a relative vault folder")
    return folder


def write_process(process_dir: Path, template_stem: str, outline: dict, *,
                  destination: str | None = None, required: list[str] | None = None,
                  guidance: str = "") -> dict:
    """Write a process file, replacing any marker; rejects unknown required points.

    DestinationError when destination is given and vault_folder refuses it.
    """
    path = process_path(process_dir, template_stem)
    folder = _destination_to_write(destination)
    names = [r.strip() for r in required or [] if r.strip()]
    points = outline_points(outline)
    rejected = [r for r in names if r not in points]
    if rejected:
        return {"written": False, "rejected_required": rejected}
    fm: dict = {}
    if folder:
        fm["destination"] = folder
    if names:
        fm["required"] = names
    _write_atomic(path, _render(fm, guidance))
    return {"written": True, "rejected_required": []}


def write_decline(process_dir: Path, template_stem: str) -> dict:
    """Write the decline marker (``offer: never`` alone)."""
    path = process_path(process_dir, template_stem)
    _write_atomic(path, _render({"offer": DECLINE_VALUE}, ""))
    return {"written": True}
