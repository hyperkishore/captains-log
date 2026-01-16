'use client';

import { useState, useEffect } from 'react';
import { Header } from '@/components/layout/Header';
import { getAllApps } from '@/lib/api';
import { Monitor, Calendar, BarChart3 } from 'lucide-react';

interface AppStats {
  app_name: string;
  bundle_id: string;
  event_count: number;
  first_seen: string;
  last_seen: string;
}

interface AppsData {
  app_stats: AppStats[];
  today_apps: { app_name: string; count: number }[];
  today: string;
}

export default function Apps() {
  const [data, setData] = useState<AppsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const result = await getAllApps();
        setData(result);
      } catch (error) {
        console.error('Failed to fetch data:', error);
        setData(null);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const formatDate = (dateStr: string): string => {
    if (!dateStr) return '-';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateStr.split('T')[0];
    }
  };

  const barColors = [
    'bg-blue-500', 'bg-emerald-500', 'bg-amber-500', 'bg-red-500', 'bg-purple-500',
    'bg-pink-500', 'bg-cyan-500', 'bg-lime-500', 'bg-orange-500', 'bg-indigo-500'
  ];

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
        <Header title="App Usage" showDatePicker={false} />
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      </div>
    );
  }

  const maxTodayCount = Math.max(...(data?.today_apps.map(a => a.count) || [1]), 1);
  const maxAllTimeCount = Math.max(...(data?.app_stats.slice(0, 10).map(a => a.event_count) || [1]), 1);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <Header title="App Usage" showDatePicker={false} />

      <div className="p-6 space-y-6">
        {/* Today's Apps */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Calendar className="w-5 h-5 text-blue-400" />
            Today ({data?.today})
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {data?.today_apps.length ? (
              data.today_apps.map((app) => (
                <div key={app.app_name} className="bg-slate-700/50 rounded-lg p-4 text-center hover:bg-slate-700/70 transition-colors">
                  <div className="text-2xl font-bold text-white">{app.count}</div>
                  <div className="text-sm text-slate-400 truncate" title={app.app_name}>
                    {app.app_name}
                  </div>
                </div>
              ))
            ) : (
              <div className="col-span-full text-center py-8 text-slate-500">
                No apps tracked today yet.
              </div>
            )}
          </div>
        </div>

        {/* All-time Stats */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Monitor className="w-5 h-5 text-purple-400" />
            All-Time Statistics
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs font-medium text-slate-400 uppercase border-b border-slate-700">
                  <th className="px-4 py-3">App</th>
                  <th className="px-4 py-3">Bundle ID</th>
                  <th className="px-4 py-3">Events</th>
                  <th className="px-4 py-3">First Seen</th>
                  <th className="px-4 py-3">Last Seen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {data?.app_stats.length ? (
                  data.app_stats.map((app) => (
                    <tr key={app.bundle_id || app.app_name} className="hover:bg-slate-700/30 transition-colors">
                      <td className="px-4 py-3 text-sm font-medium">{app.app_name}</td>
                      <td className="px-4 py-3 text-xs font-mono text-slate-500">
                        {app.bundle_id || '-'}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <span className="font-semibold text-blue-400">{app.event_count}</span>
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-400">
                        {formatDate(app.first_seen)}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-400">
                        {formatDate(app.last_seen)}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                      No apps tracked yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Usage Chart */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-emerald-400" />
            Top Apps Distribution
          </h2>
          <div className="space-y-3">
            {data?.app_stats.slice(0, 10).map((app, index) => {
              const width = (app.event_count / maxAllTimeCount) * 100;
              return (
                <div key={app.bundle_id || app.app_name} className="flex items-center gap-3">
                  <div className="w-28 truncate text-sm text-slate-300" title={app.app_name}>
                    {app.app_name}
                  </div>
                  <div className="flex-1">
                    <div className="h-6 bg-slate-700/50 rounded overflow-hidden">
                      <div
                        className={`h-full ${barColors[index % barColors.length]} rounded transition-all`}
                        style={{ width: `${width}%` }}
                      />
                    </div>
                  </div>
                  <div className="w-16 text-right text-sm font-medium text-slate-400">
                    {app.event_count}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
