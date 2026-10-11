#!/usr/bin/env python3
"""test_038_t4_5_withheld_attachment_relay.py — spec 038 T4.5.

A withheld attachment was reported in three places and none of them was the
shell: the wire, the instruction document's "**Attachments still in the
inbox**" block, and a `[warn]` line on stderr. A skip is not an error, so
`instruction-render.py` exits 0 and `synthesis-conductor.md`'s Step 3b treats
exit 0 as plain success; its Step 4 report lists the doc count, the coverage
audit, drift warnings and withheld *deletes*. The owner's loop depends on the
missing step — see it in the shell, go back to the instructions document,
change the decision, re-run `/inbox --pass2 --force` — so T4.5 re-applies
spec 036's relay for attachments.

Nothing new is invented here. `sync_notice_relay_file` (the generalised
`sync_withheld_deletes_file`) already carries pre-sanitised notice lines
through the per-entry overwrite of `--output-dir`, keyed on a `.run_id`
sidecar, and already removes both files when a new run has nothing to say.
`_render_skipped_asset_notice` (`lib/render_md.py`) is called a second time to
build the relay, exactly as `_render_withdrawn_delete_notice` is — which is
what makes "one source, two surfaces" true rather than claimed.

RED before T4.5's implementation: `_render_skipped_asset_notice` does not
exist (the bullet is built inline), `sync_notice_relay_file` does not exist
(the writer is still `sync_withheld_deletes_file`), and no run writes
`tomo-tmp/withheld-attachments.md` at all.

Whole lines, never containment — see
`tests/test_038_t4_5_asset_notice_extraction.py`'s docstring for why two
containment assertions were removed from this spec as unsound. The expected
text is never restated here either: the comparison that matters is the
document's bullets against the relay's lines, and a test restating both
passes when both have drifted the same way.

What this file deliberately does NOT test: Step 4's report itself.
`synthesis-conductor.md` is an LLM-loaded runtime prompt, and the report is
produced by a model at runtime — there is no output for pytest to capture,
and asserting the instruction prose exists in the file only asserts that a
string is in the file someone just wrote it into. The executable check is
Phase 5's live run. What IS built here is a wiring guard on the relay PATH
(`TestAgentWiringGuard`), which catches two failure modes that are otherwise
silent in a live run: the instruction deleted while the writer stays, and
either side drifting to a different filename.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

_ir_spec = importlib.util.spec_from_file_location(
    "instruction_render_t4_5_relay", SCRIPTS_DIR / "instruction-render.py"
)
_ir = importlib.util.module_from_spec(_ir_spec)
assert _ir_spec.loader is not None
sys.modules["instruction_render_t4_5_relay"] = _ir
_ir_spec.loader.exec_module(_ir)

# The four-kinds fixture lives with the byte-identity pin, so both surfaces
# are exercised over exactly the same `skipped_assets` entries.
from test_038_t4_5_asset_notice_extraction import (  # noqa: E402
    build_four_kinds_skipped_assets,
)

RUN_A = "2026-10-03T10-00-00Z-aaaaaa"
RUN_B = "2026-10-03T11-30-00Z-bbbbbb"

RELAY_NAME = "withheld-attachments.md"
SIDECAR_NAME = "withheld-attachments.run_id"


def _client() -> MagicMock:
    client = MagicMock()
    client.note_exists.return_value = True
    return client


def _stub_pipeline(
    monkeypatch, base_dir: Path, skipped_assets: list[dict], run_id: str | None
) -> Path:
    """Stub the I/O boundary (`build_actions` + Kado reads) and run every
    guard and both renderers for real, mirroring
    `tests/test_instruction_render_withheld_deletes_relay.py`'s harness —
    kept self-contained there and here rather than imported, so neither
    file's dependency on the other is a hidden coupling.

    `--output-dir` is always `base_dir / "out"`, so the run-level relay lands
    at `base_dir / "withheld-attachments.md"`: one directory above, matching
    the real `tomo-tmp/rendered` -> `tomo-tmp/withheld-attachments.md`.

    `build_actions` returns no actions and the given `skipped_assets`, which
    is the real production shape for a run whose every attachment was
    withheld — `suppress_moves_for_unfiled_attachments` takes `skipped_assets`
    read-only, so nothing downstream extends it.
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    suggestions_file = base_dir / "suggestions.json"
    suggestions_file.write_text(
        json.dumps({
            "confirmed_items": [{"id": "C0"}],
            "daily_updates": [],
            "skipped": [],
        }),
        encoding="utf-8",
    )
    cfg_file = base_dir / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        _ir, "load_config",
        lambda _path: {
            "concepts.inbox": "100 Inbox",
            "profile": "miyo",
            "callouts.editable": ["NOTE", "IDEAS"],
        },
    )
    monkeypatch.setattr(_ir, "KadoClient", lambda: _client())
    monkeypatch.setattr(
        _ir, "build_actions", lambda *_a, **_kw: ([], skipped_assets)
    )
    monkeypatch.setattr(_ir, "resolve_target_moc_paths", lambda _actions, _client: 0)
    monkeypatch.setattr(_ir, "resolve_section_names", lambda *_a, **_kw: 0)
    monkeypatch.setattr(_ir, "_validate_action_paths", lambda _actions: [])
    monkeypatch.setattr(_ir, "backfill_supporting_items_parents", lambda _items: None)

    out_dir = base_dir / "out"
    argv = [
        "instruction-render.py",
        "--suggestions", str(suggestions_file),
        "--output-dir", str(out_dir),
        "--config", str(cfg_file),
    ]
    if run_id is not None:
        argv += ["--run-id", run_id]
    monkeypatch.setattr(sys, "argv", argv)
    return out_dir


def _document_bullets(out_dir: Path) -> list[str]:
    """The withheld-attachment block's lines as the owner reads them, from the
    instruction document this run actually wrote.

    Located STRUCTURALLY — the block's heading, then its blank line, then
    every line up to the next blank — and deliberately not by matching the
    bullet's own `- ⚠️ **Attachment not filed:**` prefix. A prefix filter is
    something `_render_skipped_asset_notice` itself produces, so it makes this
    helper return `[]` whenever that function is broken, and the comparison
    below then fails for a run in which the two surfaces actually AGREED
    (both emitting the broken sentence). Measured 2026-10-03: a source
    mutation of the notice function failed
    `test_relay_lines_are_the_documents_own_bullets` for exactly that reason,
    which reads as evidence of divergence when it is nothing of the kind. Keyed
    on the heading, this helper only ever fails on real divergence.
    """
    doc = out_dir / "instructions.md"
    assert doc.exists(), sorted(out_dir.iterdir())
    lines = doc.read_text(encoding="utf-8").splitlines()
    heading = next(
        (i for i, ln in enumerate(lines)
         if ln.startswith("**Attachments still in the inbox**")),
        None,
    )
    if heading is None:
        return []
    start = heading + 1
    while start < len(lines) and lines[start] == "":
        start += 1
    end = start
    while end < len(lines) and lines[end] != "":
        end += 1
    return lines[start:end]


# ── 1. Every withheld attachment reaches the run-level relay file ──────────


class TestWithheldAttachmentsReachTheRelayFile:
    def test_all_four_kinds_are_relayed_as_whole_lines(self, monkeypatch, tmp_path):
        """One line per withheld attachment, never a count `[ref: PRD/C1]`.

        Mutation that fires: drop the relay call added beside the
        withheld-delete relay in `instruction-render.py`'s `main` — the file
        never appears and `relay_path.exists()` fails. Narrowing the call's
        list comprehension to one `kind` fails the length assertion.
        """
        skipped = build_four_kinds_skipped_assets()
        out_dir = _stub_pipeline(monkeypatch, tmp_path, skipped, RUN_A)
        assert _ir.main() == 0

        relay_path = out_dir.parent / RELAY_NAME
        assert relay_path.exists()
        lines = relay_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 4
        # Each line names its own attachment, and the four are distinct.
        assert [ln.split("`")[1] for ln in lines] == [
            "100 Inbox/Scans/",
            "100 Inbox/Scans/karte.png",
            "100 Inbox/Scans/B/foto.jpg",
            "100 Inbox/Scans/bild.png",
        ]
        # Relay-file contract (spec 036): notice lines and nothing else — no
        # run id, no header, no internals. Step 4 `cat`s this verbatim.
        assert all(ln.startswith("- ⚠️ **Attachment not filed:** `") for ln in lines)
        assert RUN_A not in relay_path.read_text(encoding="utf-8")

        sidecar = out_dir.parent / SIDECAR_NAME
        assert sidecar.exists()
        assert sidecar.read_text(encoding="utf-8").strip() == RUN_A

    def test_relay_lines_are_the_documents_own_bullets(self, monkeypatch, tmp_path):
        """The two surfaces, compared against each other rather than against
        restated text: a test that restates the expected sentence twice passes
        when both surfaces have drifted the same way.

        Mutation that fires: have the relay call build its own f-string
        instead of calling `_render_skipped_asset_notice` — any difference at
        all, down to one character of punctuation, breaks this equality. See
        `TestSharedCodePathUnderMutation` for the proof that both surfaces die
        together under one mutation of that function.
        """
        skipped = build_four_kinds_skipped_assets()
        out_dir = _stub_pipeline(monkeypatch, tmp_path, skipped, RUN_A)
        assert _ir.main() == 0

        relay_lines = (out_dir.parent / RELAY_NAME).read_text(
            encoding="utf-8"
        ).splitlines()
        assert relay_lines == _document_bullets(out_dir)


# ── 2. Nothing withheld: the previous run's file is REMOVED ────────────────


class TestNothingWithheldRemovesAPreviousRunsFile:
    def _write_stale_run(self, base_dir: Path) -> tuple[Path, Path]:
        base_dir.mkdir(parents=True, exist_ok=True)
        relay = base_dir / RELAY_NAME
        sidecar = base_dir / SIDECAR_NAME
        relay.write_text(
            "- ⚠️ **Attachment not filed:** `100 Inbox/Scans/stale.png` — "
            "left behind by an earlier run.\n",
            encoding="utf-8",
        )
        sidecar.write_text(RUN_A + "\n", encoding="utf-8")
        return relay, sidecar

    def test_a_new_run_with_nothing_withheld_removes_both_files(
        self, monkeypatch, tmp_path
    ):
        """Step 4 keys on the file's EXISTENCE, so a run with nothing to say
        must leave no file — and the contract is removal, not absence. A
        fresh directory where nothing ever existed proves nothing.

        Mutation that fires: pass the relay call an empty list only when
        `skipped_assets` is truthy (i.e. guard the call with `if
        skipped_assets:`) — the writer is then never reached on a clean run,
        RUN_A's file survives, and Step 4 relays a previous run's withheld
        attachment into this run's report.
        """
        relay, sidecar = self._write_stale_run(tmp_path)
        assert relay.exists() and sidecar.exists()

        _stub_pipeline(monkeypatch, tmp_path, [], RUN_B)
        assert _ir.main() == 0

        assert not relay.exists()
        assert not sidecar.exists()

    def test_a_new_run_replaces_a_previous_runs_notices(self, monkeypatch, tmp_path):
        """Staleness's other half: a new run that DOES withhold something
        rewrites both files rather than appending to the old run's.

        Mutation that fires: write the relay file with mode `"a"`
        unconditionally — the stale line below survives and the length
        assertion fails.
        """
        self._write_stale_run(tmp_path)

        skipped = build_four_kinds_skipped_assets()
        out_dir = _stub_pipeline(monkeypatch, tmp_path, skipped, RUN_B)
        assert _ir.main() == 0

        lines = (out_dir.parent / RELAY_NAME).read_text(
            encoding="utf-8"
        ).splitlines()
        assert len(lines) == 4
        assert lines == _document_bullets(out_dir)
        assert (out_dir.parent / SIDECAR_NAME).read_text(
            encoding="utf-8"
        ).strip() == RUN_B


# ── 3. The two surfaces share ONE code path, proven by mutation ────────────


class TestSharedCodePathUnderMutation:
    """The gate's requirement (ii), as an executable test rather than a
    one-off experiment.

    A test comparing the document's bullet to the relay's line passes even
    when the relay builds the same string independently, so on its own it
    cannot catch a later maintainer re-deriving the sentence. Mutating
    `_render_skipped_asset_notice` and asserting that BOTH surfaces change is
    what proves they share one code path: if only one moved, the relay is not
    calling the function and T4.5's design is absent while its tests are
    green.

    **DO NOT DELETE THIS TEST AS REDUNDANT.** What it uniquely catches is a
    relay that re-derives its line by COPY-PASTING the notice function's body,
    so both surfaces emit **byte-identical** strings today and drift only when
    one copy is later edited. Every test that compares the two surfaces is
    blind to that, because the two surfaces genuinely agree — measured, and
    the copy-paste variant kills only this test (`1 failed, 7 passed`). A
    duplicate that differs by one character is the easy case and the
    comparison tests do catch it, which is why this test looks redundant until
    the realistic regression is the one you run. Comparing two surfaces proves
    they agree; only mutating their shared source proves they cannot disagree.

    The mutation goes through each call site's own `__globals__`. See
    `docs/tomo/scripts/instruction-render.md`, "Why the Mutation Patches
    `__globals__`", for the Python semantics that make a module-attribute
    patch able to miss a surface silently.
    """

    def test_mutating_the_notice_function_moves_both_surfaces(
        self, monkeypatch, tmp_path
    ):
        """Mutation that fires: `_render_skipped_asset_notice` patched to emit
        a fixed broken line. BOTH surfaces must become that line. If either
        one survives the mutation, that surface is building the sentence
        itself, and T4.5's design is absent while its other tests are green.

        The mutation is applied to the GLOBALS OF THE TWO FUNCTIONS THAT
        CONTAIN THE CALL SITES, never to a module reached by `import`. **Two
        patches because there are two bindings of one function** — do not
        delete either as belt-and-braces: the document's call lives inside
        `render_instructions_md`, whose `__globals__` is the defining module's
        dict, and the relay's call lives inside `main`, whose `__globals__` is
        `instruction-render.py`'s own dict, because that script does
        `from lib.render_md import _render_skipped_asset_notice`.

        A patch on each call site's own globals cannot miss, because that dict
        IS the namespace the call resolves through; a
        `monkeypatch.setattr(lib.render_md, …)` can — see
        `docs/tomo/scripts/instruction-render.md`, "Why the Mutation Patches
        `__globals__`", for why, and for the measurement.

        Patching both does not weaken the claim. A relay that built its own
        f-string would emit real sentences under this patch and fail the
        second assertion; a document block that built its own would fail the
        first.
        """
        broken = "- MUTATED NOTICE"
        monkeypatch.setitem(
            _ir.render_instructions_md.__globals__,
            "_render_skipped_asset_notice", lambda _entry: broken,
        )
        monkeypatch.setitem(
            _ir.main.__globals__,
            "_render_skipped_asset_notice", lambda _entry: broken,
        )
        # Reported on failure: which module each call site resolves through,
        # and every live copy of render_md.py. With the patches above these
        # cannot cause a miss; the names are here so a future failure says
        # where it rendered from instead of leaving it to be inferred.
        diag = (
            f"document call site globals __name__="
            f"{_ir.render_instructions_md.__globals__.get('__name__')!r}; "
            f"relay call site globals __name__="
            f"{_ir.main.__globals__.get('__name__')!r}; "
            f"live render_md copies="
            + repr(sorted(
                k for k, m in list(sys.modules.items())
                if getattr(m, "__file__", None)
                and str(getattr(m, "__file__", "")).endswith("render_md.py")
            ))
        )

        skipped = build_four_kinds_skipped_assets()
        out_dir = _stub_pipeline(monkeypatch, tmp_path, skipped, RUN_A)
        assert _ir.main() == 0

        relay_lines = (out_dir.parent / RELAY_NAME).read_text(
            encoding="utf-8"
        ).splitlines()
        # Both surfaces moved to the mutated string — neither built its own.
        assert _document_bullets(out_dir) == [broken] * 4, diag
        assert relay_lines == [broken] * 4, diag


# ── 4. Wiring guard: the runtime prompt names the path the writer writes ───


class TestAgentWiringGuard:
    def test_conductor_cats_the_path_the_writer_writes(self):
        """One assertion, one direction: the runtime file references the same
        relay path `instruction-render.py` writes. Not the prose — pytest
        cannot verify what a model does with a prompt (the executable check is
        Phase 5's live run), but it can stop the instruction being deleted
        while the writer stays, or either side drifting to a different
        filename. Both are silent in a live run: a missing `cat` just reports
        nothing withheld.

        Mutation that fires: rename `WITHHELD_ATTACHMENTS_RELAY` in
        `instruction-render.py` without touching `synthesis-conductor.md`.
        """
        agent = (
            REPO_ROOT / "tomo" / "dot_claude" / "agents" / "synthesis-conductor.md"
        ).read_text(encoding="utf-8")
        assert f"tomo-tmp/{_ir.WITHHELD_ATTACHMENTS_RELAY}" in agent
