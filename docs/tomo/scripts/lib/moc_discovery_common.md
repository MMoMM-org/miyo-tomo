# WHY: lib/moc_discovery_common.py

> Rationale for decisions in `tomo/scripts/lib/moc_discovery_common.py`.
> The module holds the primitives every discovery module shares: the `[moc-discovery]` log prefix and `_log`, `ABORT_MESSAGES`, `DEFAULT_PROFILES_DIR`, `_load_yaml`, the `Candidate` record, `_stem_from_path` and `_load_moc_config`.

## Split Out of moc-discovery.py (#216)

WHY this module exists: `moc-discovery.py` had grown to 2560 lines, past the
constitution's ~300-500 LOC guidance for dense logic (#216). It was split along
its phase seams; the moved code is unchanged, and `moc-discovery.py` re-exports
every name so tests and callers that load the script keep working. The
decision rationale for the behaviour itself stays in
`docs/tomo/scripts/moc-discovery.md`.

## One Log Helper, One Prefix

WHY: every progress line of the script carries the `[moc-discovery]` prefix and the
moc-architect agent and tests read stderr by it. A single `_log` shared by all
phase modules keeps the prefix byte-identical; a per-module copy would drift.

## Profiles Directory Computed From the Lib Path

WHY: `DEFAULT_PROFILES_DIR` was `SCRIPT_DIR.parent / "profiles"` in the script. From
`scripts/lib/` the same directory is three parents up. Both the source tree
(`tomo/scripts/lib`) and the instance (`<instance>/scripts/lib`) keep `lib/` under
`scripts/`, so the value is unchanged in both layouts.

## `_load_moc_config` Loads shared-ctx-builder by Path

WHY: `MocProposalConfig` lives in the hyphenated `shared-ctx-builder.py`, which
cannot be imported by name. The module is registered in `sys.modules` before
`exec_module` because Python 3.14's dataclass machinery reads the owning module's
`__dict__`. It sits here because the cluster pipeline, `--emit-phase1` and the
uplink audit all need it.
