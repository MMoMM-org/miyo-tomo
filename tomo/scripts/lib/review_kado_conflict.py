# review_kado_conflict.py — why Kado refused a /review delivery write: its error code and the reason, as names.
# version: 0.1.1
"""Read a ``KadoError`` a ``/review`` delivery caught (spec 045 ADR-11, P6 live walk; split out of
``review_delivery`` at spec 046 T6.2).

``tool_error_payload`` is the MCP error payload after ``KadoClient``'s prefix as a dict, ``tool_error_code`` its
``code`` (the exact ``"code":"CONFLICT"`` token when the payload is not JSON); ``is_conflict`` says Kado refused the
guard (the client's ``KadoConcurrencyError``, or a tool error whose code is ``CONFLICT``); ``conflict_reason`` names
why: ``open-unsaved`` for Kado's dirty-editor message, ``changed-since-read`` for the write guard's message and for
``KadoConcurrencyError``, else ``unknown`` — never Kado's message itself. ``error_of`` is a failed write's
``error`` for a script's output: the exception's class name, plus Kado's code when it is a closed uppercase token.

Imports the exception classes only; no Kado call, no clock, no file I/O.

Design notes: docs/tomo/scripts/lib/review_kado_conflict.md
"""
from __future__ import annotations

import json
import re
from typing import Optional

from lib.kado_client import KadoConcurrencyError, KadoError, KadoToolError

CONFLICT = "CONFLICT"                                   # Kado's error code for a refused guard or a dirty editor
TOOL_ERROR_PREFIX = "returned an error: "               # KadoClient's prefix before the MCP error payload
OPEN_UNSAVED, CHANGED_SINCE_READ, UNKNOWN_CONFLICT = "open-unsaved", "changed-since-read", "unknown"
EDITOR_PHRASE = "open in the editor with unsaved changes"   # Kado's dirty-editor refusal (note-adapter conflictEditorError)
GUARD_PHRASE = "updated in the background"                  # Kado's write guard (concurrency-guard)
ERROR_CODE = re.compile(r"[A-Z][A-Z_]{0,39}")                # a closed code token, never free text


def tool_error_payload(exc: KadoToolError) -> Optional[dict]:
    """The MCP error payload after the client's prefix as a dict; None when it is not a JSON object."""
    text = str(exc)
    payload = text.split(TOOL_ERROR_PREFIX, 1)[1] if TOOL_ERROR_PREFIX in text else text
    try:
        data = json.loads(payload)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def tool_error_code(exc: KadoToolError) -> Optional[str]:
    """The ``code`` of the MCP error payload after the client's prefix; the exact ``"code":"CONFLICT"``
    token when the payload is not JSON; None when neither names a code."""
    data = tool_error_payload(exc)
    if data is None:
        return CONFLICT if f'"code":"{CONFLICT}"' in str(exc) else None
    code = data.get("code")
    return code if isinstance(code, str) else None


def is_conflict(exc: KadoError) -> bool:
    """Kado refused the guard: the client's concurrency error, or a tool error whose code is CONFLICT."""
    return isinstance(exc, KadoConcurrencyError) or (
        isinstance(exc, KadoToolError) and tool_error_code(exc) == CONFLICT)


def conflict_reason(exc: KadoError) -> str:
    """Why Kado refused the guard, as a name only: ``open-unsaved`` for the dirty-editor message,
    ``changed-since-read`` for the write guard's message and for ``KadoConcurrencyError``, else ``unknown``."""
    if isinstance(exc, KadoConcurrencyError):
        return CHANGED_SINCE_READ
    data = tool_error_payload(exc) if isinstance(exc, KadoToolError) else None
    message = data.get("message") if data is not None else None
    message = message if isinstance(message, str) else ""
    if EDITOR_PHRASE in message:
        return OPEN_UNSAVED
    if GUARD_PHRASE in message:
        return CHANGED_SINCE_READ
    return UNKNOWN_CONFLICT


def error_of(exc: KadoError) -> dict:
    """``{kind, code?}``: the exception's class name, plus Kado's code when it is a closed uppercase token
    (never the message)."""
    error = {"kind": type(exc).__name__}
    code = tool_error_code(exc) if isinstance(exc, KadoToolError) else None
    if isinstance(code, str) and ERROR_CODE.fullmatch(code):
        error["code"] = code
    return error
