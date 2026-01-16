'use client';

import { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { Header } from '@/components/layout/Header';
import { MetricCard } from '@/components/dashboard/MetricCard';
import { getStats, getTimeBlocks, getPareto, getDailyInsights } from '@/lib/api';
import type { DailyStats, TimeBlock, ParetoAnalysis, Insights } from '@/lib/types';
import { Activity, Clock, Zap, Target, Brain, AlertCircle } from 'lucide-react';

export default function Dashboard() {
  const [date, setDate] = useState(new Date());
  const [stats, setStats] = useState<DailyStats | null>(null);
  const [timeBlocks, setTimeBlocks] = useState<TimeBlock[]>([]);
  const [pareto, setPareto] = useState<ParetoAnalysis | null>(null);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(true);

  const dateStr = format(date, 'yyyy-MM-dd');

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
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
        console.error('Failed to fetch data:', error);
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
