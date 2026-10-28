# WHY: lib/kado_client.py

> Rationale for the request-budget additions to `tomo/scripts/lib/kado_client.py`
> (spec 042, ADR-4). The rest of the client is documented in its docstrings.

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
