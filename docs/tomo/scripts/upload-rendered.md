# WHY: upload-rendered.py

> Rationale for decisions in `tomo/scripts/upload-rendered.py`.

## The Filename Timestamp Is Local Time (#202)

WHY `_derive_timestamp` converts to local time: `instructions.json` carries a UTC
`generated`, and its `md_peer` names the `.md` sibling with a local-time prefix from
`instruction-render.py`. The two must produce one name, in the same process time
zone, or Hashi's peer lookup fails.
