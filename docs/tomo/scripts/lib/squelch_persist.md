# WHY: squelch_persist.py

> Rationale for decisions in `tomo/scripts/lib/squelch_persist.py`.

## Link Members Do Not Reach the Signature (spec 042 T2.3, SDD ADR-7)

WHY `persist_rejected_clusters` computes the signature from the stems that
`enumerate_all_moc_sections` returns, and that function leaves out Children
lines carrying `LINK_MEMBER_MARKER`: a rejected proposal must stay squelched
when a later run finds different link members for the same topic cluster. Only
topic members feed `compute_topic_signature`, so rejecting a document with link
members stores the same signature as rejecting it without them.

There is no marker logic in this file on purpose. The exclusion lives in the
parser (one place, one constant in `lib/link_members.py`); a second filter here
would be a copy that can drift.

## `around:` Sections Are Not Squelched (spec 042, owner decision)

WHY: rejecting an `around:` proposal must not write a registry entry (the owner
decided `around:` proposals are not squelched). This module needs no code for
that: it works from `enumerate_all_moc_sections`, which leaves `around:`
sections out, so a document that holds only an around section yields no
rejected cluster and `persist_rejected_clusters` returns 0 without touching the
registry. The filter lives in the parser (one place, next to the marker
logic); a second check here would be a copy that can drift. See
`docs/tomo/scripts/suggestion-parser.md` for the marker.
