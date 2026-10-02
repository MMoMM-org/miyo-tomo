# WHY: lib/typed_name_check.py

> Rationale for decisions in `tomo/scripts/lib/typed_name_check.py`.
> A pure verdict on one owner-typed attachment name: usable, or refused with
> one of three reason codes. Only non-obvious decisions are recorded here.

## Refusal, Never Substitution (spec 038 T3.1, ADR-5, v0.1.0)

WHY this module verdicts instead of reusing `sanitize_stem`
(`lib/obsidian_filename.py`), which already knows every character Obsidian
forbids and already produces a usable name from an unusable one.

Because producing a usable name is precisely the defect spec 038 exists to
close. `sanitize_stem` substitutes in place — `/` becomes `-` — so an owner who
typed `Rechnung 4/2026.pdf` would get a file named `Rechnung 4-2026.pdf` and no
indication that anything had happened to it. F3's user story is the anchor: the
owner must never be quietly given a different name than the one they typed. A
silent substitution is not a lesser version of that failure, it is that failure
with a helpful face on — the owner's instruction was followed in form and
discarded in substance, and the only artefact that could have told them says
the move succeeded.

Reusing the sanitiser here would therefore have been the spec's own defect
wearing a different hat, which is why the module is written as a function that
cannot rewrite: `TypedNameVerdict` carries `name` back unchanged on the accept
path, and there is no code path on which the returned string differs from the
argument. That is a structural guarantee rather than a convention — a future
change that wanted to trim or substitute would have to alter the dataclass's
documented contract to do it, not just add a line.

ADR-5 closes the set of permitted outcomes to two, accept-verbatim or refuse,
and the one case that tempts a third is recorded in `check_typed_name`'s own
docstring rather than here because it is still open: a name padded with leading
or trailing whitespace (`"  a.png  "`) is none of the three refusal classes, so
it is accepted padding and all. Flagged to the owner 2026-10-01 — whitespace is
easy to type by accident and invisible once typed — and deliberately left as
accept-as-is pending a ruling, because trimming it is the one thing ADR-5 does
not permit and inventing a fourth class to refuse it would pre-empt the owner's
decision. `tests/test_038_t3_1_typed_name_check.py` pins the current behaviour
so the ruling, when it comes, arrives against a test rather than into a gap.

## A Separate Module, Not a Branch in the Move Builder (spec 038 T3.1)

WHY ~80 lines get their own file rather than living inside
`_build_move_asset_actions`, where the only production caller is.

Two consumers, reachable independently. The same rule has to serve the Pass 2
move builder (`render_actions.py`, which refuses the name and emits a
`typed_name_refused` skip) and the markdown control surface that T3.4 renders.
A rule expressed as a branch inside the builder is reachable from neither
independently: the markdown side would have to call the whole builder — with a
manifest, a confirmed list, a config, a counter — to ask a question about one
string, and a test of the rule itself would have to assemble that same fixture
to exercise a one-argument decision.

The module takes no dependency on `render_actions.py` or any other caller,
which is what keeps the parser side available as a consumer without a cycle. It
imports exactly one thing from the rest of the tree — `FORBIDDEN_CHARS` from
`lib/obsidian_filename.py` — so the forbidden set has one definition and this
module cannot drift from the sanitiser's idea of what Obsidian rejects even
though it draws the opposite conclusion from it.

The usual argument against a module this small is that it is indirection for
its own sake. It is not, and the measurable reason is the import list: a
function whose entire input is one `str` and whose entire output is a frozen
dataclass has no seam to hide behind, so the file's size is the honest size of
the rule rather than a wrapper around one elsewhere.

## Three String Classes, and Why `taken` Is Not the Fourth (spec 038 T3.1, owner 2026-10-01)

WHY `REFUSAL_REASONS` has exactly three members when F3 names four things that
can be wrong with a typed name — separator, forbidden character, blank, and
*already taken*.

Because `taken` is not a property of the string. The first three can be decided
by looking at the name and nothing else, which is what makes them answerable by
a one-argument pure function. Occupancy is a property of the run: whether
`karte.png` is free depends on what the other items in this same Pass 2 have
already claimed, and that is a question only the run can answer. The run does
answer it, at `render_actions.py:927` — `claimant = claimed.get(destination.
casefold())` — and a typed destination reaches that check by design, not by
accident: the remedy branch recomputes `destination` and then falls through to
the same claimed check every other attachment uses (`render_actions.py:922-926`
spells that out in a comment). Adding `taken` here would mean handing this
module the run's `claimed` map so it could duplicate a check that already
exists and already covers the typed case. That was put to the owner and
rejected on 2026-10-01.

The sharper half of the argument is that the vault-side reading of the fourth
criterion is not decidable in Pass 2 **by any module**, so no amount of state
passed to this one would make it answerable. Measured 2026-10-01 and recorded
at `requirements.md:300`: Pass 2 performs no vault listing — `path_exists`
appears nowhere in `render_actions.py` or `render_md.py` (confirmed again
2026-10-02 at T3.5: zero occurrences in either file) — and the wire carries only
`destination`, `same_file` and `proposed_name` per ADR-3. Pass 1 owns occupancy
and hands forward one `proposed_name`. So "already taken at the destination"
has two readings, run-local and vault-side; the run-local one is satisfied by
the existing claimed check, and the vault-side one cannot be satisfied in
Pass 2 at all. The PRD records both readings rather than collapsing them,
because a reader who finds three classes where the requirement named four
should be able to see that the fourth was analysed and allocated, not dropped.

Downstream of that ruling, the owner scoped "refused name" for T3.4's reporting
obligation to these three classes only (`requirements.md:302`, 2026-10-02): a
typed name that is a usable string but collides is refused by the claimed check
and reported with the pre-existing shared collision sentence, which names no
provenance. Two ways of adding the framing were measured and declined — forking
that sentence when the name was typed, and plumbing `name_is_owner_supplied`
onto the skipped entry — both for buying little, since the owner is reading a
document rendered from the run in which they typed the name.

The set is `frozenset` and the module docstring calls it closed, which is load-
bearing downstream rather than decorative: `_typed_name_refusal_reason`
(`render_actions.py:692`) has three branches and reaches its final `return` only
for `blank`, not as a fallback for an unrecognised code. Measured at T3.5 by
disabling that function's first branch — a separate code that fell through
would not be re-labelled as a forbidden character, it would be announced to the
owner as *blank*, because the function branches on the code and never
re-inspects the string. A fourth member added to this frozenset without a
matching branch there would ship that sentence.

### WHY `/` Is Reported as `separator_present` and Not `forbidden_character`

`/` is a member of `FORBIDDEN_CHARS`, so the two checks genuinely overlap and
the one that runs first decides what the owner is told. The separator check runs
first, and `_NON_SEPARATOR_FORBIDDEN_CHARS` subtracts `/` from the set the
second check consults, so the split is stated twice — once as ordering, once as
set membership — rather than resting on ordering alone. The duplication is
deliberate: a future reader reordering the two checks for tidiness would make
`separator_present` unreachable, and the subtracted set is the thing that makes
that reordering visibly wrong at the point of the change instead of only in a
test.

The distinction is worth preserving because the two sentences send the owner
somewhere different. "Contains a path separator, which is not allowed in a
filename" tells someone who typed `a/b.png` that they tried to express a folder
and cannot; "contains a character Obsidian does not allow" tells someone who
typed `a*b.png` that one character has to go. Collapsing them would give the
first owner the second instruction.

## One Argument, No Run State (spec 038 T3.1)

WHY `check_typed_name(name: str)` takes nothing else — no config, no vault
client, no `claimed` map, no run id.

It is the same argument as the three classes, stated as a signature. Everything
this function can decide is decidable from the string, so every additional
parameter would be either unused or a second mechanism for something the run
already does. The practical payoff is in the tests: each refusal class is one
string and one assertion, with no fixture, which is why `REFUSAL_REASONS` could
be exercised exhaustively in both directions — the L1 both-paths rule for
permission-shaped behaviour — at essentially no cost.

It also keeps the module honest about what it does not know. A function handed a
vault client invites a future contributor to probe the filesystem "while we're
here", at which point Pass 2 acquires a vault read that ADR-3 and the SDD's
Error Handling section both say it does not have, and the refusal set quietly
grows a member whose answer depends on when the run happened. The empty
parameter list is the cheapest available guard against that, and it is why the
docstring names the rejected alternative rather than only describing the chosen
one.
