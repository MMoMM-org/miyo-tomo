# WHY: lib/moc_discovery_rendered_links.py

> Rationale for decisions in `tomo/scripts/lib/moc_discovery_rendered_links.py`.
> The module holds the pure halves of link-member augmentation: `plan_link_lookups` (which member paths of the rendered slice are looked up) and `apply_link_results` (writing `link_members` / `link_lookup_status` back).

## Split Out of moc-discovery.py (#216)

WHY this module exists: `moc-discovery.py` had grown to 2560 lines, past the
constitution's ~300-500 LOC guidance for dense logic (#216). It was split along
its phase seams; the moved code is unchanged, and `moc-discovery.py` re-exports
every name so tests and callers that load the script keep working. The
decision rationale for the behaviour itself stays in
`docs/tomo/scripts/moc-discovery.md`.

## The Lookup Session Stays in the Script

WHY: tests inject a budget by patching `LinkLookup` on the loaded script module
(`monkeypatch.setattr(mod, "LinkLookup", partial(LinkLookup, budget=N))`). A
`with LinkLookup(...)` inside this module would resolve its own import and the
patch would no longer apply. So `_augment_rendered_clusters` in the script opens
the session between the two pure halves defined here. The script is loaded under
several module names by different tests, so this module cannot reach back into
"the" script module instead.
