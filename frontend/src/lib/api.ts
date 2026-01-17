// API Client for Captain's Log
// Version: 0.2.0
export const API_VERSION = '0.2.0';

import type {
  Activity,
  TimeBlock,
  CategoryBreakdown,
  ProjectBreakdown,
  ParetoAnalysis,
  FocusDataPoint,
  DeepWorkSession,
  DailyStats,
  TreemapNode,
  HeatmapCell,
  CategoryTrend,
  PeakHour,
  Pattern,
  Insights,
  Screenshot,
} from './types';

// Local backend URL
const LOCAL_API = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

// Cloud API URL (Railway)
const CLOUD_API = process.env.NEXT_PUBLIC_CLOUD_API_URL || 'https://generous-gentleness-production.up.railway.app';

// Get device ID from URL or localStorage
export function getDeviceId(): string | null {
  if (typeof window === 'undefined') return null;

  // Check URL parameter first
  const params = new URLSearchParams(window.location.search);
  const urlDeviceId = params.get('device');
  if (urlDeviceId) {
    // Store in localStorage for persistence
    localStorage.setItem('captains_log_device_id', urlDeviceId);
    return urlDeviceId;
  }

  // Fall back to localStorage
  return localStorage.getItem('captains_log_device_id');
}

// Check if we're using cloud mode
export function isCloudMode(): boolean {
  return getDeviceId() !== null;
}

// Get the appropriate API base URL
export function getApiBase(): string {
  const deviceId = getDeviceId();
  if (deviceId) {
    return CLOUD_API;
  }
  return LOCAL_API;
}

// Get cloud URL with device ID prefix for endpoints
function getCloudEndpoint(endpoint: string, deviceId: string): string {
  // Transform /api/stats/2026-01-16 -> /api/{deviceId}/stats/2026-01-16
  if (endpoint.startsWith('/api/stats/')) {
    return endpoint.replace('/api/stats/', `/api/${deviceId}/stats/`);
  }
  if (endpoint.startsWith('/api/analytics/time-blocks/')) {
    return endpoint.replace('/api/analytics/time-blocks/', `/api/${deviceId}/time-blocks/`);
  }
  if (endpoint.startsWith('/api/analytics/pareto/')) {
    return endpoint.replace('/api/analytics/pareto/', `/api/${deviceId}/pareto/`);
  }
  if (endpoint.startsWith('/api/insights/daily/')) {
    return endpoint.replace('/api/insights/daily/', `/api/${deviceId}/insights/`);
  }
  if (endpoint.startsWith('/api/analytics/focus/')) {
    return endpoint.replace('/api/analytics/focus/', `/api/${deviceId}/focus/`);
  }
  // Default: not supported in cloud mode
  return endpoint;
}

async function fetchAPI<T>(endpoint: string): Promise<T> {
  const deviceId = getDeviceId();
  let url: string;

  if (deviceId) {
    // Cloud mode: use cloud API with device-prefixed endpoint
    url = `${CLOUD_API}${getCloudEndpoint(endpoint, deviceId)}`;
  } else {
    // Local mode: use local API
    url = `${LOCAL_API}${endpoint}`;
  }

  console.log(`[Captain's Log] Fetching: ${url}`);

  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.error(`[Captain's Log] API error: ${res.status} ${res.statusText} for ${url}`);
      throw new Error(`API error: ${res.status} ${res.statusText}`);
    }
    const data = await res.json();
    console.log(`[Captain's Log] Success: ${endpoint}`, data);
    return data;
  } catch (error) {
    console.error(`[Captain's Log] Fetch failed for ${url}:`, error);
    throw error;
  }
}

// Health check
export async function getHealth() {
  return fetchAPI<{
    status: string;
    database_connected: boolean;
    database_size_mb: number;
    total_activities: number;
  }>('/api/health');
}

// Activities
export async function getActivities(date?: string, limit = 100, offset = 0): Promise<Activity[]> {
  const params = new URLSearchParams();
  if (date) params.set('date', date);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  return fetchAPI<Activity[]>(`/api/activities?${params}`);
}

export async function getStats(date: string): Promise<DailyStats> {
  return fetchAPI<DailyStats>(`/api/stats/${date}`);
}

export async function getTimeline(date: string): Promise<Activity[]> {
  // Use activities endpoint which returns individual events with proper format
  return fetchAPI<Activity[]>(`/api/activities?date=${date}&limit=500`);
}

// App Summary
export async function getAppsSummary(days = 7) {
  return fetchAPI<{
    app_name: string;
    bundle_id: string;
    total_events: number;
    active_days: number;
  }[]>(`/api/apps/summary?days=${days}`);
}

// Analytics
export async function getTimeBlocks(date: string): Promise<TimeBlock[]> {
  return fetchAPI<TimeBlock[]>(`/api/analytics/time-blocks/${date}`);
}

export async function getTreemap(date: string): Promise<TreemapNode> {
  return fetchAPI<TreemapNode>(`/api/analytics/treemap/${date}`);
}

export async function getPareto(date: string): Promise<ParetoAnalysis> {
  return fetchAPI<ParetoAnalysis>(`/api/analytics/pareto/${date}`);
}

export async function getFocusHistory(days = 28): Promise<{
  date: string;
  focus_score: number;
  event_count: number;
}[]> {
  return fetchAPI(`/api/analytics/focus-history?days=${days}`);
}

// Insights
export async function getDailyInsights(date: string): Promise<Insights> {
  return fetchAPI<Insights>(`/api/insights/daily/${date}`);
}

// Screenshots
export async function getScreenshots(date?: string, limit = 50): Promise<Screenshot[]> {
  const params = new URLSearchParams();
  if (date) params.set('date', date);
  params.set('limit', String(limit));
  return fetchAPI<Screenshot[]>(`/api/screenshots/?${params}`);
}

export async function getRecentScreenshots(limit = 10): Promise<Screenshot[]> {
  return fetchAPI<Screenshot[]>(`/api/screenshots/recent?limit=${limit}`);
}

export async function getNearestScreenshot(timestamp: string, maxDelta = 300): Promise<Screenshot | null> {
  try {
    return await fetchAPI<Screenshot>(`/api/screenshots/nearest?timestamp=${encodeURIComponent(timestamp)}&max_delta=${maxDelta}`);
  } catch {
    return null;
  }
}

// Screenshot URL helper
export function getScreenshotUrl(screenshot: Screenshot): string {
  // Screenshots are only available in local mode
  return `${LOCAL_API}/screenshots/files/${screenshot.file_path}`;
}

// Screenshot analysis
export interface ScreenshotAnalysis {
  summary: string;
  activity_type: string;
  key_content: string | null;
  focus_indicator: string;
  tokens_used: number | null;
  estimated_cost: number | null;
}

// Deep work analysis
export interface WorkAnalysis {
  project: string | null;
  category: string;
  subcategory: string;
  technologies: string[];
  task_description: string | null;
  file_or_document: string | null;
  key_text: string | null;
  deep_work_score: number;
  context_richness: number;
  summary: string;
  focus_indicator: string;
  tokens_used: number | null;
  estimated_cost: number | null;
}

export async function analyzeScreenshot(screenshotId: number): Promise<ScreenshotAnalysis> {
  const res = await fetch(`${LOCAL_API}/api/screenshots/analyze/${screenshotId}`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error(`Analysis failed: ${res.status}`);
  }
  return res.json();
}

export async function analyzeScreenshotDeep(screenshotId: number): Promise<WorkAnalysis> {
  const res = await fetch(`${LOCAL_API}/api/screenshots/analyze-deep/${screenshotId}`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error(`Deep analysis failed: ${res.status}`);
  }
  return res.json();
}

export async function getScreenshotAnalysis(screenshotId: number): Promise<{
  analyzed: boolean;
  summary?: string;
  activity_type?: string;
  focus_indicator?: string;
}> {
  return fetchAPI(`/api/screenshots/analysis/${screenshotId}`);
}

// Time Analysis
export async function getTimeAnalysis(date: string): Promise<{
  app_time: { app: string; minutes: number }[];
  category_time: { category: string; minutes: number }[];
  total_hours: number;
  context_switches: number;
  focus_score: number;
  focus_sessions: { app: string; start: string; duration: number }[];
}> {
  return fetchAPI(`/api/time-analysis/${date}`);
}

// Apps
export async function getAllApps(): Promise<{
  app_stats: {
    app_name: string;
    bundle_id: string;
    event_count: number;
    first_seen: string;
    last_seen: string;
  }[];
  today_apps: { app_name: string; count: number }[];
  today: string;
}> {
  return fetchAPI('/api/apps/all');
}

// Analytics Overview
export async function getAnalyticsOverview(date: string): Promise<{
  time_blocks: TimeBlock[];
  categories: CategoryBreakdown[];
  projects: ProjectBreakdown[];
  deep_work_sessions: DeepWorkSession[];
  pareto: ParetoAnalysis;
  focus_score: number;
  focus_over_time: FocusDataPoint[];
  context_switches: number;
  total_hours: number;
  deep_work_hours: number;
  total_events: number;
}> {
  // Fetch multiple endpoints in parallel
  const [timeBlocks, pareto, focusHistory, insights] = await Promise.all([
    getTimeBlocks(date),
    getPareto(date),
    getFocusHistory(7).catch(() => []),
    getDailyInsights(date).catch(() => null),
  ]);

  // Calculate derived data
  const totalEvents = timeBlocks.reduce((sum, b) => sum + b.total, 0);
  const totalHours = totalEvents * 0.5 / 60;

  // Build categories from time blocks
  const categoryMap: Record<string, number> = {};
  timeBlocks.forEach(block => {
    Object.entries(block.categories).forEach(([cat, count]) => {
      categoryMap[cat] = (categoryMap[cat] || 0) + count;
    });
  });
  const totalCatCount = Object.values(categoryMap).reduce((a, b) => a + b, 0) || 1;
  const categories: CategoryBreakdown[] = Object.entries(categoryMap)
    .sort((a, b) => b[1] - a[1])
    .map(([category, count]) => ({
      category,
      count,
      percent: Math.round(count / totalCatCount * 100),
      minutes: Math.round(count * 0.5),
      top_apps: [],
    }));

  return {
    time_blocks: timeBlocks,
    categories,
    projects: [],
    deep_work_sessions: insights?.metrics?.deep_work_minutes ? [{
      app: 'Various',
      category: 'Development',
      start: '09:00',
      duration_min: insights.metrics.deep_work_minutes,
      events: 0,
    }] : [],
    pareto,
    focus_score: insights?.metrics?.focus_score || 0,
    focus_over_time: [],
    context_switches: insights?.metrics?.context_switches || 0,
    total_hours: Math.round(totalHours * 10) / 10,
    deep_work_hours: insights?.metrics?.deep_work_minutes ? Math.round(insights.metrics.deep_work_minutes / 60 * 10) / 10 : 0,
    total_events: totalEvents,
  };
}

// Date helpers
export function formatDate(date: Date): string {
  return date.toISOString().split('T')[0];
}

export function today(): string {
  return formatDate(new Date());
}
