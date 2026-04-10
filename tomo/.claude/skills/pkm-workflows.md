# PKM Workflows
# version: 0.1.0

Knowledge patterns for inbox processing state machine, classification heuristics, and batch workflows.

## State Machine

### Lifecycle States

| State | Applied To | Set By | Meaning |
|-------|-----------|--------|---------|
| `captured` | Inbox items | User or auto-capture | Fresh, untouched |
| `proposed` | Suggestions doc | Tomo (suggestion-builder) | Pass 1 complete, awaiting review |
| `confirmed` | Suggestions doc | **User** | Direction approved, ready for Pass 2 |
| `instructions` | Instruction set | Tomo (instruction-builder) | Pass 2 complete, awaiting application |
| `applied` | Instruction set | **User** | Actions applied in vault |
| `active` | Inbox items | Tomo (vault-executor) | Item integrated into vault |
| `archived` | Suggestions/Instructions | Tomo (vault-executor) | Document retired |

### Tag Format

`#<prefix>/<state>` where prefix is from `vault-config.yaml lifecycle.tag_prefix` (default: `MiYo-Tomo`).

Example: `#MiYo-Tomo/captured`, `#MiYo-Tomo/proposed`

### Invariants

1. Exactly one lifecycle tag per document at any time
2. Tomo never sets user-owned states (`confirmed`, `applied`)
3. Transitions are monotonic — no backwards movement
4. Terminal states: `active` (for source items), `archived` (for workflow documents)

### Run-to-Run Discovery Priority

When `/inbox` is invoked, check in this order (first non-empty wins):

1. `#<prefix>/applied` → action: cleanup (vault-executor)
2. `#<prefix>/confirmed` → action: pass2 (instruction-builder)
3. `#<prefix>/captured` → action: pass1 (inbox-analyst + suggestion-builder)
4. Nothing found → action: idle

## Classification Heuristics

### Note Type Detection

Apply heuristics with confidence scoring. First match above 0.7 wins.

| Type | Key Signals |
|------|-------------|
| `fleeting_note` | Short (<200 words), unstructured, personal prose, no code/URLs |
| `coding_insight` | Code blocks (```), file paths (`/`, `./`, `~`), CLI commands, technical vocabulary (API, function, debug, deploy, config, install) |
| `system_action` | Past tense action verbs: installed, configured, set up, migrated, updated, deployed, created, enabled, disabled |
| `external_source` | URLs (http/https), blockquotes with attribution, "Source:", "From:", "Via:", DOI patterns |
| `quote` | Blockquote dominant (>50% lines start with `>`), attribution line (— Author, – Author), short content |
| `question` | Ends with `?`, starts with interrogative (How, Why, What, When, Where, Is, Can, Should, Does) |
| `task` | Checkbox markers (`- [ ]`, `- [x]`), imperative verbs, deadline mentions (by, due, before, deadline) |
| `attachment` | Binary file (non-.md extension, PDF, image, etc.) — deterministic, confidence 1.0 |
| `unknown` | No heuristic reaches 0.5 — flag for user attention |

### Confidence Scoring

- Each matching signal adds to confidence (typically +0.2 to +0.3)
- Multiple signals compound: coding_insight with 3 code blocks + CLI command → 0.8+
- Ties broken by order in the table above (fleeting_note before coding_insight)
- Below 0.5: classify as `unknown`, flag for user in suggestions

### Date Extraction from Filenames

Common patterns to detect:
- `YYYY-MM-DD` — ISO date
- `YYYYMMDD` — compact date
- `DD-MM-YYYY` — European format
- `YYYY-MM-DD_HHMM` — date with time
- Prefix or suffix position both valid

## Batch Processing Patterns

### Batch Limits

| Items | Behavior |
|-------|----------|
| 1-30 | Single suggestions document |
| 31-50 | Single document with warning header |
| 51+ | Split into multiple documents, grouped by topic cluster or type |

### Cross-Item Patterns

After individual analysis, look for batch-level patterns:

- **Topic clusters**: 3+ items sharing extracted topics → group in suggestions
- **Date grouping**: multiple items for same date → batch daily note updates
- **Project grouping**: items related to same project tag → note in suggestions
- **Mental Squeeze Point**: 3+ items sharing topics with no MOC match → propose new MOC

### Processing Order

Items processed in filename order for reproducibility. Within the suggestions document,
items are sorted by type (groups similar actions together) then by confidence (highest first).

## Workflow Document Naming

| Document | Filename Pattern |
|----------|-----------------|
| Suggestions | `YYYY-MM-DD_HHMM_suggestions.md` |
| Instruction Set | `YYYY-MM-DD_HHMM_instructions.md` |
| Rendered Note | `YYYY-MM-DD_HHMM_<slug>.md` |
| Diff Document | `YYYY-MM-DD_HHMM_<slug>-diff.md` |
| Archive Folder | `<inbox>/archive/YYYY-MM/` |
