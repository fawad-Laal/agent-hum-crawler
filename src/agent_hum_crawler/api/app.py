"""FastAPI application factory for the Moltis dashboard API (Phase B).

Usage::

    # From scripts/dashboard_api.py
    from agent_hum_crawler.api.app import create_app
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8788)

All route modules live under :mod:`agent_hum_crawler.api.routes`.
The API surface is identical to the legacy ``http.server`` implementation
so the TypeScript frontend requires no changes.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    """Construct and return the configured FastAPI application."""
    app = FastAPI(
        title="Moltis Dashboard API",
        version="2.0.0",
        description=(
            "Humanitarian disaster intelligence platform — "
            "Phase B: direct Python calls, async job system."
        ),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # ── CORS (allow the Vite dev server on :5175 and any localhost) ───────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5175", "http://127.0.0.1:5175", "http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    # ── Mount all route modules under /api prefix ─────────────────────────
    from .routes.health import router as health_router
    from .routes.jobs import router as jobs_router
    from .routes.overview import router as overview_router
    from .routes.cycle import router as cycle_router
    from .routes.reports import router as reports_router
    from .routes.situation_analysis import router as sa_router
    from .routes.workbench import router as workbench_router
    from .routes.db import router as db_router
    from .routes.settings import router as settings_router

    for rtr in (
        health_router,
        jobs_router,
        overview_router,
        cycle_router,
        reports_router,
        sa_router,
        workbench_router,
        db_router,
        settings_router,
    ):
        app.include_router(rtr, prefix="/api")

    return app
