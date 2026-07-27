import { useState, useEffect, useCallback } from "react";
import {
  GitBranch,
  Play,
  CheckCircle2,
  Clock,
  ArrowRight,
  Layers,
  Loader2,
} from "lucide-react";
import { useApi, usePolling } from "../hooks/useApi";
import { api } from "../api/client";
import { StatusBadge } from "../components/shared/StatusBadge";
import { MetricCard } from "../components/shared/MetricCard";
import { CodeBlock } from "../components/shared/CodeBlock";
import { EmptyState } from "../components/shared/EmptyState";
import { useToast } from "../hooks/useToast";
import { useAppStore } from "../store/app";
import { formatMs, formatTokens, formatRelative } from "../utils/format";
import type {
  AgentConfig,
  OrchestrateResponse,
  OrchestrationResult,
  SubTaskResult,
} from "../types/api";

export function Orchestrate() {
  const toast = useToast();
  const { agents, setAgents } = useAppStore();
  const { data: agentsData } = useApi(() => api.agents.list());
  const { orchestrationHistory, addOrchestration } = useAppStore();
  const [running, setRunning] = useState(false);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [task, setTask] = useState("");
  const [selectedStrategy, setSelectedStrategy] = useState("auto");
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);

  useEffect(() => {
    if (agentsData) setAgents(agentsData.map((a) => ({
      name: a.name,
      role: a.role,
      goal: a.goal,
      capabilities: [] as import("../types/api").AgentCapability[],
      status: a.status as import("../types/api").AgentStatus,
      last_heartbeat: null,
      endpoint: null,
      metadata: {},
    })));
  }, [agentsData, setAgents]);

  const shouldPoll = currentId !== null && running;

  const { data: pollResult } = usePolling(
    () => api.orchestrations.get(currentId!),
    1000,
    shouldPoll,
  ) as { data: OrchestrateResponse | null; loading: boolean; error: string | null; refetch: () => void };

  useEffect(() => {
    if (pollResult?.result && running) {
      const r = pollResult.result;
      if (r.status === "completed" || r.status === "failed") {
        setRunning(false);
        addOrchestration(r);
        setCurrentId(null);
        if (r.status === "completed") {
          toast.success("Orchestration completed");
        } else {
          toast.error(r.error ?? "Orchestration failed");
        }
      }
    }
  }, [pollResult, running, addOrchestration, toast]);

  const handleStart = useCallback(async () => {
    if (!task.trim()) return;
    if (selectedAgents.length === 0) {
      toast.error("Select at least one agent");
      return;
    }

    setRunning(true);
    try {
      const agentConfigs: Record<string, AgentConfig> = {};
      for (const name of selectedAgents) {
        const agent = agents.find((a) => a.name === name);
        if (agent) {
          agentConfigs[name] = {
            name: agent.name,
            role: agent.role,
            goal: agent.goal,
            model: { name: "llama3.2:3b", provider: "ollama", temperature: 0.7, max_tokens: 2048, top_p: 0.9 },
            tools: [],
            memory: { type: "none", collection: "default", embedding_model: "nomic-embed-text", top_k: 5, score_threshold: 0.5 },
            max_iterations: 10,
            system_prompt_extra: "",
            environment: {},
          };
        }
      }

      const response = await api.orchestrations.create({
        task: task.trim(),
        agents: agentConfigs,
        config: {
          strategy: selectedStrategy as "auto" | "sequential" | "parallel" | "supervisor",
          agent_roles: selectedAgents,
        },
      });

      setCurrentId(response.id);
      toast.info("Orchestration started");
    } catch (err) {
      setRunning(false);
      toast.error(err instanceof Error ? err.message : "Failed to start orchestration");
    }
  }, [task, selectedAgents, selectedStrategy, agents, toast]);

  const latestResult = orchestrationHistory[0];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Orchestration</h1>
          <p className="text-sm text-slate-500 mt-1">
            Run multi-agent workflows with automatic task decomposition
          </p>
        </div>
      </div>

      <div className="glass rounded-xl p-5 space-y-4">
        <h2 className="text-lg font-semibold text-slate-100">New Orchestration</h2>

        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1.5">
            Task
          </label>
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Describe the task for your agents..."
            rows={3}
            className="w-full px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
              text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50
              transition-colors resize-none"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">
              Strategy
            </label>
            <select
              value={selectedStrategy}
              onChange={(e) => setSelectedStrategy(e.target.value)}
              className="w-full px-3 py-2.5 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
                text-slate-200 focus:outline-none focus:border-cyan-500/50 transition-colors"
            >
              <option value="auto">Auto (Smart Select)</option>
              <option value="sequential">Sequential</option>
              <option value="parallel">Parallel</option>
              <option value="supervisor">Supervisor</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">
              Agents ({selectedAgents.length} selected)
            </label>
            <div className="flex flex-wrap gap-2">
              {agents.map((agent) => (
                <button
                  key={agent.name}
                  onClick={() =>
                    setSelectedAgents((prev) =>
                      prev.includes(agent.name)
                        ? prev.filter((n) => n !== agent.name)
                        : [...prev, agent.name],
                    )
                  }
                  className={`px-3 py-1.5 text-xs rounded-lg border transition-all ${
                    selectedAgents.includes(agent.name)
                      ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/30"
                      : "bg-slate-800/50 text-slate-400 border-slate-700 hover:border-slate-600"
                  }`}
                >
                  {agent.name}
                </button>
              ))}
              {agents.length === 0 && (
                <span className="text-xs text-slate-500">No agents registered</span>
              )}
            </div>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            onClick={handleStart}
            disabled={running || !task.trim() || selectedAgents.length === 0}
            className="flex items-center gap-2 px-6 py-2.5 bg-cyan-500/10 text-cyan-400 rounded-lg
              hover:bg-cyan-500/20 transition-all text-sm font-medium border border-cyan-500/20
              disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {running ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Start Orchestration
              </>
            )}
          </button>
        </div>
      </div>

      {running && currentId && (
        <div className="glass rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-sm font-medium text-slate-300">
              Orchestration in progress...
            </span>
            <span className="text-xs text-slate-500">ID: {currentId.slice(0, 8)}</span>
          </div>
          <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-cyan-400 via-violet-400 to-emerald-400 rounded-full animate-progress" />
          </div>
        </div>
      )}

      {latestResult && (
        <div className="space-y-4 animate-slide-up">
          <h2 className="text-lg font-semibold text-slate-100">Latest Result</h2>
          <OrchestrationResultCard result={latestResult} />
        </div>
      )}

      {orchestrationHistory.length === 0 && !running && (
        <EmptyState
          icon={GitBranch}
          title="No orchestrations yet"
          description="Start your first multi-agent orchestration to see results here."
        />
      )}
    </div>
  );
}

function OrchestrationResultCard({ result }: { result: OrchestrationResult }) {
  const [expandedSubTask, setExpandedSubTask] = useState<string | null>(null);

  return (
    <div className="glass rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <StatusBadge status={result.status} size="md" animated />
          <span className="text-xs text-slate-500 font-mono">
            {result.id.slice(0, 8)}
          </span>
        </div>
        <span className="text-xs text-slate-500">
          {formatRelative(result.finished_at ?? result.started_at)}
        </span>
      </div>

      <p className="text-sm text-slate-300 line-clamp-2">{result.task}</p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard icon={GitBranch} label="Strategy" value={result.strategy} color="cyan" />
        <MetricCard icon={Layers} label="Sub-tasks" value={result.sub_results.length} color="violet" />
        <MetricCard icon={Clock} label="Duration" value={formatMs(result.total_duration_ms)} color="amber" />
        <MetricCard icon={CheckCircle2} label="Tokens" value={formatTokens(result.total_tokens)} color="emerald" />
      </div>

      {result.sub_results.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-slate-400 mb-3">Sub-tasks</h3>
          <div className="space-y-2">
            {result.sub_results.map((sub) => (
              <SubTaskRow
                key={sub.sub_task_id}
                sub={sub}
                expanded={expandedSubTask === sub.sub_task_id}
                onToggle={() =>
                  setExpandedSubTask(
                    expandedSubTask === sub.sub_task_id ? null : sub.sub_task_id,
                  )
                }
              />
            ))}
          </div>
        </div>
      )}

      {result.final_output && (
        <CodeBlock
          code={result.final_output}
          language="text"
          title="Final Output"
        />
      )}

      {result.error && (
        <CodeBlock
          code={result.error}
          language="text"
          title="Error"
        />
      )}
    </div>
  );
}

function SubTaskRow({
  sub,
  expanded,
  onToggle,
}: {
  sub: SubTaskResult;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="glass rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-800/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <StatusBadge status={sub.status} size="sm" />
          <span className="text-sm text-slate-300">{sub.description}</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          {sub.agent_name && (
            <span className="text-cyan-400">{sub.agent_name}</span>
          )}
          <span>{formatMs(sub.duration_ms)}</span>
          <ArrowRight className="w-3 h-3" />
        </div>
      </button>
      {expanded && (
        <div className="px-4 pb-3 space-y-2 animate-fade-in">
          {sub.output && (
            <CodeBlock code={sub.output} language="text" title="Output" maxHeight="200px" />
          )}
          {sub.error && (
            <CodeBlock code={sub.error} language="text" title="Error" maxHeight="200px" />
          )}
          <div className="flex gap-4 text-xs text-slate-500">
            <span>Iterations: {sub.iterations}</span>
            <span>Tokens: {sub.tokens_used}</span>
          </div>
        </div>
      )}
    </div>
  );
}
