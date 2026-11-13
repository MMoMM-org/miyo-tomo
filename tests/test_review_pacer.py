#!/usr/bin/env python3
# version: 0.2.1
"""test_review_pacer.py — the pacing policy of /review's period read and the
fake vault it is tested against (spec 045 T3.1; PRD F3-AC10, F3-AC11,
F3-AC12; SDD ADR-4, Implementation Examples / pacer).

Part 1 — tests/review_fake_vault.py as the shared Phase 3 fake: list_notes
with a Kado filter and cursor pages, byName globs, byFrontmatter with empty
frontmatter, injected 429 bursts / 503 / connection and auth errors, and the
retry accounting that mirrors KadoClient._call_tool (attempt_count,
call_count, retry_wait_s, pace_wait_s, min_interval) on a virtual clock,
proven against the real client by a parity test.

Part 2 — lib/review_pacer.ReviewPacer: start at 0.3 s, doubling up to 2 s
after a call that needed retries, failed paths retried once at 2 s at the
end, only those failing then reported, connection and auth errors propagate,
summary() with calls / retried / waited_s / not_read / advice, the widest
interval kept after finish() (reads after the end pass stay at 2 s; T3.4),
min_interval restored by close() and the exit (also after an exception).
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
from http.client import HTTPMessage
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from review_fake_vault import ReviewFakeVault  # noqa: E402
from lib.kado_client import (  # noqa: E402
    _MAX_RETRIES,
    _RETRY_BACKOFF_BASE,
    _RETRY_BACKOFF_CAP,
    _RETRY_STATUSES,
    KadoAuthError,
    KadoClient,
    KadoConnectionError,
    KadoNotFoundError,
    KadoRateLimitError,
)
from lib.review_pacer import (  # noqa: E402
    ADVICE_RAISE_LIMIT,
    MAX_INTERVAL_S,
    START_INTERVAL_S,
    ReviewPacer,
)

DAILY = "Calendar/301 Daily/"
A, B, C, D, E = (DAILY + f"2026-03-2{i}.md" for i in range(3, 8))

MS_DAY = 86_400_000


def _vault(**extra) -> ReviewFakeVault:
    files = {
        A: "---\ntags: [daily, journal]\n---\n# Monday\n\n[[Project X]] and ![[DP-2026-03-23|Dayplanner]]\n",
        B: "# Tuesday\n\n## Notes\n[[Project Y]]\n",
        C: "# Wednesday\n",
        D: "# Thursday\n",
        E: "# Friday\n",
        DAILY + "2025/2025-12-31.md": "# old\n",
        "Efforts/300 Planner/DP-2026-03-23.md": "# plan\n",
    }
    files.update(extra)
    return ReviewFakeVault(files)


# ===========================================================================
# Part 1 — the fake vault
# ===========================================================================

# ---------------------------------------------------------------- list_notes


def test_list_notes_filters_by_created_and_modified_in_unix_ms():
    fake = _vault()
    for i, p in enumerate((A, B, C, D, E)):
        fake.stamp(p, created=(i + 1) * MS_DAY, modified=(i + 10) * MS_DAY)
    created = fake.list_notes(DAILY, depth=1, filter={"createdAfter": 2 * MS_DAY, "createdBefore": 4 * MS_DAY})
    assert [n["path"] for n in created] == [B, C, D], "bounds are inclusive"
    modified = fake.list_notes(DAILY, depth=1, filter={"modifiedAfter": 13 * MS_DAY})
    assert [n["path"] for n in modified] == [D, E]
    assert fake.list_notes_filters[-1] == {"modifiedAfter": 13 * MS_DAY}
    assert all({"path", "created", "modified"} <= set(n) for n in created)


def test_list_notes_without_filter_lists_every_note_under_the_path():
    fake = _vault()
    paths = [n["path"] for n in fake.list_notes(DAILY)]
    assert paths == sorted([A, B, C, D, E, DAILY + "2025/2025-12-31.md"])
    assert fake.list_notes_filters == [None]


def test_list_notes_follows_cursor_pages_one_call_each():
    fake = _vault()
    fake.page_size = 2
    notes = fake.list_notes(DAILY, depth=1, filter={"createdAfter": 0})
    assert [n["path"] for n in notes] == [A, B, C, D, E]
    assert fake.call_count == 3, "five notes in pages of two are three Kado calls"
    assert fake.list_notes_filters == [{"createdAfter": 0}] * 3, "the filter is repeated on every page"


def test_list_notes_fields_links_tags_headings():
    fake = _vault()
    (note,) = fake.list_notes(DAILY, depth=1, fields=["links", "tags", "headings"],
                              filter={"path": A})
    assert note["links"] == [
        {"kind": "link", "target": "Project X"},
        {"kind": "embed", "target": "DP-2026-03-23|Dayplanner"},
    ]
    assert note["tags"] == ["#daily", "#journal"]
    assert note["headings"] == ["Monday"]
    plain = fake.list_notes(DAILY, depth=1, filter={"path": A})[0]
    assert "links" not in plain and "tags" not in plain


def test_list_notes_with_an_empty_result_is_one_call_and_an_empty_list():
    fake = _vault()
    assert fake.list_notes(DAILY, filter={"createdAfter": 10 ** 15}) == []
    assert fake.call_count == 1


# ------------------------------------------------------------ byName / byFrontmatter


def test_by_name_glob_and_substring():
    fake = _vault()
    assert [h["path"] for h in fake.search_by_name("2026-03-2?.md")] == [A, B, C, D, E]
    assert [h["path"] for h in fake.search_by_name("DP-*")] == ["Efforts/300 Planner/DP-2026-03-23.md"]
    assert [h["path"] for h in fake.search_by_name("03-23")] == [A, "Efforts/300 Planner/DP-2026-03-23.md"]


def test_by_frontmatter_hits_carry_empty_frontmatter_like_kado():
    fake = _vault(**{"Inbox/2026-W13 Review.md": "---\ntomo:\n  doc_type: review\n---\n# r\n"})
    hits = fake.search_by_frontmatter("tomo.doc_type=review", path_prefix="Inbox/")
    assert hits == [{"path": "Inbox/2026-W13 Review.md", "frontmatter": {}}]
    assert ("search_by_frontmatter", "tomo.doc_type=review") in fake.events


# --------------------------------------------------------- injected failures


def test_rate_limit_burst_then_success_counts_like_the_client():
    fake = _vault()
    fake.rate_limit(A, failures=2)
    assert fake.read_note(A)["content"].startswith("---")
    assert fake.call_count == 1
    assert fake.attempt_count == 3
    assert fake.retry_wait_s == pytest.approx(2.0), "a 429 waits Retry-After (1 s) per retry"
    assert [s["outcome"] for s in fake.sends] == [429, 429, "ok"]
    fake.read_note(A)
    assert fake.attempt_count == 4, "the burst is spent; the next call goes through"


def test_permanent_rate_limit_outlasts_the_retries():
    fake = _vault()
    fake.rate_limit(A)
    with pytest.raises(KadoRateLimitError) as exc:
        fake.read_note(A)
    assert exc.value.status == 429
    assert fake.call_count == 1
    assert fake.attempt_count == _MAX_RETRIES + 1
    assert fake.retry_wait_s == pytest.approx(float(_MAX_RETRIES))
    assert fake.attempt_count - fake.call_count == _MAX_RETRIES


def test_503_backs_off_without_retry_after():
    fake = _vault()
    fake.rate_limit(A, status=503)
    with pytest.raises(KadoRateLimitError) as exc:
        fake.read_note(A)
    assert exc.value.status == 503
    assert fake.retry_wait_s == pytest.approx(0.5 + 1.0 + 2.0 + 4.0)


def test_burst_turns_away_the_next_sends_on_any_path():
    fake = _vault()
    fake.burst(3)
    fake.read_note(A)  # 3 failures, then ok
    assert fake.attempt_count == 4 and fake.call_count == 1
    fake.read_note(B)
    assert fake.attempt_count == 5, "the burst is over"
    assert [s["path"] for s in fake.sends] == [A, A, A, A, B]


def test_per_path_rate_limit_applies_to_every_operation_on_that_path():
    fake = _vault()
    fake.rate_limit(A, failures=1)
    fake.read_frontmatter(A)
    assert fake.attempt_count == 2
    fake.rate_limit(DAILY, failures=1)
    fake.list_notes(DAILY)
    assert fake.attempt_count == 4


def test_connection_and_auth_errors_are_not_retried():
    fake = _vault()
    fake.fail[("read_note", A)] = KadoConnectionError("lost")
    with pytest.raises(KadoConnectionError):
        fake.read_note(A)
    assert fake.attempt_count == 1 and fake.retry_wait_s == 0.0
    fake.auth_error = KadoAuthError("401")
    with pytest.raises(KadoAuthError):
        fake.read_note(B)
    assert fake.attempt_count == 2
    fake.auth_error = None
    fake.connection_error = KadoConnectionError("down")
    with pytest.raises(KadoConnectionError):
        fake.list_notes(DAILY)


def test_paths_seen_records_every_path_asked_for():
    fake = _vault()
    fake.read_note(A)
    fake.list_notes(DAILY)
    fake.search_by_name("DP-*")
    assert {A, DAILY, "DP-*"} <= fake.paths_seen


# ------------------------------------------------------------- pace accounting


def test_pace_wait_accrues_min_interval_between_instant_sends():
    fake = _vault()
    fake.min_interval = 0.3
    fake.read_note(A)
    fake.read_note(B)
    fake.read_note(C)
    assert fake.pace_wait_s == pytest.approx(0.6)
    assert fake.clock == pytest.approx(0.6)


def test_a_retry_sleep_longer_than_the_interval_costs_no_pace_wait():
    fake = _vault()
    fake.min_interval = 0.3
    fake.rate_limit(A, failures=1)
    fake.read_note(A)
    assert fake.retry_wait_s == pytest.approx(1.0)
    assert fake.pace_wait_s == 0.0


def _ok() -> MagicMock:
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "result": {"content": [{"type": "text", "text": json.dumps({"content": "x"})}]}}).encode()
    resp = MagicMock()
    resp.read.return_value = body
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=resp)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _429(retry_after: str = "1") -> urllib.error.HTTPError:
    h = HTTPMessage()
    h["Retry-After"] = retry_after
    return urllib.error.HTTPError("http://x/mcp", 429, "Too Many", h, io.BytesIO(b""))


def test_fake_accounting_matches_the_real_client_on_one_429_scenario():
    """Two reads at 0.3 s: the first turned away twice (Retry-After 1 s), the second clean."""
    real = KadoClient(base_url="http://localhost:23026", token="t", min_interval=0.3)
    now = [100.0]

    def fake_sleep(s: float) -> None:
        now[0] += s

    with patch("lib.kado_client.urllib.request.urlopen", side_effect=[_429(), _429(), _ok(), _ok()]), \
            patch("lib.kado_client.time.monotonic", side_effect=lambda: now[0]), \
            patch("lib.kado_client.time.sleep", side_effect=fake_sleep):
        real.read_note(A)
        real.read_note(B)

    fake = _vault()
    fake.min_interval = 0.3
    fake.rate_limit(A, failures=2)
    fake.read_note(A)
    fake.read_note(B)

    for counter in ("call_count", "attempt_count", "retry_wait_s", "pace_wait_s"):
        assert getattr(fake, counter) == pytest.approx(getattr(real, counter)), counter
    assert fake.attempt_count - fake.call_count == 2


# ===========================================================================
# Part 2 — ReviewPacer
# ===========================================================================


def test_the_clients_retry_constants_are_the_ones_the_pacer_budget_rests_on():
    """The fake imports these from production, so every fake-based test follows a change of them silently; the
    45- and 170-call budgets and the pacer's 0.3 s / 2 s spacing were derived with exactly these (SDD Performance)."""
    assert _MAX_RETRIES == 4
    assert _RETRY_BACKOFF_BASE == 0.5 and _RETRY_BACKOFF_CAP == 10.0
    assert _RETRY_STATUSES == {429, 503}


def test_constants_match_the_sdd():
    assert START_INTERVAL_S == 0.3
    assert MAX_INTERVAL_S == 2.0
    assert ADVICE_RAISE_LIMIT == "raise-kado-limit"


def test_pacer_starts_at_0_3_s_and_returns_the_value():
    fake = _vault()
    with ReviewPacer(fake) as pacer:
        assert fake.min_interval == 0.3
        assert pacer.read(A, fake.read_note)["content"].startswith("---")
        pacer.read(B, fake.read_note)
        pacer.read(C, fake.read_note)
        assert fake.pace_wait_s == pytest.approx(0.6)
        assert fake.min_interval == 0.3, "no retries, no widening"
        assert pacer.finish() == []


def test_spacing_doubles_after_each_call_that_needed_retries_up_to_2_s():
    fake = _vault()
    for p in (A, B, C, D):
        fake.rate_limit(p, failures=1)
    with ReviewPacer(fake) as pacer:
        pacer.read(A, fake.read_note)
        assert fake.min_interval == pytest.approx(0.6)
        pacer.read(E, fake.read_note)
        assert fake.min_interval == pytest.approx(0.6), "a clean call keeps the spacing"
        pacer.read(B, fake.read_note)
        assert fake.min_interval == pytest.approx(1.2)
        pacer.read(C, fake.read_note)
        assert fake.min_interval == pytest.approx(2.0)
        pacer.read(D, fake.read_note)
        assert fake.min_interval == pytest.approx(2.0), "capped"
        assert pacer.finish() == []


def test_widened_spacing_is_what_the_following_sends_wait():
    fake = _vault()
    fake.rate_limit(A, failures=1)
    with ReviewPacer(fake) as pacer:
        pacer.read(A, fake.read_note)
        pacer.read(B, fake.read_note)
        pacer.read(C, fake.read_note)
        pacer.finish()
    assert [s["interval"] for s in fake.sends] == [0.3, 0.3, 0.6, 0.6]
    assert fake.pace_wait_s == pytest.approx(1.2)


def test_a_read_that_outlasts_the_retries_returns_none_and_is_recovered_at_the_end():
    fake = _vault()
    fake.rate_limit(A, failures=_MAX_RETRIES + 1)  # the whole first chain, then free
    with ReviewPacer(fake) as pacer:
        assert pacer.read(A, fake.read_note) is None
        assert pacer.read(B, fake.read_note) is not None
        assert pacer.failed == [(A, fake.read_note)]
        assert fake.min_interval == pytest.approx(0.6)
        not_read = pacer.finish()
    assert not_read == []
    assert pacer.recovered[A]["content"].startswith("---")
    assert fake.sends[-1]["path"] == A and fake.sends[-1]["interval"] == 2.0, "the end pass runs at the widest spacing"
    assert pacer.failed == []


def test_only_what_fails_in_the_end_pass_is_not_read():
    fake = _vault()
    fake.rate_limit(A)                                 # permanent
    fake.rate_limit(C, failures=_MAX_RETRIES + 1)      # fails once, free at the end
    with ReviewPacer(fake) as pacer:
        assert pacer.read(A, fake.read_note) is None
        assert pacer.read(B, fake.read_note) is not None
        assert pacer.read(C, fake.read_note) is None
        not_read = pacer.finish()
    assert not_read == [A]
    assert C in pacer.recovered and A not in pacer.recovered


def test_the_end_pass_retries_a_failed_path_exactly_once():
    fake = _vault()
    fake.rate_limit(A)
    with ReviewPacer(fake) as pacer:
        pacer.read(A, fake.read_note)
        pacer.finish()
    assert fake.call_count == 2, "the first read and one end-pass read"
    assert fake.attempt_count == 2 * (_MAX_RETRIES + 1)
    assert fake.min_interval == 0.0, "restored"


def test_finish_with_nothing_failed_makes_no_call():
    fake = _vault()
    with ReviewPacer(fake) as pacer:
        pacer.read(A, fake.read_note)
        before = fake.call_count
        assert pacer.finish() == []
    assert fake.call_count == before


@pytest.mark.parametrize("exc", [KadoConnectionError("lost"), KadoAuthError("401"), KadoNotFoundError("NOT_FOUND")])
def test_connection_auth_and_not_found_errors_propagate_and_restore(exc):
    fake = _vault()
    fake.min_interval = 0.05
    fake.fail[("read_note", A)] = exc
    with pytest.raises(type(exc)):
        with ReviewPacer(fake) as pacer:
            pacer.read(A, fake.read_note)
    assert fake.min_interval == 0.05
    assert pacer.failed == []


def test_connection_error_in_the_end_pass_propagates_and_restores():
    fake = _vault()
    fake.min_interval = 0.05
    fake.rate_limit(A, failures=_MAX_RETRIES + 1)
    calls = {"n": 0}

    def flaky(path):
        calls["n"] += 1
        if calls["n"] == 2:
            raise KadoConnectionError("lost")
        return fake.read_note(path)

    with pytest.raises(KadoConnectionError):
        with ReviewPacer(fake) as pacer:
            assert pacer.read(A, flaky) is None
            pacer.finish()
    assert fake.min_interval == 0.05


def test_finish_keeps_the_widest_interval_until_close_restores_the_previous_value():
    # RED when finish() restores the saved interval again (T3.4): reads after the end pass must stay at 2 s
    fake = _vault()
    fake.min_interval = 0.05
    pacer = ReviewPacer(fake)
    assert fake.min_interval == 0.3
    assert pacer.finish() == []
    assert fake.min_interval == MAX_INTERVAL_S, "finish() leaves the widest spacing installed"
    pacer.read(A, fake.read_note)
    assert fake.sends[-1]["interval"] == MAX_INTERVAL_S, "a read after the end pass is sent at 2 s"
    pacer.close()
    assert fake.min_interval == 0.05
    with ReviewPacer(fake):
        assert fake.min_interval == 0.3
    assert fake.min_interval == 0.05, "the context manager's exit restores"
    with ReviewPacer(fake) as pacer:
        pacer.close()
        fake.min_interval = 0.07
    assert fake.min_interval == 0.07, "the restore happens once, not again on exit"


def test_summary_reports_calls_retried_waited_not_read_and_the_advice():
    fake = _vault()
    fake.rate_limit(A)
    fake.rate_limit(B, failures=2)
    with ReviewPacer(fake) as pacer:
        pacer.read(A, fake.read_note)
        pacer.read(B, fake.read_note)
        pacer.read(C, fake.read_note)
        not_read = pacer.finish()
    summary = pacer.summary(not_read)
    assert summary == {
        "calls": fake.call_count,
        "retried": fake.attempt_count - fake.call_count,
        "waited_s": round(fake.retry_wait_s + fake.pace_wait_s, 1),
        "not_read": [A],
        "advice": [ADVICE_RAISE_LIMIT],
    }
    assert summary["calls"] == 4 and summary["retried"] == 2 * _MAX_RETRIES + 2
    assert summary["waited_s"] > 0


def test_summary_without_retries_has_no_advice():
    fake = _vault()
    with ReviewPacer(fake) as pacer:
        pacer.read(A, fake.read_note)
        pacer.read(B, fake.read_note)
        not_read = pacer.finish()
    assert pacer.summary(not_read) == {"calls": 2, "retried": 0, "waited_s": 0.3, "not_read": [], "advice": []}


def test_pacer_never_installs_an_attempt_gate():
    fake = _vault()
    with ReviewPacer(fake):
        assert fake.attempt_gate is None
