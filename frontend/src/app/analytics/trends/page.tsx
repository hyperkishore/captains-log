'use client';

import { useState, useEffect } from 'react';
import { Header } from '@/components/layout/Header';
import { getFocusHistory } from '@/lib/api';
import { TrendingUp, TrendingDown, Minus, Calendar, Zap, BarChart3 } from 'lucide-react';

interface FocusHistoryPoint {
  date: string;
  focus_score: number;
  event_count: number;
}

export default function Trends() {
  const [focusHistory, setFocusHistory] = useState<FocusHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const data = await getFocusHistory(28);
        setFocusHistory(data);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  // Calculate weekly comparison
  const today = new Date();
  const thisWeekStart = new Date(today);
  thisWeekStart.setDate(today.getDate() - today.getDay());
  const lastWeekStart = new Date(thisWeekStart);
  lastWeekStart.setDate(lastWeekStart.getDate() - 7);

  const thisWeekData = focusHistory.filter(d => {
    const date = new Date(d.date);
    return date >= thisWeekStart;
  });

  const lastWeekData = focusHistory.filter(d => {
    const date = new Date(d.date);
    return date >= lastWeekStart && date < thisWeekStart;
  });

  const thisWeekHours = thisWeekData.reduce((sum, d) => sum + d.event_count * 0.5 / 60, 0);
  const lastWeekHours = lastWeekData.reduce((sum, d) => sum + d.event_count * 0.5 / 60, 0);
  const hoursChange = lastWeekHours > 0 ? Math.round((thisWeekHours - lastWeekHours) / lastWeekHours * 100) : 0;

  const thisWeekFocus = thisWeekData.length > 0
    ? Math.round(thisWeekData.reduce((sum, d) => sum + d.focus_score, 0) / thisWeekData.length)
    : 0;
  const lastWeekFocus = lastWeekData.length > 0
    ? Math.round(lastWeekData.reduce((sum, d) => sum + d.focus_score, 0) / lastWeekData.length)
    : 0;
  const focusChange = lastWeekFocus > 0 ? Math.round((thisWeekFocus - lastWeekFocus) / lastWeekFocus * 100) : 0;

  // Heatmap data (last 28 days)
  const heatmapData = Array.from({ length: 28 }, (_, i) => {
    const date = new Date(today);
    date.setDate(today.getDate() - (27 - i));
    const dateStr = date.toISOString().split('T')[0];
    const dayData = focusHistory.find(d => d.date === dateStr);
    const score = dayData?.focus_score || 0;
    const level = dayData ? Math.min(5, Math.floor(score / 20)) : 0;
    return {
      date: dateStr,
      day: date.getDate(),
      dayOfWeek: date.getDay(),
      score,
      level,
      isToday: date.toDateString() === today.toDateString(),
    };
  });

  const levelColors = [
    'bg-slate-700',
    'bg-emerald-900',
    'bg-emerald-700',
    'bg-emerald-500',
    'bg-emerald-400',
    'bg-emerald-300',
  ];

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
        <Header title="Trends" showDatePicker={false} />
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <Header title="Trends" showDatePicker={false} />

      <div className="p-6 space-y-6">
        {/* Weekly Comparison */}
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-blue-400" />
              This Week vs Last Week
            </h2>
            <div className="grid grid-cols-2 gap-4">
              {/* Hours Comparison */}
              <div className="bg-slate-700/30 rounded-lg p-4">
                <div className="text-sm text-slate-400 mb-1">Hours Tracked</div>
                <div className="flex items-end gap-2">
                  <span className="text-2xl font-bold">{thisWeekHours.toFixed(1)}h</span>
                  <span className={`flex items-center text-sm ${hoursChange >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {hoursChange >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                    {Math.abs(hoursChange)}%
                  </span>
                </div>
                <div className="text-xs text-slate-500 mt-1">Last week: {lastWeekHours.toFixed(1)}h</div>
              </div>

              {/* Focus Comparison */}
              <div className="bg-slate-700/30 rounded-lg p-4">
                <div className="text-sm text-slate-400 mb-1">Avg Focus Score</div>
                <div className="flex items-end gap-2">
                  <span className="text-2xl font-bold">{thisWeekFocus}</span>
                  <span className={`flex items-center text-sm ${focusChange >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {focusChange >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                    {Math.abs(focusChange)}%
                  </span>
                </div>
                <div className="text-xs text-slate-500 mt-1">Last week: {lastWeekFocus}</div>
              </div>
            </div>

            {/* Daily Bars */}
            <div className="mt-6">
              <div className="text-sm text-slate-400 mb-3">Daily Hours (This Week)</div>
              <div className="flex gap-2 h-24">
                {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day, index) => {
                  const dayData = thisWeekData.find(d => new Date(d.date).getDay() === index);
                  const hours = dayData ? dayData.event_count * 0.5 / 60 : 0;
                  const maxHours = Math.max(...thisWeekData.map(d => d.event_count * 0.5 / 60), 1);
                  const height = (hours / maxHours) * 100;
                  const isToday = new Date().getDay() === index;

                  return (
                    <div key={day} className="flex-1 flex flex-col items-center">
                      <div className="flex-1 w-full flex items-end">
                        <div
                          className={`w-full rounded-t transition-all ${isToday ? 'bg-blue-500' : 'bg-blue-500/50'}`}
                          style={{ height: `${height}%` }}
                          title={`${hours.toFixed(1)}h`}
                        />
                      </div>
                      <span className={`text-xs mt-1 ${isToday ? 'text-blue-400 font-semibold' : 'text-slate-500'}`}>
                        {day}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Focus Heatmap */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Calendar className="w-5 h-5 text-emerald-400" />
              Focus Score Heatmap (28 Days)
            </h2>
            <div className="grid grid-cols-7 gap-1">
              {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((day, idx) => (
                <div key={`day-${idx}`} className="text-xs text-slate-500 text-center py-1">{day}</div>
              ))}
              {heatmapData.map((day, index) => (
                <div
                  key={index}
                  className={`aspect-square rounded ${levelColors[day.level]} ${day.isToday ? 'ring-2 ring-blue-500' : ''} transition-colors cursor-default`}
                  title={`${day.date}: ${day.score} focus score`}
                />
              ))}
            </div>
            <div className="flex items-center justify-end gap-2 mt-4">
              <span className="text-xs text-slate-500">Less</span>
              {levelColors.map((color, i) => (
                <div key={i} className={`w-3 h-3 rounded ${color}`} />
              ))}
              <span className="text-xs text-slate-500">More</span>
            </div>
          </div>
        </div>

        {/* Patterns */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-400" />
            Patterns & Insights
          </h2>
          <div className="grid grid-cols-3 gap-4">
            {thisWeekFocus > lastWeekFocus && (
              <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4">
                <div className="text-2xl mb-2">📈</div>
                <div className="font-medium text-emerald-400">Focus Improving</div>
                <div className="text-sm text-slate-400 mt-1">
                  Your focus score is up {focusChange}% compared to last week
                </div>
              </div>
            )}

            {thisWeekHours > lastWeekHours && (
              <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
                <div className="text-2xl mb-2">⏱️</div>
                <div className="font-medium text-blue-400">More Active</div>
                <div className="text-sm text-slate-400 mt-1">
                  You&apos;ve tracked {(thisWeekHours - lastWeekHours).toFixed(1)} more hours this week
                </div>
              </div>
            )}

            {thisWeekData.filter(d => d.focus_score >= 70).length >= 3 && (
              <div className="bg-purple-500/10 border border-purple-500/30 rounded-lg p-4">
                <div className="text-2xl mb-2">🎯</div>
                <div className="font-medium text-purple-400">Strong Focus Week</div>
                <div className="text-sm text-slate-400 mt-1">
                  {thisWeekData.filter(d => d.focus_score >= 70).length} high-focus days this week
                </div>
              </div>
            )}

            {thisWeekData.length < 3 && (
              <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4">
                <div className="text-2xl mb-2">💡</div>
                <div className="font-medium text-amber-400">Track More</div>
                <div className="text-sm text-slate-400 mt-1">
                  Run the daemon daily for better trend insights
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
