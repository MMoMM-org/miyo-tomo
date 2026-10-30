# WHY: scripts/topic-extract.py

> Rationale for decisions in `tomo/scripts/topic-extract.py`.
> The script turns a note into topic keywords. `moc-tree-builder.py` calls it
> through `--content` for every entry of the MOC-structure cache, and
> `/moc-propose` clusters orphans by those topics.

## Two Entry Points, One Rule Set for Noise

- `extract_topics(content, title)` is the content path. It is the only one
  production uses, through the CLI that `moc-tree-builder.py` calls as a
  subprocess.
- `extract_topics_from_fields(...)` is the structured path (ADR-3). It works
  on Kado `listNotes` fields and has no production caller today.

WHY the noise rules live in `deduplicate_and_rank`: both paths end there, so a
noise rule cannot apply to one path and silently miss the other. That miss is
exactly what happened with H2 headings (next section).

## H2 Headings Are No Topics (0.5.0)

WHY: version 0.3.0 dropped H2 headings, but only from the structured path.
Its docstring said "H2 headings excluded" while the content path, the one the
cache uses, kept reading them. Most H2s are template sections, so whole
template families clustered on them. Measured live on 2026-10-30 over 214
orphans: "related notes", "resources", "why it's important", "problem
statement" and "result / syntax / etc" formed clusters of 30 each. "Url (MOC)"
over the `2071 Links` folder came from the link template's `## URL`.

## Stop Words and Letterless Topics (0.5.0)

WHY: title analysis also yields each word of a multi-word title. The old stop
list held 26 English words, so pronouns, auxiliaries and every German function
word passed. Quote and value titles then produced clusters such as "you",
"have", "not", "if", "ist", "nicht" and "und". Links to daily notes added date
clusters such as "2022-09-11".

- The stop list covers English and German function words and common English
  contractions. It holds no content words: borderline terms such as "make",
  "time" and "show" stay. A content word wrongly dropped loses a real topic,
  while a function word wrongly kept only costs one weak cluster the user can
  untick.
- `is_noise` drops topics with no letter (dates, numbers, punctuation). It does
  not use a minimum length, so short topics such as "ai" survive.

Effect on the instance data from 2026-10-30, both measured with the same
clustering:

| Candidates | Clusters before | Clusters after |
|---|---|---|
| 214 orphans | 151 | 88 |
| 45 orphans after the folder-home filter | 17 | 12 |

The 12 remaining clusters are dataview, knowledge, framework, perplexity,
zettelkasten, japan, vault, plugin, obsidian, principles and applied, plus a
cluster with a single note (jahresreflektion).

## Why Not the Full Structured Rules

WHY: the structured path also stops splitting titles into words and keeps only
tags under `topic/`. Applied to the content path, that left 2 clusters out of
45 candidates. Real topics such as "zettelkasten", "obsidian" and "knowledge"
come from title words, so the word split stays.

## Rollout

Topics are computed when the cache is built. An existing
`moc-structure-cache.yaml` keeps its old topics until its TTL (`ttl_days`,
default 1) expires and the loader rebuilds it.
