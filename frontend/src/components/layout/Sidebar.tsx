'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Clock,
  PieChart,
  AppWindow,
  BarChart3,
  Layers,
  TrendingUp,
  Lightbulb,
  Settings,
  Monitor,
} from 'lucide-react';
import { ThemeToggle } from '@/components/theme-toggle';
import { getMyDevices } from '@/lib/api';
import type { Device } from '@/lib/api';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Timeline', href: '/timeline', icon: Clock },
  { name: 'Time Analysis', href: '/time-analysis', icon: PieChart },
  { name: 'Apps', href: '/apps', icon: AppWindow },
  { type: 'divider', label: 'Analytics' },
  { name: 'Overview', href: '/analytics', icon: BarChart3 },
  { name: 'Deep Dive', href: '/analytics/deep-dive', icon: Layers },
  { name: 'Trends', href: '/analytics/trends', icon: TrendingUp },
  { name: 'Insights', href: '/analytics/insights', icon: Lightbulb },
  { type: 'divider', label: 'Account' },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const [devices, setDevices] = useState<Device[]>([]);
  const [devicesLoaded, setDevicesLoaded] = useState(false);

  useEffect(() => {
    // Only fetch devices on deployed site
    if (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
      getMyDevices().then((devs) => {
        setDevices(devs);
        setDevicesLoaded(true);
      });
    } else {
      setDevicesLoaded(true);
    }
  }, []);

  const primaryDevice = devices.length > 0 ? devices[0] : null;

  return (
    <aside className="fixed inset-y-0 left-0 z-50 w-64 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col">
      <div className="flex h-16 items-center gap-2 px-6 border-b border-slate-200 dark:border-slate-800">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
          <span className="text-white font-bold text-sm">CL</span>
        </div>
        <span className="text-lg font-semibold text-slate-900 dark:text-white">Captain&apos;s Log</span>
      </div>

      <nav className="p-4 space-y-1 flex-1">
        {navigation.map((item, index) => {
          if ('type' in item && item.type === 'divider') {
            return (
              <div key={index} className="pt-4 pb-2">
                <span className="px-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  {item.label}
                </span>
              </div>
            );
          }

          const Icon = item.icon;
          const isActive = pathname === item.href ||
            (item.href !== '/' && pathname?.startsWith(item.href as string));

          return (
            <Link
              key={item.name}
              href={item.href as string}
              className={`
                flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors
                ${isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800'
                }
              `}
            >
              {Icon && <Icon className="w-5 h-5" />}
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* Device indicator */}
      {devicesLoaded && (
        <div className="px-4 pb-2">
          {primaryDevice ? (
            <Link
              href="/settings"
              className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors group"
            >
              <div className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-slate-700 dark:text-slate-300 truncate">
                  Connected
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-500 truncate">
                  {primaryDevice.name || primaryDevice.id.slice(0, 12)}
                </p>
              </div>
              <Monitor className="w-3.5 h-3.5 text-slate-400 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
            </Link>
          ) : (
            <Link
              href="/settings"
              className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <div className="w-2 h-2 rounded-full bg-slate-400 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                  No device
                </p>
              </div>
              <span className="text-xs text-blue-500 dark:text-blue-400 flex-shrink-0">
                Connect &rarr;
              </span>
            </Link>
          )}
        </div>
      )}

      <div className="p-4 border-t border-slate-200 dark:border-slate-800">
        <ThemeToggle />
      </div>
    </aside>
  );
}
