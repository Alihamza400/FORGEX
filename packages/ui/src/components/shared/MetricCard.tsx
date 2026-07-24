import type { LucideIcon } from "lucide-react";

interface MetricCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  trend?: { value: number; positive: boolean };
  color: "cyan" | "emerald" | "violet" | "amber";
  loading?: boolean;
  onClick?: () => void;
}

const glowMap = {
  cyan: "glow-cyan",
  emerald: "glow-emerald",
  violet: "glow-violet",
  amber: "glow-amber",
};

const iconColorMap = {
  cyan: "text-cyan-400 bg-cyan-500/10",
  emerald: "text-emerald-400 bg-emerald-500/10",
  violet: "text-violet-400 bg-violet-500/10",
  amber: "text-amber-400 bg-amber-500/10",
};

export function MetricCard({
  icon: Icon,
  label,
  value,
  trend,
  color,
  loading = false,
  onClick,
}: MetricCardProps) {
  if (loading) {
    return (
      <div className="glass rounded-xl p-5 animate-pulse">
        <div className="h-10 w-10 rounded-lg bg-slate-800 mb-3" />
        <div className="h-3 w-24 bg-slate-800 rounded mb-2" />
        <div className="h-6 w-16 bg-slate-800 rounded" />
      </div>
    );
  }

  return (
    <div
      onClick={onClick}
      className={`glass rounded-xl p-5 ${glowMap[color]} ${onClick ? "cursor-pointer glass-hover" : ""} animate-fade-in`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className={`p-2 rounded-lg ${iconColorMap[color]}`}>
          <Icon className="w-5 h-5" />
        </div>
        {trend && (
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded-full ${
              trend.positive
                ? "text-emerald-400 bg-emerald-500/10"
                : "text-red-400 bg-red-500/10"
            }`}
          >
            {trend.positive ? "+" : ""}
            {trend.value}%
          </span>
        )}
      </div>
      <p className="text-slate-400 text-sm font-medium mb-1">{label}</p>
      <p className="text-2xl font-bold text-slate-100">{value}</p>
    </div>
  );
}
