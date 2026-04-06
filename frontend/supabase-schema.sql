-- Captain's Log Cloud Schema for Supabase
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard/project/fupoylarelcwiewnvoyu/sql

-- Devices table
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_sync TIMESTAMPTZ
);

-- Daily aggregated stats (main data source for dashboard)
CREATE TABLE IF NOT EXISTS daily_stats (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES devices(id),
    date TEXT NOT NULL,
    total_events INTEGER,
    unique_apps INTEGER,
    top_apps JSONB,
    hourly_breakdown JSONB,
    time_blocks JSONB,
    categories JSONB,
    focus_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(device_id, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_stats_device_date ON daily_stats(device_id, date);

-- Synced activities (raw activity data)
CREATE TABLE IF NOT EXISTS synced_activities (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES devices(id),
    timestamp TIMESTAMPTZ NOT NULL,
    app_name TEXT NOT NULL,
    bundle_id TEXT,
    window_title TEXT,
    url TEXT,
    idle_seconds REAL,
    idle_status TEXT,
    work_category TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_synced_activities_device_ts ON synced_activities(device_id, timestamp);

-- Synced AI summaries
CREATE TABLE IF NOT EXISTS synced_summaries (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES devices(id),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    primary_app TEXT,
    activity_type TEXT,
    focus_score INTEGER,
    key_activities JSONB,
    context TEXT,
    context_switches INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_synced_summaries_device_period ON synced_summaries(device_id, period_start);
