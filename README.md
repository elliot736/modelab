# modelab

Provider-agnostic A/B testing for LLM systems in production.

**Two components:**
1. **Python SDK** — zero-dependency library for assignment, tracking, and evaluation
2. **Server + Dashboard** — self-hosted FastAPI + React app for visualization (Docker Compose)

## Quick Start

### SDK (local development)

```bash
pip install modelab
```

```python
import modelab
from modelab import Flag, Variant, EvalContext

# Initialize — point to the modelab server
modelab.init(
    server="http://localhost:8100",
    flags=[
        Flag(
            name="summarizer_v2",
            variants=[
                Variant("control", weight=50, config={"model": "gpt-3.5-turbo", "prompt": "Summarize: {input}"}),
                Variant("treatment", weight=50, config={"model": "gpt-4", "prompt": "Concisely summarize: {input}"}),
            ],
            rollout_pct=100,
        ),
    ],
)

# Assign a variant
ctx = EvalContext(user_id="user_123", session_id="abc")
assignment = modelab.assign("summarizer_v2", ctx)

if assignment is None:
    # Outside rollout — use default behavior
    response = call_llm(model="gpt-3.5-turbo", prompt=text)
else:
    # In experiment — use assigned variant config
    response = call_llm(
        model=assignment.config["model"],
        prompt=assignment.config["prompt"].format(input=text),
    )
    assignment.record(response, cost=0.013)
    assignment.mark_success()

# Evaluate results
results = modelab.evaluate("summarizer_v2")
print(results)
```

### Self-Hosted Server + Dashboard

```bash
docker compose up
```

This starts:
- **PostgreSQL** on port 5432
- **modelab server + dashboard** on port 8100

## Concepts

### Flags
An experiment with one or more variants and a rollout percentage (0-100%).

### Variants
Each variant has a name, weight (for traffic splitting), and a config dict you use to parameterize your LLM calls.

### Assignment
Deterministic — the same `(flag_name, user_id)` always maps to the same variant. Uses MD5 hashing into 10,000 buckets for 0.01% rollout granularity.

### Recording

Use `assignment.record(response)` to capture execution metrics. Token counts are automatically extracted from the response object via duck-typing (supports OpenAI and Anthropic response formats). Cost, latency, error, and arbitrary metadata can be passed as keyword arguments:

```python
assignment.record(response, cost=0.013, latency_ms=250.0, model="gpt-4o")
```

You can also record without a response object:

```python
assignment.record(input_tokens=50, output_tokens=100, cost=0.01)
```

### Events
Mark assignments as success/failure or record custom events (e.g., "copied", "thumbs_up").

### Evaluation
`modelab.evaluate(flag_name)` returns per-variant metrics: success rate, avg latency, avg cost, token usage, and custom event counts.

## Server API

### Ingestion (from SDK)
```
POST /api/v1/ingest/assignments    (batch)
POST /api/v1/ingest/executions     (batch)
POST /api/v1/ingest/events         (batch)
```

### Dashboard API
```
GET /api/v1/flags                  — list flags with summary stats
GET /api/v1/flags/{name}           — detailed per-variant evaluation
GET /api/v1/flags/{name}/timeline  — time-series metrics
```

## Development

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest

# Run dashboard dev server
cd dashboard && npm install && npm run dev

# Run API server (requires Postgres)
uvicorn server.app:app --reload --port 8100
```

## Architecture

```
Developer's App
│
├── modelab SDK (pip install modelab)
│   └── ServerStorage ──HTTP POST──▶ modelab-server
│
modelab-server (docker compose up)
├── FastAPI backend
├── React dashboard (served as static files)
└── PostgreSQL
```

## License

MIT
