---
phase: 1
title: "Foundation — Kado client + structured topic extraction"
status: completed
---

# Phase 1: Foundation — Kado client + structured topic extraction

## Phase Context

**GATE**: Read all referenced files before starting.

**Specification References**:
- `[ref: SDD/Internal Interfaces]` — `list_notes()`, `read_inline_fields()`, `extract_topics_from_fields()` signatures
- `[ref: SDD/Architecture Decisions/ADR-2, ADR-3, ADR-4]` — listNotes, structured entry, links-only
- `[ref: SDD/External Interfaces]` — Kado `listNotes` + `dataview-inline-field` request/response shapes
- `[ref: Kado/docs/api-reference.md §listNotes]` — authoritative item shape

**Key Decisions**: ADR-2/3/4 (locked). No new dependencies (CON-4). Additive only —
existing `extract_topics(content)` and all current `KadoClient` call sites untouched.

**Dependencies**: none. T1.1 and T1.2 are independent `[parallel: true]`.

## Tasks

### T1.1 — `kado_client` gains `list_notes()` + `read_inline_fields()` `[parallel: true]` `[activity: backend-integration]`

1. **Prime**: Read `tomo/scripts/lib/kado_client.py` — `_search_all()` (cursor loop, lines ~437-470), `list_dir()` (the sibling pattern, ~174), `_call_read()` (~432). Read `[ref: SDD/External Interfaces]` for the two Kado op shapes and `[ref: Kado/docs/api-reference.md §listNotes]`.
2. **Test**: `tests/test_kado_client_listnotes.py` (mock `_call_tool`): `test_list_notes_call_shape` (asserts `operation=listNotes`, `path`, `fields=["links","headings","tags"]`, `limit`); `test_list_notes_paginates_via_cursor` (two-page mock → merged items); `test_list_notes_omits_fields_when_none`; `test_read_inline_fields_call_shape` (`kado-read operation=dataview-inline-field`); `test_read_inline_fields_returns_dict`; `test_search_all_fields_passthrough` (fields reaches args only when set). No live Kado.
3. **Implement**: Extend `tomo/scripts/lib/kado_client.py` (bump `# version:`). Add `fields: list[str] | None = None` param to `_search_all` → `args["fields"] = fields` only when set. Add `list_notes(self, path, *, fields=None, depth=None, limit=500)` → `_search_all("listNotes", path=path, depth=depth, limit=limit, fields=fields)`. Add `read_inline_fields(self, path) -> dict` → `_call_read("dataview-inline-field", path)`. Additive only — do not alter existing methods/signatures.
4. **Validate**: `pytest tests/test_kado_client_listnotes.py -v`; `pytest tests/ -q` (no regression); `ruff check tomo/scripts/lib/kado_client.py`; `python3 -c "from lib.kado_client import KadoClient; assert hasattr(KadoClient,'list_notes')"`.
5. **Success**: Correctly-shaped JSON-RPC for both ops `[ref: SDD/External Interfaces]`; pagination merges pages `[ref: PRD/A1]`; existing call sites unaffected (CON-1).

### T1.2 — `topic-extract` gains `extract_topics_from_fields()` `[parallel: true]` `[activity: domain-logic]`

1. **Prime**: Read `tomo/scripts/topic-extract.py` fully — the 4 methods (`extract_from_title`, `extract_from_headings`, `extract_from_links`, `extract_from_tags`), `normalize()`, `deduplicate_and_rank()`, constants (`BOILERPLATE_HEADINGS`, `STRUCTURAL_TAG_PREFIXES`, `MAX_LINKS`, `MAX_TOPICS`). Read `[ref: SDD/Internal Interfaces]` signature and `[ref: SDD/Risks/Gotcha — link target shapes]`.
2. **Test**: `tests/test_topic_extract_fields.py`: `test_h1_heading_used_as_title`; `test_filename_title_fallback_when_no_h1`; `test_level2_headings_become_subtopics_boilerplate_skipped`; `test_links_kind_link_used_kind_embed_dropped` (ADR-4 — `{target:'diagram.excalidraw',kind:'embed'}` excluded); `test_link_target_alias_path_anchor_stripped` (`Folder/Note#heading|Alias` → `note`); `test_tags_hash_prefix_stripped_then_structural_filtered` (`#type/x` dropped, `#nlp` → `nlp`); `test_parity_with_content_path_on_equivalent_input` (same topics as `extract_topics()` given equivalent markdown); `test_empty_fields_returns_empty_topics`.
3. **Implement**: Add `extract_topics_from_fields(*, title, headings, links, tags) -> dict` to `topic-extract.py` (bump `# version:`). Reuse the existing normalise/dedup/rank core (refactor a shared `_rank(source_methods)` if needed — SDD Tech-Debt note: align, don't duplicate). Map: H1 (`level==1`) or `title` → method 1; `level==2` headings (skip `BOILERPLATE_HEADINGS`) → method 2; `links` filtered to `kind=='link'`, then alias(`|`)/path(`/`)/anchor(`#`,`^`)-stripped, capped `MAX_LINKS` → method 3; tags `lstrip('#')` then `STRUCTURAL_TAG_PREFIXES` filter + `/`-split → method 4. Return the same `{topics, source_methods}` shape.
4. **Validate**: `pytest tests/test_topic_extract_fields.py -v`; `ruff check tomo/scripts/topic-extract.py`; confirm `extract_topics()` tests still pass (parity).
5. **Success**: Structured input yields topics consistent with the content path `[ref: SDD/ADR-3]`; embeds excluded `[ref: SDD/ADR-4]`; target shapes stripped `[ref: SDD/Risks]`.
