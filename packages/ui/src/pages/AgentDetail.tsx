import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Bot,
  FileJson,
  Send,
  Cpu,
  Hash,
  Timer,
  Thermometer,
  Braces,
  Terminal,
  Clock,
  History,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api } from "../api/client";
import { Modal } from "../components/shared/Modal";
import { StatusBadge } from "../components/shared/StatusBadge";
import { MetricCard } from "../components/shared/MetricCard";
import { CodeBlock } from "../components/shared/CodeBlock";
import { PageSkeleton } from "../components/shared/LoadingSkeleton";
import { useToast } from "../hooks/useToast";
import { useAppStore } from "../store/app";
import { formatRelative } from "../utils/format";
import type { AgentConfig, TaskResult, RunHistory } from "../types/api";

export function AgentDetail() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const { agents } = useAppStore();
  const agent = agents.find((a) => a.name === name);
  const { data: agentsData } = useApi(() => api.agents.list());
  const { data: runHistory, refetch: refetchRuns } = useApi(
    () => (name ? api.agents.runs(name) : Promise.resolve([])),
    [name],
  );

  const [task, setTask] = useState("");
  const [running, setRunning] = useState(false);
  const [showSaveTemplate, setShowSaveTemplate] = useState(false);
  const [result, setResult] = useState<TaskResult | null>(null);
  const [streamOutput, setStreamOutput] = useState("");
  const [toolCalls, setToolCalls] = useState<{ tool: string; args: string; result?: string }[]>([]);
  const [currentIteration, setCurrentIteration] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [streamOutput, toolCalls]);

  const handleRun = useCallback(async () => {
    if (!task.trim()) return;
    setRunning(true);
    setResult(null);
    setStreamOutput("");
    setToolCalls([]);
    setCurrentIteration(0);

    const config: AgentConfig = {
      name: agent!.name,
      role: agent!.role,
      goal: agent!.goal,
      model: { name: "llama3.2:3b", provider: "ollama", temperature: 0.7, max_tokens: 2048, top_p: 0.9 },
      tools: [],
      memory: { type: "none", collection: "default", embedding_model: "nomic-embed-text", top_k: 5, score_threshold: 0.5 },
      max_iterations: 10,
      system_prompt_extra: "",
      environment: {},
    };

    let fullOutput = "";

    abortRef.current = api.agents.runStream(
      { config, task: task.trim() },
      (event: { type: string; data: Record<string, unknown> }) => {
        switch (event.type) {
          case "iteration":
            setCurrentIteration((event.data as { iteration: number }).iteration);
            break;
          case "token":
            fullOutput += (event.data as { token: string }).token;
            setStreamOutput(fullOutput);
            break;
          case "tool_call":
            setToolCalls((prev) => [
              ...prev,
              { tool: (event.data as { tool: string }).tool, args: JSON.stringify((event.data as { args: Record<string, unknown> }).args, null, 2) },
            ]);
            break;
          case "tool_result":
            setToolCalls((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last) last.result = (event.data as { result: string }).result.slice(0, 500);
              return updated;
            });
            break;
          case "error":
            toast.error((event.data as { error: string }).error);
            break;
        }
      },
      () => {
        setRunning(false);
        setResult({
          agent_name: agent!.name,
          task: task.trim(),
          output: fullOutput,
          iterations: currentIteration || 1,
          tokens_used: 0,
          error: null,
          duration_ms: 0,
        });
        refetchRuns();
      },
      (err: Error) => {
        setRunning(false);
        toast.error(err.message);
        setResult({
          agent_name: agent!.name,
          task: task.trim(),
          output: fullOutput,
          iterations: currentIteration || 1,
          tokens_used: 0,
          error: err.message,
          duration_ms: 0,
        });
        refetchRuns();
      },
    );
  }, [task, agent, toast, currentIteration]);

  const handleStop = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
      setRunning(false);
    }
  }, []);

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
              <button
                onClick={() => setShowSaveTemplate(true)}
                className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium
                  bg-violet-500/10 text-violet-400 rounded-lg hover:bg-violet-500/20 transition-all
                  border border-violet-500/20 ml-2"
                title="Save as template"
              >
                <FileJson className="w-3.5 h-3.5" />
                Save Template
              </button>
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
            onKeyDown={(e) => e.key === "Enter" && !running && handleRun()}
            className="flex-1 px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
              text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 transition-colors"
          />
          {running ? (
            <button
              onClick={handleStop}
              className="flex items-center gap-2 px-5 py-2.5 bg-red-500/10 text-red-400 rounded-lg
                hover:bg-red-500/20 transition-all text-sm font-medium border border-red-500/20"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={handleRun}
              disabled={!task.trim()}
              className="flex items-center gap-2 px-5 py-2.5 bg-cyan-500/10 text-cyan-400 rounded-lg
                hover:bg-cyan-500/20 transition-all text-sm font-medium border border-cyan-500/20 disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
              Run
            </button>
          )}
        </div>
      </div>

      {running && (
        <div className="glass rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-sm text-slate-400">
              {currentIteration > 0 ? `Iteration ${currentIteration}...` : "Agent is thinking..."}
            </span>
          </div>
          <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-cyan-400 to-emerald-400 rounded-full animate-progress" />
          </div>
        </div>
      )}

      {running && streamOutput && (
        <div className="glass rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Terminal className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-medium text-slate-300">Live Output</h3>
          </div>
          <div
            ref={outputRef}
            className="max-h-96 overflow-y-auto font-mono text-sm text-slate-300 whitespace-pre-wrap"
          >
            {streamOutput}
            <span className="inline-block w-2 h-4 bg-cyan-400 animate-pulse ml-0.5" />
          </div>
        </div>
      )}

      {toolCalls.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-slate-400 flex items-center gap-2">
            <Braces className="w-4 h-4" />
            Tool Calls ({toolCalls.length})
          </h3>
          {toolCalls.map((tc, i) => (
            <div key={i} className="glass rounded-xl p-4 space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <Terminal className="w-3.5 h-3.5 text-amber-400" />
                <span className="font-mono text-amber-400">{tc.tool}</span>
              </div>
              <CodeBlock code={tc.args} language="json" title="Arguments" />
              {tc.result && (
                <CodeBlock code={tc.result} language="text" title="Result" />
              )}
            </div>
          ))}
        </div>
      )}

      {result && !running && (
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

      {runHistory && runHistory.length > 0 && (
        <div className="space-y-3 animate-fade-in">
          <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <History className="w-5 h-5" />
            Run History
          </h2>
          <div className="space-y-2">
            {runHistory.map((run) => (
              <RunHistoryCard key={run.id} run={run} />
            ))}
          </div>
        </div>
      )}

      {showSaveTemplate && agent && (
        <SaveTemplateModal
          agentName={agent.name}
          agentRole={agent.role}
          agentGoal={agent.goal}
          onClose={() => setShowSaveTemplate(false)}
          onSaved={() => setShowSaveTemplate(false)}
        />
      )}
    </div>
  );
}

function SaveTemplateModal({
  agentName,
  agentRole,
  agentGoal,
  onClose,
  onSaved,
}: {
  agentName: string;
  agentRole: string;
  agentGoal: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState(`${agentName}-template`);
  const [description, setDescription] = useState(`Template for ${agentRole}`);
  const [category, setCategory] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { toast.error("Name is required"); return; }
    setLoading(true);
    try {
      const config_json = {
        name: agentName,
        role: agentRole,
        goal: agentGoal,
        model: { name: "llama3.2:3b", provider: "ollama", temperature: 0.7, max_tokens: 2048, top_p: 0.9 },
        tools: [],
        memory: { type: "none", collection: "default", embedding_model: "nomic-embed-text", top_k: 5, score_threshold: 0.5 },
        max_iterations: 10,
        system_prompt_extra: "",
        environment: {},
      };
      const tags = tagsInput.split(",").map((t) => t.trim()).filter(Boolean);
      await api.templates.create({
        name: name.trim(),
        description: description.trim() || undefined,
        category: category.trim() || undefined,
        tags: tags.length > 0 ? tags : undefined,
        config_json,
      });
      toast.success("Template saved");
      onSaved();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save template");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Save as Template" size="md">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">Name *</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
              text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 transition-colors font-mono"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
              text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 transition-colors resize-none"
          />
        </div>
        <div className="flex gap-3">
          <div className="flex-1">
            <label className="block text-sm font-medium text-slate-300 mb-1">Category</label>
            <input
              type="text"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g. coding, writing"
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
                text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 transition-colors"
            />
          </div>
          <div className="flex-1">
            <label className="block text-sm font-medium text-slate-300 mb-1">Tags</label>
            <input
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="code, review"
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
                text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 transition-colors"
            />
          </div>
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <button type="button" onClick={onClose}
            className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 glass rounded-lg glass-hover transition-all"
          >
            Cancel
          </button>
          <button type="submit" disabled={loading}
            className="px-4 py-2 text-sm font-medium bg-cyan-500/10 text-cyan-400 rounded-lg
              hover:bg-cyan-500/20 transition-all border border-cyan-500/20 disabled:opacity-50"
          >
            {loading ? "Saving..." : "Save Template"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function RunHistoryCard({ run }: { run: RunHistory }) {
  const [expanded, setExpanded] = useState(false);

  const timeAgo = (dateStr: string) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  };

  return (
    <div className="glass rounded-xl">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left"
      >
        <div className={`p-1.5 rounded-lg ${
          run.status === "completed" ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
        }`}>
          {run.status === "completed" ? (
            <Terminal className="w-3.5 h-3.5" />
          ) : (
            <Terminal className="w-3.5 h-3.5" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-200 truncate">{run.input}</p>
          <p className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
            <Clock className="w-3 h-3" />
            {timeAgo(run.created_at)}
            <span>·</span>
            <span>{run.iterations} iterations</span>
            <span>·</span>
            <span>{run.duration_ms}ms</span>
          </p>
        </div>
        <StatusBadge status={run.status as "completed" | "failed"} size="sm" />
      </button>
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-slate-800 pt-3">
          {run.output && (
            <CodeBlock code={run.output} language="text" title="Output" />
          )}
          {run.error && (
            <CodeBlock code={run.error} language="text" title="Error" />
          )}
        </div>
      )}
    </div>
  );
}
