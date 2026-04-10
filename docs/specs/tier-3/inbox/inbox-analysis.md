# Tier 3: Inbox Analysis

> Parent: [Inbox Processing](../../tier-2/workflows/inbox-processing.md)
> Status: Draft
> Agent: `inbox-analyst`

---

## 1. Purpose

Define what the `inbox-analyst` agent does during Pass 1 of inbox processing. It reads the inbox, classifies each item, and produces a structured analysis object that `suggestion-builder` consumes.

## 2. Inputs

| Input | Source | Usage |
|-------|--------|-------|
| Inbox folder path | `concepts.inbox` from vault-config | Where to look |
| Discovery cache | `discovery-cache.yaml` | MOC matching, tag usage patterns, classification keywords |
| Framework profile | `profiles/<name>.yaml` | Classification categories, keywords, MOC state icons |
| User config | `vault-config.yaml` | Tag taxonomy, tracker definitions, lifecycle prefix |
| Kado MCP | runtime | Read inbox files, sample content |

## 3. Trigger

The agent runs as Step 2 of the inbox processing workflow, invoked after Step 1 (Read Inbox). It runs when:
- A fresh `/inbox` invocation finds unprocessed items in the inbox folder
- No `#MiYo-Tomo/confirmed` work is already pending (run-to-run state machine checks these first)

**Item discovery:** Tomo scans for ALL files in the inbox folder, not only files tagged `#MiYo-Tomo/captured`. Users may drop files into the inbox without any frontmatter or tags at all — those are valid inbox items too. The `captured` tag is applied by Tomo during analysis as a tracking mechanism, not a prerequisite for discovery. Any file in the inbox folder that does NOT have a lifecycle tag (`proposed`, `confirmed`, `instructions`, `applied`, `active`, `archived`) is treated as a fresh item.

## 4. Process

For each unprocessed inbox item:

```
1. Detect file type
   → Is it markdown (.md)? → parse as note
   → Is it binary (PDF, JPG, PNG, etc.)? → extract metadata only (filename, date, size)
   → Is it other text? → treat as plain content

2. Parse filename (flexible — not enforcing a pattern)
   → Try: YYYY-MM-DD_HHMM_<description>.md (structured timestamp)
   → Try: YYYYMMDD_<description>.md (date only)
   → Try: <description>.md (name only, no date)
   → Fallback: use file creation date from Kado metadata
   The filename pattern is informational, not required.

3. Read content (if markdown) via kado-read
   → Get full markdown body
   → Parse any existing frontmatter
   → Parse any existing tags
   For binary files: skip content parsing, use filename + metadata only.

4. Tag as captured
   → If the item has no lifecycle tag yet, add #MiYo-Tomo/captured
   → This marks it as "Tomo has seen this" for the state machine

5. Classify item type
   → For markdown: fleeting_note | coding_insight | system_action |
     external_source | quote | question | task | unknown
   → For binary: attachment (PDF, image, etc.)
   (See §5 Classification Heuristics)

6. Determine date relevance
   → Is this a daily-note-worthy event? (tracker matches, daily mentions)
   → Which date does it refer to? (filename date vs content date vs file metadata)

7. Match against MOCs
   → Use discovery-cache map_notes index
   → Compare item topics against MOC topics
   → Rank by confidence (topic overlap + depth bonus)
   → Return top 3 candidates

8. Match against classification system
   → If profile has classification enabled
   → Match content keywords against profile categories
   → Return top 3 candidates

9. Detect tracker actions
   → Match content against tracker trigger_keywords
   → Return proposed tracker updates with syntax

10. Detect atomic note worth
    → Heuristic: item has enough content to become a standalone note
    → (Configurable threshold, default: ≥3 meaningful sentences)
    → Binary files: always worth creating an attachment note wrapper

11. Detect new MOC potential
    → If item topic doesn't match any existing MOC
    → Check if 3+ similar unclassified items exist (Mental Squeeze Point)
    → Flag for new MOC proposal if threshold met

10. Output InboxItemAnalysis object
```

## 5. Classification Heuristics

Classification into item type uses content signals:

| Type | Signals |
|------|---------|
| `fleeting_note` | Short (<200 words), no clear structure, often thoughts/ideas |
| `coding_insight` | Code blocks, technical vocabulary, file paths, CLI commands |
| `system_action` | "installed", "configured", "set up" in first line; tool names |
| `external_source` | URL in first lines, title in quotes, attribution |
| `quote` | Quoted block, attribution pattern (— Author) |
| `question` | Ends with `?`, opens with "How/Why/What/When" |
| `task` | Checkbox marker, imperative verb first, deadline mentioned |
| `unknown` | None of the above match confidently |

Classification is soft — items can match multiple types. The primary is the strongest signal; alternatives are listed in the output.

## 6. InboxItemAnalysis Schema

The agent outputs a structured object per item (not yet a user-facing document — that's suggestion-builder's job):

```yaml
# Per inbox item
path: "+/2026-04-08_1430_oh-my-zsh.md"
filename_date: "2026-04-08"
filename_time: "14:30"
description: "oh-my-zsh"

content:
  length_chars: 420
  length_words: 72
  has_code_blocks: true
  has_urls: false
  has_checkboxes: false

classification:
  primary_type: "coding_insight"
  confidence: 0.85
  alternatives:
    - { type: "system_action", confidence: 0.60 }
    - { type: "fleeting_note", confidence: 0.20 }

topics:
  extracted: [oh-my-zsh, zsh, shell, terminal, installation]

date_relevance:
  daily_note_worthy: true
  target_date: "2026-04-08"
  reason: "system_action type, filename date matches today"

moc_matches:
  - { path: "Atlas/200 Maps/Shell & Terminal (MOC).md", confidence: 0.82, depth: 2 }
  - { path: "Atlas/200 Maps/2600 - Applied Sciences.md", confidence: 0.55, depth: 0 }
  - { path: "Atlas/200 Maps/Dotfiles (MOC).md", confidence: 0.40, depth: 2, note: "doesn't exist yet" }

classification_matches:
  - { category: 2600, name: "Applied Sciences", confidence: 0.90 }
  - { category: 2100, name: "Personal Management", confidence: 0.15 }

tracker_matches:
  - { tracker: "coding-session", syntax: "inline_field", proposed_value: true, reason: "'installed' keyword matched" }

atomic_note_worth: true
atomic_note_reason: "Has concrete how-to content (420 chars, code blocks present)"

new_moc_potential:
  flag: false
  reason: "Existing MOCs cover this topic"

issues: []   # warnings, errors, ambiguities
```

## 7. Batch Handling

The agent processes ALL captured items in a single run, not one at a time. This enables:
- **Cross-item analysis** — detect clusters that suggest new MOCs (Mental Squeeze Point)
- **Date grouping** — group daily-note actions by target date
- **Topic overlap** — if multiple items share topics, note the cluster

Output is a list of `InboxItemAnalysis` objects plus a top-level batch summary:

```yaml
batch_summary:
  total_items: 5
  by_type:
    coding_insight: 2
    fleeting_note: 2
    task: 1
  clusters:
    - topic: "shell/terminal"
      item_paths: ["+/oh-my-zsh.md", "+/zsh-aliases.md", "+/iterm-config.md"]
      new_moc_candidate: "Shell & Terminal (MOC)"
      confidence: 0.75
  dates_covered:
    - "2026-04-07"
    - "2026-04-08"
```

## 8. Error Handling

- **File read failure:** skip the item, record in `issues` with `severity: error`, continue
- **Discovery cache missing:** fall back to on-demand MOC reading; mark items with `stale_cache_fallback: true`
- **No framework profile loaded:** abort with fatal error (shouldn't happen; validated at session start)
- **Invalid frontmatter in inbox item:** treat the file as plain content, skip frontmatter parsing

## 9. Handoff to suggestion-builder

The agent outputs its analysis as a structured data blob (not a markdown document). The `suggestion-builder` agent receives this data and produces the human-readable Suggestions Document in Pass 1.

**Intermediate state:** The analysis lives in memory during a single `/inbox` invocation. It is NOT persisted to disk. If Pass 1 is interrupted, the next run starts fresh from captured inbox items.

## 10. Performance Considerations

- **Target:** process 20 inbox items in <10 seconds (not counting Kado round-trips)
- **Kado round-trips:** dominate runtime; batch where possible (e.g., use `kado-search listDir` once instead of many individual `kado-read` calls for directory listing)
- **Cache hits:** discovery cache lookups should be in-memory after first access
- **LLM calls:** classification uses prompts that should be short and focused — one call per item is OK; avoid chains
