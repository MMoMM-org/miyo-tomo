# staged_delivery.py — the staged, resumable deliver loop shared by /note and /review.
# version: 0.1.1
"""Write a set of vault files one step at a time, resumable without duplicates.

``note-instructions.py deliver`` and the /review delivery write their files in
a fixed order and must be able to resume after a failed step or a killed
process without writing a second copy of anything that landed (spec 044 ADR-2,
spec 045 ADR-11). The loop lives here once; each caller supplies what differs:
its steps in delivery order, the vault path of every step it uploads, the meta
object that records ``steps_done`` and ``failed_step``, and the callable that
persists that object.

``deliver_step(step, payload)`` applies one rule per uploaded step: a target
already in the vault with identical text (one trailing newline normalised)
counts as done; one with other text stops the delivery with
``DeliveryStop("exists", step, 3, path)`` and nothing is written; an absent
target is uploaded unless the step is already in ``steps_done`` (the file may
have been applied and moved on). Every upload is preceded by persisting the
step as ``failed_step``, so a kill between the upload and its record still
keeps the draft. A KadoError records the step as failed, prints
``<script>: delivery failed at <step> (<ErrorClass>)`` and raises
``DeliveryStop("failed", step, 1)``. A ``.md`` target goes through
``write_note``/``read_note``; any other path through ``write_file``/
``read_file_bytes``.

``record`` and ``fail`` serve steps the caller performs itself (a frontmatter
merge, for instance): they mark the step and persist the same way.
``stable_block(doc_type, state, meta)`` builds a ``tomo:`` block whose
``updated_at`` is ``meta.generated``, so a rebuilt payload is byte-identical
to the landed one.

A step the caller did not declare, or a target for one, is refused with
ValueError; the message names the problem class only, never the name.

Design notes: docs/tomo/scripts/lib/staged_delivery.md
"""
from __future__ import annotations

import sys
from collections.abc import Callable, Iterable, Mapping
from typing import Optional

from lib.doc_frontmatter import build_tomo_block
from lib.kado_client import KadoError
from lib.note_meta import mark_step_done, mark_step_failed


class DeliveryStop(Exception):
    """Ends a delivery early with an output status, a step and an exit code.

    ``reason`` is a caller's name for why the stop happened; None unless the caller sets it."""

    def __init__(self, status: str, step: str, code: int, exists_path: str = ""):
        super().__init__(status)
        self.status, self.step, self.code, self.exists_path = status, step, code, exists_path
        self.reason: Optional[str] = None


def stable_block(doc_type: str, state: str, meta) -> dict:
    """A tomo: block whose updated_at is meta.generated, so a rebuild is byte-identical."""
    block = build_tomo_block(doc_type, state, meta.run_id)
    block["updated_at"] = meta.generated
    return block


def _without_final_newline(text: str) -> str:
    return text[:-1] if text.endswith("\n") else text


def _same_text(client, path: str, payload: str) -> bool:
    if path.endswith(".md"):
        landed = client.read_note(path).get("content") or ""
    else:
        landed = client.read_file_bytes(path).decode("utf-8", errors="replace")
    return _without_final_newline(landed) == _without_final_newline(payload)


def _upload(client, path: str, payload: str) -> None:
    if path.endswith(".md"):
        client.write_note(path, payload)
    else:
        client.write_file(path, payload.encode("utf-8"))


class StagedDelivery:
    """One delivery over the caller's steps; see the module docstring for the rules."""

    def __init__(self, client, steps: Iterable[str], targets: Mapping[str, str], meta,
                 save: Callable[[], None], *, script: str = "staged-delivery"):
        self.steps = tuple(steps)
        if (not self.steps or len(set(self.steps)) != len(self.steps)
                or not all(isinstance(s, str) and s for s in self.steps)):
            raise ValueError("steps must be distinct non-empty names")
        if any(step not in self.steps for step in targets):
            raise ValueError("a target names an undeclared step")
        self.client, self.targets, self.meta, self.save, self.script = (
            client, dict(targets), meta, save, script)

    def _check(self, step: str) -> None:
        if step not in self.steps:
            raise ValueError("unknown delivery step")

    def mark_in_flight(self, step: str) -> None:
        """Persist ``step`` as failed_step before its upload: failed or possibly landed."""
        self._check(step)
        mark_step_failed(self.meta, step, steps=self.steps)
        self.save()

    def record(self, step: str) -> None:
        """Persist ``step`` as done (clearing it as the failed step)."""
        self._check(step)
        mark_step_done(self.meta, step, steps=self.steps)
        self.save()

    def fail(self, step: str, exc: Exception) -> DeliveryStop:
        """Persist ``step`` as failed, name it on stderr, return the stop to raise."""
        self._check(step)
        mark_step_failed(self.meta, step, steps=self.steps)
        self.save()
        print(f"{self.script}: delivery failed at {step} ({type(exc).__name__})",
              file=sys.stderr)
        return DeliveryStop("failed", step, 1)

    def deliver_step(self, step: str, payload: str) -> None:
        """Identical target: done. Other text: name taken. Absent: write unless already done."""
        self._check(step)
        if step not in self.targets:
            raise ValueError("delivery step has no target")
        path = self.targets[step]
        try:
            if self.client.path_exists(path):
                if not _same_text(self.client, path, payload):
                    raise DeliveryStop("exists", step, 3, path)
            elif step not in self.meta.steps_done:
                self.mark_in_flight(step)
                _upload(self.client, path, payload)
        except KadoError as exc:
            raise self.fail(step, exc) from exc
        self.record(step)
