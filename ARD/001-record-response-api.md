# ARD-001: Replace `track()` with `record(response)`

**Status:** Accepted
**Date:** 2026-02-16

## Context

The `track()` context manager forced users to nest their LLM calls inside modelab:

```python
with assignment.track() as t:
    response = client.chat.completions.create(...)
    t.set_tokens(input=usage.prompt_tokens, output=usage.completion_tokens)
    t.set_cost(0.013)
```

This couples user code to the SDK. Users with existing wrappers (LangSmith, Sentry, custom middleware) cannot compose them with `track()` — context managers don't compose cleanly. modelab should observe LLM calls, not own their execution.

## Decision

Remove `track()` and `_Tracker` entirely. Extend `record()` to accept a provider response object as its first positional argument and auto-extract token usage via duck-typing:

```python
response = client.chat.completions.create(...)
assignment.record(response, cost=0.013)
```

Duck-typing order:
1. **OpenAI**: `response.usage.prompt_tokens` / `response.usage.completion_tokens`
2. **Anthropic**: `response.usage.input_tokens` / `response.usage.output_tokens`

Explicit keyword arguments (`input_tokens=`, `output_tokens=`) always override extracted values. The backward-compatible kwargs-only call still works:

```python
assignment.record(input_tokens=50, output_tokens=100, cost=0.01)
```

## Consequences

### Positive

- **No coupling**: Users call their LLM however they want, then pass the response to `record()`.
- **Composable**: Works alongside any other middleware, wrappers, or observability tools.
- **Zero dependencies**: Duck-typing via `getattr` — no provider imports needed.
- **Simpler API surface**: One method (`record`) instead of a context manager + 3 setter methods.

### Negative

- **No auto-latency**: `track()` measured wall-clock time automatically. Users who want latency now measure it externally and pass `latency_ms=`.
- **No auto-error capture**: `track()` caught exceptions and recorded them. Users now use try/except and pass `error=` + call `mark_failure()`.
- **Breaking change**: All code using `track()`, `set_tokens()`, `set_cost()`, `set_metadata()` must migrate.

### Design decisions within this change

- **Cost stays manual**: Provider pricing changes too frequently for reliable auto-calculation.
- **No auto-latency**: Acceptable tradeoff — users who need it measure externally. Keeps the SDK stateless.
- **No auto-error capture**: Users call `mark_failure()` for explicit error handling. Cleaner separation of concerns.
- **Duck-typing order**: OpenAI first (larger market share), then Anthropic. Both are tried via `getattr` with no short-circuiting penalty.
