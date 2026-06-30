# WHY: routing-plan-consumer

> Rationale for decisions in `tomo/dot_claude/skills/routing-plan-consumer/SKILL.md`.

## Skill Instead of Inline Knowledge

WHY: Before 018, both inbox-orchestrator and instruction-builder contained duplicated routing-plan reading logic — each had its own understanding of field names, action values, and bucket semantics. When triage output changed (e.g. adding `skip_stems` or `drift_indicators`), both agents needed updating. Extracting this into a single skill means the routing-plan contract is defined in one place. Both suggestion-conductor and synthesis-conductor load it, so a field rename or new bucket only needs one edit.

## Action Table as Deterministic Router

WHY: The action branching table maps routing-plan actions to conductors with no ambiguity. This is intentional — the LLM must not reason about which conductor to invoke. The triage script (inbox-triage.py) already made the routing decision deterministically; the conductor just needs to know "action X means do Y." A prose description would invite the LLM to second-guess the triage decision.

## Typed Bucket Documentation

WHY: Each field in the routing plan has a specific shape and consumer. Documenting them as a typed reference table prevents the conductors from guessing field contents or inventing fields that don't exist. The `cache_path` key on approved docs is particularly important — it signals "read from local cache, not Kado" which is the foundation of the single-read principle (triage reads once, conductors consume from cache).

## Not User-Invocable

WHY: This is a reference skill for conductors, not a user workflow. It carries no interactive steps, no prompts, no output formatting. Making it user-invocable would add it to the command palette where it would confuse users — "Routing Plan Consumer" means nothing outside the pipeline context.
