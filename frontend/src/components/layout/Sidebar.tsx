'use client';

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
} from 'lucide-react';

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
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-50 w-64 bg-slate-900 border-r border-slate-800">
      <div className="flex h-16 items-center gap-2 px-6 border-b border-slate-800">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
          <span className="text-white font-bold text-sm">CL</span>
        </div>
        <span className="text-lg font-semibold text-white">Captain&apos;s Log</span>
      </div>

      <nav className="p-4 space-y-1">
        {navigation.map((item, index) => {
          if ('type' in item && item.type === 'divider') {
            return (
              <div key={index} className="pt-4 pb-2">
                <span className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
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
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
                }
              `}
            >
              {Icon && <Icon className="w-5 h-5" />}
              {item.name}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
