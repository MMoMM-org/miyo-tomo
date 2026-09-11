# version: 0.1.0
"""test_wire_snapshot_parity.py — cross-repo wire-schema parity against
Hashi's vendored copies (spec 035 T2.4/T4.2, ADR-7; Constitution L2).

Split out of `test_instruction_render_wire_hygiene.py` (code-quality review,
2026-09-11): that file's original concern was producer-side instruction-
render apply-blocker hygiene (#68/#69/#70/#64) for a single consumer schema.
T4.2 grew a second, orthogonal concern inside it — parity against THREE
vendored consumer schemas, with its own network tests, its own offline
fixture tests, and its own fetch-skip machinery — self-contained enough
that it needed nothing from the instruction-render fixtures in that file's
other half. The same argument the T4.2 handoff made for moving
`snapshot_parity_delta`/`render_snapshot_parity_report` out of a test
module (a concern with three callers does not belong inside a module
written for something else) applies one level out, to the test module
itself.

Behaviour-preserving move: every test here kept its exact name from the
original file, so the move is auditable as a move, not a rewrite.

## ADR-7's two comparisons

A published wire schema has two distinct things worth comparing it
against, answering different questions with different baselines and
different tolerance for failure:

| comparison | question | baseline | network? |
|---|---|---|---|
| our schema <-> the **committed** vendored copy | does the consumer accept what we emit? | their file, as checked in | no |
| the committed vendored copy <-> **live** upstream | is our copy stale? | their file, as fetched | yes |

`TestVendoredCopies` runs the FIRST comparison — hermetic, offline,
deterministic, and the ONLY place the actual known garden-audit delta
(`up_source`/`up_value`, ours-only) is asserted; the vendored copy only
moves when someone re-vendors it. `TestHashiSchemaParity`'s three
`test_*_snapshot_matches_upstream_hashi` tests run the SECOND — each
fetches Hashi's live schema and skips automatically when the upstream URL
is unreachable (offline runs), via `_fetch_or_skip`; none of them assert
on the delta's *content*, only that producing and rendering it never
raises. Conflating the two — asserting the first comparison's known delta
against the second comparison's live-fetched baseline — would make this
suite go red every time Hashi edits their schema, with no defect of ours
behind it. See `docs/tomo/scripts/lib/wire_snapshot_parity.md` for the
production-module side of this reasoning.

## Why the fetch lives here, not in `lib.wire_snapshot_parity`

`lib.wire_snapshot_parity` never touches the network — CON-2 requires the
detection to pass offline, and `snapshot_parity_delta` is pure. The
network side is entirely local to this file: `_fetch_schema_json(url)`
makes the one `urllib.request.urlopen` call, and `_fetch_or_skip(url)`
wraps it, turning any failure into `pytest.skip` rather than a failure or
(worse) a fabricated delta.

The fetch is genuinely flaky, not theoretically so: building T4.2 hit
`http.client.IncompleteRead` **twice** against
`garden-audit-wire.schema.json` specifically, in the same run that fetched
the other two documents fine. `IncompleteRead` is a **partial** response,
not an absent one — it does NOT inherit from `OSError`, so it needs its
own branch in `_fetch_or_skip`'s `except` tuple
(`http.client.HTTPException`). Letting a partial read reach `json.loads`
unguarded risks two outcomes: it raises (the common case, and still just
"unreachable"), or — far worse — it parses as a smaller-but-valid schema,
and the report then claims the consumer **removed** properties they never
removed. That is a fabricated obligation, the exact inverse of the failure
this spec exists to prevent. `json.JSONDecodeError` gets the same
treatment for the same reason: a truncated-but-parseable-looking body is
"network gave us garbage," not genuine drift.

`TestUpstreamFetchSkip` proves the skip path is RED-provable without
waiting on the network to misbehave: it monkeypatches `_fetch_schema_json`
directly (not `urllib.request.urlopen` — that end-to-end variant is
`TestHashiSchemaParity.test_incomplete_read_during_fetch_skips_not_fails`,
kept alongside as the proof the real call raises what the seam-level tests
assume), separately for `IncompleteRead`, `URLError`, and `TimeoutError`,
and asserts BOTH that `_fetch_or_skip` skips AND that the offline
comparison (`snapshot_parity_delta` against the committed garden-audit
copy) still produces its correct delta afterward — proving a patched,
failing network seam cannot leak into or block the network-free path.
"""
from __future__ import annotations

import http.client
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from lib.wire_snapshot_parity import (  # noqa: E402
    render_snapshot_parity_report,
    snapshot_parity_delta,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
# Committed verbatim copies of Hashi's published-wire schemas (T4.2 vendors
# all three; T2.4 vendored only the instructions copy). Each parity test
# runs UNCONDITIONALLY against its snapshot so it never silently skips in CI /
# containers without a co-located Hashi checkout. A separate network drift
# check (TestHashiSchemaParity's test_*_snapshot_matches_upstream_hashi tests)
# pulls the live schema from GitHub and verifies the snapshot is current —
# skips offline automatically.
HASHI_SCHEMA_SNAPSHOT = SCHEMAS_DIR / "hashi-instructions.schema.json"
HASHI_SUGGESTIONS_SNAPSHOT = SCHEMAS_DIR / "hashi-suggestions-wire.schema.json"
HASHI_GARDEN_AUDIT_SNAPSHOT = SCHEMAS_DIR / "hashi-garden-audit-wire.schema.json"

# Public GitHub raw URLs for Hashi's live schemas — no local checkout required.
# TestHashiSchemaParity's network tests fetch these; every other test uses
# the snapshot files above.
_HASHI_RAW_BASE = (
    "https://raw.githubusercontent.com/MMoMM-org/miyo-tomo-hashi/main/src/schema/"
)
_HASHI_UPSTREAM_URL = _HASHI_RAW_BASE + "instructions.schema.json"
_HASHI_SUGGESTIONS_UPSTREAM_URL = _HASHI_RAW_BASE + "suggestions-wire.schema.json"
_HASHI_GARDEN_AUDIT_UPSTREAM_URL = _HASHI_RAW_BASE + "garden-audit-wire.schema.json"

# Spec 035 T2.4: the report used to carry SNAPSHOT_AHEAD_OF_UPSTREAM here — a
# def-name-keyed exemption registry for the three actions Tomo's snapshot
# carries ahead of live upstream Hashi (edit_note_text, resolve_dead_link,
# remove_up_link). Deleted, not re-keyed: ADR-7 rules a vendored consumer
# copy is a REPORT, never a gate, because it is *supposed* to lag ours
# between a cross-repo handoff and Hashi's confirmation — and a report needs
# no exemptions, only a delta. See docs/tomo/scripts/lib/wire_gate.md.


def _fetch_schema_json(url: str) -> dict:
    """The ONE network call this file's tests make — routed through this
    single function so every skip test can patch exactly this seam
    (`monkeypatch.setattr` on this name) instead of waiting for the network
    to misbehave. Never returns partial data: a truncated transfer either
    raises out of this function or is caught by `_fetch_or_skip`, and is
    never mistaken for a smaller-but-valid schema.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "miyo-tomo-test/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status != 200:
            raise urllib.error.URLError(f"HTTP {resp.status}")
        return json.loads(resp.read().decode("utf-8"))


def _fetch_or_skip(url: str) -> dict:
    """`_fetch_schema_json(url)`, treating any failed/partial/unreachable
    fetch as "skip this test", never as "the schema changed". Three
    observed failure shapes, all folded into the same skip:

    - `urllib.error.URLError` / `TimeoutError` / `OSError` — the ordinary
      "could not reach the host" family.
    - `http.client.HTTPException` — covers `http.client.IncompleteRead`,
      raised by `resp.read()` on a truncated transfer. Hit TWICE against
      `garden-audit-wire.schema.json` specifically while building T4.2, in
      the same run that fetched the other two documents fine. `IncompleteRead`
      does NOT inherit from `OSError`, so it needs its own branch — an
      `IncompleteRead` is a PARTIAL response, not an absent one: letting it
      reach `json.loads` risks either a raise (the common case, handled
      below) or, worse, parsing as a smaller-but-valid schema that reports
      the consumer removed properties they never removed — a fabricated
      obligation, the exact inverse of the failure this spec exists to
      prevent.
    - `json.JSONDecodeError` — a truncated-but-parseable-looking body that
      fails to decode. Same "network gave us garbage" class as a transport
      failure, not genuine drift.
    """
    try:
        return _fetch_schema_json(url)
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        http.client.HTTPException,
        json.JSONDecodeError,
    ) as exc:
        pytest.skip(f"upstream schema unreachable — offline ({exc})")


@pytest.fixture(scope="module")
def instructions_schema() -> dict:
    return json.loads((SCHEMAS_DIR / "instructions.schema.json").read_text(encoding="utf-8"))


def _props(schema: dict, defname: str) -> set:
    return set(schema["$defs"][defname]["properties"].keys())


def _check_upstream_drift(snapshot: dict, document_name: str, url: str) -> None:
    """Upstream drift REPORT (spec 035 T2.4/T4.2, ADR-7) — NOT a gate: a
    vendored consumer copy is *supposed* to lag ours between a cross-repo
    handoff and the consumer's confirmation, so this never fails on a
    delta. Fetches the live schema at `url` (`_fetch_or_skip`, which skips
    rather than raising on any unreachable/partial/malformed response —
    see its own docstring), computes the full-depth structural delta
    against `snapshot` (`snapshot_parity_delta`), and prints it via
    `render_snapshot_parity_report`.

    One shared body for all three published wires (T4.2) — T2.4 built this
    inline inside a single test method for the one document that existed
    then; three documents with three near-identical method bodies is
    exactly the kind of duplication `render_wire_gate_report`'s
    multi-document form already avoids on the gate side.

    The real evidence that this is not vacuous lives in the offline
    fixture tests below (`TestVendoredCopies`, `TestUpstreamFetchSkip`),
    not in this function actually reaching the network in CI — it skips
    automatically when the upstream URL is unreachable, and this
    environment may be offline at any given run.
    """
    live = _fetch_or_skip(url)
    # REPORT, never a gate (ADR-7): no assertion on `changes` — producing
    # and rendering the delta must never raise or fail on its own.
    changes = snapshot_parity_delta(snapshot, live)
    message = render_snapshot_parity_report([{"document": document_name, "changes": changes}])
    if message:
        print(f"\n{message}")


# ── Cross-repo parity (Constitution L2) ─────────────────────────────────────


class TestHashiSchemaParity:
    """Parity guard against the COMMITTED Hashi snapshots — runs unconditionally so
    CI / containers without a co-located Hashi checkout still exercise it. Each
    snapshot is a verbatim copy of one of Hashi's three published-wire schemas; a
    separate drift check (below) catches a snapshot falling behind its live
    Hashi counterpart."""

    @pytest.fixture(scope="class")
    def hashi_snapshot(self) -> dict:
        return json.loads(HASHI_SCHEMA_SNAPSHOT.read_text(encoding="utf-8"))

    @pytest.fixture(scope="class")
    def hashi_suggestions_snapshot(self) -> dict:
        return json.loads(HASHI_SUGGESTIONS_SNAPSHOT.read_text(encoding="utf-8"))

    @pytest.fixture(scope="class")
    def hashi_garden_audit_snapshot(self) -> dict:
        return json.loads(HASHI_GARDEN_AUDIT_SNAPSHOT.read_text(encoding="utf-8"))

    def test_link_to_moc_props_match_snapshot(self, instructions_schema, hashi_snapshot):
        assert _props(instructions_schema, "link_to_moc") == _props(hashi_snapshot, "link_to_moc")

    def test_move_note_props_match_snapshot(self, instructions_schema, hashi_snapshot):
        assert _props(instructions_schema, "move_note") == _props(hashi_snapshot, "move_note")

    def test_snapshot_carries_tomo_block(self, hashi_snapshot, instructions_schema):
        """Snapshot refreshed from Hashi v0.11.0 — the optional top-level tomo
        block must be present in both Hashi's snapshot and Tomo's own schema (#74)."""
        assert "tomo" in hashi_snapshot["properties"]
        assert "tomo" in instructions_schema["properties"]

    def test_snapshot_matches_upstream_hashi(self, hashi_snapshot):
        """[ref: PRD/F8-AC1] instructions.schema.json's live-upstream drift
        report — see `_check_upstream_drift`."""
        _check_upstream_drift(hashi_snapshot, HASHI_SCHEMA_SNAPSHOT.name, _HASHI_UPSTREAM_URL)

    def test_suggestions_snapshot_matches_upstream_hashi(self, hashi_suggestions_snapshot):
        """[ref: PRD/F8-AC1] suggestions-wire.schema.json's live-upstream
        drift report — T4.2's second vendored copy. See
        `_check_upstream_drift`."""
        _check_upstream_drift(
            hashi_suggestions_snapshot,
            HASHI_SUGGESTIONS_SNAPSHOT.name,
            _HASHI_SUGGESTIONS_UPSTREAM_URL,
        )

    def test_garden_audit_snapshot_matches_upstream_hashi(self, hashi_garden_audit_snapshot):
        """[ref: PRD/F8-AC1] garden-audit-wire.schema.json's live-upstream
        drift report — T4.2's third vendored copy, the one whose fetch was
        observed flaky (`_fetch_or_skip`'s docstring). See
        `_check_upstream_drift`."""
        _check_upstream_drift(
            hashi_garden_audit_snapshot,
            HASHI_GARDEN_AUDIT_SNAPSHOT.name,
            _HASHI_GARDEN_AUDIT_UPSTREAM_URL,
        )

    def test_incomplete_read_during_fetch_skips_not_fails(self, hashi_snapshot, monkeypatch):
        """A partial network read (http.client.IncompleteRead, raised by
        resp.read() on a truncated transfer) must be treated the same as an
        unreachable upstream — skip, not fail. Fails if HTTPException is
        removed from the except tuple, since IncompleteRead does not inherit
        from OSError. Patches `urllib.request.urlopen` itself (rather than
        the `_fetch_schema_json` seam TestUpstreamFetchSkip patches below) —
        this is the end-to-end version, proving the real read call inside
        `_fetch_schema_json` raises `IncompleteRead` the way the seam-level
        tests assume it does."""

        class _TruncatedResponse:
            status = 200

            def read(self):
                raise http.client.IncompleteRead(b"", 100)

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

        monkeypatch.setattr(
            urllib.request, "urlopen", lambda *a, **kw: _TruncatedResponse()
        )

        with pytest.raises(pytest.skip.Exception):
            self.test_snapshot_matches_upstream_hashi(hashi_snapshot)


# ── Spec 035 T4.2 — the fetch seam, proven RED without waiting on the network ─
#
# The upstream fetch is genuinely flaky (T4.2 handoff: http.client.IncompleteRead
# hit TWICE against garden-audit-wire.schema.json in one run, while the other two
# documents succeeded). "Observed flaky in CI" is not a test — these inject each
# failure at the one seam `_fetch_or_skip` calls (`_fetch_schema_json`) so the skip
# path is provable on demand, and prove the OFFLINE comparison (Comparison A, ADR-7
# — our schema against the committed vendored copy) is completely unaffected by a
# failed fetch: it needs no network at all (CON-2).


class TestUpstreamFetchSkip:
    """[ref: PRD/F8-AC2] Each exception family gets its own case because
    `http.client.IncompleteRead` specifically does NOT inherit from
    `OSError` — a single collapsed case would not prove the `HTTPException`
    branch is still in the `except` tuple."""

    @pytest.mark.parametrize(
        "exc",
        [
            http.client.IncompleteRead(b"", 100),
            urllib.error.URLError("simulated network failure"),
            TimeoutError("simulated timeout"),
        ],
        ids=["incomplete_read", "url_error", "timeout"],
    )
    def test_fetch_failure_skips_and_offline_checks_still_run(self, exc, monkeypatch):
        def _raise(url: str) -> dict:
            raise exc

        monkeypatch.setattr(sys.modules[__name__], "_fetch_schema_json", _raise)

        with pytest.raises(pytest.skip.Exception):
            _fetch_or_skip("https://example.invalid/schema.json")

        # The offline comparison (Comparison A: our schema against the
        # committed vendored copy) needs no network and must be completely
        # unaffected by the patched seam above — proving the skip path
        # above did not raise from, block, or otherwise taint the
        # deterministic offline path CON-2 requires to keep working.
        recorded = json.loads(HASHI_GARDEN_AUDIT_SNAPSHOT.read_text(encoding="utf-8"))
        observed = json.loads(
            (SCHEMAS_DIR / "garden-audit-wire.schema.json").read_text(encoding="utf-8")
        )
        changes = snapshot_parity_delta(recorded, observed)
        added_properties = {
            c["detail"].removeprefix("added property: ")
            for c in changes if c["kind"] == "added_property"
        }
        assert added_properties == {"up_source", "up_value"}, (
            "the offline comparison must still produce its real delta after "
            "a patched fetch seam skipped — a failed fetch must not leak "
            "into or short-circuit the network-free path"
        )


# ── Spec 035 T2.4 — offline fixture tests for the parity REPORT ─────────────
#
# These are the REAL gate for T2.4, not the tests above. test_snapshot_
# matches_upstream_hashi skips offline in this environment, so "every
# existing test still passes" / "full suite green" are satisfied by never
# running the changed comparison code at all — and converting the check from
# a gate to a report removes its failure mode entirely, so "nothing failed"
# is now the expected outcome on every path, including the one where the
# comparison silently does nothing. Every test below runs offline, against
# SCRATCH COPIES only — a committed schema file is never mutated in place.


class TestSnapshotParityReport:
    def test_defs_free_schema_is_compared_non_vacuously(self):
        """[ref: PRD/F1-AC3] suggestions-wire.schema.json has ZERO `$defs`
        (measured, phase-2.md) — the OLD `$defs`-entries-with-an-`action`-
        property surface iterated an empty intersection here and reported
        NOTHING, which is exactly why it could never have caught the drift
        spec 035 exists to prevent. `describe_shape` + `diff_shapes` walk
        every object node regardless of `$defs`, so an added property is
        reported."""
        path = SCHEMAS_DIR / "suggestions-wire.schema.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        assert not original.get("$defs"), (
            "fixture sanity: suggestions-wire.schema.json must have zero "
            "$defs for this test to prove anything about the $defs-free case"
        )
        mutated = json.loads(path.read_text(encoding="utf-8"))  # independent copy
        mutated["properties"]["suggestions"]["items"]["properties"]["scratch_parity_probe"] = {
            "type": "string",
        }

        changes = snapshot_parity_delta(original, mutated)

        matches = [c for c in changes if "scratch_parity_probe" in c["detail"]]
        assert matches, "an added property on a $defs-free schema must be reported"
        assert matches[0]["kind"] == "added_property"

    def test_root_level_differences_are_detected(self):
        """[ref: PRD/F1-AC1] The old comparison never looked at root-level
        fields at all on either document — today's root parity is
        coincidence, not something it checked. Mutate a root-level property
        and assert it appears in the delta."""
        original = json.loads(HASHI_SCHEMA_SNAPSHOT.read_text(encoding="utf-8"))
        mutated = json.loads(HASHI_SCHEMA_SNAPSHOT.read_text(encoding="utf-8"))
        mutated["properties"]["scratch_root_probe"] = {"type": "string"}

        changes = snapshot_parity_delta(original, mutated)

        root_matches = [
            c for c in changes if c["pointer"] == "" and "scratch_root_probe" in c["detail"]
        ]
        assert root_matches, "a root-level property addition must be reported at pointer ''"
        assert root_matches[0]["kind"] == "added_property"

    def test_known_ahead_actions_report_exactly_and_only_themselves(self):
        """The strongest available test (T2.4 plan step c). Deleting
        SNAPSHOT_AHEAD_OF_UPSTREAM means its three actions (edit_note_text,
        resolve_dead_link, remove_up_link) now surface in the delta instead
        of being silenced — they are in our snapshot and, by construction
        here, absent from the synthesised 'upstream', which is precisely why
        they were exempted before. Synthesise that 'upstream' offline by
        removing those three $defs entries from a COPY of the committed
        snapshot, and assert the report names EXACTLY those three pointers
        and nothing else.

        Each appears at exactly one pointer, its own `/$defs/<name>`
        (measured 2026-09-10, phase-2.md): every property inside these three
        defs is either a plain scalar or a `$ref` to a def (action_id,
        applied_field) that is NOT being removed here, and every `oneOf`
        branch that references one of these three is a pure `{"$ref": ...}`
        object with no `properties` of its own, so it is never itself a
        recorded node. Removing the def is therefore the ONLY structural
        change, not the first of several.
        """
        snapshot = json.loads(HASHI_SCHEMA_SNAPSHOT.read_text(encoding="utf-8"))
        synthetic_upstream = json.loads(HASHI_SCHEMA_SNAPSHOT.read_text(encoding="utf-8"))
        removed_actions = {"edit_note_text", "resolve_dead_link", "remove_up_link"}
        for action in removed_actions:
            assert action in synthetic_upstream["$defs"], (
                f"fixture sanity: {action!r} must exist in the committed snapshot"
            )
            del synthetic_upstream["$defs"][action]

        changes = snapshot_parity_delta(snapshot, synthetic_upstream)

        node_removed_pointers = {c["pointer"] for c in changes if c["kind"] == "node_removed"}
        assert node_removed_pointers == {f"/$defs/{name}" for name in removed_actions}
        # Nothing else moved: no other pointer or change kind appears at all.
        assert len(changes) == len(removed_actions)

    def test_report_is_produced_and_never_raises_or_fails(self, monkeypatch, capsys):
        """[ref: SDD/Architecture Decisions; ADR-7] Both halves, not just
        one: a delta IS produced (this is not a no-op wearing a report's
        name), AND producing/rendering it — through the ACTUAL test method,
        not a reimplementation — raises nothing and fails nothing, even
        though the simulated 'live' schema genuinely drifted (missing all
        three SNAPSHOT_AHEAD_OF_UPSTREAM actions, plus a root-level probe).
        A function that fails on drift is still a gate; asserting only that
        no exception occurred would pass for a function with no body, so
        this also pins the printed report's content.
        """
        real_snapshot = json.loads(HASHI_SCHEMA_SNAPSHOT.read_text(encoding="utf-8"))
        drifted_live = json.loads(HASHI_SCHEMA_SNAPSHOT.read_text(encoding="utf-8"))
        for action in ("edit_note_text", "resolve_dead_link", "remove_up_link"):
            del drifted_live["$defs"][action]
        drifted_live["properties"]["scratch_root_probe"] = {"type": "string"}

        class _FakeResponse:
            status = 200

            def read(self):
                return json.dumps(drifted_live).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: _FakeResponse())

        # Calling the production test method directly (same pattern
        # test_incomplete_read_during_fetch_skips_not_fails already uses) —
        # a bare call with no pytest.raises around it IS the "raises
        # nothing" half. If test_snapshot_matches_upstream_hashi still
        # asserted mismatches, this call would raise AssertionError here.
        TestHashiSchemaParity().test_snapshot_matches_upstream_hashi(real_snapshot)

        printed = capsys.readouterr().out
        assert "edit_note_text" in printed
        assert "resolve_dead_link" in printed
        assert "remove_up_link" in printed
        assert "scratch_root_probe" in printed


# ── Spec 035 T4.2 (code quality review, 2026-09-11) — render_snapshot_parity_report ──
#
# Two rendering fixes bundled into the move (wire_snapshot_parity.py's own
# docstring and the T4.2 commit message call them out) were not directly
# tested by any test above — every test above inspects the `changes` list,
# never the RENDERED STRING, so neither fix was actually asserted anywhere.


class TestRenderSnapshotParityReportCosmetics:
    def test_root_level_pointer_renders_as_root_marker(self):
        """A root-level change (`pointer == ""`) used to render as bare
        leading whitespace with no marker — `f"  {pointer} {kind}: ..."`
        with an empty pointer opened the line with three spaces and nothing
        telling a reader this applies to the schema's root."""
        changes = [{
            "pointer": "", "kind": "added_property",
            "detail": "added property: scratch_root_probe",
            "consumer_affecting": False,
        }]
        message = render_snapshot_parity_report(
            [{"document": "x.schema.json", "changes": changes}]
        )
        assert "  (root) added property: scratch_root_probe" in message

    def test_node_removed_line_does_not_double_print_its_kind(self):
        """`detail` for a `node_removed`/`node_added` change already names
        its own kind in prose (`wire_shape.py`'s `_diff_node`: `f"node
        removed: {pointer}"`) — the OLD renderer's `f"{kind}: {detail}"`
        format then printed `node_removed: node removed: /$defs/x`, a
        literal duplication. The line must contain the human-readable
        detail exactly once, and must never contain the raw `kind`
        identifier (`node_removed`, with the underscore) at all."""
        changes = [{
            "pointer": "/$defs/x", "kind": "node_removed",
            "detail": "node removed: /$defs/x",
            "consumer_affecting": False,
        }]
        message = render_snapshot_parity_report(
            [{"document": "x.schema.json", "changes": changes}]
        )
        assert "  /$defs/x node removed: /$defs/x" in message
        assert "node_removed:" not in message


# ── Spec 035 T4.2 — all three consumer copies are vendored ──────────────────
#
# ADR-7's FIRST comparison (our schema <-> the COMMITTED vendored copy — "does
# the consumer accept what we emit?") runs entirely offline, hermetically, and
# deterministically: the committed copy only moves when someone re-vendors it.
# This is where the known garden-audit delta belongs — asserting it against the
# LIVE remote file instead (TestHashiSchemaParity's network tests, above) would
# make the suite go red whenever Hashi edits their schema, with no defect of
# ours behind it. See docs/tomo/scripts/lib/wire_snapshot_parity.md.


class TestVendoredCopies:
    def test_a_vendored_copy_exists_for_each_published_wire(self):
        """[ref: SDD/Architecture Decisions; ADR-7] Three published wires
        (`lib.wire_shape.PUBLISHED_WIRES`), three committed consumer
        copies. Each must parse as JSON and carry the same
        `properties.schema_version.const` shape `wire_gate.py`'s own
        validation requires — a stub or malformed vendored file would
        otherwise pass this test by merely existing."""
        from lib.wire_shape import PUBLISHED_WIRES

        assert len(PUBLISHED_WIRES) == 3, (
            "fixture sanity: this test enumerates exactly three snapshot "
            "paths below because PUBLISHED_WIRES names exactly three wires "
            "today — if that ever changes, add the fourth snapshot path too"
        )
        for snapshot_path in (
            HASHI_SCHEMA_SNAPSHOT,
            HASHI_SUGGESTIONS_SNAPSHOT,
            HASHI_GARDEN_AUDIT_SNAPSHOT,
        ):
            assert snapshot_path.is_file(), f"missing vendored copy: {snapshot_path}"
            schema = json.loads(snapshot_path.read_text(encoding="utf-8"))
            assert "const" in schema["properties"]["schema_version"], (
                f"{snapshot_path.name}: not a usable schema shape"
            )

    def test_helpers_live_in_tomo_scripts_lib_not_a_test_module(self):
        """[ref: MiYo Constitution; Code Quality] Production code must never
        import from a test module — the T4.2 carry-forward this whole move
        exists to satisfy. Two checks: the functions this file imports
        report living under `tomo/scripts/lib/`, and neither name is
        redefined anywhere under `tests/` (a regression guard against the
        exact shape T2.4 originally built — a `def` back inside a test
        file would slip past every other test here unnoticed, since they
        all call through the module-level import)."""
        import lib.wire_snapshot_parity as wire_snapshot_parity

        lib_dir = (REPO_ROOT / "tomo" / "scripts" / "lib").resolve()
        assert Path(wire_snapshot_parity.__file__).resolve().parent == lib_dir

        this_file = Path(__file__).resolve()
        tests_dir = this_file.parent
        offenders = []
        for path in tests_dir.glob("*.py"):
            if path.resolve() == this_file:
                # This file's own guard literals ("def snapshot_parity_delta(")
                # are the search needles below, not a redefinition — scanning
                # this file against itself would always self-match.
                continue
            text = path.read_text(encoding="utf-8")
            if "def snapshot_parity_delta(" in text or "def render_snapshot_parity_report(" in text:
                offenders.append(path.name)
        assert offenders == [], f"helper redefined inside a test module: {offenders}"

    def test_garden_audit_comparison_a_reports_known_delta_offline(self):
        """[ref: PRD/F8-AC1] Offline, hermetic, deterministic: OUR
        garden-audit-wire.schema.json against the COMMITTED vendored copy
        (never the live remote — see the section comment above). Measured
        2026-09-11 against the vendored copy this task commits: the only
        `added_property` changes are `up_source` and `up_value`, both on
        `findings[].detail` — exactly the delta the T4.2 handoff's ground
        truth named ("our eight properties on findings[].detail against
        their six") — and both are reported UNCLASSIFIED
        (`consumer_affecting: False`), never as obliging the consumer,
        per ADR-7 (carry-forward b: this comparison never calls
        `classify`). A same-run measurement also surfaces one more
        genuine, benign, ours-only delta outside `detail` — the `check`
        enum gaining `parent_not_moc` — which is not part of this
        assertion because the ground truth's "exactly" claim was scoped
        to the properties on `findings[].detail`, not the whole schema;
        scoping the assertion to `kind == "added_property"` matches that
        claim precisely without hardcoding a stronger one that was never
        actually measured end-to-end.
        """
        recorded = json.loads(HASHI_GARDEN_AUDIT_SNAPSHOT.read_text(encoding="utf-8"))
        observed = json.loads(
            (SCHEMAS_DIR / "garden-audit-wire.schema.json").read_text(encoding="utf-8")
        )

        changes = snapshot_parity_delta(recorded, observed)

        added_properties = {
            c["detail"].removeprefix("added property: ")
            for c in changes if c["kind"] == "added_property"
        }
        assert added_properties == {"up_source", "up_value"}
        assert all(c["consumer_affecting"] is False for c in changes), (
            "the vendored-copy comparison is deliberately unclassified "
            "(ADR-7 carry-forward b) — nothing here may claim a change "
            "obliges the consumer"
        )

        # Guard: an empty report and a correct one must not be
        # indistinguishable — the rendered text names the specific
        # pointer AND property, not just a change count.
        message = render_snapshot_parity_report(
            [{"document": HASHI_GARDEN_AUDIT_SNAPSHOT.name, "changes": changes}]
        )
        assert "/properties/findings/items/properties/detail" in message
        assert "up_source" in message
        assert "up_value" in message

    def test_suggestions_comparison_a_reports_measured_delta_offline(self):
        """[ref: PRD/F8-AC1] Offline, hermetic: OUR suggestions-wire.schema.json
        against the COMMITTED vendored copy. Measured 2026-09-11 against the
        vendored copy this task commits: the shapes are structurally
        identical (zero changes) — asserting the actual measured delta
        rather than assuming one exists, per the T4.2 handoff's
        instruction not to hardcode an expectation before looking. If a
        future re-vendor introduces a real delta here, this test is
        EXPECTED to start failing — that failure is the signal to update
        this assertion to the newly measured delta, not evidence of a
        defect in `snapshot_parity_delta` itself.
        """
        recorded = json.loads(HASHI_SUGGESTIONS_SNAPSHOT.read_text(encoding="utf-8"))
        observed = json.loads(
            (SCHEMAS_DIR / "suggestions-wire.schema.json").read_text(encoding="utf-8")
        )

        changes = snapshot_parity_delta(recorded, observed)

        assert changes == []
        assert render_snapshot_parity_report(
            [{"document": HASHI_SUGGESTIONS_SNAPSHOT.name, "changes": changes}]
        ) == ""
