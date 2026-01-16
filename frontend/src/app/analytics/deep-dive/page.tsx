'use client';

import { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { Header } from '@/components/layout/Header';
import { getTreemap, getPareto } from '@/lib/api';
import type { TreemapNode, ParetoAnalysis } from '@/lib/types';
import { Layers, BarChart3, ChevronDown, ChevronRight } from 'lucide-react';

export default function DeepDive() {
  const [date, setDate] = useState(new Date());
  const [treemapData, setTreemapData] = useState<TreemapNode | null>(null);
  const [pareto, setPareto] = useState<ParetoAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  const dateStr = format(date, 'yyyy-MM-dd');

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const [treemap, paretoData] = await Promise.all([
          getTreemap(dateStr),
          getPareto(dateStr),
        ]);
        setTreemapData(treemap);
        setPareto(paretoData);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [dateStr]);

  const toggleCategory = (category: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  const categoryColors: Record<string, string> = {
    Development: 'bg-blue-500 text-blue-400',
    Communication: 'bg-pink-500 text-pink-400',
    Design: 'bg-purple-500 text-purple-400',
    Meeting: 'bg-amber-500 text-amber-400',
    Productivity: 'bg-emerald-500 text-emerald-400',
    Browsing: 'bg-cyan-500 text-cyan-400',
    Other: 'bg-slate-500 text-slate-400',
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
        <Header title="Deep Dive" date={date} onDateChange={setDate} />
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      </div>
    );
  }

  const totalValue = treemapData?.children?.reduce((sum, cat) =>
    sum + (cat.children?.reduce((s, app) => s + (app.value || 0), 0) || 0), 0) || 1;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <Header title="Deep Dive" date={date} onDateChange={setDate} />

      <div className="p-6 space-y-6">
        <div className="grid grid-cols-2 gap-6">
          {/* Treemap Visualization (as nested list) */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Layers className="w-5 h-5 text-blue-400" />
              Activity Breakdown
            </h2>
            {treemapData?.children?.length ? (
              <div className="space-y-2">
                {treemapData.children.map((category) => {
                  const categoryTotal = category.children?.reduce((s, a) => s + (a.value || 0), 0) || 0;
                  const categoryPercent = Math.round((categoryTotal / totalValue) * 100);
                  const isExpanded = expandedCategories.has(category.name);
                  const colorClass = categoryColors[category.name] || 'bg-slate-500 text-slate-400';

                  return (
                    <div key={category.name} className="border border-slate-700 rounded-lg overflow-hidden">
                      <button
                        onClick={() => toggleCategory(category.name)}
                        className="w-full flex items-center gap-3 p-3 hover:bg-slate-700/30 transition-colors"
                      >
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4 text-slate-400" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-slate-400" />
                        )}
                        <div className={`w-3 h-3 rounded-full ${colorClass.split(' ')[0]}`} />
                        <span className="flex-1 text-left font-medium">{category.name}</span>
                        <span className={`text-sm font-semibold ${colorClass.split(' ')[1]}`}>
                          {categoryPercent}%
                        </span>
                      </button>

                      {isExpanded && category.children && (
                        <div className="border-t border-slate-700 bg-slate-800/30">
                          {category.children.map((app) => {
                            const appPercent = Math.round(((app.value || 0) / categoryTotal) * 100);
                            return (
                              <div
                                key={app.name}
                                className="flex items-center gap-3 px-4 py-2 pl-10 border-b border-slate-700/50 last:border-b-0"
                              >
                                <span className="flex-1 text-sm text-slate-300">{app.name}</span>
                                <span className="text-xs text-slate-500">{app.value} events</span>
                                <span className="text-xs text-slate-400">{appPercent}%</span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-slate-500 text-center py-8">No data for this day</p>
            )}
          </div>

          {/* Pareto Analysis */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-amber-400" />
              80/20 Analysis
            </h2>
            {pareto && (pareto.top_apps.length > 0 || pareto.rest_apps.length > 0) ? (
              <div className="space-y-6">
                {/* Summary */}
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-amber-400">{pareto.ratio}</div>
                    <div className="text-sm text-slate-400">Apps Account for 80% of Time</div>
                  </div>
                </div>

                {/* Top Apps (80%) */}
                <div>
                  <h3 className="text-sm font-medium text-slate-400 mb-3 uppercase tracking-wide">
                    Top {pareto.top_apps.length} Apps ({pareto.top_percent}% of time)
                  </h3>
                  <div className="space-y-2">
                    {pareto.top_apps.map((app, index) => (
                      <div key={app.app} className="flex items-center gap-3">
                        <span className="w-6 h-6 bg-amber-500/20 text-amber-400 rounded flex items-center justify-center text-xs font-bold">
                          {index + 1}
                        </span>
                        <span className="flex-1 text-sm truncate">{app.app}</span>
                        <span className="text-sm font-semibold text-amber-400">{app.percent}%</span>
                        <span className="text-xs text-slate-500">{app.count}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Rest Apps (20%) */}
                {pareto.rest_apps.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-slate-400 mb-3 uppercase tracking-wide">
                      Other Apps ({(100 - pareto.top_percent).toFixed(1)}% of time)
                    </h3>
                    <div className="space-y-2">
                      {pareto.rest_apps.slice(0, 5).map((app) => (
                        <div key={app.app} className="flex items-center gap-3 text-slate-400">
                          <span className="w-6" />
                          <span className="flex-1 text-sm truncate">{app.app}</span>
                          <span className="text-sm">{app.percent}%</span>
                          <span className="text-xs text-slate-500">{app.count}</span>
                        </div>
                      ))}
                      {pareto.rest_apps.length > 5 && (
                        <div className="text-xs text-slate-500 pl-6">
                          +{pareto.rest_apps.length - 5} more apps
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-slate-500 text-center py-8">No data for analysis</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
