// API Response Types for Captain's Log

export interface Activity {
  id: number;
  timestamp: string;
  app_name: string;
  bundle_id: string | null;
  window_title: string | null;
  url: string | null;
  idle_status: 'ACTIVE' | 'IDLE_BUT_PRESENT' | 'AWAY' | 'WATCHING_MEDIA' | 'READING';
  idle_seconds: number | null;
  work_category: string | null;
  work_project: string | null;
  engagement_score: number | null;
}

export interface TimeBlock {
  hour: number;
  hour_label: string;
  categories: Record<string, number>;
  total: number;
  primary_category: string;
}

export interface CategoryBreakdown {
  category: string;
  count: number;
  percent: number;
  minutes: number;
  top_apps: { app: string; count: number }[];
}

export interface ProjectBreakdown {
  project: string;
  count: number;
  percent: number;
  minutes: number;
  primary_app: string;
}

export interface ParetoAnalysis {
  top_apps: {
    app: string;
    count: number;
    percent: number;
    cumulative_percent: number;
  }[];
  rest_apps: {
    app: string;
    count: number;
    percent: number;
    cumulative_percent: number;
  }[];
  ratio: string;
  top_percent: number;
}

export interface FocusDataPoint {
  time: string;
  timestamp: string;
  focus_score: number;
  context_switches: number;
  event_count: number;
}

export interface DeepWorkSession {
  app: string;
  category: string;
  start: string;
  duration_min: number;
  events: number;
}

export interface DailyStats {
  date: string;
  total_events: number;
  unique_apps: number;
  top_apps: { app_name: string; count: number }[];
  hourly_breakdown: { hour: string; count: number }[];
}

export interface TreemapNode {
  name: string;
  value?: number;
  children?: TreemapNode[];
}

export interface HeatmapCell {
  date: string;
  day: number;
  score: number;
  level: number;
  is_today: boolean;
}

export interface CategoryTrend {
  category: string;
  this_week_pct: number;
  last_week_pct: number;
  change: number;
  direction: 'up' | 'down' | 'same';
}

export interface PeakHour {
  hour: number;
  label: string;
  this_week_pct: number;
  last_week_pct: number;
}

export interface Pattern {
  icon: string;
  title: string;
  description: string;
}

export interface Win {
  title: string;
  description: string;
  metric?: string;
}

export interface Improvement {
  title: string;
  description: string;
  severity: 'warning' | 'info';
}

export interface Recommendation {
  title: string;
  description: string;
  action?: string;
  priority: 'high' | 'medium' | 'low';
}

export interface Insights {
  narrative: string;
  wins: Win[];
  improvements: Improvement[];
  recommendations: Recommendation[];
  metrics: {
    total_events: number;
    context_switches: number;
    deep_work_minutes: number;
    productive_hours: number;
    top_category: string;
    focus_score?: number;
  };
}

export interface Screenshot {
  id: number;
  timestamp: string;
  file_path: string;
  file_size_bytes: number;
  width: number;
  height: number;
  url: string;
}

export interface WeeklyReflection {
  total_hours: number;
  deep_work_hours: number;
  top_category: string;
  wins: number;
  improvements: number;
}
