#!/usr/bin/env python3
# version: 0.1.0
"""test_035_schema_identity.py — the two instruction schemas stop sharing an $id (spec 035 T3.2).

Both `tomo/schemas/instructions.schema.json` (Tomo's producer copy) and
`tomo/schemas/hashi-instructions.schema.json` (the contract — a verbatim
mirror of Hashi's live wire schema) declared the SAME `$id`
(`https://miyo.tomo/schemas/instructions.schema.json`) with identical title
and description, despite differing structurally (the contract carries a
`replace_section` $def the producer copy lacks). That collision is the
mechanical cause of a consumer diffing the wrong file and reporting drift
that did not exist.

ADR-6: the producer copy takes a distinct `$id`; the contract keeps the
canonical one, because the contract is the document a consumer vendors.

Scope note (owner-approved, see plan/README.md deviation row): only the
producer copy is annotated with a role-stating title/description. The
contract is left byte-identical — annotating a verbatim mirror would stop
it being verbatim, and any such annotation is destroyed by the next
re-vendor (T4.2/T4.4 in this same spec), which is worse than no annotation
at all.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
PRODUCER_PATH = SCHEMAS_DIR / "instructions.schema.json"
CONTRACT_PATH = SCHEMAS_DIR / "hashi-instructions.schema.json"

CANONICAL_ID = "https://miyo.tomo/schemas/instructions.schema.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_producer_id_differs_from_canonical():
    """The producer copy's $id must no longer equal the canonical contract URL.

    Fails today: both schemas declare the identical $id, so a consumer that
    resolves by $id (or a human comparing the two) cannot tell them apart.
    """
    producer = _load(PRODUCER_PATH)
    assert producer["$id"] != CANONICAL_ID, (
        f"{PRODUCER_PATH} still declares the canonical $id ({CANONICAL_ID}); "
        "ADR-6 requires the producer copy to take a distinct identity."
    )


def test_producer_identifies_its_role():
    """The producer copy's title or description must state it is Tomo's producer copy.

    The contract (hashi-instructions.schema.json) must NOT claim to be the
    producer — it stays byte-identical to Hashi's vendored file (a verbatim
    mirror), so this test does not require it to self-identify at all.
    """
    producer = _load(PRODUCER_PATH)
    role_text = (producer.get("title", "") + " " + producer.get("description", "")).lower()
    assert "producer" in role_text, (
        f"{PRODUCER_PATH}'s title/description does not state its role as "
        "Tomo's producer copy."
    )

    contract = _load(CONTRACT_PATH)
    contract_role_text = (contract.get("title", "") + " " + contract.get("description", "")).lower()
    assert "producer" not in contract_role_text, (
        f"{CONTRACT_PATH} must stay a byte-identical mirror of Hashi's wire "
        "schema — it must not claim to be the producer copy."
    )


def test_contract_id_unchanged_at_canonical_url():
    """GUARD (green today, must stay green): the contract keeps the canonical $id.

    Asserted against the hardcoded literal, not against "whatever the
    producer copy isn't" — moving the WRONG file would satisfy the two tests
    above while breaking the real consumer, and nothing else in the suite
    would notice. Hashi's own file declares this URL; if our mirror moves,
    it stops matching theirs and the upstream drift report starts flagging
    a disagreement we manufactured ourselves.
    """
    contract = _load(CONTRACT_PATH)
    assert contract["$id"] == CANONICAL_ID, (
        f"{CONTRACT_PATH}'s $id must remain the canonical literal {CANONICAL_ID} "
        "— it is the document Hashi's own schema declares and the one a "
        "consumer vendors."
    )


def test_no_ref_resolves_the_canonical_url_to_the_producer_copy():
    """GUARD (true today, tripwire for the future): nothing $ref's/resolves the old URL to the producer copy.

    This is deliberately narrower than "the URL appears near the producer
    file's path" — the producer file's own `$id` line legitimately carries
    this URL today (that collision is exactly what test 1 above fails on
    and this task fixes), so a naive "no hit touching the producer path"
    check would be RED before the fix and is not what this guard is for.

    What this guard actually checks, and what must be — and already is —
    true regardless of whether the collision is fixed: no `$ref`, no
    `RefResolver`/`Registry`-style code, and no schema-loading call site
    anywhere in the repo binds this URL to the producer file. Every
    consumer (tomo/scripts/lib/wire_shape.py, instruction-render.py,
    validate-result.py, the parity test) resolves the producer schema by
    its filename path, never by `$id`.
    """
    result = subprocess.run(
        ["git", "grep", "-n", "-F", CANONICAL_ID],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in (0, 1), (
        f"git grep failed unexpectedly: {result.stderr}"
    )
    hits = [line for line in result.stdout.splitlines() if line.strip()]

    own_id_declarations = {
        f'{SCHEMAS_DIR.joinpath("instructions.schema.json").relative_to(REPO_ROOT)}:3:  "$id": "{CANONICAL_ID}",',
        f'{SCHEMAS_DIR.joinpath("hashi-instructions.schema.json").relative_to(REPO_ROOT)}:3:  "$id": "{CANONICAL_ID}",',
    }
    # Anything left over, once each schema's own (single) $id line is
    # excluded, that IS a $ref or a .py call site is a binding: a
    # $ref, a resolver registry entry, or a schema-loading call site.
    suspicious = [
        line
        for line in hits
        if line not in own_id_declarations
        and ("$ref" in line.lower().replace(" ", "") or line.split(":", 1)[0].endswith(".py"))
    ]
    assert not suspicious, (
        "Found a $ref or a .py call site binding the canonical URL to a "
        f"file — this must never resolve the producer copy: {suspicious}"
    )
