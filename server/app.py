"""FastAPI application — entrypoint for the modelab server."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.config import settings
from server.database import close_pool, init_pool, init_schema
from server.routes import api, ingest


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_pool()
    init_schema()
    yield
    close_pool()


app = FastAPI(title="modelab", version="0.1.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API key middleware
@app.middleware("http")
async def check_api_key(request: Request, call_next) -> Response:
    if settings.API_KEY and request.url.path.startswith("/api/v1/ingest"):
        key = request.headers.get("X-API-Key", "")
        if key != settings.API_KEY:
            return Response(content="Unauthorized", status_code=401)
    return await call_next(request)


# Routes
app.include_router(ingest.router)
app.include_router(api.router)

# Serve dashboard static files if they exist
_dashboard_dir = Path(__file__).parent.parent / "dashboard" / "dist"
if _dashboard_dir.exists():
    app.mount("/", StaticFiles(directory=str(_dashboard_dir), html=True), name="dashboard")
