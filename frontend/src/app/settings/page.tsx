'use client';

import { useState, useEffect } from 'react';
import { Header } from '@/components/layout/Header';
import { getMyDevices } from '@/lib/api';
import type { Device } from '@/lib/api';
import { getSupabase } from '@/lib/supabase';
import { Monitor, Terminal, User, RefreshCw, CheckCircle2, Clock } from 'lucide-react';

export default function SettingsPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    // Get user email from Supabase
    async function fetchUser() {
      const supabase = getSupabase();
      if (supabase) {
        const { data: { user } } = await supabase.auth.getUser();
        setUserEmail(user?.email || null);
      }
    }
    fetchUser();

    // Fetch devices
    getMyDevices().then((devs) => {
      setDevices(devs);
      setLoading(false);
    });
  }, []);

  const refreshDevices = () => {
    setLoading(true);
    getMyDevices().then((devs) => {
      setDevices(devs);
      setLoading(false);
    });
  };

  const formatLastSync = (lastSync: string | null) => {
    if (!lastSync) return 'Never';
    const date = new Date(lastSync);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <Header title="Settings" showDatePicker={false} />

      <div className="p-6 max-w-2xl space-y-6">
        {/* User Info */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
            <User className="w-5 h-5 text-blue-400" />
            Account
          </h2>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center">
              <span className="text-sm font-bold text-blue-400">
                {userEmail ? userEmail[0].toUpperCase() : '?'}
              </span>
            </div>
            <div>
              <p className="text-sm font-medium text-white">
                {userEmail || 'Loading...'}
              </p>
              <p className="text-xs text-slate-400">Google OAuth</p>
            </div>
          </div>
        </div>

        {/* Connected Devices */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Monitor className="w-5 h-5 text-emerald-400" />
              Connected Devices
            </h2>
            <button
              onClick={refreshDevices}
              disabled={loading}
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
            </div>
          ) : devices.length > 0 ? (
            <div className="space-y-3">
              {devices.map((device) => (
                <div
                  key={device.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-slate-700/30 border border-slate-700/50"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-emerald-400" />
                    <div>
                      <p className="text-sm font-medium text-white">
                        {device.name || 'Mac'}
                      </p>
                      <p className="text-xs text-slate-500 font-mono">
                        {device.id.slice(0, 16)}...
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-slate-400">
                    <Clock className="w-3.5 h-3.5" />
                    {formatLastSync(device.last_sync)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6">
              <div className="w-12 h-12 rounded-full bg-slate-700/50 flex items-center justify-center mx-auto mb-3">
                <Monitor className="w-6 h-6 text-slate-500" />
              </div>
              <p className="text-sm text-slate-400 mb-1">No devices connected</p>
              <p className="text-xs text-slate-500">Follow the instructions below to link your Mac</p>
            </div>
          )}
        </div>

        {/* How to Connect */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
            <Terminal className="w-5 h-5 text-purple-400" />
            How to Connect a Device
          </h2>

          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-xs font-bold text-purple-400">1</span>
              </div>
              <div>
                <p className="text-sm text-white">Install Captain&apos;s Log on your Mac</p>
                <div className="mt-1.5 bg-slate-900 border border-slate-700 rounded-lg p-2.5">
                  <code className="text-xs text-emerald-400 font-mono">
                    pip install captains-log
                  </code>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="w-6 h-6 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-xs font-bold text-purple-400">2</span>
              </div>
              <div>
                <p className="text-sm text-white">Link your device to your account</p>
                <div className="mt-1.5 bg-slate-900 border border-slate-700 rounded-lg p-2.5">
                  <code className="text-xs text-emerald-400 font-mono">
                    captains-log link {userEmail || 'your-email@hyperverge.co'}
                  </code>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="w-6 h-6 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-xs font-bold text-purple-400">3</span>
              </div>
              <div>
                <p className="text-sm text-white">Start the daemon</p>
                <div className="mt-1.5 bg-slate-900 border border-slate-700 rounded-lg p-2.5">
                  <code className="text-xs text-emerald-400 font-mono">
                    captains-log start
                  </code>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-5 bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3 flex items-start gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-slate-400">
              Data syncs automatically every few minutes. Only daily summaries and aggregated stats are sent to the cloud — raw activity data stays on your device.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
