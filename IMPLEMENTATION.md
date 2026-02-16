# modelab — Implementation Plan

## Overview

**modelab** is a provider-agnostic Python library + self-hosted server for A/B testing LLM systems in production.

Two components:
1. **Python SDK** — zero-dep library developers install in their app (assignment, tracking, events)
2. **Server + Dashboard** — self-hosted FastAPI + React app for visualization (Docker Compose)

---

## API

```python
import modelab
from modelab import Flag, Variant, EvalContext

# Initialize
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

# Assign
ctx = EvalContext(user_id="123", session_id="abc")
assignment = modelab.assign("summarizer_v2", ctx)

if assignment is None:
    # Outside rollout — default behavior
    response = call_llm(model="gpt-3.5-turbo", prompt=text)
else:
    # In experiment — use assigned variant
    response = call_llm(
        model=assignment.config["model"],
        prompt=assignment.config["prompt"].format(input=text),
    )
    assignment.record(response, cost=0.013)

    assignment.mark_success()
    assignment.mark_custom_event("copied")

# Evaluate
results = modelab.evaluate("summarizer_v2")
```

---

## System Architecture

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

---

## File Structure

```
modelab/                         # Python SDK
    __init__.py                  # Public API: init(), assign(), evaluate()
    _types.py                    # Flag, Variant, EvalContext, records, Storage Protocol
    _engine.py                   # Deterministic hashing + bucketing
    _assignment.py               # Assignment class: record(), mark_*()
    _storage.py                  # Storage Protocol + SQLiteStorage
    _server_storage.py           # ServerStorage (HTTP + buffering)
    _aggregator.py               # Metrics evaluation queries
    _state.py                    # Module-level singleton state
    _errors.py                   # Exception hierarchy
    py.typed                     # PEP 561 marker

server/                          # FastAPI backend
    __init__.py
    app.py                       # FastAPI app + static file mount
    config.py                    # Settings via env vars
    database.py                  # Postgres connection, schema, queries
    models.py                    # Pydantic request/response schemas
    routes/
        __init__.py
        ingest.py                # POST /api/v1/ingest/*
        api.py                   # GET /api/v1/flags/*

dashboard/                       # React SPA
    package.json
    vite.config.ts
    tsconfig.json
    src/
        main.tsx
        App.tsx
        lib/
            utils.ts             # shadcn utils
            api.ts               # Fetch wrapper for server API
        components/
            ui/                  # shadcn components
            flags-table.tsx
            flag-detail.tsx
            variant-card.tsx
            metrics-chart.tsx
        pages/
            overview.tsx         # /
            flag.tsx             # /flags/:name

tests/
    conftest.py
    test_engine.py
    test_storage.py
    test_assignment.py
    test_aggregator.py
    test_integration.py

pyproject.toml
Dockerfile
docker-compose.yml
README.md
```

---

## Data Model

### assignments
| Column | Type | Description |
|--------|------|-------------|
| assignment_id | UUID PK | Unique ID |
| flag_name | TEXT | Flag identifier |
| variant_name | TEXT | Assigned variant |
| user_id | TEXT | User identifier |
| session_id | TEXT | Optional session |
| config_json | JSONB | Variant config snapshot |
| assigned_at | TIMESTAMPTZ | When assigned |

### executions (1:1 with assignments)
| Column | Type | Description |
|--------|------|-------------|
| assignment_id | UUID PK FK | Links to assignment |
| latency_ms | FLOAT | Wall-clock latency |
| input_tokens | INT | Input token count |
| output_tokens | INT | Output token count |
| cost | FLOAT | Dollar cost |
| error | TEXT | Exception message |
| metadata_json | JSONB | Arbitrary metadata |
| recorded_at | TIMESTAMPTZ | When recorded |

### events (1:N with assignments)
| Column | Type | Description |
|--------|------|-------------|
| event_id | UUID PK | Unique ID |
| assignment_id | UUID FK | Links to assignment |
| event_type | TEXT | success / failure / custom |
| event_name | TEXT | For custom events |
| payload_json | JSONB | Optional payload |
| created_at | TIMESTAMPTZ | When created |

### Indexes
- `(flag_name, variant_name)` on assignments
- `(flag_name, user_id)` on assignments
- `(assigned_at)` on assignments
- `(assignment_id)` on events
- `(assignment_id, event_type)` on events

---

## Server API

### Ingestion (from SDK)
```
POST /api/v1/ingest/assignments    body: AssignmentRecord[]
POST /api/v1/ingest/executions     body: ExecutionRecord[]
POST /api/v1/ingest/events         body: EventRecord[]
```
All accept batches. Authenticated via `X-API-Key` header.

### Dashboard API
```
GET /api/v1/flags                  → list of flags with summary stats
GET /api/v1/flags/{name}           → detailed per-variant evaluation
GET /api/v1/flags/{name}/timeline  → time-series metrics for charts
```

---

## Dashboard Pages

### Flags Overview (`/`)
- Table: flag name, variants, total assignments, success rate, status
- Click row → detail page

### Flag Detail (`/flags/:name`)
- Variant comparison cards (assignments, success rate, avg latency, avg cost)
- Charts (recharts):
  - Success rate bar chart
  - Latency comparison
  - Cost comparison
  - Assignments over time
- Events breakdown table

---

## Implementation Sequence

### Phase 1: SDK Foundation
**Files:** `_errors.py`, `_types.py`, `_engine.py`
- Exception classes: `ModelabError`, `NotInitializedError`, `FlagNotFoundError`, `InvalidFlagError`
- Dataclasses: `Flag`, `Variant`, `EvalContext`, `AssignmentRecord`, `ExecutionRecord`, `EventRecord`
- `Storage` Protocol
- Assignment engine: md5 hash → 10,000 buckets → rollout gate → weighted variant selection
- `test_engine.py`

### Phase 2: SQLite Storage
**Files:** `_storage.py`
- `SQLiteStorage` implementing `Storage` Protocol
- Schema auto-creation (idempotent)
- Thread-safe writes (`threading.Lock`, `check_same_thread=False`)
- `test_storage.py`

### Phase 3: Assignment Lifecycle
**Files:** `_assignment.py`
- `Assignment` class: properties (flag_name, variant_name, config, context)
- `record(response)` with duck-typed token extraction (OpenAI + Anthropic)
- `mark_success()`, `mark_failure()`, `mark_custom_event()`
- Fail-soft storage writes (log warnings, never crash)
- `test_assignment.py`

### Phase 4: Public API + Aggregator
**Files:** `_state.py`, `__init__.py`, `_aggregator.py`
- Module singleton: flag registry, storage reference
- `modelab.init(storage, flags)` — configure once
- `modelab.assign(flag_name, ctx)` → `Assignment | None`
- `modelab.evaluate(flag_name)` → structured dict with per-variant metrics
- SQL GROUP BY: success_rate, avg_latency, avg_cost, event counts
- `test_integration.py`, `test_aggregator.py`

### Phase 5: Server Backend
**Files:** `server/*`
- FastAPI app with CORS, static file serving
- Postgres connection with connection pool
- Schema auto-migration on startup
- Ingest routes: batch insert assignments/executions/events
- API routes: flag listing, evaluation, timeline queries
- API key middleware
- `server/requirements.txt`: fastapi, uvicorn, psycopg[binary,pool]

### Phase 6: ServerStorage
**Files:** `_server_storage.py`
- HTTP client using `urllib.request` (zero deps)
- In-memory buffer, flushes every 50 records or 5 seconds
- Background flush thread (daemon)
- `atexit` hook for remaining buffer
- Fail-soft: log warning if server unreachable

### Phase 7: Dashboard
**Files:** `dashboard/*`
- Vite + React 19 + Tailwind v4 + shadcn/ui
- API client (`lib/api.ts`)
- Overview page: flags table with shadcn `<Table>`, status badges
- Flag detail page: variant cards, recharts bar/line charts, events table
- React Router for navigation

### Phase 8: Docker + Packaging
**Files:** `Dockerfile`, `docker-compose.yml`, `pyproject.toml`, `README.md`
- Multi-stage Dockerfile (Node build → Python runtime)
- docker-compose: server + postgres
- pyproject.toml: zero deps for core, optional `[server]` extra
- README: quick start, SDK usage, self-hosting guide

---

## LOC Estimate

| Component | LOC |
|-----------|-----|
| **SDK** | **~775** |
| _errors.py | ~25 |
| _types.py | ~80 |
| _engine.py | ~70 |
| _assignment.py | ~120 |
| _storage.py | ~200 |
| _server_storage.py | ~100 |
| _aggregator.py | ~80 |
| _state.py + __init__.py | ~100 |
| **Server** | **~300** |
| **Dashboard** | **~500-600** |
| **Tests** | **~400-500** |
| **Infra** | **~100** |
| **Total** | **~2000-2200** |

---

## Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| LLM coupling | None — `assign()` returns config, dev calls their own LLM | Works with any stack |
| Events target | Assignment object only | Explicit, no ambiguity with multi-flag |
| Hashing | md5 (stdlib) | Zero deps, excellent distribution |
| Bucket count | 10,000 | 0.01% rollout granularity |
| Storage errors | Log warning, don't crash | Feature flags are auxiliary |
| Python version | 3.10+ | Modern type hints |
| SDK dependencies | Zero | Maximum adoptability |
| Server DB | PostgreSQL | Production-grade, JSONB, proper timestamps |
| Dashboard | React + shadcn/ui | Polished components, good DX |
| Deployment | Single Dockerfile, docker-compose | One command to self-host |

---

## Excluded from v1

- Async SDK
- LLM provider integrations
- Statistical significance / p-values
- Bayesian testing
- Multi-armed bandits
- Remote flag management (flags in code, dashboard is read-only)
- User auth in dashboard (API key only)
- Real-time streaming
