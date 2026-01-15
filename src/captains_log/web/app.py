"""FastAPI web application for Captain's Log dashboard."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from captains_log.core.config import get_config
from captains_log.storage.database import Database

logger = logging.getLogger(__name__)

# Paths
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

# Global database connection for web app
_db: Database | None = None


async def get_db() -> Database:
    """Get database connection."""
    global _db
    if _db is None:
        config = get_config()
        _db = Database(config.db_path)
        await _db.connect()
    return _db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Captain's Log dashboard...")
    config = get_config()

    global _db
    _db = Database(config.db_path)
    await _db.connect()

    yield

    # Shutdown
    if _db:
        await _db.close()
        _db = None
    logger.info("Dashboard shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Captain's Log",
        description="Personal Activity Tracking Dashboard",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Mount static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # Setup templates
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    app.state.templates = templates

    # Import and include routes
    from captains_log.web.routes import api, dashboard

    app.include_router(dashboard.router)
    app.include_router(api.router, prefix="/api")

    return app


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run the web server."""
    import uvicorn

    config = get_config()
    host = config.web.host
    port = config.web.port

    logger.info(f"Starting dashboard at http://{host}:{port}")

    uvicorn.run(
        "captains_log.web.app:create_app",
        host=host,
        port=port,
        factory=True,
        log_level="info",
    )
