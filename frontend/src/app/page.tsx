'use client';

import { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { Header } from '@/components/layout/Header';
import { MetricCard } from '@/components/dashboard/MetricCard';
import { getStats, getTimeBlocks, getPareto, getDailyInsights } from '@/lib/api';
import type { DailyStats, TimeBlock, ParetoAnalysis, Insights } from '@/lib/types';
import { Activity, Clock, Zap, Target, Brain, AlertCircle } from 'lucide-react';

// Demo data for when API is unavailable
const DEMO_STATS: DailyStats = {
  date: new Date().toISOString().split('T')[0],
  total_events: 480,
  unique_apps: 12,
  top_apps: [
    { app_name: 'VS Code', count: 156 },
    { app_name: 'Chrome', count: 98 },
    { app_name: 'Terminal', count: 67 },
    { app_name: 'Slack', count: 54 },
    { app_name: 'Figma', count: 42 },
  ],
  hourly_breakdown: [
    { hour: '9 AM', count: 45 },
    { hour: '10 AM', count: 52 },
    { hour: '11 AM', count: 48 },
    { hour: '12 PM', count: 20 },
    { hour: '1 PM', count: 55 },
    { hour: '2 PM', count: 58 },
    { hour: '3 PM', count: 50 },
    { hour: '4 PM', count: 45 },
    { hour: '5 PM', count: 35 },
  ],
};

const DEMO_TIME_BLOCKS: TimeBlock[] = [
  { hour: 9, hour_label: '9 AM', total: 45, categories: { Development: 30, Communication: 10, Other: 5 }, primary_category: 'Development' },
  { hour: 10, hour_label: '10 AM', total: 52, categories: { Development: 40, Design: 8, Communication: 4 }, primary_category: 'Development' },
  { hour: 11, hour_label: '11 AM', total: 48, categories: { Development: 35, Meeting: 10, Communication: 3 }, primary_category: 'Development' },
  { hour: 12, hour_label: '12 PM', total: 20, categories: { Other: 15, Communication: 5 }, primary_category: 'Other' },
  { hour: 13, hour_label: '1 PM', total: 55, categories: { Development: 45, Communication: 6, Design: 4 }, primary_category: 'Development' },
  { hour: 14, hour_label: '2 PM', total: 58, categories: { Development: 48, Productivity: 6, Communication: 4 }, primary_category: 'Development' },
  { hour: 15, hour_label: '3 PM', total: 50, categories: { Development: 38, Meeting: 8, Communication: 4 }, primary_category: 'Development' },
  { hour: 16, hour_label: '4 PM', total: 45, categories: { Development: 32, Design: 8, Communication: 5 }, primary_category: 'Development' },
  { hour: 17, hour_label: '5 PM', total: 35, categories: { Development: 22, Communication: 8, Other: 5 }, primary_category: 'Development' },
];

const DEMO_PARETO: ParetoAnalysis = {
  top_apps: [
    { app: 'VS Code', count: 156, percent: 32.5, cumulative_percent: 32.5 },
    { app: 'Chrome', count: 98, percent: 20.4, cumulative_percent: 52.9 },
    { app: 'Terminal', count: 67, percent: 14.0, cumulative_percent: 66.9 },
  ],
  rest_apps: [
    { app: 'Slack', count: 54, percent: 11.3, cumulative_percent: 78.2 },
    { app: 'Figma', count: 42, percent: 8.8, cumulative_percent: 87.0 },
  ],
  top_percent: 20,
  ratio: '3/12',
};

const DEMO_INSIGHTS: Insights = {
  narrative: 'A productive day focused on development with minimal distractions.',
  metrics: {
    total_events: 480,
    context_switches: 23,
    deep_work_minutes: 240,
    focus_score: 78,
    productive_hours: 6.5,
    top_category: 'Development',
  },
  wins: [
    { title: '4 hours of deep work', description: 'Great focus session in the morning!' },
    { title: 'Low context switches', description: 'Only 23 switches - well done!' },
  ],
  improvements: [
    { title: 'Afternoon slump', description: 'Consider a short walk after lunch', severity: 'info' },
  ],
  recommendations: [],
};

export default function Dashboard() {
  const [date, setDate] = useState(new Date());
  const [stats, setStats] = useState<DailyStats | null>(null);
  const [timeBlocks, setTimeBlocks] = useState<TimeBlock[]>([]);
  const [pareto, setPareto] = useState<ParetoAnalysis | null>(null);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(true);
  const [isDemo, setIsDemo] = useState(false);

  const dateStr = format(date, 'yyyy-MM-dd');

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setIsDemo(false);
      try {
        const [statsData, blocksData, paretoData, insightsData] = await Promise.all([
          getStats(dateStr),
          getTimeBlocks(dateStr),
          getPareto(dateStr),
          getDailyInsights(dateStr).catch(() => null),
        ]);
        setStats(statsData);
        setTimeBlocks(blocksData);
        setPareto(paretoData);
        setInsights(insightsData);
      } catch (error) {
        console.error('Failed to fetch data, using demo mode:', error);
        // Use demo data when API is unavailable
        setStats(DEMO_STATS);
        setTimeBlocks(DEMO_TIME_BLOCKS);
        setPareto(DEMO_PARETO);
        setInsights(DEMO_INSIGHTS);
        setIsDemo(true);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [dateStr]);

  // Calculate metrics
  const totalHours = stats ? (stats.total_events * 0.5 / 60).toFixed(1) : '0';
  const focusScore = insights?.metrics?.deep_work_minutes
    ? Math.min(100, Math.round(insights.metrics.deep_work_minutes / 60 * 25))
    : 0;
  const deepWorkHours = insights?.metrics?.deep_work_minutes
    ? (insights.metrics.deep_work_minutes / 60).toFixed(1)
    : '0';

  // Category colors
  const categoryColors: Record<string, string> = {
    Development: 'bg-blue-500',
    Communication: 'bg-pink-500',
    Design: 'bg-purple-500',
    Meeting: 'bg-amber-500',
    Productivity: 'bg-emerald-500',
    Other: 'bg-slate-500',
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
        <Header title="Dashboard" date={date} onDateChange={setDate} />
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <Header title="Dashboard" date={date} onDateChange={setDate} />

      <div className="p-6 space-y-6">
        {/* Demo Mode Banner */}
        {isDemo && (
          <div className="bg-gradient-to-r from-purple-500/20 to-blue-500/20 border border-purple-500/30 rounded-xl p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-purple-500/20 flex items-center justify-center">
                <Zap className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <p className="font-semibold text-purple-300">Demo Mode</p>
                <p className="text-sm text-slate-400">Showing sample data. Install locally to track your activity.</p>
              </div>
            </div>
            <a
              href="/setup.html"
              className="px-4 py-2 bg-purple-600 hover:bg-purple-500 rounded-lg text-sm font-medium transition-colors"
            >
              Install Now
            </a>
          </div>
        )}
        {/* Metrics Grid */}
        <div className="grid grid-cols-4 gap-4">
          <MetricCard
            title="Total Tracked"
            value={`${totalHours}h`}
            color="blue"
          />
          <MetricCard
            title="Deep Work"
            value={`${deepWorkHours}h`}
            color="green"
          />
          <MetricCard
            title="Focus Score"
            value={focusScore}
            color="purple"
          />
          <MetricCard
            title="80/20 Ratio"
            value={pareto?.ratio || '0/0'}
            color="orange"
          />
        </div>

        <div className="grid grid-cols-3 gap-6">
          {/* Time Blocks */}
          <div className="col-span-2 bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Clock className="w-5 h-5 text-blue-400" />
              Time Blocks
            </h2>
            <div className="space-y-2">
              {timeBlocks.length > 0 ? (
                timeBlocks.map((block) => (
                  <div key={block.hour} className="flex items-center gap-3">
                    <span className="text-xs text-slate-400 w-12 text-right">
                      {block.hour_label}
                    </span>
                    <div className="flex-1 h-6 bg-slate-700/50 rounded overflow-hidden flex">
                      {Object.entries(block.categories).map(([cat, count]) => {
                        const width = (count / block.total) * 100;
                        return (
                          <div
                            key={cat}
                            className={`h-full ${categoryColors[cat] || 'bg-slate-500'}`}
                            style={{ width: `${width}%` }}
                            title={`${cat}: ${count} events`}
                          />
                        );
                      })}
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-slate-500 text-center py-8">No activity data for this day</p>
              )}
            </div>
          </div>

          {/* Category Breakdown */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-purple-400" />
              Categories
            </h2>
            <div className="space-y-3">
              {timeBlocks.length > 0 ? (
                (() => {
                  // Aggregate categories from time blocks
                  const categoryTotals: Record<string, number> = {};
                  let total = 0;
                  timeBlocks.forEach(block => {
                    Object.entries(block.categories).forEach(([cat, count]) => {
                      categoryTotals[cat] = (categoryTotals[cat] || 0) + count;
                      total += count;
                    });
                  });

                  return Object.entries(categoryTotals)
                    .sort((a, b) => b[1] - a[1])
                    .map(([category, count]) => {
                      const percent = total > 0 ? ((count / total) * 100).toFixed(0) : 0;
                      return (
                        <div key={category} className="flex items-center gap-3">
                          <div className={`w-3 h-3 rounded-full ${categoryColors[category] || 'bg-slate-500'}`} />
                          <span className="flex-1 text-sm">{category}</span>
                          <span className="text-sm font-semibold">{percent}%</span>
                        </div>
                      );
                    });
                })()
              ) : (
                <p className="text-slate-500 text-sm">No categories yet</p>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Top Apps */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-emerald-400" />
              Top Apps
            </h2>
            <div className="space-y-2">
              {stats?.top_apps?.slice(0, 5).map((app, index) => (
                <div key={app.app_name} className="flex items-center gap-3 p-2 rounded-lg bg-slate-700/30">
                  <span className="w-6 h-6 rounded bg-blue-600/20 text-blue-400 flex items-center justify-center text-xs font-bold">
                    {index + 1}
                  </span>
                  <span className="flex-1 text-sm truncate">{app.app_name}</span>
                  <span className="text-sm text-slate-400">{app.count} events</span>
                </div>
              )) || <p className="text-slate-500 text-sm">No app data</p>}
            </div>
          </div>

          {/* Quick Insights */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Brain className="w-5 h-5 text-amber-400" />
              Quick Insights
            </h2>
            <div className="space-y-3">
              {insights?.wins?.slice(0, 2).map((win, index) => (
                <div key={index} className="flex items-start gap-3 p-3 rounded-lg bg-emerald-500/10 border-l-2 border-emerald-500">
                  <Zap className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-emerald-400">{win.title}</p>
                    <p className="text-xs text-slate-400">{win.description}</p>
                  </div>
                </div>
              ))}

              {insights?.improvements?.slice(0, 2).map((item, index) => (
                <div key={index} className="flex items-start gap-3 p-3 rounded-lg bg-amber-500/10 border-l-2 border-amber-500">
                  <AlertCircle className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-amber-400">{item.title}</p>
                    <p className="text-xs text-slate-400">{item.description}</p>
                  </div>
                </div>
              ))}

              {(!insights?.wins?.length && !insights?.improvements?.length) && (
                <p className="text-slate-500 text-sm">No insights available for this day</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
