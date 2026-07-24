import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bot,
  Cpu,
  Activity,
  AlertTriangle,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api } from "../api/client";
import { MetricCard } from "../components/shared/MetricCard";
import { StatusBadge } from "../components/shared/StatusBadge";
import { DataTable } from "../components/shared/DataTable";
import { PageSkeleton } from "../components/shared/LoadingSkeleton";
import { useAppStore } from "../store/app";
import { formatRelative } from "../utils/format";
import type { AgentDescriptor } from "../types/api";

export function Dashboard() {
  const navigate = useNavigate();
  const { agents, setAgents } = useAppStore();
  const { data: health } = useApi(() => api.health());
  const { data: agentsData, loading } = useApi(() => api.agents.list());

  useEffect(() => {
    if (agentsData) setAgents(agentsData.agents);
  }, [agentsData, setAgents]);

  if (loading || !health) return <PageSkeleton />;

  const onlineAgents = agents.filter((a) => a.status !== "offline");
  const busyAgents = agents.filter((a) => a.status === "busy");
  const errorAgents = agents.filter((a) => a.status === "error");

  const stats = [
    {
      icon: Bot,
      label: "Total Agents",
      value: agents.length,
      color: "cyan" as const,
      trend: agents.length > 0 ? { value: agents.length, positive: true } : undefined,
    },
    {
      icon: Activity,
      label: "Online Agents",
      value: onlineAgents.length,
      color: "emerald" as const,
    },
    {
      icon: Cpu,
      label: "Busy Agents",
      value: busyAgents.length,
      color: "violet" as const,
    },
    {
      icon: AlertTriangle,
      label: "Error Agents",
      value: errorAgents.length,
      color: "amber" as const,
    },
  ];

  const agentColumns = [
    {
      key: "name",
      header: "Agent",
      sortable: true,
      render: (a: AgentDescriptor) => (
        <span className="font-medium text-slate-200">{a.name}</span>
      ),
    },
    {
      key: "role",
      header: "Role",
      sortable: true,
      render: (a: AgentDescriptor) => (
        <span className="text-slate-400">{a.role}</span>
      ),
    },
    {
      key: "capabilities",
      header: "Capabilities",
      render: (a: AgentDescriptor) => (
        <div className="flex flex-wrap gap-1">
          {a.capabilities.map((cap) => (
            <span
              key={cap}
              className="px-2 py-0.5 text-xs rounded-full bg-cyan-500/10 text-cyan-400 capitalize"
            >
              {cap}
            </span>
          ))}
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortable: true,
      render: (a: AgentDescriptor) => (
        <StatusBadge status={a.status} animated />
      ),
    },
    {
      key: "last_heartbeat",
      header: "Last Seen",
      sortable: true,
      render: (a: AgentDescriptor) => (
        <span className="text-slate-400 text-xs">
          {formatRelative(a.last_heartbeat)}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">
            Status: {health.status} &middot; Services:{" "}
            {Object.keys(health.services).join(", ")}
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 glass rounded-lg">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-sm text-slate-400">All Systems Nominal</span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <MetricCard key={stat.label} {...stat} />
        ))}
      </div>

      <div className="glass rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-100">
            Registered Agents
          </h2>
          <button
            onClick={() => navigate("/agents")}
            className="text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            View All &rarr;
          </button>
        </div>
        <DataTable
          columns={agentColumns}
          data={agents}
          keyExtractor={(a) => a.name}
          searchable
          searchKeys={["name", "role"]}
          emptyMessage="No agents registered"
          onRowClick={(a) => navigate(`/agents/${a.name}`)}
        />
      </div>
    </div>
  );
}
