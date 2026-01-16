"""FastAPI web application for Captain's Log dashboard."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from captains_log.core.config import Config, get_config
from captains_log.storage.database import Database

logger = logging.getLogger(__name__)

# Global config reference for routes
_config: Config | None = None

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


def get_web_config() -> Config:
    """Get config for web routes."""
    global _config
    if _config is None:
        _config = get_config()
    return _config


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

    # Add CORS middleware for React frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Get config for directory paths
    config = get_config()

    # Mount static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # Mount screenshots directory for serving screenshot images
    screenshots_dir = config.screenshots_dir
    if screenshots_dir.exists():
        app.mount(
            "/screenshots/files",
            StaticFiles(directory=screenshots_dir),
            name="screenshot_files",
        )
        logger.info(f"Mounted screenshots directory: {screenshots_dir}")
    else:
        # Create the directory for future screenshots
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        app.mount(
            "/screenshots/files",
            StaticFiles(directory=screenshots_dir),
            name="screenshot_files",
        )
        logger.info(f"Created and mounted screenshots directory: {screenshots_dir}")

    # Setup templates
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    app.state.templates = templates

    # Import and include routes
    from captains_log.web.routes import analytics, api, dashboard, insights, screenshots

    app.include_router(dashboard.router)
    app.include_router(analytics.router)
    app.include_router(insights.router)
    app.include_router(api.router, prefix="/api")
    app.include_router(screenshots.router, prefix="/api")

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
