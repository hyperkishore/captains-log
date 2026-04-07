'use client';

import { Monitor, Terminal, RefreshCw, CheckCircle2 } from 'lucide-react';

interface DeviceSetupProps {
  userEmail?: string;
}

export function DeviceSetup({ userEmail }: DeviceSetupProps) {
  const email = userEmail || 'your-email@hyperverge.co';

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center p-6">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center mx-auto mb-4">
            <Monitor className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">
            Welcome to Captain&apos;s Log!
          </h1>
          <p className="text-slate-400">
            To see your activity data, connect your Mac.
          </p>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 space-y-5">
          <div className="flex items-start gap-4">
            <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-sm font-bold text-blue-400">1</span>
            </div>
            <div>
              <p className="text-sm font-medium text-white">Open Terminal on your Mac</p>
              <p className="text-xs text-slate-400 mt-1">
                You can find it in Applications &gt; Utilities &gt; Terminal
              </p>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-sm font-bold text-blue-400">2</span>
            </div>
            <div>
              <p className="text-sm font-medium text-white">Run the link command</p>
              <div className="mt-2 bg-slate-900 border border-slate-700 rounded-lg p-3 flex items-center gap-2">
                <Terminal className="w-4 h-4 text-slate-500 flex-shrink-0" />
                <code className="text-sm text-emerald-400 font-mono">
                  captains-log link {email}
                </code>
              </div>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-sm font-bold text-blue-400">3</span>
            </div>
            <div>
              <p className="text-sm font-medium text-white">Wait a few minutes for data to sync</p>
              <p className="text-xs text-slate-400 mt-1">
                The daemon will begin tracking and syncing your activity
              </p>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-sm font-bold text-blue-400">4</span>
            </div>
            <div>
              <p className="text-sm font-medium text-white">Refresh this page</p>
              <p className="text-xs text-slate-400 mt-1">
                Your data will appear automatically once your device is linked
              </p>
            </div>
          </div>
        </div>

        <div className="mt-6 flex items-center justify-center gap-4">
          <button
            onClick={() => window.location.reload()}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh Page
          </button>
        </div>

        <div className="mt-8 bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-4 flex items-start gap-3">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-emerald-400">Privacy first</p>
            <p className="text-xs text-slate-400 mt-1">
              Raw activity data stays on your Mac. Only daily summaries and aggregated stats are synced to the cloud.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
