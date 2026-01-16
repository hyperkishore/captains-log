'use client';

import { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { Header } from '@/components/layout/Header';
import { getTimeline, getScreenshots, getScreenshotUrl, analyzeScreenshotDeep, type WorkAnalysis } from '@/lib/api';
import type { Activity, Screenshot } from '@/lib/types';
import { Clock, Globe, Monitor, Image as ImageIcon, ExternalLink, Sparkles, Loader2, Code, FolderGit2, Brain, FileText } from 'lucide-react';

export default function Timeline() {
  const [date, setDate] = useState(new Date());
  const [activities, setActivities] = useState<Activity[]>([]);
  const [screenshots, setScreenshots] = useState<Screenshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedScreenshot, setSelectedScreenshot] = useState<Screenshot | null>(null);
  const [analysis, setAnalysis] = useState<WorkAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  const dateStr = format(date, 'yyyy-MM-dd');

  const handleAnalyze = async (screenshot: Screenshot) => {
    setAnalyzing(true);
    setAnalysis(null);
    try {
      const result = await analyzeScreenshotDeep(screenshot.id);
      setAnalysis(result);
    } catch (err) {
      console.error('Analysis failed:', err);
    } finally {
      setAnalyzing(false);
    }
  };

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const [activitiesData, screenshotsData] = await Promise.all([
          getTimeline(dateStr),
          getScreenshots(dateStr),
        ]);
        setActivities(activitiesData);
        setScreenshots(screenshotsData);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [dateStr]);

  // Find screenshot nearest to activity timestamp
  const findNearestScreenshot = (timestamp: string): Screenshot | null => {
    const activityTime = new Date(timestamp).getTime();
    let nearest: Screenshot | null = null;
    let minDelta = 60000; // 60 seconds max

    for (const screenshot of screenshots) {
      const screenshotTime = new Date(screenshot.timestamp).getTime();
      const delta = Math.abs(screenshotTime - activityTime);
      if (delta < minDelta) {
        minDelta = delta;
        nearest = screenshot;
      }
    }
    return nearest;
  };

  const idleStatusColors: Record<string, string> = {
    ACTIVE: 'bg-emerald-500',
    IDLE_BUT_PRESENT: 'bg-amber-500',
    WATCHING_MEDIA: 'bg-blue-500',
    READING: 'bg-purple-500',
    AWAY: 'bg-slate-500',
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
        <Header title="Timeline" date={date} onDateChange={setDate} />
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <Header title="Timeline" date={date} onDateChange={setDate} />

      <div className="p-6">
        {/* Stats Header */}
        <div className="flex items-center gap-6 mb-6 text-sm text-slate-400">
          <span className="flex items-center gap-2">
            <Clock className="w-4 h-4" />
            {activities.length} activities
          </span>
          <span className="flex items-center gap-2">
            <ImageIcon className="w-4 h-4" />
            {screenshots.length} screenshots
          </span>
        </div>

        {/* Timeline */}
        <div className="space-y-2">
          {activities.length > 0 ? (
            activities.map((activity, index) => {
              const screenshot = findNearestScreenshot(activity.timestamp);
              const time = format(new Date(activity.timestamp), 'HH:mm:ss');

              return (
                <div
                  key={index}
                  className="flex gap-4 p-4 bg-slate-800/50 border border-slate-700 rounded-xl hover:bg-slate-800/70 transition-colors"
                >
                  {/* Time */}
                  <div className="w-20 flex-shrink-0">
                    <span className="text-sm text-slate-400 font-mono">{time}</span>
                  </div>

                  {/* Status indicator */}
                  <div className="flex-shrink-0">
                    <div
                      className={`w-3 h-3 rounded-full ${idleStatusColors[activity.idle_status] || 'bg-slate-500'}`}
                      title={activity.idle_status}
                    />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Monitor className="w-4 h-4 text-blue-400" />
                      <span className="font-medium truncate">{activity.app_name}</span>
                    </div>
                    {activity.window_title && (
                      <p className="text-sm text-slate-400 truncate">{activity.window_title}</p>
                    )}
                    {activity.url && (
                      <div className="flex items-center gap-1 mt-1">
                        <Globe className="w-3 h-3 text-slate-500" />
                        <a
                          href={activity.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-blue-400 hover:underline truncate"
                        >
                          {activity.url}
                        </a>
                        <ExternalLink className="w-3 h-3 text-slate-500" />
                      </div>
                    )}
                  </div>

                  {/* Screenshot thumbnail */}
                  {screenshot && (
                    <button
                      onClick={() => setSelectedScreenshot(screenshot)}
                      className="flex-shrink-0 w-24 h-16 rounded-lg overflow-hidden border border-slate-600 hover:border-blue-500 transition-colors"
                    >
                      <img
                        src={getScreenshotUrl(screenshot)}
                        alt="Screenshot"
                        className="w-full h-full object-cover"
                      />
                    </button>
                  )}
                </div>
              );
            })
          ) : (
            <div className="text-center py-16 text-slate-500">
              <Clock className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No activities recorded for this day</p>
            </div>
          )}
        </div>
      </div>

      {/* Screenshot Modal */}
      {selectedScreenshot && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setSelectedScreenshot(null);
              setAnalysis(null);
            }
          }}
        >
          <div className="max-w-4xl max-h-[90vh] overflow-auto bg-slate-900 rounded-xl p-4">
            <img
              src={getScreenshotUrl(selectedScreenshot)}
              alt="Screenshot"
              className="rounded-lg"
            />
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-slate-400">
                {format(new Date(selectedScreenshot.timestamp), 'MMM d, yyyy HH:mm:ss')}
              </p>
              <button
                onClick={() => handleAnalyze(selectedScreenshot)}
                disabled={analyzing}
                className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 rounded-lg text-sm transition-colors"
              >
                {analyzing ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4" />
                )}
                {analyzing ? 'Analyzing...' : 'Analyze with AI'}
              </button>
            </div>

            {/* Analysis Results */}
            {analysis && (
              <div className="mt-4 p-4 bg-slate-800/50 border border-slate-700 rounded-lg space-y-4">
                {/* Header */}
                <div className="flex items-center gap-2">
                  <Brain className="w-4 h-4 text-purple-400" />
                  <span className="text-sm font-medium text-purple-400">Deep Work Analysis</span>
                  {analysis.estimated_cost && (
                    <span className="text-xs text-slate-500 ml-auto">
                      ${analysis.estimated_cost.toFixed(4)}
                    </span>
                  )}
                </div>

                {/* Summary */}
                <p className="text-slate-300">{analysis.summary}</p>

                {/* Project & Task */}
                <div className="grid grid-cols-2 gap-3">
                  {analysis.project && (
                    <div className="flex items-center gap-2 p-2 bg-slate-700/50 rounded-lg">
                      <FolderGit2 className="w-4 h-4 text-blue-400" />
                      <div>
                        <span className="text-xs text-slate-500">Project</span>
                        <p className="text-sm font-medium">{analysis.project}</p>
                      </div>
                    </div>
                  )}
                  {analysis.file_or_document && (
                    <div className="flex items-center gap-2 p-2 bg-slate-700/50 rounded-lg">
                      <FileText className="w-4 h-4 text-amber-400" />
                      <div>
                        <span className="text-xs text-slate-500">File</span>
                        <p className="text-sm font-medium truncate">{analysis.file_or_document}</p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Task Description */}
                {analysis.task_description && (
                  <div className="p-2 bg-slate-700/30 rounded-lg">
                    <span className="text-xs text-slate-500">Task</span>
                    <p className="text-sm text-slate-300">{analysis.task_description}</p>
                  </div>
                )}

                {/* Technologies */}
                {analysis.technologies && analysis.technologies.length > 0 && (
                  <div className="flex items-center gap-2 flex-wrap">
                    <Code className="w-4 h-4 text-slate-500" />
                    {analysis.technologies.map((tech) => (
                      <span key={tech} className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded">
                        {tech}
                      </span>
                    ))}
                  </div>
                )}

                {/* Scores and Category */}
                <div className="flex items-center gap-3 text-xs">
                  <span className={`px-2 py-1 rounded ${
                    analysis.category === 'development' ? 'bg-blue-500/20 text-blue-400' :
                    analysis.category === 'communication' ? 'bg-pink-500/20 text-pink-400' :
                    analysis.category === 'research' ? 'bg-amber-500/20 text-amber-400' :
                    analysis.category === 'writing' ? 'bg-purple-500/20 text-purple-400' :
                    'bg-slate-500/20 text-slate-400'
                  }`}>
                    {analysis.category}/{analysis.subcategory}
                  </span>
                  <span className={`px-2 py-1 rounded ${
                    analysis.focus_indicator === 'productive' ? 'bg-emerald-500/20 text-emerald-400' :
                    analysis.focus_indicator === 'distraction' ? 'bg-red-500/20 text-red-400' :
                    'bg-slate-500/20 text-slate-400'
                  }`}>
                    {analysis.focus_indicator}
                  </span>
                  <div className="ml-auto flex items-center gap-4">
                    <div className="flex items-center gap-1">
                      <span className="text-slate-500">Deep Work:</span>
                      <span className={`font-medium ${
                        analysis.deep_work_score >= 70 ? 'text-emerald-400' :
                        analysis.deep_work_score >= 40 ? 'text-amber-400' :
                        'text-slate-400'
                      }`}>
                        {analysis.deep_work_score}%
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-slate-500">Context:</span>
                      <span className="text-slate-300">{analysis.context_richness}%</span>
                    </div>
                  </div>
                </div>

                {/* Key Text */}
                {analysis.key_text && (
                  <p className="text-xs text-slate-500 italic border-l-2 border-slate-600 pl-2">
                    &ldquo;{analysis.key_text}&rdquo;
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
