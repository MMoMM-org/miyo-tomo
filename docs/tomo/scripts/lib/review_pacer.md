# WHY: lib/review_pacer.py

> Rationale for decisions in `tomo/scripts/lib/review_pacer.py`.
> The module owns the pacing policy of `/review`'s period read (spec 045,
> T3.1, ADR-4; PRD F3-AC10–F3-AC12): call spacing, widening after retries,
> the end-of-run retry pass, the not-read list, and the retry/wait summary
> `review-read.py` prints. It is modelled on `link_members.LinkLookup`.

## WHY a Pacer Instead of a Call Budget

WHY: the PRD replaced a call budget with pace-and-retry (owner decision
2026-11-11): a month read on a busy Kado must come back complete and slow,
never cut short. `/moc-propose` can stop at 120 attempts because a missing
link member costs nothing; a review that silently covers fewer days is wrong
in a way the user cannot see. So the pacer never installs an `attempt_gate`;
it only sets `min_interval` and lets the client's own retry loop (429 with
`Retry-After` honoured, 503 with backoff, four retries) do the waiting.

## WHY the Policy Lives Here and the Counters in the Client

WHY: ADR-4. The seconds slept belong where the sleeping happens
(`KadoClient.retry_wait_s`, `pace_wait_s`), and the number of retries is
already derivable as `attempt_count - call_count` — the client counts every
HTTP send and every logical call, so the pacer keeps no counter of its own
that could drift from the client's. The policy (start, cap, when to widen,
the end pass) is the run's business: a different script may pace differently
on the same client.

## WHY 0.3 s, Doubling, 2 s

WHY: Kado's default limit is 20 calls per 5 s per IP, shared with everything
else Tomo runs at the time; 0.25 s is exactly that rate, 0.3 s leaves room
for a second process. A call that needed retries is the signal that the
window is full, so the spacing doubles after it — `0.3 → 0.6 → 1.2 → 2.0` —
and stays doubled; a call without retries never narrows it again, because
the pressure that caused the retry is usually another process that is still
running. 2 s is the cap: at 2 s a month (≈ 110 calls) still fits the
five-minute KPI, and anything slower would not be a review session anymore.

## WHY a Failed Read Returns None and Is Retried Once at the End

WHY: F3-AC12. A read that outlasts the client's four retries is not lost yet:
the burst that caused it may be over by the end of the run. `read()` records
the path and its function, returns None so the caller reports the part as
not read for now, and `finish()` retries every recorded path once at the
widest spacing. Only what fails in that pass is "not read" and named in the
report and at the top of the document (F3-AC13). One end pass, not a loop:
a Kado that still refuses at 2 s spacing after the whole run is a limit to
raise, not a wait to extend — the summary carries `advice: raise-kado-limit`
whenever any retry happened.

The end pass stores the values it recovered in `recovered` (path → value):
`finish()` returns the not-read paths, as the SDD says, and the caller that
handed a plain reader function to `read()` still gets the late value without
having to build a closure with side effects.

## WHY Connection and Auth Errors Propagate

WHY: F3-AC10 and the `Stopped` design of `lib/review_vault.py`. Only
`KadoRateLimitError` is the pacer's to handle; a dead connection or a refused
key is not a pacing problem, and retrying it at 2 s would waste the user's
time before the same stop. The pacer lets every other `KadoError` through, so
`review-read.py` maps them to `status: stopped` the way the session script
does, and writes nothing. `KadoNotFoundError` propagates for the same reason:
a missing linked note is the day reader's finding, not a rate-limit event.

## WHY `min_interval` Is Restored by `close()`, Not by `finish()`

WHY: the pattern of `LinkLookup.close`. The pacer changes a shared client's
state; a caller that reuses the client after the read (the same script writes
`read.json` and may probe the inbox) must not inherit a 2 s spacing. The
previous value is saved at construction and restored by `close()` and by
`__exit__` — also when `read()` raised — and the restore is idempotent, so
`with ReviewPacer(client) as pacer: … pacer.finish()` restores exactly once,
at the exit.

`finish()` itself keeps the widest interval installed (T3.4 decision, 0.2.0;
until then it restored the saved value, as the SDD example sketched). The
period read makes reads *after* the end pass: when the end pass recovered a
daily or weekly folder listing, the notes that listing exposes are resolved
and read only then (`lib/review_period.py`). Those reads happen on the same
Kado that just turned the listing away for the whole run, so they must run at
the spacing the run widened to — 2 s — and not at the restored value (0 s
for a plain client), which would fire the first seven dailies into a window
that is known to be full and make the one not-read list grow after the end
pass. The interval therefore holds until `close()`; a script that wants the
old spacing back closes the pacer (or leaves the `with` block) before it
reuses the client. `tests/test_review_pacer.py` pins the interval after
`finish()`, `tests/test_review_read.py` pins the sends after a recovered
listing.

## WHY the Fake Vault Simulates the Client's Retry Loop

WHY: the policy must be testable without Kado and without real sleeping.
`tests/review_fake_vault.py` re-implements `KadoClient._call_tool`'s
accounting on a virtual clock — `attempt_count` per send, `call_count` per
logical call, `retry_wait_s` for the 429/503 sleeps (a deterministic
`Retry-After` of 1 s for 429, the client's backoff base and cap for 503, no
jitter), `pace_wait_s` for the `min_interval` gaps, `_MAX_RETRIES` imported
from the client — rather than driving the real client through a fake
transport, because every review script and every Phase 3 test uses the same
fake for its vault content, and a JSON-RPC transport stub for every Kado
operation would be a second client to maintain. A parity test in
`tests/test_review_pacer.py` runs one 429 scenario through the real client
(patched `urlopen`, `sleep`, `monotonic`) and through the fake and asserts
the same four counters, so the simulation cannot drift from the client
unnoticed.
