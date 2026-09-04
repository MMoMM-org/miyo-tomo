#!/usr/bin/env python3
# version: 0.1.0
"""test_garden_audit_broken_up_no_vault_access.py — spec 033 T5.3 (CON-1).

garden-audit.py's data-source split (ADR-5) puts broken_up/parent_not_moc on
the cache-only side: `_check_broken_up` must never trigger a Kado call. Spec
033 did NOT add a second check function for `parent_not_moc` — one function,
`_check_broken_up`, emits BOTH check names (routed by up_broken_reason), so
proving the property for that one function covers both outputs.

Structural, not behavioural: a runtime call-count assertion passes for the
wrong reason whenever the test's own cache happens to be warm (no calls
needed regardless of whether the function COULD call out). The guarantee
that matters is that the function's own interface makes an outbound call
impossible to wire up in the first place — checked two ways:

  1. Signature: no parameter shaped like a vault-callable
     (`graph_audit_fn`, `list_dir_fn`) is even accepted.
  2. Source text: the function body never references a vault/network
     identifier via a closure or an inline import — a gap the signature
     check alone cannot see (a global `client` or a `from lib.kado_client
     import ...` inside the function body would smuggle vault access in
     without adding a parameter at all).

Extended to the sibling cache-only checks (`_check_unparented`,
`_check_duplicate_stem`) for consistency — same property, same proof.
`_check_orphan`/`_check_dead_link` are deliberately NOT included: they take
an already-resolved `graph_result` dict, not a callable, by design (ADR-5) —
a different shape, not this property. `_check_stale_moc` is the one check
that legitimately accepts `list_dir_fn` and is asserted as the contrast case.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import sys
import textwrap
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load_garden_audit():
    path = SCRIPTS_DIR / "garden-audit.py"
    spec = importlib.util.spec_from_file_location("garden_audit_con1", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


garden_audit = _load_garden_audit()

# Identifiers that would signal vault/network access if they appeared as a
# parameter name or anywhere in a cache-only check's source body.
_VAULT_CALLABLE_MARKERS = ("graph_audit", "list_dir", "kado_client", "KadoClient")


def _param_names(fn) -> set[str]:
    return set(inspect.signature(fn).parameters)


def _body_identifiers(fn) -> set[str]:
    """Every Name/Attribute/import identifier referenced in `fn`'s BODY —
    via the AST, not a text search, so a docstring or comment that merely
    MENTIONS a vault-callable name (as `_check_broken_up`'s own docstring
    does: "cache-only, NEVER triggers graph_audit") can never register as a
    hit. The signature (parameters) is excluded here too — that's
    `_param_names`'s job — by dropping the leading docstring statement and
    walking only what remains of the function body.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef)
    body = func.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]  # drop the docstring — prose, not code
    names: set[str] = set()
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name)
            if node.asname:
                names.add(node.asname)
    return names


def _source_forbidden_hits(fn) -> list[str]:
    identifiers = _body_identifiers(fn)
    return sorted(
        ident for ident in identifiers
        if any(marker in ident for marker in _VAULT_CALLABLE_MARKERS)
    )


class TestCheckBrokenUpStructurallyCacheOnly:
    """CON-1: `_check_broken_up` — the single function that emits both
    `broken_up` and `parent_not_moc` (spec 033 ADR-1 routing) — accepts no
    vault-callable parameter and never references one in its body."""

    def test_signature_has_no_vault_callable_parameter(self):
        params = _param_names(garden_audit._check_broken_up)
        assert params == {"entries", "exclusions", "counter"}, (
            f"_check_broken_up's signature grew a parameter beyond the "
            f"cache-only set: {params}"
        )
        for marker in ("graph_audit_fn", "list_dir_fn"):
            assert marker not in params

    def test_source_never_references_a_vault_callable_identifier(self):
        # Catches what the signature check cannot: a module-level client or
        # an inline `from lib.kado_client import ...` inside the function
        # body would grant vault access without ever adding a parameter.
        hits = _source_forbidden_hits(garden_audit._check_broken_up)
        assert hits == [], (
            f"_check_broken_up's body references vault-callable identifiers "
            f"it was never passed: {hits}"
        )


class TestSiblingCacheOnlyChecksForConsistency:
    """Same property, same proof, for the other two checks ADR-5 places on
    the cache-only side — not because CON-1 names them, but because a
    signature/source guard that only ever looks at `_check_broken_up` would
    itself be a hollow proxy for "cache-only checks stay cache-only"."""

    def test_check_unparented_has_no_vault_callable_parameter(self):
        params = _param_names(garden_audit._check_unparented)
        assert params == {"entries", "exclusions", "counter"}

    def test_check_duplicate_stem_has_no_vault_callable_parameter(self):
        params = _param_names(garden_audit._check_duplicate_stem)
        assert params == {"entries", "exclusions", "counter"}


class TestStaleMocIsTheLegitimateContrastCase:
    """`_check_stale_moc` is the one check ADR-5 puts on the listDir side —
    asserting it DOES take `list_dir_fn` proves the guard above is actually
    discriminating (cache-only vs. not), not just describing every check the
    same way regardless of its real data source."""

    def test_check_stale_moc_does_take_list_dir_fn(self):
        params = _param_names(garden_audit._check_stale_moc)
        assert "list_dir_fn" in params
