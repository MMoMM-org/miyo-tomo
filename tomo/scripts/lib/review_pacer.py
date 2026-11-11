# review_pacer.py — paces /review's Kado reads: spacing, widening after retries, the end-of-run pass, the not-read list.
# version: 0.1.0
"""The pacing policy of ``review-read.py`` (spec 045, ADR-4; PRD F3-AC10..12).

A period read must come back complete and slow on a busy Kado, never cut
short, so this module installs no attempt budget. ``ReviewPacer`` sets the
client's ``min_interval`` (``START_INTERVAL_S``), doubles it up to
``MAX_INTERVAL_S`` after every call that needed retries, records a read that
outlasted the client's retries (``KadoRateLimitError``) instead of raising,
retries every recorded path once more at the widest spacing in ``finish()``
and names only what still failed. Connection, auth and not-found errors
propagate: they are the caller's to map, not pacing events. The counters come
from the client (``call_count``, ``attempt_count``, ``retry_wait_s``,
``pace_wait_s``); retries are ``attempt_count - call_count``. The previous
``min_interval`` is restored by ``finish()``, ``close()`` and the context
manager's exit, once.

Design notes: docs/tomo/scripts/lib/review_pacer.md
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from lib.kado_client import KadoRateLimitError

START_INTERVAL_S = 0.3  # 0.25 s is exactly Kado's default 20 calls per 5 s
MAX_INTERVAL_S = 2.0
ADVICE_RAISE_LIMIT = "raise-kado-limit"


class ReviewPacer:
    """Paced reads on one client; use as a context manager and call ``finish()`` before leaving."""

    def __init__(self, client):
        self.client = client
        self.failed: List[Tuple[str, Callable[[str], Any]]] = []
        self.recovered: Dict[str, Any] = {}
        self._saved = client.min_interval
        self._installed = True
        client.min_interval = START_INTERVAL_S

    def __enter__(self) -> "ReviewPacer":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        if self._installed:
            self.client.min_interval = self._saved
            self._installed = False

    def retries(self) -> int:
        return self.client.attempt_count - self.client.call_count

    def read(self, path: str, fn: Callable[[str], Any]) -> Any:
        """``fn(path)``, or None when the read outlasted the client's retries (recorded for ``finish``)."""
        before = self.retries()
        try:
            return fn(path)
        except KadoRateLimitError:
            self.failed.append((path, fn))
            return None
        finally:
            if self.retries() > before:
                self.client.min_interval = min(MAX_INTERVAL_S, self.client.min_interval * 2)

    def finish(self) -> List[str]:
        """Retry every failed path once at the widest spacing; return the paths that still failed."""
        self.client.min_interval = MAX_INTERVAL_S
        retry, self.failed = self.failed, []
        not_read: List[str] = []
        try:
            for path, fn in retry:
                try:
                    self.recovered[path] = fn(path)
                except KadoRateLimitError:
                    not_read.append(path)
        finally:
            self.close()
        return not_read

    def summary(self, not_read: List[str]) -> dict:
        retried = self.retries()
        return {
            "calls": self.client.call_count,
            "retried": retried,
            "waited_s": round(self.client.retry_wait_s + self.client.pace_wait_s, 1),
            "not_read": list(not_read),
            "advice": [ADVICE_RAISE_LIMIT] if retried else [],
        }
