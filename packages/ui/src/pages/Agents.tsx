import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bot,
  FileJson,
  Plus,
  RefreshCw,
  Search,
  Wifi,
  WifiOff,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api } from "../api/client";
import { StatusBadge } from "../components/shared/StatusBadge";
import { EmptyState } from "../components/shared/EmptyState";
import { Modal } from "../components/shared/Modal";
import { PageSkeleton } from "../components/shared/LoadingSkeleton";
import { useToast } from "../hooks/useToast";
import { useAppStore } from "../store/app";
import { formatRelative } from "../utils/format";
import type { AgentDescriptor } from "../types/api";

const capabilityColors: Record<string, string> = {
  search: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  analysis: "bg-violet-500/10 text-violet-400 border-violet-500/20",
  code: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  writing: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  reasoning: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
  summarization: "bg-pink-500/10 text-pink-400 border-pink-500/20",
  custom: "bg-slate-500/10 text-slate-400 border-slate-500/20",
};

export function Agents() {
  const navigate = useNavigate();
  const { agents, setAgents } = useAppStore();
  const { data, loading, refetch } = useApi(() => api.agents.list());
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (data) setAgents(data.map((a) => ({
      name: a.name,
      role: a.role,
      goal: a.goal,
      capabilities: [] as import("../types/api").AgentCapability[],
      status: a.status as import("../types/api").AgentStatus,
      last_heartbeat: null,
      endpoint: null,
      metadata: {},
    })));
  }, [data, setAgents]);

  const filtered = agents.filter(
    (a) =>
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.role.toLowerCase().includes(search.toLowerCase()),
  );

  if (loading) return <PageSkeleton />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Agents</h1>
          <p className="text-sm text-slate-500 mt-1">
            Manage your AI agents and their capabilities
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-3 py-2 text-sm text-slate-400 hover:text-slate-200
              glass rounded-lg glass-hover transition-all"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={() => navigate("/templates")}
            className="flex items-center gap-2 px-3 py-2 text-sm text-violet-400 hover:text-violet-300
              bg-violet-500/10 rounded-lg hover:bg-violet-500/20 transition-all border border-violet-500/20"
          >
            <FileJson className="w-4 h-4" />
            From Template
          </button>
          <button
            onClick={() => setShowRegisterModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-cyan-500/10 text-cyan-400 rounded-lg
              hover:bg-cyan-500/20 transition-all text-sm font-medium border border-cyan-500/20"
          >
            <Plus className="w-4 h-4" />
            Register Agent
          </button>
        </div>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="text"
          placeholder="Search agents..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg
            text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50
            transition-colors"
        />
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={Bot}
          title="No agents found"
          description={
            search
              ? "No agents match your search. Try a different query."
              : "Register your first AI agent to get started."
          }
          action={
            search
              ? undefined
              : {
                  label: "Register Agent",
                  onClick: () => setShowRegisterModal(true),
                }
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((agent) => (
            <AgentCard
              key={agent.name}
              agent={agent}
              onClick={() => navigate(`/agents/${agent.name}`)}
            />
          ))}
        </div>
      )}

      {showRegisterModal && (
        <RegisterAgentModal
          onClose={() => setShowRegisterModal(false)}
          onRegistered={() => {
            setShowRegisterModal(false);
            refetch();
          }}
        />
      )}
    </div>
  );
}

function AgentCard({
  agent,
  onClick,
}: {
  agent: AgentDescriptor;
  onClick: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className="glass rounded-xl p-5 glass-hover cursor-pointer group animate-fade-in"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-cyan-500/10 text-cyan-400 group-hover:bg-cyan-500/20 transition-colors">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-200">{agent.name}</h3>
            <p className="text-xs text-slate-500 mt-0.5">{agent.role}</p>
          </div>
        </div>
        {agent.status === "offline" ? (
          <WifiOff className="w-4 h-4 text-slate-600" />
        ) : (
          <Wifi className="w-4 h-4 text-emerald-400" />
        )}
      </div>

      <div className="flex items-center gap-2 mb-3">
        <StatusBadge status={agent.status} animated />
        {agent.last_heartbeat && (
          <span className="text-xs text-slate-500">
            {formatRelative(agent.last_heartbeat)}
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {agent.capabilities.map((cap) => (
          <span
            key={cap}
            className={`px-2 py-0.5 text-xs rounded-full border capitalize ${
              capabilityColors[cap] ?? capabilityColors.custom
            }`}
          >
            {cap}
          </span>
        ))}
      </div>
    </div>
  );
}

function RegisterAgentModal({
  onClose,
  onRegistered,
}: {
  onClose: () => void;
  onRegistered: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [goal, setGoal] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !role) {
      toast.error("Name and role are required");
      return;
    }
    setLoading(true);
    try {
      const config = {
        name,
        role,
        goal,
        model: { name: "tinyllama", provider: "ollama", temperature: 0.7, max_tokens: 2048, top_p: 0.9 },
        tools: [],
        memory: { type: "none", collection: "default", embedding_model: "nomic-embed-text", top_k: 5, score_threshold: 0.5 },
        max_iterations: 10,
        system_prompt_extra: "",
        environment: {},
      };
      const result = await api.agents.validate({ config });
      if (!result.valid) {
        toast.error(result.errors.join(", "));
        return;
      }
      await api.agents.create({
        name,
        role,
        goal,
        model_name: config.model.name,
      });
      toast.success(`Agent "${name}" created`);
      onRegistered();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Register Agent" size="lg">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">
            Name *
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="my-agent"
            className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
              text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 transition-colors"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">
            Role *
          </label>
          <input
            type="text"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="e.g., Code Assistant"
            className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
              text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 transition-colors"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">
            Goal
          </label>
          <textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="Describe the agent's purpose..."
            rows={3}
            className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
              text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 transition-colors resize-none"
          />
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200
              glass rounded-lg glass-hover transition-all"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 text-sm font-medium bg-cyan-500/10 text-cyan-400 rounded-lg
              hover:bg-cyan-500/20 transition-all border border-cyan-500/20 disabled:opacity-50"
          >
            {loading ? "Validating..." : "Register"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
