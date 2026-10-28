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
