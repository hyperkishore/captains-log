'use client';

import { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { Header } from '@/components/layout/Header';
import { getDailyInsights } from '@/lib/api';
import type { Insights } from '@/lib/types';
import {
  Brain,
  Trophy,
  AlertTriangle,
  Lightbulb,
  TrendingUp,
  Clock,
  Target,
  Zap
} from 'lucide-react';

export default function InsightsPage() {
  const [date, setDate] = useState(new Date());
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const dateStr = format(date, 'yyyy-MM-dd');

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const data = await getDailyInsights(dateStr);
        setInsights(data);
      } catch (err) {
        console.error('Failed to fetch insights:', err);
        setError('No insights available for this day');
        setInsights(null);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [dateStr]);

  const priorityColors = {
    high: 'bg-red-500/20 text-red-400 border-red-500/30',
    medium: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    low: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
        <Header title="Insights" date={date} onDateChange={setDate} />
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <Header title="Insights" date={date} onDateChange={setDate} />

      <div className="p-6 space-y-6">
        {error || !insights ? (
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-12">
            <div className="text-center text-slate-500">
              <Brain className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <h3 className="text-xl font-semibold mb-2">No Insights Available</h3>
              <p className="text-slate-400">
                AI insights are generated from activity data. Make sure the daemon is running
                and you have activity tracked for this day.
              </p>
            </div>
          </div>
        ) : (
          <>
            {/* Daily Narrative */}
            {insights.narrative && (
              <div className="bg-gradient-to-r from-blue-900/30 to-purple-900/30 border border-blue-700/50 rounded-xl p-6">
                <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
                  <Brain className="w-5 h-5 text-blue-400" />
                  Daily Summary
                </h2>
                <p className="text-slate-300 leading-relaxed">{insights.narrative}</p>
              </div>
            )}

            {/* Metrics Summary */}
            {insights.metrics && (
              <div className="grid grid-cols-4 gap-4">
                <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 text-center">
                  <Clock className="w-6 h-6 mx-auto mb-2 text-blue-400" />
                  <div className="text-2xl font-bold">{insights.metrics.productive_hours.toFixed(1)}h</div>
                  <div className="text-xs text-slate-400 uppercase tracking-wide">Productive</div>
                </div>
                <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 text-center">
                  <Target className="w-6 h-6 mx-auto mb-2 text-emerald-400" />
                  <div className="text-2xl font-bold">{insights.metrics.deep_work_minutes}m</div>
                  <div className="text-xs text-slate-400 uppercase tracking-wide">Deep Work</div>
                </div>
                <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 text-center">
                  <Zap className="w-6 h-6 mx-auto mb-2 text-amber-400" />
                  <div className="text-2xl font-bold">{insights.metrics.context_switches}</div>
                  <div className="text-xs text-slate-400 uppercase tracking-wide">Switches</div>
                </div>
                <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 text-center">
                  <TrendingUp className="w-6 h-6 mx-auto mb-2 text-purple-400" />
                  <div className="text-2xl font-bold">{insights.metrics.top_category}</div>
                  <div className="text-xs text-slate-400 uppercase tracking-wide">Top Category</div>
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-6">
              {/* Wins */}
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <Trophy className="w-5 h-5 text-amber-400" />
                  Wins Today
                </h2>
                {insights.wins.length > 0 ? (
                  <div className="space-y-3">
                    {insights.wins.map((win, index) => (
                      <div key={index} className="flex items-start gap-3 p-3 bg-emerald-500/10 border-l-3 border-emerald-500 rounded-r-lg">
                        <div className="text-emerald-400 mt-0.5">✓</div>
                        <div>
                          <div className="font-medium text-emerald-400">{win.title}</div>
                          <div className="text-sm text-slate-400">{win.description}</div>
                          {win.metric && (
                            <div className="text-xs text-emerald-500/70 mt-1">{win.metric}</div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-500 text-center py-4">No wins recorded yet</p>
                )}
              </div>

              {/* Areas for Improvement */}
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-amber-400" />
                  Areas for Improvement
                </h2>
                {insights.improvements.length > 0 ? (
                  <div className="space-y-3">
                    {insights.improvements.map((item, index) => (
                      <div
                        key={index}
                        className={`flex items-start gap-3 p-3 rounded-lg ${
                          item.severity === 'warning'
                            ? 'bg-amber-500/10 border-l-3 border-amber-500'
                            : 'bg-blue-500/10 border-l-3 border-blue-500'
                        }`}
                      >
                        <div className={item.severity === 'warning' ? 'text-amber-400' : 'text-blue-400'}>!</div>
                        <div>
                          <div className={`font-medium ${item.severity === 'warning' ? 'text-amber-400' : 'text-blue-400'}`}>
                            {item.title}
                          </div>
                          <div className="text-sm text-slate-400">{item.description}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-500 text-center py-4">Nothing to improve</p>
                )}
              </div>
            </div>

            {/* Recommendations */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Lightbulb className="w-5 h-5 text-purple-400" />
                Recommendations
              </h2>
              {insights.recommendations.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {insights.recommendations.map((rec, index) => (
                    <div
                      key={index}
                      className={`p-4 rounded-lg border ${priorityColors[rec.priority]}`}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`text-xs font-semibold uppercase px-2 py-0.5 rounded ${
                          rec.priority === 'high' ? 'bg-red-500/30' :
                          rec.priority === 'medium' ? 'bg-amber-500/30' : 'bg-blue-500/30'
                        }`}>
                          {rec.priority}
                        </span>
                      </div>
                      <div className="font-medium mb-1">{rec.title}</div>
                      <div className="text-sm text-slate-400">{rec.description}</div>
                      {rec.action && (
                        <div className="text-xs text-slate-500 mt-2 italic">{rec.action}</div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-500 text-center py-4">No recommendations available</p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
