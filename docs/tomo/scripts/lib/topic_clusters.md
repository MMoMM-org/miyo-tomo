# WHY: scripts/lib/topic_clusters.py

> Rationale for decisions in `tomo/scripts/lib/topic_clusters.py`.
> The lib groups atomic-note candidates into Proposed-MOC clusters for two
> callers: `suggestions-reducer.py` (Pass-1 Proposed MOCs) and
> `moc-discovery.py` (`/moc-propose`).

## WHY a topic whose normalised key is empty never clusters (#216)

`normalise_topic` strips every non-word character, so a punctuation-only topic
such as `§` (the user's source-note prefix) normalises to `""`. Grouping used
that key unchecked, so every punctuation-only topic landed in ONE cluster with
the empty key, displayed as the first raw topic. A live `/moc-propose` scan
proposed "§ (MOC)" from stems like `§ Basic Dataview Query Builder`. A key with
no characters carries no topic, so `build_topic_clusters` skips such a
candidate exactly like an empty topic. It forms no cluster and joins none.

## WHY the display topic drops wrapping brackets and edge punctuation (#216)

The grouping key already ignores brackets, so `(quote)` groups under `quote`,
but the cluster kept the first raw spelling for display and the MOC title was
built from it: "(Quote) (MOC)". The emitted `topic` is now cleaned by
`clean_display_topic`:

- one matching bracket pair that wraps the WHOLE topic is removed
  (`(quote)` -> `quote`; also `[...]` and `{...}`), repeated until stable;
- leading and trailing non-word characters and whitespace are removed.

Internal brackets stay: `Gesundheit (Lebensbereich)` keeps its parentheses
because the pair does not wrap the whole string, and the trailing `)` is only
removed when it is the closer of a pair that opens at position 0. The grouping
key is computed from the raw topic as before, so no group changes; only the
emitted display string does. The clean-up lives in the lib, not in
`moc-discovery.py`, so the Pass-1 path shares one rule (SSoT) and the title
builder stays untouched.

Trade-off: a trailing symbol that is part of a name (`C++`, `C#`) is also
dropped from the display. The grouping key already lost it (`c`), so the
cluster was never distinguishable from "C"; the spec accepted this.

### Wrap-strip and edge-strip iterate together (#216 follow-up)

Running the wrap-strip once and then the edge-strip left a pair that the edge
strip had just exposed: `" -- (quote)"` became `"(quote)"`, `"(quote)."` became
`"(quote)"` and `"(x) -- "` became `"(x)"`. `clean_display_topic` now repeats
both steps until the string stops changing, so all three give the bare word.
Results the tests pin stay as they were: `"(a) (b)"` and
`"Gesundheit (Lebensbereich)"` are unchanged, `"((x))"` gives `"x"`,
`"(a (b))"` gives `"a (b)"`, `"()"` is unchanged.

### One-off: squelch signatures of bracketed or punctuated topics

`compute_topic_signature` hashes the cleaned topic. A squelch registry entry
recorded earlier under a bracketed or punctuated topic (for example
`(Quote)`) therefore gets a new signature, and that cluster may resurface
once. This is acceptable: its title was the broken one.

### Pass-1 per-item note uses the same spelling

The per-item "Proposed MOC" note in `suggestions-reducer.py` printed the raw
`proposed_moc_topic`, while the Proposed MOCs section showed the cleaned
cluster topic. The note now passes the topic through `clean_display_topic`
after the marker strip, so both places show the same spelling.
