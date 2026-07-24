import { useState, useMemo } from "react";
import {
  Logs as LogsIcon,
  Search,
  AlertCircle,
  Info,
  AlertTriangle,
  Bug,
  ChevronDown,
  Trash2,
  Download,
  RefreshCw,
} from "lucide-react";
import { usePolling } from "../hooks/useApi";
import { api } from "../api/client";
import { EmptyState } from "../components/shared/EmptyState";
import { formatAbsolute } from "../utils/format";
import type { AgentDescriptor } from "../types/api";

type LogLevel = "info" | "warn" | "error" | "debug";
type LogEntry = {
  timestamp: string;
  level: LogLevel;
  message: string;
  agent: string;
};

const levelIcons: Record<LogLevel, typeof Info> = {
  info: Info,
  warn: AlertTriangle,
  error: AlertCircle,
  debug: Bug,
};

const levelColors: Record<LogLevel, string> = {
  info: "text-blue-400 bg-blue-500/10",
  warn: "text-amber-400 bg-amber-500/10",
  error: "text-red-400 bg-red-500/10",
  debug: "text-slate-400 bg-slate-500/10",
};

const levelDotColors: Record<LogLevel, string> = {
  info: "bg-blue-400",
  warn: "bg-amber-400",
  error: "bg-red-400",
  debug: "bg-slate-400",
};

const mockLogs: LogEntry[] = Array.from({ length: 50 }, (_, i) => {
  const levels: LogLevel[] = ["info", "info", "info", "warn", "error", "debug"];
  const level = levels[Math.floor(Math.random() * levels.length)]!;
  const agents = ["agent-alpha", "agent-beta", "agent-gamma", "forge-api", "system"];
  return {
    timestamp: new Date(Date.now() - i * 30000).toISOString(),
    level,
    message: ([
      "Task completed successfully",
      "Agent heartbeat received",
      "Processing sub-task #" + (i + 1),
      "Connection to Ollama established",
      "Memory store operation completed",
      "Token budget at 75% utilization",
      "Agent status changed to busy",
      "Orchestration plan generated",
      "Sub-task dependency resolved",
      "Cache hit for embedding query",
    ] as const)[Math.floor(Math.random() * 10)]!,
    agent: agents[Math.floor(Math.random() * agents.length)]!,
  };
});

export function Logs() {
  const [search, setSearch] = useState("");
  const [levelFilter, setLevelFilter] = useState<LogLevel | "all">("all");
  const [agentFilter, setAgentFilter] = useState<string>("all");
  const [autoRefresh, setAutoRefresh] = useState(true);

  const { data: agentsData } = usePolling(
    () => api.agents.list(),
    5000,
    autoRefresh,
  );

  const filtered = useMemo(() => {
    return mockLogs.filter((log) => {
      if (levelFilter !== "all" && log.level !== levelFilter) return false;
      if (agentFilter !== "all" && log.agent !== agentFilter) return false;
      if (search && !log.message.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [search, levelFilter, agentFilter]);

  const agents = agentsData?.agents ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Logs</h1>
          <p className="text-sm text-slate-500 mt-1">
            Real-time agent and system logs
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-all ${
              autoRefresh
                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                : "text-slate-400 glass glass-hover"
            }`}
          >
            <RefreshCw className={`w-4 h-4 ${autoRefresh ? "animate-spin-slow" : ""}`} />
            Auto
          </button>
          <button className="flex items-center gap-2 px-3 py-2 text-sm text-slate-400 glass rounded-lg glass-hover">
            <Download className="w-4 h-4" />
            Export
          </button>
          <button className="flex items-center gap-2 px-3 py-2 text-sm text-slate-400 glass rounded-lg glass-hover">
            <Trash2 className="w-4 h-4" />
            Clear
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search logs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg
              text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50
              transition-colors"
          />
        </div>

        <div className="flex gap-2">
          {(["all", "info", "warn", "error", "debug"] as const).map((level) => (
            <button
              key={level}
              onClick={() => setLevelFilter(level)}
              className={`px-3 py-2 text-xs rounded-lg capitalize transition-all ${
                levelFilter === level
                  ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"
                  : "text-slate-400 glass glass-hover border border-transparent"
              }`}
            >
              {level === "all" ? "All" : level}
            </button>
          ))}
        </div>

        <select
          value={agentFilter}
          onChange={(e) => setAgentFilter(e.target.value)}
          className="px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
            text-slate-200 focus:outline-none focus:border-cyan-500/50 transition-colors"
        >
          <option value="all">All Agents</option>
          {agents.map((a: AgentDescriptor) => (
            <option key={a.name} value={a.name}>
              {a.name}
            </option>
          ))}
          <option value="system">System</option>
        </select>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={LogsIcon}
          title="No logs found"
          description="Try adjusting your filters or search query."
        />
      ) : (
        <div className="glass rounded-xl overflow-hidden">
          <div className="divide-y divide-slate-800/50 max-h-[600px] overflow-y-auto">
            {filtered.map((log, i) => (
              <LogRow key={i} log={log} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function LogRow({ log }: { log: LogEntry }) {
  const Icon = levelIcons[log.level];
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={`px-4 py-2.5 hover:bg-slate-800/30 transition-colors cursor-pointer ${
        log.level === "error" ? "bg-red-500/5" : ""
      }`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center gap-3">
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${levelDotColors[log.level]}`} />
        <span className={`p-1 rounded ${levelColors[log.level]}`}>
          <Icon className="w-3 h-3" />
        </span>
        <span className="text-xs font-mono text-slate-500 w-20 flex-shrink-0">
          {log.level.toUpperCase().padEnd(5)}
        </span>
        <span className="text-xs text-cyan-400 font-mono flex-shrink-0 w-24">
          {log.agent}
        </span>
        <span className="text-sm text-slate-300 flex-1 truncate">
          {log.message}
        </span>
        <span className="text-xs text-slate-600 flex-shrink-0">
          {formatAbsolute(log.timestamp)}
        </span>
        <ChevronDown
          className={`w-3 h-3 text-slate-600 transition-transform ${
            expanded ? "rotate-180" : ""
          }`}
        />
      </div>
      {expanded && (
        <div className="mt-2 ml-8 p-3 glass rounded-lg text-xs text-slate-400 font-mono animate-fade-in">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="text-slate-500">Timestamp: </span>
              {formatAbsolute(log.timestamp)}
            </div>
            <div>
              <span className="text-slate-500">Agent: </span>
              {log.agent}
            </div>
            <div>
              <span className="text-slate-500">Level: </span>
              {log.level}
            </div>
            <div>
              <span className="text-slate-500">Message: </span>
              {log.message}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
