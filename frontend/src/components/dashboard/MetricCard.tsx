interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  color?: 'blue' | 'green' | 'purple' | 'orange' | 'red';
}

const colorClasses = {
  blue: 'text-blue-400',
  green: 'text-emerald-400',
  purple: 'text-purple-400',
  orange: 'text-amber-400',
  red: 'text-red-400',
};

export function MetricCard({ title, value, subtitle, color = 'blue' }: MetricCardProps) {
  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 hover:bg-slate-800/70 transition-colors">
      <p className="text-sm text-slate-400 mb-1">{title}</p>
      <p className={`text-3xl font-bold ${colorClasses[color]}`}>{value}</p>
      {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
    </div>
  );
}
