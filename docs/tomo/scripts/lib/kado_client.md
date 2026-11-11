# WHY: lib/kado_client.py

> Rationale for the request-budget additions to `tomo/scripts/lib/kado_client.py`
> (spec 042, ADR-4), for the transport-error wrapping (spec 044) and for the
> wait counters, the rate-limit error and the search filter (spec 045, ADR-4).
> The rest of the client is documented in its docstrings.

## Attempts vs calls — `attempt_count` is a second counter

WHY: `call_count` counts logical tool calls (one per `_call_tool`), and callers
key persistent cost records to it, so its meaning must not change. Kado's rate
limiter, however, counts HTTP requests: a call that is answered 429 and retried
twice costs three requests but one `call_count`. Retries are invisible to
`call_count`, so a budget keyed to it would under-count exactly the traffic that
triggers the limiter. `attempt_count` is incremented before every HTTP send,
retries included.

## The gate — `attempt_gate` stops the client, the caller owns the policy

WHY: Kado allows 20 requests / 5 s per IP, shared with interactive MCP traffic
and applied inside the container too. A run therefore needs a hard cap on
requests, but the client must not know what the cap is or how it is shared
across lookups. `attempt_gate` is a zero-argument callable consulted before
**every** send — the first try and each retry. `False` raises
`KadoBudgetExhausted` without sending and without incrementing `attempt_count`
(a refused send is not an attempt). Checking only retries would let a caller
with an exhausted budget still make one more request per call.

On a 429 with `Retry-After` the existing delay is honoured (clamped to 60 s),
and the owner requires backoff support rather than skipping the retry. The gate
is asked again after that sleep, so no send goes out against a budget that ran
out meanwhile.

`KadoBudgetExhausted` subclasses `KadoError`, not `KadoToolError`: it is not an
MCP tool failure, and callers that already degrade on `KadoError` (the base for
every client failure) degrade on exhaustion without new except clauses, while
callers that care can catch it first.

## Pacing — `min_interval` spaces sends, it does not cap them

WHY: staying under 20 requests / 5 s needs sends at least ~0.3 s apart even when
nothing fails. `min_interval` (seconds, monotonic clock) sleeps the difference
between the previous send and this one, after the gate check so a refused send
never waits. Default 0 and `attempt_gate=None` leave every existing caller
unchanged; only the discovery path opts in.

A failed send still stamps the pacing timestamp, because it is an attempt Kado's
limiter counted.

## Transport errors — every failed exchange is a `KadoConnectionError`

WHY: `urlopen` and `resp.read()` raise more than `HTTPError` and `URLError`. A
timeout or a reset while the response is read surfaces as a bare
`TimeoutError` or `ConnectionResetError` (both `OSError`), and a truncated body
as `http.client.IncompleteRead`, which is an `http.client.HTTPException` and no
`OSError` at all. Escaping raw, they skip every caller's `except KadoError`:
`note-instructions.py deliver` then mapped a mid-upload timeout to exit 2
"local I/O" with no `failed_step`, and `kado-read-file.py` reported it as a
failed local write. `_call_tool` therefore wraps any `OSError` or
`HTTPException` raised during the request or response into
`KadoConnectionError`, chained to the original, after the `HTTPError` and
`URLError` branches so their specific handling is unchanged. These are not
retried: a timeout has already waited `_DEFAULT_TIMEOUT`, and retry stays the
policy for the 429/503 statuses Kado sends on purpose. Callers that catch
`KadoError` handle the new case without new except clauses, which is the same
reason `KadoBudgetExhausted` subclasses it.

## Wait counters — `retry_wait_s` and `pace_wait_s` live where the sleeping happens

WHY: `/review` (spec 045) replaces a call budget with pace-and-retry and has to
tell the user how long a run spent waiting, so the user can decide whether to
raise Kado's limit. The client is the only place that knows the two kinds of
wait: `retry_wait_s` accumulates every delay slept before a 429/503 retry (the
`Retry-After` value or the jittered backoff, exactly what `time.sleep` is
handed), `pace_wait_s` accumulates every sleep `_pace` makes to keep sends
`min_interval` apart. They are two counters, not one, because they answer
different questions — retry waiting means Kado pushed back, pacing waiting is
the client's own choice — and the report advises raising the limit only on the
first. Both start at 0.0 and are plain public floats a caller may read or
reset; nothing in the client reads them back.

There is no `retry_count`: retries are already `attempt_count - call_count`
(every attempt beyond the first per call is a retry). A third counter would be
a second source of truth for the same number.

## `KadoRateLimitError` — a 429/503 that outlasts the retries is its own class

WHY: a 429 or 503 that survives all `_MAX_RETRIES` used to surface as a plain
`KadoError`, indistinguishable from a 500 or a protocol error. The review
pacer needs to tell "Kado is rate-limiting, retry this later at a wider
spacing" apart from "something else broke, stop the run" — the first path is
retried at the end of the run, the second (`KadoConnectionError`,
`KadoAuthError`) stops it. `KadoRateLimitError` subclasses `KadoError`, carries
the HTTP status in `.status` (429 or 503, so a caller can tell `Retry-After`
pressure from a busy server), keeps the existing message text, and is raised
only when the retries are exhausted — a 429 that succeeds on retry is still
invisible to the caller. Existing `except KadoError` clauses catch it unchanged.

## `filter` on `list_notes` and `_search_all` — the universal filter, passed through

WHY: a weekly review reads the notes created in a period; without the filter
the client would list the whole folder and drop most of it on the caller's
side, paying a Kado page per 500 notes. Kado's search tools accept a universal
`filter` object (`modifiedAfter`/`modifiedBefore`/`createdAfter`/
`createdBefore` in Unix milliseconds, plus `path`, `tags`, `frontmatter`) that
is applied server-side on every operation. The client does not interpret it:
`filter` is an opaque dict sent verbatim as the `filter` argument, and it is
repeated on every cursor page because Kado's cursor does not carry the filter
— a page requested without it would return the unfiltered remainder. `None`
(the default) omits the key, so every existing caller's request body is
byte-for-byte unchanged.
