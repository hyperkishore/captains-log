'use client';

import { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { Header } from '@/components/layout/Header';
import { MetricCard } from '@/components/dashboard/MetricCard';
import { getAnalyticsOverview } from '@/lib/api';
import type { TimeBlock, CategoryBreakdown, DeepWorkSession, ParetoAnalysis } from '@/lib/types';
import { Clock, Target, Zap, CheckCircle, AlertTriangle, ChevronRight, BarChart3, Brain } from 'lucide-react';

interface AnalyticsData {
  time_blocks: TimeBlock[];
  categories: CategoryBreakdown[];
  deep_work_sessions: DeepWorkSession[];
  pareto: ParetoAnalysis;
  focus_score: number;
  context_switches: number;
  total_hours: number;
  deep_work_hours: number;
  total_events: number;
}

export default function AnalyticsOverview() {
  const [date, setDate] = useState(new Date());
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);

  const dateStr = format(date, 'yyyy-MM-dd');

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const result = await getAnalyticsOverview(dateStr);
        setData(result);
      } catch (error) {
        console.error('Failed to fetch data:', error);
        setData(null);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [dateStr]);

  const categoryColors: Record<string, string> = {
    Development: 'bg-blue-500',
    Communication: 'bg-pink-500',
    Design: 'bg-purple-500',
    Meeting: 'bg-amber-500',
    Productivity: 'bg-emerald-500',
    Browsing: 'bg-cyan-500',
    Other: 'bg-slate-500',
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
        <Header title="Analytics" date={date} onDateChange={setDate} />
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <Header title="Analytics" date={date} onDateChange={setDate} />

      <div className="p-6 space-y-6">
        {data && data.total_events > 0 ? (
          <>
            {/* Metrics Grid */}
            <div className="grid grid-cols-4 gap-4">
              <MetricCard
                title="Total Tracked"
                value={`${data.total_hours}h`}
                color="blue"
              />
              <MetricCard
                title="Deep Work"
                value={`${data.deep_work_hours}h`}
                color="green"
              />
              <MetricCard
                title="Focus Score"
                value={data.focus_score}
                color="purple"
              />
              <MetricCard
                title="80/20 Ratio"
                value={data.pareto.ratio}
                color="orange"
              />
            </div>

            <div className="grid grid-cols-3 gap-6">
              {/* Time Blocks */}
              <div className="col-span-2 bg-slate-800/50 border border-slate-700 rounded-xl p-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-blue-400" />
                  Time Blocks
                </h2>
                <div className="space-y-2">
                  {data.time_blocks.length > 0 ? (
                    data.time_blocks.map((block) => (
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
                    <p className="text-slate-500 text-center py-8">No activity data</p>
                  )}
                </div>
              </div>

              {/* Categories */}
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <Target className="w-5 h-5 text-purple-400" />
                  Categories
                </h2>
                <div className="space-y-3">
                  {data.categories.map((cat) => (
                    <div key={cat.category} className="flex items-center gap-3 py-2 border-b border-slate-700/50 last:border-b-0">
                      <div className={`w-3 h-3 rounded-full ${categoryColors[cat.category] || 'bg-slate-500'}`} />
                      <span className="flex-1 text-sm">{cat.category}</span>
                      <span className="text-sm font-semibold">{cat.percent}%</span>
                      <span className="text-xs text-slate-400">~{cat.minutes}m</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              {/* Deep Work Sessions */}
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <Brain className="w-5 h-5 text-emerald-400" />
                  Deep Work Sessions (25+ min)
                </h2>
                {data.deep_work_sessions.length > 0 ? (
                  <div className="space-y-2">
                    {data.deep_work_sessions.map((session, index) => (
                      <div
                        key={index}
                        className="flex items-center gap-3 p-3 bg-emerald-500/10 border-l-3 border-emerald-500 rounded-r-lg"
                      >
                        <span className="text-xs text-slate-400 w-12">{session.start}</span>
                        <span className="flex-1 font-medium">{session.app}</span>
                        <span className="bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded text-xs font-semibold">
                          {session.duration_min}m
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-500">
                    <div className="text-4xl mb-2">😴</div>
                    <p>No deep work sessions detected today</p>
                  </div>
                )}
              </div>

              {/* Quick Insights */}
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <Zap className="w-5 h-5 text-amber-400" />
                  Quick Insights
                </h2>
                <div className="space-y-3">
                  {data.deep_work_sessions.length > 0 && (
                    <div className="flex items-start gap-3 p-3 bg-emerald-500/10 rounded-lg">
                      <CheckCircle className="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" />
                      <span className="text-sm text-slate-300">
                        Longest focus block: {Math.max(...data.deep_work_sessions.map(s => s.duration_min))} min
                      </span>
                    </div>
                  )}

                  {data.context_switches > 20 ? (
                    <div className="flex items-start gap-3 p-3 bg-amber-500/10 rounded-lg">
                      <AlertTriangle className="w-5 h-5 text-amber-400 mt-0.5 flex-shrink-0" />
                      <span className="text-sm text-slate-300">
                        High context switching: {data.context_switches} switches today
                      </span>
                    </div>
                  ) : (
                    <div className="flex items-start gap-3 p-3 bg-emerald-500/10 rounded-lg">
                      <CheckCircle className="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" />
                      <span className="text-sm text-slate-300">
                        Good focus: only {data.context_switches} context switches
                      </span>
                    </div>
                  )}

                  {data.pareto.top_apps.length > 0 && (
                    <div className="flex items-start gap-3 p-3 bg-blue-500/10 rounded-lg">
                      <ChevronRight className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
                      <span className="text-sm text-slate-300">
                        80/20 ratio: {data.pareto.ratio} - top {data.pareto.top_apps.length} apps = {data.pareto.top_percent}% of time
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        ) : (
          /* Empty State */
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-12">
            <div className="text-center text-slate-500">
              <div className="text-6xl mb-4">📭</div>
              <h3 className="text-xl font-semibold mb-2">No activity data for this day</h3>
              <p>Start the daemon to begin tracking: <code className="bg-slate-700 px-2 py-1 rounded">captains-log start</code></p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
