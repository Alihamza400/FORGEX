import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  FileJson,
  Plus,
  Search,
  Trash2,
  Clock,
  Copy,
  RefreshCw,
  Tags,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api } from "../api/client";
import { Modal } from "../components/shared/Modal";
import { EmptyState } from "../components/shared/EmptyState";
import { PageSkeleton } from "../components/shared/LoadingSkeleton";
import { useToast } from "../hooks/useToast";
import type { AgentTemplate, AgentConfig } from "../types/api";

export function Templates() {
  const navigate = useNavigate();
  const toast = useToast();
  const { data, loading, refetch } = useApi(() => api.templates.list());
  const [search, setSearch] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);

  const filtered = (data || []).filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      (t.description || "").toLowerCase().includes(search.toLowerCase()),
  );

  const handleApply = async (tmpl: AgentTemplate) => {
    try {
      const result = await api.templates.use(tmpl.id);
      const config = result.config as unknown as AgentConfig;
      toast.success(`Creating agent from "${tmpl.name}"...`);

      const created = await api.agents.create({
        name: config.name,
        role: config.role,
        goal: config.goal,
        config_yaml: "",
        model_name: config.model.name,
      });
      toast.success(`Agent "${created.name}" created`);
      navigate(`/agents/${created.name}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create agent");
    }
  };

  const handleDelete = async (id: number, name: string) => {
    try {
      await api.templates.delete(id);
      toast.success(`Template "${name}" deleted`);
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete");
    }
  };

  if (loading) return <PageSkeleton />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Agent Templates</h1>
          <p className="text-sm text-slate-500 mt-1">
            Save and reuse agent configurations across projects
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
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-cyan-500/10 text-cyan-400 rounded-lg
              hover:bg-cyan-500/20 transition-all text-sm font-medium border border-cyan-500/20"
          >
            <Plus className="w-4 h-4" />
            New Template
          </button>
        </div>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="text"
          placeholder="Search templates..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg
            text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50
            transition-colors"
        />
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={FileJson}
          title="No templates found"
          description={
            search
              ? "No templates match your search."
              : "Save your first agent as a template to reuse it later."
          }
          action={
            search
              ? undefined
              : {
                  label: "Create Template",
                  onClick: () => setShowCreateModal(true),
                }
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((tmpl) => (
            <TemplateCard
              key={tmpl.id}
              template={tmpl}
              onApply={() => handleApply(tmpl)}
              onDelete={() => handleDelete(tmpl.id, tmpl.name)}
            />
          ))}
        </div>
      )}

      {showCreateModal && (
        <CreateTemplateModal
          onClose={() => setShowCreateModal(false)}
          onCreated={() => {
            setShowCreateModal(false);
            refetch();
          }}
        />
      )}
    </div>
  );
}

function TemplateCard({
  template,
  onApply,
  onDelete,
}: {
  template: AgentTemplate;
  onApply: () => void;
  onDelete: () => void;
}) {
  const config = template.config_json as { role?: string; goal?: string; model?: { name?: string } };
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
    <div className="glass rounded-xl p-5 glass-hover group animate-fade-in">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-violet-500/10 text-violet-400 group-hover:bg-violet-500/20 transition-colors">
            <FileJson className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-200">{template.name}</h3>
            {template.category && (
              <span className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
                <Tags className="w-3 h-3" />
                {template.category}
              </span>
            )}
          </div>
        </div>
      </div>

      {template.description && (
        <p className="text-sm text-slate-400 mb-3 line-clamp-2">{template.description}</p>
      )}

      {config.role && (
        <p className="text-xs text-slate-500 mb-2">Role: {config.role}</p>
      )}

      {template.tags && template.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {template.tags.map((tag) => (
            <span
              key={tag}
              className="px-2 py-0.5 text-xs rounded-full bg-slate-700/50 text-slate-400 border border-slate-700"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center gap-3 text-xs text-slate-500 mb-4">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {timeAgo(template.created_at)}
        </span>
        <span className="flex items-center gap-1">
          <Copy className="w-3 h-3" />
          Used {template.usage_count} times
        </span>
      </div>

      <div className="flex gap-2">
        <button
          onClick={onApply}
          className="flex-1 px-3 py-1.5 text-xs font-medium bg-cyan-500/10 text-cyan-400 rounded-lg
            hover:bg-cyan-500/20 transition-all border border-cyan-500/20"
        >
          Create Agent
        </button>
        <button
          onClick={onDelete}
          className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
          title="Delete template"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

function CreateTemplateModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [configJson, setConfigJson] = useState(`{
  "name": "my-agent",
  "role": "Assistant",
  "goal": "Help users with tasks",
  "model": {
    "name": "tinyllama",
    "provider": "ollama",
    "temperature": 0.7,
    "max_tokens": 2048,
    "top_p": 0.9
  },
  "tools": [],
  "memory": {
    "type": "none",
    "collection": "default",
    "embedding_model": "nomic-embed-text",
    "top_k": 5,
    "score_threshold": 0.5
  },
  "max_iterations": 10,
  "system_prompt_extra": "",
  "environment": {}
}`);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { toast.error("Name is required"); return; }
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(configJson);
    } catch {
      toast.error("Invalid JSON in config");
      return;
    }
    setLoading(true);
    try {
      const tags = tagsInput.split(",").map((t) => t.trim()).filter(Boolean);
      await api.templates.create({
        name: name.trim(),
        description: description.trim() || undefined,
        category: category.trim() || undefined,
        tags: tags.length > 0 ? tags : undefined,
        config_json: parsed,
      });
      toast.success("Template created");
      onCreated();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create template");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Create Template" size="lg">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">Name *</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="code-reviewer-template"
            className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
              text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 transition-colors font-mono"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Template for code review agents..."
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
              placeholder="e.g. coding, writing, research"
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
                text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 transition-colors"
            />
          </div>
          <div className="flex-1">
            <label className="block text-sm font-medium text-slate-300 mb-1">Tags (comma-separated)</label>
            <input
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="code, review, python"
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
                text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 transition-colors"
            />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">
            Agent Config <span className="text-slate-500">(JSON)</span>
          </label>
          <textarea
            value={configJson}
            onChange={(e) => setConfigJson(e.target.value)}
            rows={12}
            className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
              text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 transition-colors
              font-mono resize-none"
          />
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 glass rounded-lg glass-hover transition-all"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 text-sm font-medium bg-cyan-500/10 text-cyan-400 rounded-lg
              hover:bg-cyan-500/20 transition-all border border-cyan-500/20 disabled:opacity-50"
          >
            {loading ? "Creating..." : "Create Template"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
