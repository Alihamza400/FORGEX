import { formatDistanceToNow, format, formatDuration as fDuration, intervalToDuration } from "date-fns";

export function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const mins = Math.floor(ms / 60_000);
  const secs = Math.floor((ms % 60_000) / 1000);
  return `${mins}m ${secs}s`;
}

export function formatTokens(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)}k`;
  return `${(n / 1_000_000).toFixed(1)}M`;
}

export function formatRelative(iso: string | null): string {
  if (!iso) return "—";
  return formatDistanceToNow(new Date(iso), { addSuffix: true });
}

export function formatAbsolute(iso: string | null): string {
  if (!iso) return "—";
  return format(new Date(iso), "MMM d, yyyy HH:mm:ss");
}

export function formatDuration(isoStart: string | null, isoEnd: string | null): string {
  if (!isoStart) return "—";
  const start = new Date(isoStart);
  const end = isoEnd ? new Date(isoEnd) : new Date();
  const duration = intervalDurationToObject({ start, end });
  return fDuration(duration, { format: ["hours", "minutes", "seconds"], delimiter: " " }) || "<1s";
}

function intervalDurationToObject({ start, end }: { start: Date; end: Date }) {
  const d = intervalToDuration({ start, end });
  return { hours: d.hours ?? 0, minutes: d.minutes ?? 0, seconds: d.seconds ?? 0 };
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    idle: "text-gray-400",
    busy: "text-cyan-400",
    error: "text-red-400",
    offline: "text-gray-600",
    completed: "text-emerald-400",
    running: "text-blue-400",
    failed: "text-red-400",
    pending: "text-yellow-400",
    skipped: "text-gray-500",
  };
  return map[status] ?? "text-gray-400";
}

export function statusBgColor(status: string): string {
  const map: Record<string, string> = {
    idle: "bg-gray-500/20",
    busy: "bg-cyan-500/20",
    error: "bg-red-500/20",
    offline: "bg-gray-700/20",
    completed: "bg-emerald-500/20",
    running: "bg-blue-500/20",
    failed: "bg-red-500/20",
    pending: "bg-yellow-500/20",
    skipped: "bg-gray-600/20",
  };
  return map[status] ?? "bg-gray-500/20";
}
