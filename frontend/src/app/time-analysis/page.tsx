'use client';

import { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { Header } from '@/components/layout/Header';
import { MetricCard } from '@/components/dashboard/MetricCard';
import { getTimeAnalysis } from '@/lib/api';
import { Clock, Zap, RefreshCw, Target, AlertTriangle, CheckCircle } from 'lucide-react';

interface TimeAnalysisData {
  app_time: { app: string; minutes: number }[];
  category_time: { category: string; minutes: number }[];
  total_hours: number;
  context_switches: number;
  focus_score: number;
  focus_sessions: { app: string; start: string; duration: number }[];
}

export default function TimeAnalysis() {
  const [date, setDate] = useState(new Date());
  const [data, setData] = useState<TimeAnalysisData | null>(null);
  const [loading, setLoading] = useState(true);

  const dateStr = format(date, 'yyyy-MM-dd');

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const result = await getTimeAnalysis(dateStr);
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
    Communication: 'bg-amber-500',
    Development: 'bg-emerald-500',
    Browsing: 'bg-blue-500',
    Productivity: 'bg-purple-500',
    Media: 'bg-pink-500',
    Other: 'bg-slate-500',
  };

  const formatTime = (minutes: number): string => {
    if (minutes >= 60) {
      return `${(minutes / 60).toFixed(1)}h`;
    }
    return `${Math.round(minutes)}m`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
        <Header title="Time Analysis" date={date} onDateChange={setDate} />
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      </div>
    );
  }

  const totalMinutes = data?.app_time.reduce((sum, a) => sum + a.minutes, 0) || 1;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <Header title="Time Analysis" date={date} onDateChange={setDate} />

      <div className="p-6 space-y-6">
        {/* Metrics Grid */}
        <div className="grid grid-cols-4 gap-4">
          <MetricCard
            title="Total Tracked"
            value={`${data?.total_hours || 0}h`}
            color="blue"
          />
          <MetricCard
            title="Focus Score"
            value={data?.focus_score || 0}
            color={data?.focus_score && data.focus_score >= 70 ? 'green' : data?.focus_score && data.focus_score >= 40 ? 'orange' : 'red'}
          />
          <MetricCard
            title="Context Switches"
            value={data?.context_switches || 0}
            color="orange"
          />
          <MetricCard
            title="Focus Sessions"
            value={data?.focus_sessions.length || 0}
            color="purple"
          />
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Time by App */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Clock className="w-5 h-5 text-blue-400" />
              Time by App
            </h2>
            <div className="space-y-3">
              {data?.app_time.length ? (
                data.app_time.map((app) => {
                  const percent = (app.minutes / totalMinutes) * 100;
                  return (
                    <div key={app.app} className="flex items-center gap-3">
                      <div className="w-28 truncate text-sm font-medium text-slate-300" title={app.app}>
                        {app.app}
                      </div>
                      <div className="flex-1">
                        <div className="h-4 bg-slate-700/50 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded-full transition-all"
                            style={{ width: `${percent}%` }}
                          />
                        </div>
                      </div>
                      <div className="w-16 text-right text-sm text-slate-400">
                        {formatTime(app.minutes)}
                      </div>
                    </div>
                  );
                })
              ) : (
                <p className="text-slate-500 text-center py-8">No data for this day</p>
              )}
            </div>
          </div>

          {/* Time by Category */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-purple-400" />
              Time by Category
            </h2>
            <div className="space-y-4">
              {data?.category_time.length ? (
                data.category_time.map((cat) => {
                  const catTotalMinutes = data.category_time.reduce((sum, c) => sum + c.minutes, 0) || 1;
                  const percent = (cat.minutes / catTotalMinutes) * 100;
                  return (
                    <div key={cat.category} className="space-y-1">
                      <div className="flex justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <div className={`w-3 h-3 rounded-full ${categoryColors[cat.category] || 'bg-slate-500'}`} />
                          <span className="text-slate-300">{cat.category}</span>
                        </div>
                        <span className="font-medium">{formatTime(cat.minutes)}</span>
                      </div>
                      <div className="h-2 bg-slate-700/50 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${categoryColors[cat.category] || 'bg-slate-500'}`}
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>
                  );
                })
              ) : (
                <p className="text-slate-500 text-center py-8">No categories yet</p>
              )}
            </div>
          </div>
        </div>

        {/* Insights & Recommendations */}
        <div className="bg-gradient-to-r from-blue-900/30 to-purple-900/30 border border-blue-700/50 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-400" />
            Insights & Recommendations
          </h2>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <h4 className="text-sm font-medium text-slate-300 mb-3">Top Time Consumers</h4>
              <ul className="space-y-2">
                {data?.app_time.slice(0, 3).map((app) => (
                  <li key={app.app} className="flex items-center text-sm">
                    <span className="w-2 h-2 bg-red-400 rounded-full mr-2" />
                    <span className="font-medium text-slate-300">{app.app}</span>
                    <span className="ml-auto text-slate-400">{formatTime(app.minutes)}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-sm font-medium text-slate-300 mb-3">To Improve Focus</h4>
              <ul className="space-y-2 text-sm text-slate-400">
                {data && data.context_switches > 20 && (
                  <li className="flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
                    <span>High context switching ({data.context_switches}). Try time-blocking.</span>
                  </li>
                )}
                {data?.category_time.find(c => c.category === 'Communication' && c.minutes > 60) && (
                  <li className="flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-orange-500 mt-0.5 flex-shrink-0" />
                    <span>
                      {formatTime(data.category_time.find(c => c.category === 'Communication')!.minutes)} on communication. Batch checks to 3x daily.
                    </span>
                  </li>
                )}
                {data && data.focus_sessions.length < 3 && (
                  <li className="flex items-start gap-2">
                    <Zap className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
                    <span>Only {data.focus_sessions.length} focus sessions. Aim for 4+ sessions of 25+ mins.</span>
                  </li>
                )}
                {data && data.focus_score >= 70 && (
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
                    <span>Great focus today! Keep up the momentum.</span>
                  </li>
                )}
              </ul>
            </div>
          </div>
        </div>

        {/* Focus Sessions */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <RefreshCw className="w-5 h-5 text-emerald-400" />
            Focus Sessions (5+ mins uninterrupted)
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs font-medium text-slate-400 uppercase">
                  <th className="px-4 py-3">Start Time</th>
                  <th className="px-4 py-3">App</th>
                  <th className="px-4 py-3">Duration</th>
                  <th className="px-4 py-3">Quality</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {data?.focus_sessions.length ? (
                  data.focus_sessions.map((session, index) => (
                    <tr key={index} className="hover:bg-slate-700/30">
                      <td className="px-4 py-3 text-sm text-slate-400">{session.start}</td>
                      <td className="px-4 py-3 text-sm font-medium">{session.app}</td>
                      <td className="px-4 py-3 text-sm text-slate-300">{session.duration} min</td>
                      <td className="px-4 py-3">
                        {session.duration >= 45 ? (
                          <span className="px-2 py-1 text-xs font-medium rounded-full bg-emerald-500/20 text-emerald-400">
                            Deep Work
                          </span>
                        ) : session.duration >= 25 ? (
                          <span className="px-2 py-1 text-xs font-medium rounded-full bg-blue-500/20 text-blue-400">
                            Good Focus
                          </span>
                        ) : (
                          <span className="px-2 py-1 text-xs font-medium rounded-full bg-amber-500/20 text-amber-400">
                            Short Sprint
                          </span>
                        )}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                      No focus sessions detected. Try to minimize context switching.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
