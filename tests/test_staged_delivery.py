#!/usr/bin/env python3
# version: 0.1.0
"""test_staged_delivery.py — the staged deliver loop shared by /note and /review
(spec 045 T1.3, ADR-11; the rules come from spec 044 ADR-2).

The loop takes its steps, its step → vault-path map, the meta object and the
callable that persists it from the caller. Each test drives it on
tests/note_fake_vault.NoteFakeVault with a plain dataclass as meta (not
NoteDraftMeta), so the lib is proven to depend on nothing /note-specific.
Never a live vault.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

import note_fake_vault as nfv  # noqa: E402
from lib import note_meta  # noqa: E402
from lib import staged_delivery as sd  # noqa: E402
from lib.kado_client import KadoError  # noqa: E402

STEPS = ("summary", "set_json", "set_md", "stamp")
TARGETS = {"summary": "Reviews/2026-W13.md", "set_json": "Reviews/2026-W13_instructions.json",
           "set_md": "Reviews/2026-W13_instructions.md"}
PAYLOADS = {"summary": "# Week 13\n\nbody\n", "set_json": '{"a": 1}\n', "set_md": "# Set\n"}
MARKER = "zzpriv_step_7f3a"


@dataclass
class Meta:
    """The two fields the loop records, plus the two stable_block reads."""
    run_id: str = "run-1"
    generated: str = "2026-03-30T10:00:00Z"
    steps_done: list[str] = field(default_factory=list)
    failed_step: str = ""


class Saves:
    """A persist callable that snapshots meta and the vault's write count at each call."""

    def __init__(self, meta: Meta, vault):
        self.meta, self.vault, self.calls = meta, vault, []

    def __call__(self) -> None:
        writes = [e for e in self.vault.events if e[0] in ("write_note", "write_file")]
        self.calls.append((list(self.meta.steps_done), self.meta.failed_step, len(writes)))


def _delivery(vault, meta, steps=STEPS, targets=TARGETS):
    saves = Saves(meta, vault)
    return sd.StagedDelivery(vault, steps, targets, meta, saves, script="t"), saves


def _writes(vault):
    return [e for e in vault.events if e[0] in ("write_note", "write_file")]


# ── ordered caller-supplied steps ─────────────────────────────────────────


def test_steps_run_in_the_callers_order_with_the_callers_targets():
    vault = nfv.NoteFakeVault({})
    meta = Meta()
    delivery, saves = _delivery(vault, meta)
    for step in STEPS[:3]:
        delivery.deliver_step(step, PAYLOADS[step])
    assert _writes(vault) == [("write_note", TARGETS["summary"]),
                              ("write_file", TARGETS["set_json"]),
                              ("write_note", TARGETS["set_md"])]
    assert vault.text(TARGETS["set_json"]) == PAYLOADS["set_json"]
    assert meta.steps_done == list(STEPS[:3]) and meta.failed_step == ""
    # Each uploaded step persists twice: in flight, then done.
    assert [s[0] for s in saves.calls] == [[], ["summary"], ["summary"],
                                           ["summary", "set_json"], ["summary", "set_json"],
                                           ["summary", "set_json", "set_md"]]


def test_a_step_without_a_target_is_served_by_record_and_fail():
    """The caller performs the step itself (a frontmatter merge) and records it."""
    vault = nfv.NoteFakeVault({})
    meta = Meta()
    delivery, saves = _delivery(vault, meta)
    delivery.record("stamp")
    assert meta.steps_done == ["stamp"] and saves.calls == [(["stamp"], "", 0)]
    stop = delivery.fail("stamp", KadoError("503"))
    assert isinstance(stop, sd.DeliveryStop)
    assert (stop.status, stop.step, stop.code, stop.exists_path) == ("failed", "stamp", 1, "")
    assert meta.failed_step == "stamp" and saves.calls[-1] == (["stamp"], "stamp", 0)


def test_fail_names_the_step_and_the_error_class_on_stderr(capsys):
    delivery, _ = _delivery(nfv.NoteFakeVault({}), Meta())
    delivery.fail("set_md", KadoError("503 after retries " + MARKER))
    err = capsys.readouterr().err
    assert err == "t: delivery failed at set_md (KadoError)\n"
    assert MARKER not in err


# ── identical text counts as done ─────────────────────────────────────────


@pytest.mark.parametrize("step, landed, payload", [
    ("summary", PAYLOADS["summary"], PAYLOADS["summary"]),
    ("summary", PAYLOADS["summary"].rstrip("\n"), PAYLOADS["summary"]),
    ("set_json", PAYLOADS["set_json"].rstrip("\n"), PAYLOADS["set_json"]),
    ("set_md", PAYLOADS["set_md"], PAYLOADS["set_md"].rstrip("\n")),
])
def test_a_landed_target_with_identical_text_counts_as_done_without_a_write(step, landed,
                                                                             payload):
    vault = nfv.NoteFakeVault({TARGETS[step]: landed})
    meta = Meta()
    delivery, saves = _delivery(vault, meta)
    delivery.deliver_step(step, payload)
    assert _writes(vault) == []
    assert meta.steps_done == [step] and meta.failed_step == ""
    assert saves.calls == [([step], "", 0)]


def test_two_missing_newlines_are_not_one_missing_newline():
    """Only one trailing newline is normalised, as Kado stores the text."""
    vault = nfv.NoteFakeVault({TARGETS["summary"]: PAYLOADS["summary"] + "\n\n"})
    meta = Meta()
    delivery, _ = _delivery(vault, meta)
    with pytest.raises(sd.DeliveryStop):
        delivery.deliver_step("summary", PAYLOADS["summary"])


# ── different text stops with EXISTS ──────────────────────────────────────


@pytest.mark.parametrize("step", STEPS[:3])
def test_a_landed_target_with_other_text_stops_as_exists_and_writes_nothing(step):
    vault = nfv.NoteFakeVault({TARGETS[step]: "someone else's " + MARKER})
    meta = Meta(steps_done=["summary"] if step != "summary" else [])
    before = (list(meta.steps_done), meta.failed_step)
    delivery, saves = _delivery(vault, meta)
    with pytest.raises(sd.DeliveryStop) as stop:
        delivery.deliver_step(step, PAYLOADS[step])
    assert (stop.value.status, stop.value.step, stop.value.code) == ("exists", step, 3)
    assert stop.value.exists_path == TARGETS[step]
    assert _writes(vault) == []
    assert (meta.steps_done, meta.failed_step) == before and saves.calls == []


def test_a_done_step_whose_target_was_edited_is_still_reported_as_taken():
    """The comparison runs for steps in steps_done too: an edit is never shipped over."""
    vault = nfv.NoteFakeVault({TARGETS["summary"]: "edited in Obsidian\n"})
    meta = Meta(steps_done=["summary"])
    delivery, _ = _delivery(vault, meta)
    with pytest.raises(sd.DeliveryStop) as stop:
        delivery.deliver_step("summary", PAYLOADS["summary"])
    assert stop.value.status == "exists" and _writes(vault) == []


# ── a done step with an absent target is never rewritten ──────────────────


@pytest.mark.parametrize("step", STEPS[:3])
def test_a_done_step_whose_target_is_absent_is_never_written_again(step):
    vault = nfv.NoteFakeVault({})
    meta = Meta(steps_done=[step])
    delivery, saves = _delivery(vault, meta)
    delivery.deliver_step(step, PAYLOADS[step])
    assert _writes(vault) == []
    assert TARGETS[step] not in vault.files
    assert meta.steps_done == [step] and meta.failed_step == ""
    assert saves.calls == [([step], "", 0)]


# ── failed_step is recorded before the upload ─────────────────────────────


@pytest.mark.parametrize("step", STEPS[:3])
def test_the_step_is_persisted_as_in_flight_before_its_upload(step):
    vault = nfv.NoteFakeVault({})
    meta = Meta()
    delivery, saves = _delivery(vault, meta)
    delivery.deliver_step(step, PAYLOADS[step])
    # First persist: failed_step names the step, nothing written yet. Second: done.
    assert saves.calls == [([], step, 0), ([step], "", 1)]


@pytest.mark.parametrize("step", STEPS[:3])
def test_a_failed_upload_keeps_the_in_flight_mark_and_stops_as_failed(step):
    vault = nfv.NoteFakeVault({})
    method = "write_note" if TARGETS[step].endswith(".md") else "write_file"
    vault.fail[(method, TARGETS[step])] = KadoError("503 after retries")
    meta = Meta()
    delivery, saves = _delivery(vault, meta)
    with pytest.raises(sd.DeliveryStop) as stop:
        delivery.deliver_step(step, PAYLOADS[step])
    assert (stop.value.status, stop.value.step, stop.value.code) == ("failed", step, 1)
    assert isinstance(stop.value.__cause__, KadoError)
    assert meta.steps_done == [] and meta.failed_step == step
    assert saves.calls == [([], step, 0), ([], step, 1)]


def test_a_failed_probe_is_recorded_as_failed_without_an_upload():
    vault = nfv.NoteFakeVault({})
    vault.fail[("read_frontmatter", TARGETS["summary"])] = KadoError("503")
    meta = Meta()
    delivery, saves = _delivery(vault, meta)
    with pytest.raises(sd.DeliveryStop) as stop:
        delivery.deliver_step("summary", PAYLOADS["summary"])
    assert stop.value.status == "failed" and _writes(vault) == []
    assert saves.calls == [([], "summary", 0)]


def test_a_persist_failure_before_the_upload_propagates_and_uploads_nothing():
    vault = nfv.NoteFakeVault({})
    meta = Meta()

    def save():
        raise OSError("disk full")

    delivery = sd.StagedDelivery(vault, STEPS, TARGETS, meta, save, script="t")
    with pytest.raises(OSError):
        delivery.deliver_step("summary", PAYLOADS["summary"])
    assert _writes(vault) == []


# ── an undeclared step is refused ─────────────────────────────────────────


def test_an_undeclared_step_is_refused_without_echoing_it():
    vault = nfv.NoteFakeVault({})
    meta = Meta()
    delivery, saves = _delivery(vault, meta)
    for call in (lambda: delivery.deliver_step(MARKER, "x\n"),
                 lambda: delivery.record(MARKER),
                 lambda: delivery.fail(MARKER, KadoError("x")),
                 lambda: delivery.mark_in_flight(MARKER)):
        with pytest.raises(ValueError) as exc:
            call()
        assert MARKER not in str(exc.value)
    assert vault.events == [] and saves.calls == []
    assert meta.steps_done == [] and meta.failed_step == ""


def test_a_declared_step_without_a_target_cannot_be_uploaded():
    delivery, _ = _delivery(nfv.NoteFakeVault({}), Meta())
    with pytest.raises(ValueError) as exc:
        delivery.deliver_step("stamp", "x\n")
    assert "stamp" not in str(exc.value)


def test_a_target_for_an_undeclared_step_is_refused_at_construction():
    with pytest.raises(ValueError) as exc:
        sd.StagedDelivery(nfv.NoteFakeVault({}), STEPS, {**TARGETS, MARKER: "x.md"},
                          Meta(), lambda: None)
    assert MARKER not in str(exc.value)


@pytest.mark.parametrize("steps", [("a", "a"), ("a", ""), ("a", 1), ()])
def test_steps_must_be_distinct_non_empty_names(steps):
    with pytest.raises(ValueError):
        sd.StagedDelivery(nfv.NoteFakeVault({}), steps, {}, Meta(), lambda: None)


def test_note_meta_marks_accept_the_callers_step_set():
    """mark_step_done / mark_step_failed take the step set; the default is /note's."""
    meta = Meta()
    note_meta.mark_step_done(meta, "summary", steps=STEPS)
    note_meta.mark_step_failed(meta, "set_json", steps=STEPS)
    assert meta.steps_done == ["summary"] and meta.failed_step == "set_json"
    note_meta.mark_step_failed(meta, note_meta.KADO_CONFIG, steps=STEPS)
    assert meta.failed_step == note_meta.KADO_CONFIG
    with pytest.raises(ValueError):
        note_meta.mark_step_done(meta, "summary")
    with pytest.raises(ValueError):
        note_meta.mark_step_done(meta, note_meta.KADO_CONFIG, steps=STEPS)
    with pytest.raises(ValueError):
        note_meta.mark_step_failed(meta, "note", steps=STEPS)


# ── stable_block pins updated_at ──────────────────────────────────────────


def test_stable_block_pins_updated_at_to_generated_and_carries_the_run_id():
    meta = Meta(run_id="run-9", generated="2026-03-30T10:00:00Z")
    block = sd.stable_block("instructions", "pending-apply", meta)
    assert block["updated_at"] == meta.generated and block["run_id"] == meta.run_id
    assert block["doc_type"] == "instructions" and block["state"] == "pending-apply"
    assert sd.stable_block("instructions", "pending-apply", meta) == block


# ── the lib is the one loop /note runs ────────────────────────────────────


def test_note_instructions_runs_the_shared_loop():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "note_instructions", SCRIPTS_DIR / "note-instructions.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.DeliveryStop is sd.DeliveryStop
    assert mod.StagedDelivery is sd.StagedDelivery
    for private in ("_deliver_step", "_mark_in_flight", "_record", "_fail", "_stable_block",
                    "_same_text", "_upload", "_without_final_newline"):
        assert not hasattr(mod, private), private
