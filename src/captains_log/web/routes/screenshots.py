"""Screenshot viewing and serving routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/screenshots", tags=["screenshots"])


class ScreenshotResponse(BaseModel):
    """Screenshot metadata response."""

    id: int
    timestamp: str
    file_path: str
    file_size_bytes: int
    width: int
    height: int
    url: str  # URL to access the screenshot


class ScreenshotStatsResponse(BaseModel):
    """Screenshot storage statistics."""

    total_count: int
    total_size_mb: float
    oldest_timestamp: str | None
    newest_timestamp: str | None
    count_today: int
    pending_cleanup: int


@router.get("/", response_model=list[ScreenshotResponse])
async def list_screenshots(
    date: str | None = Query(None, description="Date in YYYY-MM-DD format"),
    limit: int = Query(50, ge=1, le=200),
) -> list[ScreenshotResponse]:
    """List screenshots, optionally filtered by date."""
    from captains_log.web.app import get_db

    db = await get_db()

    if date:
        rows = await db.fetch_all(
            """
            SELECT id, timestamp, file_path, file_size_bytes, width, height
            FROM screenshots
            WHERE date(timestamp) = ? AND is_deleted = FALSE
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (date, limit),
        )
    else:
        rows = await db.fetch_all(
            """
            SELECT id, timestamp, file_path, file_size_bytes, width, height
            FROM screenshots
            WHERE is_deleted = FALSE
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )

    return [
        ScreenshotResponse(
            id=row["id"],
            timestamp=row["timestamp"],
            file_path=row["file_path"],
            file_size_bytes=row["file_size_bytes"],
            width=row["width"],
            height=row["height"],
            url=f"/screenshots/files/{row['file_path']}",
        )
        for row in rows
    ]


@router.get("/stats", response_model=ScreenshotStatsResponse)
async def get_screenshot_stats() -> ScreenshotStatsResponse:
    """Get screenshot storage statistics."""
    from captains_log.web.app import get_db

    db = await get_db()

    # Get overall stats
    stats_row = await db.fetch_one(
        """
        SELECT
            COUNT(*) as total_count,
            COALESCE(SUM(file_size_bytes), 0) as total_bytes,
            MIN(timestamp) as oldest,
            MAX(timestamp) as newest
        FROM screenshots
        WHERE is_deleted = FALSE
        """
    )

    # Count today's screenshots
    today = datetime.now().strftime("%Y-%m-%d")
    today_row = await db.fetch_one(
        """
        SELECT COUNT(*) as count
        FROM screenshots
        WHERE date(timestamp) = ? AND is_deleted = FALSE
        """,
        (today,),
    )

    # Get pending cleanup count
    now = datetime.utcnow().isoformat()
    pending_row = await db.fetch_one(
        """
        SELECT COUNT(*) as count
        FROM screenshots
        WHERE expires_at <= ? AND is_deleted = FALSE
        """,
        (now,),
    )

    return ScreenshotStatsResponse(
        total_count=stats_row["total_count"] if stats_row else 0,
        total_size_mb=(stats_row["total_bytes"] / (1024 * 1024)) if stats_row else 0,
        oldest_timestamp=stats_row["oldest"] if stats_row else None,
        newest_timestamp=stats_row["newest"] if stats_row else None,
        count_today=today_row["count"] if today_row else 0,
        pending_cleanup=pending_row["count"] if pending_row else 0,
    )


@router.get("/by-id/{screenshot_id}")
async def get_screenshot_by_id(screenshot_id: int) -> FileResponse:
    """Serve a screenshot image by ID."""
    from captains_log.web.app import get_db, get_web_config

    db = await get_db()
    config = get_web_config()

    row = await db.fetch_one(
        """
        SELECT file_path FROM screenshots
        WHERE id = ? AND is_deleted = FALSE
        """,
        (screenshot_id,),
    )

    if not row:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    file_path = config.screenshots_dir / row["file_path"]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Screenshot file not found")

    return FileResponse(
        path=file_path,
        media_type="image/webp",
        filename=file_path.name,
    )


@router.get("/nearest")
async def get_nearest_screenshot(
    timestamp: str = Query(..., description="ISO timestamp"),
    max_delta: int = Query(300, description="Max seconds from timestamp"),
) -> ScreenshotResponse | None:
    """Find screenshot nearest to a timestamp."""
    from captains_log.web.app import get_db

    db = await get_db()

    row = await db.fetch_one(
        """
        SELECT id, timestamp, file_path, file_size_bytes, width, height,
               ABS(strftime('%s', timestamp) - strftime('%s', ?)) as delta
        FROM screenshots
        WHERE is_deleted = FALSE
          AND ABS(strftime('%s', timestamp) - strftime('%s', ?)) <= ?
        ORDER BY delta ASC
        LIMIT 1
        """,
        (timestamp, timestamp, max_delta),
    )

    if not row:
        return None

    return ScreenshotResponse(
        id=row["id"],
        timestamp=row["timestamp"],
        file_path=row["file_path"],
        file_size_bytes=row["file_size_bytes"],
        width=row["width"],
        height=row["height"],
        url=f"/screenshots/files/{row['file_path']}",
    )


@router.get("/recent", response_model=list[ScreenshotResponse])
async def get_recent_screenshots(
    limit: int = Query(10, ge=1, le=50),
) -> list[ScreenshotResponse]:
    """Get the most recent screenshots."""
    from captains_log.web.app import get_db

    db = await get_db()

    rows = await db.fetch_all(
        """
        SELECT id, timestamp, file_path, file_size_bytes, width, height
        FROM screenshots
        WHERE is_deleted = FALSE
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    )

    return [
        ScreenshotResponse(
            id=row["id"],
            timestamp=row["timestamp"],
            file_path=row["file_path"],
            file_size_bytes=row["file_size_bytes"],
            width=row["width"],
            height=row["height"],
            url=f"/screenshots/files/{row['file_path']}",
        )
        for row in rows
    ]


@router.post("/cleanup")
async def trigger_cleanup() -> dict[str, Any]:
    """Manually trigger screenshot cleanup."""
    from captains_log.storage.screenshot_manager import ScreenshotManager
    from captains_log.web.app import get_db, get_web_config

    db = await get_db()
    config = get_web_config()

    manager = ScreenshotManager(db, config.screenshots_dir)
    files_deleted, records_updated = await manager.cleanup_expired()

    return {
        "files_deleted": files_deleted,
        "records_updated": records_updated,
    }


class ScreenshotAnalysis(BaseModel):
    """Screenshot analysis result."""

    summary: str
    activity_type: str
    key_content: str | None
    focus_indicator: str
    tokens_used: int | None = None
    estimated_cost: float | None = None


class WorkAnalysis(BaseModel):
    """Deep work analysis result."""

    # Core identification
    project: str | None
    category: str
    subcategory: str
    technologies: list[str]

    # Task context
    task_description: str | None
    file_or_document: str | None
    key_text: str | None

    # Scores
    deep_work_score: int  # 0-100
    context_richness: int  # 0-100

    # For display
    summary: str
    focus_indicator: str

    # Metadata
    tokens_used: int | None = None
    estimated_cost: float | None = None


@router.post("/analyze/{screenshot_id}", response_model=ScreenshotAnalysis)
async def analyze_single_screenshot(screenshot_id: int) -> ScreenshotAnalysis:
    """Analyze a single screenshot using Claude Haiku (basic analysis).

    Cost: ~$0.0002 per screenshot.
    """
    from captains_log.ai.screenshot_analyzer import analyze_screenshot
    from captains_log.web.app import get_db, get_web_config

    db = await get_db()
    config = get_web_config()

    # Get screenshot info
    row = await db.fetch_one(
        """
        SELECT id, file_path, timestamp
        FROM screenshots
        WHERE id = ? AND is_deleted = FALSE
        """,
        (screenshot_id,),
    )

    if not row:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    screenshot_timestamp = row["timestamp"]

    # Get nearest activity for context
    activity_row = await db.fetch_one(
        """
        SELECT app_name, window_title
        FROM activity_logs
        WHERE ABS(strftime('%s', timestamp) - strftime('%s', ?)) < 60
        ORDER BY ABS(strftime('%s', timestamp) - strftime('%s', ?))
        LIMIT 1
        """,
        (screenshot_timestamp, screenshot_timestamp),
    )

    app_name = activity_row["app_name"] if activity_row else None
    window_title = activity_row["window_title"] if activity_row else None

    file_path = config.screenshots_dir / row["file_path"]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Screenshot file not found")

    # Analyze the screenshot
    result = await analyze_screenshot(
        file_path,
        app_name=app_name,
        window_title=window_title,
    )

    # Store the analysis result
    await db.execute(
        """
        UPDATE screenshots
        SET analysis_summary = ?, analysis_type = ?, analysis_focus = ?
        WHERE id = ?
        """,
        (result.get("summary"), result.get("activity_type"), result.get("focus_indicator"), screenshot_id),
    )

    return ScreenshotAnalysis(
        summary=result.get("summary", ""),
        activity_type=result.get("activity_type", "unknown"),
        key_content=result.get("key_content"),
        focus_indicator=result.get("focus_indicator", "neutral"),
        tokens_used=result.get("tokens_used"),
        estimated_cost=result.get("estimated_cost"),
    )


@router.post("/analyze-deep/{screenshot_id}", response_model=WorkAnalysis)
async def analyze_screenshot_deep(screenshot_id: int) -> WorkAnalysis:
    """Deep work analysis of a screenshot with full context.

    Extracts:
    - Project/repository being worked on
    - Work category and subcategory
    - Technologies used
    - Task description
    - Deep work score

    Cost: ~$0.0004 per screenshot (more tokens for richer output).
    """
    import json

    from captains_log.ai.work_analyzer import analyze_work_context
    from captains_log.web.app import get_db, get_web_config

    db = await get_db()
    config = get_web_config()

    # Get screenshot info
    row = await db.fetch_one(
        """
        SELECT id, file_path, timestamp
        FROM screenshots
        WHERE id = ? AND is_deleted = FALSE
        """,
        (screenshot_id,),
    )

    if not row:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    screenshot_timestamp = row["timestamp"]

    # Get nearest activity for richer context
    activity_row = await db.fetch_one(
        """
        SELECT app_name, window_title, url
        FROM activity_logs
        WHERE ABS(strftime('%s', timestamp) - strftime('%s', ?)) < 60
        ORDER BY ABS(strftime('%s', timestamp) - strftime('%s', ?))
        LIMIT 1
        """,
        (screenshot_timestamp, screenshot_timestamp),
    )

    app_name = activity_row["app_name"] if activity_row else None
    window_title = activity_row["window_title"] if activity_row else None
    url = activity_row["url"] if activity_row else None

    # Get recent activities for additional context
    recent_activities = await db.fetch_all(
        """
        SELECT app_name, window_title, url
        FROM activity_logs
        WHERE timestamp <= ?
        ORDER BY timestamp DESC
        LIMIT 5
        """,
        (screenshot_timestamp,),
    )

    file_path = config.screenshots_dir / row["file_path"]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Screenshot file not found")

    # Deep analysis with full context
    result = await analyze_work_context(
        file_path,
        app_name=app_name,
        window_title=window_title,
        url=url,
        recent_activities=recent_activities,
    )

    # Store the rich analysis result
    visible_content = result.get("visible_content", {})
    await db.execute(
        """
        UPDATE screenshots
        SET analysis_summary = ?,
            analysis_type = ?,
            analysis_focus = ?,
            analysis_cost = ?,
            analysis_project = ?,
            analysis_category = ?,
            analysis_subcategory = ?,
            analysis_technologies = ?,
            analysis_task = ?,
            analysis_file = ?,
            analysis_deep_work_score = ?,
            analysis_context_richness = ?,
            analysis_full = ?,
            analyzed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            result.get("summary"),
            result.get("category"),
            result.get("focus_indicator"),
            result.get("estimated_cost"),
            result.get("project"),
            result.get("category"),
            result.get("subcategory"),
            json.dumps(result.get("technologies", [])),
            result.get("task_description"),
            visible_content.get("file_or_document"),
            result.get("deep_work_score", 0),
            result.get("context_richness", 0),
            json.dumps(result),
            screenshot_id,
        ),
    )

    return WorkAnalysis(
        project=result.get("project"),
        category=result.get("category", "unknown"),
        subcategory=result.get("subcategory", "unknown"),
        technologies=result.get("technologies", []),
        task_description=result.get("task_description"),
        file_or_document=visible_content.get("file_or_document"),
        key_text=visible_content.get("key_text"),
        deep_work_score=result.get("deep_work_score", 0),
        context_richness=result.get("context_richness", 0),
        summary=result.get("summary", ""),
        focus_indicator=result.get("focus_indicator", "neutral"),
        tokens_used=result.get("tokens_used"),
        estimated_cost=result.get("estimated_cost"),
    )


class BulkAnalysisResponse(BaseModel):
    """Bulk analysis result."""
    total: int
    analyzed: int
    failed: int
    total_cost: float
    results: list[dict[str, Any]]


@router.post("/analyze-bulk", response_model=BulkAnalysisResponse)
async def analyze_screenshots_bulk(
    date: str | None = Query(None, description="Date in YYYY-MM-DD format"),
    limit: int = Query(50, ge=1, le=200),
    skip_analyzed: bool = Query(True, description="Skip already analyzed screenshots"),
) -> BulkAnalysisResponse:
    """Bulk deep analysis of screenshots.

    Analyzes multiple screenshots in sequence.
    Cost: ~$0.0006 per screenshot.
    """
    import json

    from captains_log.ai.work_analyzer import analyze_work_context
    from captains_log.web.app import get_db, get_web_config

    db = await get_db()
    config = get_web_config()

    # Get screenshots to analyze
    if date:
        if skip_analyzed:
            rows = await db.fetch_all(
                """
                SELECT id, file_path, timestamp
                FROM screenshots
                WHERE date(timestamp) = ? AND is_deleted = FALSE
                  AND (analysis_project IS NULL OR analysis_project = '')
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (date, limit),
            )
        else:
            rows = await db.fetch_all(
                """
                SELECT id, file_path, timestamp
                FROM screenshots
                WHERE date(timestamp) = ? AND is_deleted = FALSE
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (date, limit),
            )
    else:
        if skip_analyzed:
            rows = await db.fetch_all(
                """
                SELECT id, file_path, timestamp
                FROM screenshots
                WHERE is_deleted = FALSE
                  AND (analysis_project IS NULL OR analysis_project = '')
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
        else:
            rows = await db.fetch_all(
                """
                SELECT id, file_path, timestamp
                FROM screenshots
                WHERE is_deleted = FALSE
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )

    results = []
    total_cost = 0.0
    analyzed = 0
    failed = 0

    for row in rows:
        screenshot_id = row["id"]
        screenshot_timestamp = row["timestamp"]

        try:
            # Get activity context
            activity_row = await db.fetch_one(
                """
                SELECT app_name, window_title, url
                FROM activity_logs
                WHERE ABS(strftime('%s', timestamp) - strftime('%s', ?)) < 60
                ORDER BY ABS(strftime('%s', timestamp) - strftime('%s', ?))
                LIMIT 1
                """,
                (screenshot_timestamp, screenshot_timestamp),
            )

            app_name = activity_row["app_name"] if activity_row else None
            window_title = activity_row["window_title"] if activity_row else None
            url = activity_row["url"] if activity_row else None

            # Get recent activities
            recent_activities = await db.fetch_all(
                """
                SELECT app_name, window_title, url
                FROM activity_logs
                WHERE timestamp <= ?
                ORDER BY timestamp DESC
                LIMIT 5
                """,
                (screenshot_timestamp,),
            )

            file_path = config.screenshots_dir / row["file_path"]

            if not file_path.exists():
                failed += 1
                results.append({"id": screenshot_id, "error": "File not found"})
                continue

            # Deep analysis
            result = await analyze_work_context(
                file_path,
                app_name=app_name,
                window_title=window_title,
                url=url,
                recent_activities=recent_activities,
            )

            # Store result
            visible_content = result.get("visible_content", {})
            await db.execute(
                """
                UPDATE screenshots
                SET analysis_summary = ?,
                    analysis_type = ?,
                    analysis_focus = ?,
                    analysis_cost = ?,
                    analysis_project = ?,
                    analysis_category = ?,
                    analysis_subcategory = ?,
                    analysis_technologies = ?,
                    analysis_task = ?,
                    analysis_file = ?,
                    analysis_deep_work_score = ?,
                    analysis_context_richness = ?,
                    analysis_full = ?,
                    analyzed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    result.get("summary"),
                    result.get("category"),
                    result.get("focus_indicator"),
                    result.get("estimated_cost"),
                    result.get("project"),
                    result.get("category"),
                    result.get("subcategory"),
                    json.dumps(result.get("technologies", [])),
                    result.get("task_description"),
                    visible_content.get("file_or_document"),
                    result.get("deep_work_score", 0),
                    result.get("context_richness", 0),
                    json.dumps(result),
                    screenshot_id,
                ),
            )

            cost = result.get("estimated_cost", 0) or 0
            total_cost += cost
            analyzed += 1

            results.append({
                "id": screenshot_id,
                "project": result.get("project"),
                "category": result.get("category"),
                "deep_work_score": result.get("deep_work_score"),
                "cost": cost,
            })

        except Exception as e:
            failed += 1
            results.append({"id": screenshot_id, "error": str(e)})

    return BulkAnalysisResponse(
        total=len(rows),
        analyzed=analyzed,
        failed=failed,
        total_cost=round(total_cost, 6),
        results=results,
    )


@router.get("/analysis/{screenshot_id}")
async def get_screenshot_analysis(screenshot_id: int) -> dict[str, Any]:
    """Get cached analysis for a screenshot."""
    from captains_log.web.app import get_db

    db = await get_db()

    row = await db.fetch_one(
        """
        SELECT analysis_summary, analysis_type, analysis_focus
        FROM screenshots
        WHERE id = ? AND is_deleted = FALSE
        """,
        (screenshot_id,),
    )

    if not row:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    if not row["analysis_summary"]:
        return {"analyzed": False}

    return {
        "analyzed": True,
        "summary": row["analysis_summary"],
        "activity_type": row["analysis_type"],
        "focus_indicator": row["analysis_focus"],
    }
