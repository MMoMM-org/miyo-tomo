# Specification: 002-Phase 2 — Vault Explorer

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-04-10 |
| **Current Phase** | PLAN |
| **Last Updated** | 2026-04-10 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | skipped | Covered by Kokoro Tier 1-3 specs in docs/specs/ |
| solution.md | skipped | Architecture defined in pkm-intelligence-architecture.md |
| plan/ | in_progress | Derived from Kokoro Phase 2 implementation plan |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-10 | Skip PRD/SDD — use existing Kokoro specs | All tiers copied to docs/specs/ |
| 2026-04-10 | Python scripts call Kado HTTP API directly | Agents delegate deterministic work to scripts; scripts return compact JSON |

## Context

Phase 2 (Vault Explorer) builds the /explore-vault command that scans vault via Kado,
builds MOC tree, detects frontmatter/tag/callout patterns, and generates discovery cache.

Requires Kado v0.1.6 running. All vault access via Kado MCP.

Source specs: docs/specs/ (all tiers)

---
*This file is managed by the xdd-meta skill.*
