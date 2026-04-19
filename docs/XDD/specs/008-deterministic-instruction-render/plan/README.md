---
title: "Deterministic Instruction Render — Implementation Plan"
status: draft
version: "1.0"
---

# Implementation Plan

## Context Priming

**Specification**:
- `docs/XDD/specs/008-deterministic-instruction-render/README.md`

**Key Design Decisions**:
- `instruction-render.py` produces BOTH `instructions.json` AND `instructions.md`
- `instructions.json` is the single source of truth — the MD is rendered from it
- The instruction-builder agent becomes a pure orchestrator (no markdown assembly)
- `parsed-suggestions.json` remains the canonical input

**Current Data Flow** (before):
```
suggestion-parser.py → parsed-suggestions.json
                              ↓
                     instruction-render.py → manifest.json + rendered note files
                              ↓
                     instruction-builder (LLM) → instructions.md  ← LLM assembles markdown
```

**Target Data Flow** (after):
```
suggestion-parser.py → parsed-suggestions.json
                              ↓
                     instruction-render.py
                       ↓           ↓           ↓
              rendered notes   instructions.json   instructions.md
              (files)          (machine-readable)   (human view, rendered from JSON)
```

## Implementation Phases

- [ ] [Phase 1: Extend instruction-render.py](phase-1.md)
- [ ] [Phase 2: Simplify instruction-builder agent](phase-2.md)
- [ ] [Phase 3: Validation](phase-3.md)
