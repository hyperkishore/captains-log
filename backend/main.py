"""Captain's Log Cloud API - Sync and serve activity data."""
import os
from datetime import datetime, date
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import engine, get_db, Base
from models import Device, SyncedActivity, SyncedSummary, DailyStats

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Captain's Log Cloud API",
    description="Cloud sync and data serving for Captain's Log activity tracker",
    version="0.2.0",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Pydantic Models ============

class DeviceRegister(BaseModel):
    device_id: str
    name: Optional[str] = None


class ActivitySync(BaseModel):
    device_id: str
    activities: list[dict]


class DailyStatsSync(BaseModel):
    device_id: str
    date: str
    total_events: int
    unique_apps: int
    top_apps: list[dict]
    hourly_breakdown: list[dict]
    time_blocks: Optional[list[dict]] = None
    categories: Optional[dict] = None
    focus_data: Optional[list[dict]] = None


class SummarySync(BaseModel):
    device_id: str
    summaries: list[dict]


# ============ Health & Info ============

@app.get("/")
def root():
    return {
        "service": "Captain's Log Cloud API",
        "version": "0.1.0",
        "status": "healthy",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# ============ Device Registration ============

@app.post("/api/devices/register")
def register_device(data: DeviceRegister, db: Session = Depends(get_db)):
    """Register a new device or update existing."""
    device = db.query(Device).filter(Device.id == data.device_id).first()
    if device:
        device.name = data.name or device.name
        device.last_sync = datetime.utcnow()
    else:
        device = Device(id=data.device_id, name=data.name)
        db.add(device)
    db.commit()
    return {"status": "registered", "device_id": data.device_id}


@app.get("/api/devices/{device_id}")
def get_device(device_id: str, db: Session = Depends(get_db)):
    """Get device info."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return {
        "id": device.id,
        "name": device.name,
        "created_at": device.created_at.isoformat() if device.created_at else None,
        "last_sync": device.last_sync.isoformat() if device.last_sync else None,
    }


# ============ Sync Endpoints ============

@app.post("/api/sync/activities")
def sync_activities(data: ActivitySync, db: Session = Depends(get_db)):
    """Receive activity data from local daemon."""
    count = 0
    for activity in data.activities:
        synced = SyncedActivity(
            device_id=data.device_id,
            timestamp=datetime.fromisoformat(activity["timestamp"]),
            app_name=activity["app_name"],
            bundle_id=activity.get("bundle_id"),
            window_title=activity.get("window_title"),
            url=activity.get("url"),
            idle_seconds=activity.get("idle_seconds"),
            idle_status=activity.get("idle_status"),
            work_category=activity.get("work_category"),
        )
        db.add(synced)
        count += 1

    # Update device last_sync
    device = db.query(Device).filter(Device.id == data.device_id).first()
    if device:
        device.last_sync = datetime.utcnow()

    db.commit()
    return {"status": "synced", "count": count}


@app.post("/api/sync/daily-stats")
def sync_daily_stats(data: DailyStatsSync, db: Session = Depends(get_db)):
    """Receive daily aggregated stats from local daemon."""
    # Upsert daily stats
    existing = db.query(DailyStats).filter(
        DailyStats.device_id == data.device_id,
        DailyStats.date == data.date
    ).first()

    if existing:
        existing.total_events = data.total_events
        existing.unique_apps = data.unique_apps
        existing.top_apps = data.top_apps
        existing.hourly_breakdown = data.hourly_breakdown
        existing.time_blocks = data.time_blocks
        existing.categories = data.categories
        existing.focus_data = data.focus_data
        existing.updated_at = datetime.utcnow()
    else:
        stats = DailyStats(
            device_id=data.device_id,
            date=data.date,
            total_events=data.total_events,
            unique_apps=data.unique_apps,
            top_apps=data.top_apps,
            hourly_breakdown=data.hourly_breakdown,
            time_blocks=data.time_blocks,
            categories=data.categories,
            focus_data=data.focus_data,
        )
        db.add(stats)

    # Update device last_sync
    device = db.query(Device).filter(Device.id == data.device_id).first()
    if device:
        device.last_sync = datetime.utcnow()

    db.commit()
    return {"status": "synced", "date": data.date}


@app.post("/api/sync/summaries")
def sync_summaries(data: SummarySync, db: Session = Depends(get_db)):
    """Receive AI summaries from local daemon."""
    count = 0
    for summary in data.summaries:
        synced = SyncedSummary(
            device_id=data.device_id,
            period_start=datetime.fromisoformat(summary["period_start"]),
            period_end=datetime.fromisoformat(summary["period_end"]),
            primary_app=summary.get("primary_app"),
            activity_type=summary.get("activity_type"),
            focus_score=summary.get("focus_score"),
            key_activities=summary.get("key_activities"),
            context=summary.get("context"),
            context_switches=summary.get("context_switches"),
        )
        db.add(synced)
        count += 1

    db.commit()
    return {"status": "synced", "count": count}


# ============ Data Retrieval (for Frontend) ============

@app.get("/api/{device_id}/stats/{date_str}")
def get_stats(device_id: str, date_str: str, db: Session = Depends(get_db)):
    """Get daily stats for a device."""
    stats = db.query(DailyStats).filter(
        DailyStats.device_id == device_id,
        DailyStats.date == date_str
    ).first()

    if not stats:
        raise HTTPException(status_code=404, detail="No data for this date")

    return {
        "date": stats.date,
        "total_events": stats.total_events,
        "unique_apps": stats.unique_apps,
        "top_apps": stats.top_apps or [],
        "hourly_breakdown": stats.hourly_breakdown or [],
    }


@app.get("/api/{device_id}/time-blocks/{date_str}")
def get_time_blocks(device_id: str, date_str: str, db: Session = Depends(get_db)):
    """Get time blocks for a device."""
    stats = db.query(DailyStats).filter(
        DailyStats.device_id == device_id,
        DailyStats.date == date_str
    ).first()

    if not stats or not stats.time_blocks:
        return []

    return stats.time_blocks


@app.get("/api/{device_id}/pareto/{date_str}")
def get_pareto(device_id: str, date_str: str, db: Session = Depends(get_db)):
    """Get Pareto analysis for a device."""
    stats = db.query(DailyStats).filter(
        DailyStats.device_id == device_id,
        DailyStats.date == date_str
    ).first()

    if not stats or not stats.top_apps:
        return {"top_apps": [], "rest_apps": [], "ratio": "0/0", "top_percent": 0}

    # Calculate Pareto from top_apps
    top_apps = stats.top_apps[:3] if stats.top_apps else []
    rest_apps = stats.top_apps[3:] if len(stats.top_apps) > 3 else []
    total = sum(a.get("count", 0) for a in stats.top_apps)

    result_top = []
    cumulative = 0
    for app in top_apps:
        count = app.get("count", 0)
        percent = (count / total * 100) if total > 0 else 0
        cumulative += percent
        result_top.append({
            "app": app.get("app_name", "Unknown"),
            "count": count,
            "percent": round(percent, 1),
            "cumulative_percent": round(cumulative, 1),
        })

    result_rest = []
    for app in rest_apps:
        count = app.get("count", 0)
        percent = (count / total * 100) if total > 0 else 0
        cumulative += percent
        result_rest.append({
            "app": app.get("app_name", "Unknown"),
            "count": count,
            "percent": round(percent, 1),
            "cumulative_percent": round(cumulative, 1),
        })

    return {
        "top_apps": result_top,
        "rest_apps": result_rest,
        "ratio": f"{len(top_apps)}/{stats.unique_apps}",
        "top_percent": 20,
    }


@app.get("/api/{device_id}/insights/{date_str}")
def get_insights(device_id: str, date_str: str, db: Session = Depends(get_db)):
    """Get insights for a device."""
    stats = db.query(DailyStats).filter(
        DailyStats.device_id == device_id,
        DailyStats.date == date_str
    ).first()

    if not stats:
        raise HTTPException(status_code=404, detail="No data for this date")

    # Generate basic insights from stats
    categories = stats.categories or {}
    top_category = max(categories.items(), key=lambda x: x[1])[0] if categories else "Unknown"

    # Estimate deep work (simplified)
    dev_events = categories.get("Development", 0) + categories.get("Productivity", 0)
    deep_work_minutes = int(dev_events * 0.5)  # Rough estimate

    wins = []
    improvements = []

    if stats.total_events > 200:
        wins.append({
            "title": "Active day",
            "description": f"Logged {stats.total_events} activity events!",
        })

    if deep_work_minutes > 120:
        wins.append({
            "title": f"{deep_work_minutes // 60}+ hours of focused work",
            "description": "Great concentration today!",
        })

    return {
        "narrative": f"A day focused on {top_category.lower()} work.",
        "metrics": {
            "total_events": stats.total_events,
            "context_switches": stats.total_events // 10,  # Rough estimate
            "deep_work_minutes": deep_work_minutes,
            "productive_hours": round(stats.total_events * 0.5 / 60, 1),
            "top_category": top_category,
            "focus_score": min(100, deep_work_minutes // 2),
        },
        "wins": wins,
        "improvements": improvements,
        "recommendations": [],
    }


@app.get("/api/{device_id}/focus/{date_str}")
def get_focus(device_id: str, date_str: str, db: Session = Depends(get_db)):
    """Get focus data for a device."""
    stats = db.query(DailyStats).filter(
        DailyStats.device_id == device_id,
        DailyStats.date == date_str
    ).first()

    if not stats or not stats.focus_data:
        return []

    return stats.focus_data


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
