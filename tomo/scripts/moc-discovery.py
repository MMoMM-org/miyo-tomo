#!/usr/bin/env python3
# version: 0.27.1
"""moc-discovery.py — Discover MOC candidates and emit a DiscoveryReport.

Backs the `/moc-propose` skill (F-43, spec 013-moc-creation-skill). Accepts a
mutually-exclusive scope flag (`--tag`, `--folder`, `--class`, `--title`), an
optional free-text positional, or no args (whole-vault density scan), and walks
through the six discovery phases described in the SDD §Pseudocode (lines
845-895):

    Phase 1   — Candidate selection (mode handlers + pre-filter + caps)
    Phase 2   — Topic extraction (cache lookup + LLM cache-miss batching)
    Phase 3   — Cluster detection (thin wrapper around lib.topic_clusters)
    Phase 4   — Title generation (per-profile suffix rules + mode override)
    Phase 5   — Parent resolution (classification keyword overlap, top-3)
    Phase 6   — Duplicate detection (Jaccard ≥ 0.80) + squelch read-only lookup
    Links     — Link members for the rendered clusters (lib.link_members)
    Phase 6.5 — Existing-up:: validation per candidate (absent/valid/broken)

`--around NAME_OR_PATH` is a separate single-pass mode: resolve the seed in the
cache, look up its neighbours once, emit one new-MOC cluster (seed + link
members) — no Phase 1-3, no Phase 6 / D3, no squelch.

This file orchestrates; the phases live in `lib/moc_discovery_*.py` and every
name is re-exported here. The functions that call `_build_kado_client` or
`LinkLookup` stay in this file so both names resolve on this module.

Usage:
    python3 moc-discovery.py [--tag X | --folder X | --class X | --title X | --around X]
                             [free-text]
                             [--config PATH] [--profile NAME] [--cache PATH]
                             [--dry-run] [--candidate-cap N]

Output:
    Stdout — DiscoveryReport JSON (see SDD §Application Data Models, lines 534-553).
    Stderr — progress logs, prefixed `[moc-discovery]`.

Exit codes (SDD §Error Handling):
    0 success
    1 partial-failure
    2 fatal (cache missing, profile unresolved)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Allow importing from scripts/lib/
sys.path.insert(0, os.path.dirname(__file__))

from lib.link_members import (  # noqa: E402
    DONE as _LINKS_DONE,
    LinkLookup,
    NodeEligibility,
    augment_clusters,
)
from lib.moc_cache_loader import load_moc_cache  # noqa: E402
from lib.profile_conventions import resolve_conventions  # noqa: E402
from lib.squelch import (  # noqa: E402
    decrement_all as _squelch_decrement_all,
    load_registry as _squelch_load_registry,
    save_registry_atomic as _squelch_save_registry_atomic,
)

# Re-exports: tests and callers reach every phase through this module.
from lib.moc_discovery_args import (  # noqa: E402, F401
    DEFAULT_CACHE_PATH,
    DEFAULT_CONFIG_PATH,
    DEFAULT_SQUELCH_STATE_PATH,
    build_parser,
    resolve_profile,
    route_input,
)
from lib.moc_discovery_around import (  # noqa: E402, F401
    AROUND_CLUSTER_ID,
    AROUND_INELIGIBLE_REASONS,
    AROUND_MIN_NEIGHBOURS,
    AroundSeed,
    _around_abort,
    _around_key,
    _ref_stem,
    _up_targets_stem,
    apply_around_extension,
    around_too_few,
    build_around_cluster,
    fill_around_note_report,
    resolve_around_seed,
)
from lib.moc_discovery_common import (  # noqa: E402, F401
    ABORT_MESSAGES,
    DEFAULT_PROFILES_DIR,
    LOG_PREFIX,
    Candidate,
    _load_moc_config,
    _load_yaml,
    _log,
    _stem_from_path,
)
from lib.moc_discovery_dedupe import (  # noqa: E402, F401
    JACCARD_DUP_THRESHOLD,
    _MEMBER_OVERLAP_THRESHOLD,
    _candidate_stems,
    _cluster_topic_set,
    _compute_topic_signature,
    _dedupe_overlapping_clusters,
    _find_exact_title_match,
    _find_jaccard_match,
    _moc_topic_set,
    _normalise_title,
    phase6_dedupe,
)
from lib.moc_discovery_enrich import (  # noqa: E402, F401
    ParentOption,
    _category_keywords,
    _cluster_topic_keywords,
    _enrich_cluster,
    _format_parent_label,
    _format_parent_stem,
    _moc_location,
    _serialise_parents,
    _topic_title,
    phase4_title,
    phase5_resolve_parents,
)
from lib.moc_discovery_existing_up import (  # noqa: E402, F401
    _moc_stems_from_cache,
    _note_stems_from_cache,
    phase65_validate_existing_up,
)
from lib.moc_discovery_phase1 import (  # noqa: E402, F401
    _atomic_note_paths,
    _candidate_from_path,
    _handle_class,
    _handle_folder,
    _handle_scan,
    _handle_tag,
    _handle_title_or_freetext,
    _is_md_file,
    _resolve_class_subdir,
    phase1_select_candidates,
    restrict_to_atomic_note_paths,
    validate_cache_loaded,
)
from lib.moc_scan import read_scope_paths  # noqa: E402
from lib.moc_discovery_phase1_io import (  # noqa: E402, F401
    _BODY_EXCERPT_CHARS,
    _load_phase1_input,
    _write_phase1_emit,
)
from lib.moc_discovery_rendered_links import (  # noqa: E402, F401
    NOT_RENDERED,
    _item_stem,
    _member_up_fields,
    apply_link_results,
    plan_link_lookups,
)
from lib.moc_discovery_report import (  # noqa: E402, F401
    _EMPTY_LINK_STATS,
    _emit_abort_report,
    build_pipeline_report,
    candidate_rows,
    emit_report,
    empty_report,
)
from lib.moc_discovery_topics import (  # noqa: E402, F401
    LLM_BATCH_SIZE,
    LLMClient,
    _batch_llm_extract,
    _build_topics_index,
    phase2_extract_topics,
    phase3_cluster,
)
from lib.moc_discovery_uplinks import _cap_orphans, _run_moc_uplink_check  # noqa: E402, F401


# ──────────────────────────────────────────────────────────────────────────────
# Paths & defaults
# ──────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent


# ──────────────────────────────────────────────────────────────────────────────
# Kado client + link lookups (kept here: tests patch these names on this module)
# ──────────────────────────────────────────────────────────────────────────────


def _build_kado_client():
    """Instantiate KadoClient; fall back to a null stub on KadoError.

    Title/free-text mode is cache-only in Phase 1, so the stub is enough for
    those modes. Scan/tag/folder/class modes will raise KadoError on the first
    Kado call and surface a clear error via the phase1 handler. Phase 6.5 read
    failures are caught per-candidate and treated as state="absent".
    """
    from lib.kado_client import KadoClient as _KC, KadoError as _KE

    class _NullKadoClient:
        """Stand-in when Kado is unreachable. Read errors degrade to state='absent'."""

        def _fail(self) -> None:
            raise _KE("Kado unavailable — client not initialised")

        def search_by_tag(self, *_a, **_k):  # pragma: no cover
            self._fail()

        def list_dir(self, *_a, **_k):  # pragma: no cover
            self._fail()

        def read_note(self, *_a, **_k):  # pragma: no cover
            self._fail()

        # LinkLookup reads and installs these; graph() fails every lookup.
        attempt_count = 0
        attempt_gate = None
        min_interval = 0.0

        def graph(self, *_a, **_k):
            self._fail()

    try:
        return _KC()
    except _KE as exc:
        _log(
            f"WARN: Kado client unavailable ({exc}); "
            f"tag/folder/class/scan modes will fail; "
            f"title/free-text and Phase 6.5 degrade gracefully"
        )
        return _NullKadoClient()


def _augment_rendered_clusters(
    clusters: list[dict],
    candidates: list[Candidate],
    kado_client,
    cache: dict,
    profile_dict: dict,
    vault_cfg: dict,
    max_results: int,
) -> dict[str, int]:
    """Attach `link_members` + `link_lookup_status` to every cluster; return `link_stats`.

    Plans the rendered slice's lookups, runs them in one `LinkLookup` session
    and writes the result back (lib/moc_discovery_rendered_links.py).
    """
    eligibility = NodeEligibility(cache, profile_dict, vault_cfg)
    rendered, lookup_clusters, path_map, path_to_stem = plan_link_lookups(
        clusters, candidates, eligibility, max_results
    )

    with LinkLookup(kado_client) as lookup:
        result = augment_clusters(lookup_clusters, path_map, lookup, eligibility, cache)

    return apply_link_results(clusters, rendered, result, path_to_stem)


def _run_pipeline(
    args,
    cache: dict,
    squelch_registry: dict,
    config_path: Path,
    profile_name: str,
    mode: str,
    trigger_arg: str,
    pre_loaded_candidates: list[Candidate] | None = None,
) -> tuple[dict | None, int]:
    """Execute Phase 1 → Phase 6.5 (+ link members) and return (report_dict, exit_code).

    Called by main() after the pre-flight checks (cache-empty, squelch
    decrement) have passed. Returns (None, exit_code) when an abort-report
    is emitted directly inside this helper (abort_reason paths), so the caller
    skips the json.dump step. For successful or partial-failure runs, the
    assembled DiscoveryReport dict is returned.

    When `pre_loaded_candidates` is provided (T6.5 `--phase1-input` flow), Phase 1
    is skipped — the candidates already carry their topics, populated by the
    moc-architect agent's topic-extract subagent between the two passes.

    Exit codes: 0 = clean, 1 = partial (some dups/squelched), 2 = fatal.
    """
    moc_config = _load_moc_config(config_path)
    if args.candidate_cap is not None:
        import dataclasses as _dc
        moc_config = _dc.replace(moc_config, candidate_cap=args.candidate_cap)

    profile_path = DEFAULT_PROFILES_DIR / f"{profile_name}.yaml"
    profile_dict = _load_yaml(profile_path)
    vault_cfg = _load_yaml(config_path)
    kado_client = _build_kado_client()

    if pre_loaded_candidates is not None:
        candidates = pre_loaded_candidates
        _log(f"phase1: skipped (--phase1-input); {len(candidates)} candidate(s) loaded")
    else:
        # Phase 1 — Candidate selection
        candidates, abort1 = phase1_select_candidates(
            mode, trigger_arg, profile_dict, cache, kado_client, moc_config
        )
        if abort1 is not None:
            _log(f"phase1: abort → {abort1!r}")
            _emit_abort_report(mode, trigger_arg, profile_name, abort1)
            return None, 0
        _log(f"phase1: {len(candidates)} candidate(s) selected")

    candidates_total = len(candidates)

    # Phase 2 — Topic extraction. With --phase1-input, every candidate already
    # has `topics` populated by the agent's topic-extract subagent, so the
    # short-circuit inside phase2_extract_topics treats them all as hits and
    # never invokes llm_client.
    candidates_with_topics, abort2 = phase2_extract_topics(
        candidates, cache, moc_config, llm_client=None
    )
    if abort2 is not None:
        _log(f"phase2: abort → {abort2!r}")
        _emit_abort_report(mode, trigger_arg, profile_name, abort2)
        return None, 0

    _log(f"phase2: {len(candidates_with_topics)} candidate(s) with topics")

    # Phase 3 — Cluster detection
    _conventions = resolve_conventions(
        profile_dict=profile_dict, profiles_dir=DEFAULT_PROFILES_DIR
    )
    _moc_suffix = _conventions.moc_suffix
    raw_clusters = phase3_cluster(candidates_with_topics, moc_config, _moc_suffix)
    _log(f"phase3: {len(raw_clusters)} raw cluster(s) (threshold={moc_config.min_notes})")

    # Phase 4+5 — Enrich clusters (title, parents, metadata)
    denom = max(1, len(candidates_with_topics))
    moc_location = _moc_location(profile_dict)

    enriched_clusters: list[dict] = []
    parent_options_per_cluster: dict[str, list[dict]] = {}
    for idx, cluster in enumerate(raw_clusters, start=1):
        enriched, parents = _enrich_cluster(
            cluster, idx, profile_dict, cache, mode, trigger_arg, denom, moc_location
        )
        enriched_clusters.append(enriched)
        parent_options_per_cluster[enriched["cluster_id"]] = parents

    _log(f"phase4+5: enriched {len(enriched_clusters)} cluster(s)")

    # Phase 6 — Duplicate detection + squelch
    kept_clusters, duplicates_skipped, squelched = phase6_dedupe(
        enriched_clusters, cache, squelch_registry, moc_config,
        member_paths={c.stem: c.path for c in candidates_with_topics},
        container_roots=read_scope_paths(vault_cfg),
    )
    _log(f"phase6: kept={len(kept_clusters)} dup={len(duplicates_skipped)} squelched={len(squelched)}")

    # D3 — Inter-cluster member-overlap dedup (SDD ADR-13 D3, spec 021 T7.4)
    kept_clusters, d3_drops = _dedupe_overlapping_clusters(kept_clusters)
    duplicates_skipped.extend(d3_drops)
    _log(f"d3: kept={len(kept_clusters)} inter-cluster-drops={len(d3_drops)}")

    kept_clusters.sort(key=lambda c: c.get("confidence", 0.0), reverse=True)

    # Link members — rendered slice only, after D3 + sort (spec 042 ADR-2)
    link_stats = _augment_rendered_clusters(
        kept_clusters, candidates_with_topics, kado_client, cache,
        profile_dict, vault_cfg, moc_config.max_results,
    )

    # Phase 6.5 — Existing up:: validation
    kept_clusters = phase65_validate_existing_up(
        kept_clusters, candidates_with_topics, kado_client, cache,
        parent_marker=_conventions.parent_marker,
    )
    _log(f"phase6.5: existing_up:: decorated {len(kept_clusters)} cluster(s)")


    # ADR-13 D1: the note-orphan pass is REMOVED from the cluster pipeline.
    # Orphan suggestions are produced ONLY by _run_moc_uplink_check
    # (--check-moc-uplinks). The per-note orphan section (### Oxx) no longer
    # appears in cluster-mode proposal-docs (scan or scoped). Interactive
    # note-orphan handling is deferred to Garden-Audit (#30).
    # emit_orphan_suggestions / _cap_orphans remain in scope — used by the
    # check path above.

    report = build_pipeline_report(
        mode, trigger_arg, profile_name,
        candidates_total, len(candidates), candidates_with_topics,
        kept_clusters, parent_options_per_cluster, duplicates_skipped, squelched,
        link_stats,
    )

    _log(f"emitting DiscoveryReport: clusters={len(kept_clusters)} mode={mode!r}")
    partial = (len(duplicates_skipped) > 0 or len(squelched) > 0) and len(kept_clusters) > 0
    return report, (1 if partial else 0)


# ──────────────────────────────────────────────────────────────────────────────
# --around — the lookup half (spec 042 F2); builders in lib/moc_discovery_around.py
# ──────────────────────────────────────────────────────────────────────────────


def _around_lookup(
    report: dict, seed: AroundSeed, cache: dict, eligibility: NodeEligibility,
    kado_client,
):
    """One budgeted `neighbors(seed)` → ClusterLinks, or None after a seed-lookup abort."""
    with LinkLookup(kado_client) as lookup:
        result = augment_clusters(
            [{"cluster_id": AROUND_CLUSTER_ID, "items": [seed.path]}],
            {seed.path: seed.path}, lookup, eligibility, cache, threshold=1,
        )
    report["link_stats"] = dict(result.stats)
    links = result.clusters[AROUND_CLUSTER_ID]
    _log(f"around: status={links.status} neighbours={len(links.link_members)}")
    if links.status != _LINKS_DONE:
        _around_abort(
            report, "seed-lookup-failed",
            f"around: seed lookup failed for '{seed.stem}' — check that Kado is "
            f"reachable and its key can read the note",
        )
        return None
    return links


def _run_around_extension(
    report: dict, seed: AroundSeed, cache: dict, eligibility: NodeEligibility
) -> dict:
    """around:<MOC> — neighbours without cached up:: to the MOC → report.extension."""
    links = _around_lookup(report, seed, cache, eligibility, _build_kado_client())
    if links is None:
        return report
    return apply_around_extension(report, seed, cache, links)


def _build_around_note(
    report: dict, seed: AroundSeed, cache: dict, profile_dict: dict,
    eligibility: NodeEligibility,
) -> dict:
    """around:<note> — one `neighbors` lookup → one new-MOC cluster or an abort."""
    kado_client = _build_kado_client()
    links = _around_lookup(report, seed, cache, eligibility, kado_client)
    if links is None:
        return report
    aborted = around_too_few(report, seed, links)
    if aborted is not None:
        return aborted

    conventions = resolve_conventions(
        profile_dict=profile_dict, profiles_dir=DEFAULT_PROFILES_DIR
    )
    cluster, parents = build_around_cluster(seed, links, profile_dict, cache)
    candidate = Candidate(stem=seed.stem, path=seed.path, topics=list(seed.topics))
    clusters = phase65_validate_existing_up(
        [cluster], [candidate], kado_client, cache,
        parent_marker=conventions.parent_marker,
    )
    return fill_around_note_report(report, candidate, clusters, parents)


def _run_around(
    cache: dict, config_path: Path, profile_name: str, trigger_arg: str
) -> dict:
    """`--around` single pass → DiscoveryReport (proposal or abort). No squelch."""
    profile_dict = _load_yaml(DEFAULT_PROFILES_DIR / f"{profile_name}.yaml")
    eligibility = NodeEligibility(cache, profile_dict, _load_yaml(config_path))
    report = empty_report("around", trigger_arg, profile_name)

    seed, reason, message = resolve_around_seed(trigger_arg, cache, eligibility)
    if seed is None:
        return _around_abort(report, reason, message)
    report["around"] = {"kind": seed.kind, "path": seed.path, "stem": seed.stem}
    _log(f"around: resolved kind={seed.kind}")
    if seed.kind == "moc":
        report = _run_around_extension(report, seed, cache, eligibility)
    else:
        report = _build_around_note(report, seed, cache, profile_dict, eligibility)
    _log("links: " + " ".join(f"{k}={v}" for k, v in report["link_stats"].items()))
    return report


def main(argv: list[str] | None = None) -> int:
    """Top-level orchestration. Returns exit code 0 / 1 / 2."""
    parser = build_parser()
    args = parser.parse_args(argv)

    config_path = Path(args.config)

    # spec 042: --around is single pass — no Pass 1/2 file, no uplink audit.
    if args.around is not None and (
        args.emit_phase1 or args.phase1_input or args.check_moc_uplinks
    ):
        print(
            f"{LOG_PREFIX} FATAL: --around cannot be combined with --emit-phase1, "
            f"--phase1-input or --check-moc-uplinks",
            file=sys.stderr,
        )
        return 2

    # ── --phase1-input branch: skip Phase 1, derive mode/trigger from JSON ────
    # T6.5: agent has already extracted topics for cache misses LLM-side.
    if args.phase1_input:
        try:
            mode, trigger_arg, profile_name, pre_loaded = _load_phase1_input(
                Path(args.phase1_input)
            )
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
            print(f"{LOG_PREFIX} FATAL: --phase1-input load failed: {exc}", file=sys.stderr)
            return 2
        _log(f"phase1-input: mode={mode} trigger_arg={trigger_arg!r} candidates={len(pre_loaded)}")

        cache_path = Path(args.cache)
        # spec 021 T2.1: read the MOC-structure cache via the loader — rebuild
        # inline if stale/missing/corrupt (ADR-3), then shim entries→map_notes.
        cache, cache_abort = load_moc_cache(str(cache_path), str(config_path))
        if cache_abort is not None:
            _log(f"{cache_abort}: cache_path={cache_path} → abort {cache_abort!r}")
            return _emit_abort_report(mode, trigger_arg, profile_name, cache_abort)

        squelch_path = Path(args.squelch_state)
        squelch_registry = _squelch_load_registry(squelch_path)
        squelch_registry = _squelch_decrement_all(squelch_registry)
        _squelch_save_registry_atomic(squelch_path, squelch_registry)

        report, exit_code = _run_pipeline(
            args, cache, squelch_registry, config_path, profile_name,
            mode, trigger_arg, pre_loaded_candidates=pre_loaded,
        )
        if report is not None:
            emit_report(report)
        return exit_code

    # ── Normal flow + --emit-phase1 branch ───────────────────────────────────
    try:
        mode, trigger_arg = route_input(args)
    except ValueError as exc:
        print(f"{LOG_PREFIX} FATAL: {exc}", file=sys.stderr)
        return 2
    _log(f"mode={mode} trigger_arg={trigger_arg!r}")

    # Profile resolution — exit 2 fatal if unresolved (SDD line 834).
    try:
        profile_name = resolve_profile(config_path, args.profile)
    except FileNotFoundError as exc:
        print(f"{LOG_PREFIX} FATAL: {exc}", file=sys.stderr)
        return 2

    _log(f"profile={profile_name}")

    # Dry-run path: emit a minimal DiscoveryReport and exit. No Kado calls,
    # no cache check (the dry-run is the T2.1 scaffolding contract).
    if args.dry_run:
        _log("dry-run — emitting minimal DiscoveryReport, skipping discovery phases")
        report = empty_report(mode, trigger_arg, profile_name)
        emit_report(report)
        return 0

    # Cache load (SDD §Pseudocode line 851 — fires BEFORE Phase 1).
    # spec 021 T2.1: the MOC-structure cache is read via moc_cache_loader, which
    # rebuilds inline when stale/missing/corrupt (ADR-3) and projects
    # entries[kind==moc] → map_notes (shim). A fresh cache loads with no rebuild;
    # a rebuild that still yields no usable map_notes aborts cache-rebuild-failed
    # (not a re-scan every run) so the agent surfaces the "run /explore-vault" hint.
    cache_path = Path(args.cache)
    cache, cache_abort = load_moc_cache(str(cache_path), str(config_path))
    if cache_abort is not None:
        _log(f"{cache_abort}: cache_path={cache_path} → abort {cache_abort!r}")
        return _emit_abort_report(mode, trigger_arg, profile_name, cache_abort)

    # ── --around branch: single pass, no squelch (spec 042 F2) ──────────────
    if mode == "around":
        report = _run_around(cache, config_path, profile_name, trigger_arg)
        emit_report(report)
        return 0

    # ── --check-moc-uplinks branch: MOC-parentage audit only, no clustering ──
    # ADR-12: a focused pass over kind==moc orphans. No squelch decrement (no
    # clustering run), no Phase 1–6. Checked before --emit-phase1 (the agent
    # never combines them).
    if args.check_moc_uplinks:
        report = _run_moc_uplink_check(cache, config_path, profile_name)
        emit_report(report)
        return 0

    # ── --emit-phase1 branch: run Phase 1 only, write JSON, exit ─────────────
    # T6.5: no squelch decrement here; squelch is a per-discovery-run counter
    # and a two-pass invocation counts as one run (decremented in pass 2).
    if args.emit_phase1:
        moc_config = _load_moc_config(config_path)
        if args.candidate_cap is not None:
            import dataclasses as _dc
            moc_config = _dc.replace(moc_config, candidate_cap=args.candidate_cap)
        profile_path = DEFAULT_PROFILES_DIR / f"{profile_name}.yaml"
        profile_dict = _load_yaml(profile_path)
        kado_client = _build_kado_client()
        candidates, abort1 = phase1_select_candidates(
            mode, trigger_arg, profile_dict, cache, kado_client, moc_config
        )
        if abort1 is not None:
            _log(f"phase1: abort → {abort1!r}")
            return _emit_abort_report(mode, trigger_arg, profile_name, abort1)
        abort_emit = _write_phase1_emit(
            Path(args.emit_phase1), mode, trigger_arg, profile_name,
            candidates, cache, moc_config, kado_client,
        )
        if abort_emit is not None:
            _log(f"emit-phase1: abort → {abort_emit!r} (written to file)")
        else:
            _log(f"emit-phase1: wrote {len(candidates)} candidate(s) to {args.emit_phase1}")
        return 0

    # ── Squelch: load → decrement → persist (T5.1) ───────────────────────────
    # SDD §Pseudocode lines 881-884: run at start of each discovery pipeline so
    # the updated runs_remaining is in effect for Phase-6 filtering.
    # Missing file → empty registry (first-run case). Corrupt → warn + empty.
    # Raises on I/O errors during save so partial writes can't silently corrupt
    # the sidecar (save_registry_atomic uses tmp-then-rename).
    squelch_path = Path(args.squelch_state)
    squelch_registry = _squelch_load_registry(squelch_path)
    squelch_registry = _squelch_decrement_all(squelch_registry)
    _squelch_save_registry_atomic(squelch_path, squelch_registry)
    _log(
        f"squelch: loaded+decremented {len(squelch_registry)} active entries "
        f"from {squelch_path}"
    )

    report, exit_code = _run_pipeline(
        args, cache, squelch_registry, config_path, profile_name, mode, trigger_arg
    )
    if report is not None:
        emit_report(report)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
