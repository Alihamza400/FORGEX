import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Bot,
  Send,
  Cpu,
  Hash,
  Timer,
  Thermometer,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api } from "../api/client";
import { StatusBadge } from "../components/shared/StatusBadge";
import { MetricCard } from "../components/shared/MetricCard";
import { CodeBlock } from "../components/shared/CodeBlock";
import { PageSkeleton } from "../components/shared/LoadingSkeleton";
import { useToast } from "../hooks/useToast";
import { useAppStore } from "../store/app";
import { formatRelative } from "../utils/format";
import type { AgentConfig, TaskResult } from "../types/api";

export function AgentDetail() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const { agents } = useAppStore();
  const agent = agents.find((a) => a.name === name);
  const { data: agentsData } = useApi(() => api.agents.list());

  const [task, setTask] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<TaskResult | null>(null);

  if (!agentsData) return <PageSkeleton />;
  if (!agent) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Bot className="w-12 h-12 text-slate-600 mb-3" />
        <h2 className="text-lg font-semibold text-slate-400">Agent not found</h2>
        <button onClick={() => navigate("/agents")} className="mt-4 text-sm text-cyan-400 hover:text-cyan-300">
          &larr; Back to Agents
        </button>
      </div>
    );
  }

  const handleRun = async () => {
    if (!task.trim()) return;
    setRunning(true);
    setResult(null);
    try {
      const config: AgentConfig = {
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
      const res = await api.agents.run({ config, task: task.trim() });
      setResult(res);
      toast.success("Task completed successfully");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Task failed");
      setResult({
        agent_name: agent.name,
        task: task.trim(),
        output: "",
        iterations: 0,
        tokens_used: 0,
        error: err instanceof Error ? err.message : "Unknown error",
        duration_ms: 0,
      });
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <button
        onClick={() => navigate("/agents")}
        className="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Agents
      </button>

      <div className="glass rounded-xl p-6">
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-xl bg-cyan-500/10 text-cyan-400">
            <Bot className="w-6 h-6" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-2xl font-bold text-slate-100">{agent.name}</h1>
              <StatusBadge status={agent.status} animated />
            </div>
            <p className="text-slate-400">{agent.role}</p>
            {agent.goal && (
              <p className="text-sm text-slate-500 mt-2">{agent.goal}</p>
            )}
            <div className="flex flex-wrap gap-2 mt-3">
              {agent.capabilities.map((cap) => (
                <span
                  key={cap}
                  className="px-2 py-0.5 text-xs rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 capitalize"
                >
                  {cap}
                </span>
              ))}
            </div>
            {agent.last_heartbeat && (
              <p className="text-xs text-slate-500 mt-3">
                Last seen {formatRelative(agent.last_heartbeat)}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard icon={Cpu} label="Status" value={agent.status} color="cyan" />
        <MetricCard icon={Hash} label="Capabilities" value={agent.capabilities.length} color="violet" />
        <MetricCard icon={Timer} label="Last Heartbeat" value={formatRelative(agent.last_heartbeat)} color="amber" />
        <MetricCard icon={Thermometer} label="Model" value="llama3.2:3b" color="emerald" />
      </div>

      <div className="glass rounded-xl p-5">
        <h2 className="text-lg font-semibold text-slate-100 mb-4">Run Task</h2>
        <div className="flex gap-3">
          <input
            type="text"
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Enter a task for this agent..."
            onKeyDown={(e) => e.key === "Enter" && handleRun()}
            className="flex-1 px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
              text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 transition-colors"
          />
          <button
            onClick={handleRun}
            disabled={running || !task.trim()}
            className="flex items-center gap-2 px-5 py-2.5 bg-cyan-500/10 text-cyan-400 rounded-lg
              hover:bg-cyan-500/20 transition-all text-sm font-medium border border-cyan-500/20 disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
            {running ? "Running..." : "Run"}
          </button>
        </div>
      </div>

      {running && (
        <div className="glass rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-sm text-slate-400">Agent is working...</span>
          </div>
          <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-cyan-400 to-emerald-400 rounded-full animate-progress" />
          </div>
        </div>
      )}

      {result && (
        <div className="space-y-4 animate-slide-up">
          <div className="glass rounded-xl p-5">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-lg font-semibold text-slate-100">Result</h2>
              <StatusBadge
                status={result.error ? "failed" : "completed"}
                size="md"
              />
            </div>
            <div className="flex gap-4 text-sm text-slate-500 mb-3">
              <span>Iterations: {result.iterations}</span>
              <span>Tokens: {result.tokens_used}</span>
              <span>Duration: {result.duration_ms}ms</span>
            </div>
          </div>
          {result.output && (
            <CodeBlock
              code={result.output}
              language="text"
              title="Output"
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
      )}
    </div>
  );
}
