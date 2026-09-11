# version: 0.3.0
"""test_instruction_render_wire_hygiene.py — apply-blocker fixes (#68/#69/#70/#64).

Covers the producer-side hygiene that makes a Tomo instruction set appliable by
Hashi without hand-patching:

  #68 — new_section is stripped from link_to_moc before the wire (Hashi's
        link_to_moc schema is additionalProperties:false and rejects it).
  #64 — fit_confidence is lifted to a top-level action field (for telemetry) and
        likewise stripped before the wire.
  #69 — forbidden filename chars (\\ / : * ? " < > |) in a suggested title are
        sanitised in the destination basename AND in every wikilink that targets
        the renamed note (alias preserves the original title for display).
  #70 — two notes assigned the same (target_moc, new_section) merge into ONE
        heading with multiple bullets instead of duplicate `## <section>` blocks.

Plus a cross-repo parity guard: Tomo's link_to_moc/move_note allowed-properties
must match Hashi's schema (MiYo Constitution L2 — coordinated public interface).

TestHashiSchemaParity's three test_*_snapshot_matches_upstream_hashi tests
require network access — each skips automatically when its upstream GitHub
URL is unreachable (offline runs), via `_fetch_or_skip`.

**Spec 035 T2.4**: the instructions comparison surface used to iterate `$defs`
entries carrying an `action` property — 18 real comparisons on the
instructions wire, but ZERO on a `$defs`-free schema (measured), and it never
compared root-level fields on either document. It is now `describe_shape` +
`diff_shapes` to full depth (`lib.wire_snapshot_parity.snapshot_parity_delta`),
and — per ADR-7, which already ruled a vendored consumer copy is a report,
never a gate, because it is *supposed* to lag ours between a cross-repo
handoff and confirmation — it never fails on a delta; it reports one.
`SNAPSHOT_AHEAD_OF_UPSTREAM` is deleted, not re-keyed: a report needs no
exemptions. TestSnapshotParityReport below carries the offline fixture tests
that are the actual evidence for this — see its docstring for why the
obvious "existing tests still pass" evidence does not prove anything here.

**Spec 035 T4.2**: the same comparison is now vendored for all three
published wires, not just instructions — `hashi-suggestions-wire.schema.json`
and `hashi-garden-audit-wire.schema.json` join `hashi-instructions.schema.json`
in `tomo/schemas/`. `snapshot_parity_delta`/`render_snapshot_parity_report`
moved out of this file into `tomo/scripts/lib/wire_snapshot_parity.py`
(production code must never import from a test module — three documents,
three callers, no longer a single-caller exception). TestVendoredCopies
below carries the OFFLINE comparison (our schema against the committed
copy — ADR-7's first comparison, never the network) that is where the known
garden-audit delta is actually asserted; see
docs/tomo/scripts/lib/wire_snapshot_parity.md.
"""
from __future__ import annotations

import http.client
import importlib.util
import io
import json
import sys
import urllib.error
import urllib.request
from contextlib import redirect_stderr
from pathlib import Path

import pytest

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from jsonschema import validate  # noqa: E402

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
_ir_spec = importlib.util.spec_from_file_location(
    "instruction_render", _SCRIPTS_DIR / "instruction-render.py"
)
_ir = importlib.util.module_from_spec(_ir_spec)
assert _ir_spec.loader is not None
sys.modules["instruction_render"] = _ir
_ir_spec.loader.exec_module(_ir)

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
# check (TestUpstreamSnapshotDrift) pulls the live schema from GitHub and
# verifies the snapshot is current — skips offline automatically.
HASHI_SCHEMA_SNAPSHOT = SCHEMAS_DIR / "hashi-instructions.schema.json"
HASHI_SUGGESTIONS_SNAPSHOT = SCHEMAS_DIR / "hashi-suggestions-wire.schema.json"
HASHI_GARDEN_AUDIT_SNAPSHOT = SCHEMAS_DIR / "hashi-garden-audit-wire.schema.json"

# Public GitHub raw URLs for Hashi's live schemas — no local checkout required.
# TestUpstreamSnapshotDrift fetches these; every other test uses the snapshot
# files above.
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
#
# `snapshot_parity_delta` / `render_snapshot_parity_report` moved to
# `tomo/scripts/lib/wire_snapshot_parity.py` for T4.2 (code-quality
# carry-forward from T2.4's review, 2026-09-10): three documents, three
# callers, and production code must never import from a test module — see
# that module's docstring and docs/tomo/scripts/lib/wire_snapshot_parity.md.


def _fetch_schema_json(url: str) -> dict:
    """The ONE network call TestUpstreamSnapshotDrift makes — routed through
    this single function so every skip test can patch exactly this seam
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
      `garden-audit-wire.schema.json` specifically while building this
      test, in the same run that fetched the other two documents fine
      (T4.2 handoff). `IncompleteRead` does NOT inherit from `OSError`, so
      it needs its own branch — an `IncompleteRead` is a PARTIAL response,
      not an absent one: letting it reach `json.loads` risks either a
      raise (the common case, handled below) or, worse, parsing as a
      smaller-but-valid schema that reports the consumer removed
      properties they never removed — a fabricated obligation, the exact
      inverse of the failure this spec exists to prevent.
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


def _link_action(**over) -> dict:
    base = {
        "id": "I01",
        "action": "link_to_moc",
        "target_moc": "Japan (MOC)",
        "target_moc_path": "Atlas/200 Maps/Japan (MOC).md",
        "anchor": {"type": "callout", "value": "[!blocks] Key Concepts"},
        "placement": "after",
        "line_to_add": "- [[Note]]",
        "source_note_title": "Note",
        "new_section": None,
        "fit_confidence": None,
        "applied": False,
    }
    base.update(over)
    return base


# ── #68 — new_section / fit_confidence no-leak ──────────────────────────────


class TestInternalFieldStrip:
    def test_strip_removes_new_section_and_fit_confidence(self):
        actions = [_link_action(new_section="Hokkaido", fit_confidence=0.82)]
        removed = _ir._strip_internal_link_fields(actions)
        assert removed == 2
        assert "new_section" not in actions[0]
        assert "fit_confidence" not in actions[0]

    def test_strip_is_idempotent(self):
        actions = [_link_action(new_section="X", fit_confidence=0.5)]
        _ir._strip_internal_link_fields(actions)
        assert _ir._strip_internal_link_fields(actions) == 0

    def test_strip_ignores_non_link_actions(self):
        actions = [{"action": "move_note", "new_section": "leftover"}]
        assert _ir._strip_internal_link_fields(actions) == 0
        assert actions[0]["new_section"] == "leftover"

    def test_serialize_then_strip_bakes_heading_and_drops_field(self):
        actions = [_link_action(new_section="Hokkaido", line_to_add="- [[Furano]]")]
        _ir._serialize_new_sections(actions)
        _ir._strip_internal_link_fields(actions)
        assert actions[0]["line_to_add"] == "## Hokkaido\n\n- [[Furano]]\n"
        assert "new_section" not in actions[0]

    def test_stripped_link_validates_against_tomo_schema(self, instructions_schema):
        action = _link_action(new_section="Hokkaido", fit_confidence=0.9,
                              line_to_add="- [[Furano]]")
        _ir._serialize_new_sections([action])
        _ir._strip_internal_link_fields([action])
        doc = {
            "schema_version": "2",
            "type": "tomo-instructions",
            "generated": "2026-06-17T00:00:00Z",
            "profile": "miyo",
            "actions": [action],
        }
        validate(instance=doc, schema=instructions_schema)  # must not raise

    def test_unstripped_new_section_would_fail_tomo_schema(self, instructions_schema):
        """Regression guard: new_section on the wire is now schema-invalid
        (mirrors Hashi's additionalProperties:false rejection)."""
        from jsonschema import ValidationError
        action = _link_action(new_section="Hokkaido")
        del action["fit_confidence"]
        # type MUST be the valid const "tomo-instructions" AND the correct
        # schema_version so the ValidationError fires on the unstripped
        # new_section (additionalProperties:false), NOT on a top-level mismatch —
        # otherwise the test would pass even if the new_section rejection regressed
        # (review H9).
        doc = {
            "schema_version": "2", "type": "tomo-instructions",
            "generated": "2026-06-17T00:00:00Z", "profile": "miyo",
            "actions": [action],
        }
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=instructions_schema)


# ── #74 — optional top-level tomo block in instructions.json ────────────────


class TestInstructionsJsonTomoBlock:
    """#74: the machine doc carries an optional top-level tomo block (state +
    sources) so it is self-describing, matching the .md frontmatter. Hashi
    ≥ v0.11.0 accepts and ignores it."""

    def test_top_level_tomo_block_validates(self, instructions_schema):
        block = _ir._build_tomo_block_for_instructions({
            "upstream_type": "suggestions",
            "upstream_path": "100 Inbox/2026-06-20_1432_suggestions.md",
            "upstream_body_path": None,
            "run_id": "pass2-run-001",
        })
        assert block is not None
        assert block["sources"][0]["path"].endswith("_suggestions.md")
        doc = {
            "schema_version": "2", "type": "tomo-instructions",
            "generated": "2026-06-20T12:00:00Z", "profile": "miyo",
            "actions": [], "tomo": block,
        }
        validate(instance=doc, schema=instructions_schema)  # must not raise

    def test_doc_without_tomo_block_still_validates(self, instructions_schema):
        """Backward-compat: tomo is not in required — omitting it stays valid."""
        doc = {
            "schema_version": "2", "type": "tomo-instructions",
            "generated": "2026-06-20T12:00:00Z", "profile": "miyo", "actions": [],
        }
        validate(instance=doc, schema=instructions_schema)  # must not raise

    def test_tomo_block_omitted_when_no_run_id(self):
        """No run_id → builder returns None → key never emitted (never null)."""
        block = _ir._build_tomo_block_for_instructions({
            "upstream_type": "suggestions", "upstream_path": "x.md",
            "upstream_body_path": None, "run_id": None,
        })
        assert block is None

    def test_strip_before_serialize_drops_heading(self):
        """Order regression (review M15): _serialize_new_sections MUST run before
        _strip_internal_link_fields. If strip runs first it consumes new_section
        and serialize has nothing to bake → the `## <section>` heading is silently
        omitted from line_to_add."""
        action = _link_action(new_section="Hokkaido", line_to_add="- [[Furano]]")
        # Wrong order: strip first, then serialize.
        _ir._strip_internal_link_fields([action])
        _ir._serialize_new_sections([action])
        assert not action["line_to_add"].startswith("## "), (
            "strip-before-serialize must NOT produce a heading (proves the "
            "ordering dependency)"
        )


# ── FOOTER_CALLOUTS cross-file sync (review M8) ─────────────────────────────


def test_footer_callouts_match_across_modules():
    """instruction-render.py and moc-tree-builder.py each hardcode FOOTER_CALLOUTS
    (the lib deliberately never hardcodes it — footer_set is caller-supplied per
    spec 022/#35/F-55). The two copies carry a "mirrors exactly" comment with no
    enforcement; this test is the enforcement (review M8)."""
    _mtb_spec = importlib.util.spec_from_file_location(
        "moc_tree_builder", _SCRIPTS_DIR / "moc-tree-builder.py"
    )
    _mtb = importlib.util.module_from_spec(_mtb_spec)
    assert _mtb_spec.loader is not None
    _mtb_spec.loader.exec_module(_mtb)
    assert set(_ir.FOOTER_CALLOUTS) == set(_mtb.FOOTER_CALLOUTS)


# ── Cross-repo parity (Constitution L2) ─────────────────────────────────────


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


# ── #69 — filename sanitisation + resolvable references ─────────────────────

COLON_TITLE = "Oxygen Not Included — Knowledge Progression: From Knowing Things"
SAFE_STEM = "Oxygen Not Included — Knowledge Progression- From Knowing Things"


class TestFilenameSanitisation:
    def test_dest_join_sanitizes_colon(self):
        dest = _ir._dest_join("Atlas/202 Notes", COLON_TITLE)
        assert dest == f"Atlas/202 Notes/{SAFE_STEM}.md"
        assert ":" not in dest

    def test_wikilink_aliases_forbidden_char_title(self):
        link = _ir._wikilink(COLON_TITLE)
        assert link == f"[[{SAFE_STEM}|{COLON_TITLE}]]"

    def test_wikilink_safe_title_no_alias(self):
        assert _ir._wikilink("Plain Title") == "[[Plain Title]]"

    def test_move_note_destination_is_obsidian_safe(self):
        from lib.obsidian_filename import is_obsidian_safe
        manifest = [{
            "action": "create_atomic_note", "title": COLON_TITLE,
            "destination": "Atlas/202 Notes/", "source_path": "src.md",
            "rendered_file": "rendered.md", "parent_mocs": [],
        }]
        actions = _ir._build_move_note_actions(manifest, "100 Inbox/", [0])
        basename = actions[0]["destination"].rsplit("/", 1)[-1]
        assert is_obsidian_safe(basename)

    def test_link_to_moc_refs_resolve_to_safe_stem(self):
        confirmed = [{
            "id": "S01", "action": "create_atomic_note", "title": COLON_TITLE,
            "parent_mocs": ["Japan (MOC)"],
            "candidate_mocs": [],
        }]
        actions = _ir._build_link_to_moc_actions(confirmed, [0])
        link = next(a for a in actions if a["action"] == "link_to_moc")
        assert link["line_to_add"] == f"- [[{SAFE_STEM}|{COLON_TITLE}]]"
        # Spec 034 T6.4b inverted the field these two assertions were written
        # against. The safe stem is still carried and still safe — it just has
        # its own field now, because source_note_title is DISPLAY text under
        # ADR-2 and the coverage audit joins on the raw title. Putting the
        # filename there made instructions-diff hard-fail every correct run
        # whose title held a forbidden character; found live, T6.4 run.
        assert link["source_note_stem"] == SAFE_STEM
        assert link["source_note_title"] == COLON_TITLE
        from lib.obsidian_filename import is_obsidian_safe
        assert is_obsidian_safe(link["source_note_stem"])


# ── #70 — same-section merge ────────────────────────────────────────────────


class TestNewSectionMerge:
    def test_two_notes_same_section_merge_into_one(self):
        actions = [
            _link_action(id="I01", new_section="Hokkaido", line_to_add="- [[Furano]]"),
            _link_action(id="I02", new_section="Hokkaido", line_to_add="- [[Hakodate]]"),
        ]
        removed = _ir._merge_new_section_links(actions)
        assert removed == 1
        links = [a for a in actions if a["action"] == "link_to_moc"]
        assert len(links) == 1
        assert links[0]["line_to_add"] == "- [[Furano]]\n- [[Hakodate]]"

    def test_distinct_sections_not_merged(self):
        actions = [
            _link_action(id="I01", new_section="Hokkaido", line_to_add="- [[Furano]]"),
            _link_action(id="I02", new_section="Kansai", line_to_add="- [[Osaka]]"),
        ]
        assert _ir._merge_new_section_links(actions) == 0
        assert len([a for a in actions if a["action"] == "link_to_moc"]) == 2

    def test_same_moc_different_reference_form_merges(self):
        """Review M9: two actions targeting the SAME MOC by different reference
        forms (bare stem vs full path) and the same new_section must merge — the
        merge key normalises target_moc through _moc_stem()."""
        actions = [
            _link_action(id="I01", target_moc="Japan (MOC)", new_section="Hokkaido",
                         line_to_add="- [[Furano]]"),
            _link_action(id="I02", target_moc="Atlas/200 Maps/Japan (MOC).md",
                         new_section="Hokkaido", line_to_add="- [[Hakodate]]"),
        ]
        assert _ir._merge_new_section_links(actions) == 1
        links = [a for a in actions if a["action"] == "link_to_moc"]
        assert len(links) == 1
        assert links[0]["line_to_add"] == "- [[Furano]]\n- [[Hakodate]]"

    def test_same_section_different_moc_not_merged(self):
        actions = [
            _link_action(id="I01", target_moc="Japan (MOC)", new_section="Maps",
                         line_to_add="- [[A]]"),
            _link_action(id="I02", target_moc="Europe (MOC)", new_section="Maps",
                         line_to_add="- [[B]]"),
        ]
        assert _ir._merge_new_section_links(actions) == 0

    def test_links_without_new_section_untouched(self):
        actions = [
            _link_action(id="I01", line_to_add="- [[A]]"),
            _link_action(id="I02", line_to_add="- [[B]]"),
        ]
        assert _ir._merge_new_section_links(actions) == 0

    def test_merged_then_serialized_is_one_section(self):
        actions = [
            _link_action(id="I01", new_section="Hokkaido", line_to_add="- [[Furano]]"),
            _link_action(id="I02", new_section="Hokkaido", line_to_add="- [[Hakodate]]"),
        ]
        _ir._merge_new_section_links(actions)
        _ir._serialize_new_sections(actions)
        links = [a for a in actions if a["action"] == "link_to_moc"]
        assert links[0]["line_to_add"] == "## Hokkaido\n\n- [[Furano]]\n- [[Hakodate]]\n"


# ── #64 — individual fit_confidence telemetry ───────────────────────────────


class TestFitConfidenceTelemetry:
    def _telemetry(self, actions) -> str:
        buf = io.StringIO()
        with redirect_stderr(buf):
            _ir._emit_resolution_telemetry(actions)
        return buf.getvalue()

    def test_individual_values_appended(self):
        actions = [
            _link_action(id="I01", anchor={"type": "heading", "value": "Concepts"},
                         fit_confidence=0.85),
            _link_action(id="I02", anchor={"type": "heading", "value": "Methods"},
                         fit_confidence=0.72),
        ]
        line = self._telemetry(actions)
        assert "fit_confidence=[0.85, 0.72]" in line

    def test_no_values_no_field(self):
        actions = [_link_action(anchor={"type": "callout", "value": "[!blocks] X"})]
        assert "fit_confidence=[" not in self._telemetry(actions)

    def test_subthreshold_confidence_still_recorded_gate_is_prompt_only(self):
        """The 0.6 fit_confidence gate (tier-1 heading vs tier-2 new-section) is
        enforced UPSTREAM by the inbox-analyst LLM prompt — there is NO Python
        code that branches on 0.6. This test pins that reality (review H10): a
        heading anchor with sub-0.6 confidence is still recorded in the telemetry
        and counted as tier1_confident (the resolver does not re-gate it). If a
        future change adds code-level gating, this test should be updated
        deliberately alongside it."""
        actions = [
            _link_action(id="I01", anchor={"type": "heading", "value": "Concepts"},
                         fit_confidence=0.59),
        ]
        line = self._telemetry(actions)
        assert "fit_confidence=[0.59]" in line
        assert "tier1_confident=1" in line

    def test_emit_lifts_fit_confidence_to_top_level(self):
        confirmed = [{
            "id": "S01", "action": "create_atomic_note", "title": "Note",
            "parent_mocs": ["Japan (MOC)"],
            "candidate_mocs": [{
                "path": "Atlas/200 Maps/Japan (MOC).md",
                "anchor": {"type": "heading", "value": "Concepts", "fit_confidence": 0.9},
            }],
        }]
        actions = _ir._build_link_to_moc_actions(confirmed, [0])
        link = next(a for a in actions if a["action"] == "link_to_moc")
        assert link["fit_confidence"] == 0.9
        # anchor no-leak: the wire anchor stays {type, value}
        assert set(link["anchor"].keys()) == {"type", "value"}
