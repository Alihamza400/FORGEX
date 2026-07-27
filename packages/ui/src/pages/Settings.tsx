import { useCallback, useEffect, useState } from "react";
import {
  Save,
  RefreshCw,
  Server,
  Database,
  Key,
  User,
  Copy,
  Trash2,
  Plus,
  FolderOpen,
  ChevronRight,
  Folder,
  Home,
  ArrowUp,
  Cpu,
  Download,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import { useAuthStore } from "../store/auth";
import { api } from "../api/client";
import { CodeBlock } from "../components/shared/CodeBlock";
import { EmptyState } from "../components/shared/EmptyState";
import { Modal } from "../components/shared/Modal";
import { useToast } from "../hooks/useToast";
import { formatAbsolute } from "../utils/format";
import type { LucideIcon } from "lucide-react";
import type { BrowseEntry } from "../types/api";

const defaultConfig = {
  api_host: "0.0.0.0",
  api_port: 8000,
  log_level: "INFO",
  log_json: false,
  ollama_base_url: "http://localhost:11434",
  ollama_default_model: "llama3.2:3b",
  redis_url: "redis://localhost:6379/0",
  database_url: "postgresql+asyncpg://forge:forge_secret@localhost:5432/forge",
  qdrant_url: "http://localhost:6333",
  minio_endpoint: "localhost:9000",
  minio_access_key: "forge",
  minio_secret_key: "forge_secret",
  data_dir: "/var/lib/forge",
  token_expire_minutes: 1440,
  rate_limit_per_minute: 60,
};

const sections: {
  id: string;
  label: string;
  icon: LucideIcon;
  keys: string[];
}[] = [
  { id: "server", label: "Server", icon: Server, keys: ["api_host", "api_port", "log_level", "log_json"] },
  { id: "ollama", label: "Ollama", icon: Server, keys: ["ollama_base_url", "ollama_default_model"] },
  { id: "database", label: "Database", icon: Database, keys: ["redis_url", "database_url", "qdrant_url"] },
  { id: "storage", label: "Storage", icon: Database, keys: ["minio_endpoint", "minio_access_key", "minio_secret_key", "data_dir"] },
  { id: "workspace", label: "Workspace", icon: FolderOpen, keys: [] },
  { id: "security", label: "Security", icon: Key, keys: ["token_expire_minutes", "rate_limit_per_minute"] },
];

export function Settings() {
  const toast = useToast();
  const { user } = useAuthStore();
  const [activeSection, setActiveSection] = useState("profile");
  const [config, setConfig] = useState(defaultConfig);
  const [saving, setSaving] = useState(false);
  const [showJson, setShowJson] = useState(false);

  const { data: apiKeys, refetch: refetchKeys } = useApi(
    () => api.auth.apiKeys.list(),
    [],
  );

  const handleChange = (key: string, value: string | number | boolean) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = useCallback(async () => {
    setSaving(true);
    await new Promise((r) => setTimeout(r, 800));
    setSaving(false);
    toast.success("Configuration saved");
  }, [toast]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Settings</h1>
          <p className="text-sm text-slate-500 mt-1">Manage Forge configuration</p>
        </div>
      </div>

      <div className="flex gap-6">
        <div className="w-48 flex-shrink-0 space-y-1">
          <SectionButton
            icon={User}
            label="Profile"
            active={activeSection === "profile"}
            onClick={() => setActiveSection("profile")}
          />
          <SectionButton
            icon={Key}
            label="API Keys"
            active={activeSection === "api-keys"}
            onClick={() => setActiveSection("api-keys")}
          />
          <SectionButton
            icon={Server}
            label="Server"
            active={activeSection === "server"}
            onClick={() => setActiveSection("server")}
          />
          <SectionButton
            icon={Server}
            label="Ollama"
            active={activeSection === "ollama"}
            onClick={() => setActiveSection("ollama")}
          />
          <SectionButton
            icon={Database}
            label="Database"
            active={activeSection === "database"}
            onClick={() => setActiveSection("database")}
          />
          <SectionButton
            icon={Database}
            label="Storage"
            active={activeSection === "storage"}
            onClick={() => setActiveSection("storage")}
          />
          <SectionButton
            icon={Cpu}
            label="Models"
            active={activeSection === "models"}
            onClick={() => setActiveSection("models")}
          />
          <SectionButton
            icon={FolderOpen}
            label="Workspace"
            active={activeSection === "workspace"}
            onClick={() => setActiveSection("workspace")}
          />
          <SectionButton
            icon={Key}
            label="Security"
            active={activeSection === "security"}
            onClick={() => setActiveSection("security")}
          />
        </div>

        <div className="flex-1">
          {activeSection === "profile" && (
            <ProfileSection user={user} />
          )}

          {activeSection === "api-keys" && (
            <ApiKeysSection
              keys={apiKeys ?? []}
              onRefresh={refetchKeys}
            />
          )}

          {activeSection === "models" && <ModelsSection />}

          {activeSection === "workspace" && <WorkspaceSection />}

          {activeSection !== "profile" && activeSection !== "api-keys" && activeSection !== "workspace" && activeSection !== "models" && (
            <>
              <div className="flex justify-end mb-4">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowJson(!showJson)}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-slate-400 glass rounded-lg glass-hover"
                  >
                    <span className="text-xs font-mono">{"{ }"}</span>
                    {showJson ? "Form View" : "JSON View"}
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="flex items-center gap-2 px-4 py-2 bg-cyan-500/10 text-cyan-400 rounded-lg
                      hover:bg-cyan-500/20 transition-all text-sm font-medium border border-cyan-500/20 disabled:opacity-50"
                  >
                    {saving ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <Save className="w-4 h-4" />
                    )}
                    {saving ? "Saving..." : "Save"}
                  </button>
                </div>
              </div>

              {showJson ? (
                <CodeBlock
                  code={JSON.stringify(config, null, 2)}
                  language="json"
                  title="forge.config.json"
                />
              ) : (
                <div className="glass rounded-xl p-5 space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {sections
                      .find((s) => s.id === activeSection)
                      ?.keys.map((key) => (
                        <div key={key}>
                          <label className="block text-sm font-medium text-slate-300 mb-1.5 capitalize">
                            {key.replace(/_/g, " ")}
                          </label>
                          {typeof config[key as keyof typeof config] === "boolean" ? (
                            <label className="relative inline-flex items-center cursor-pointer">
                              <input
                                type="checkbox"
                                checked={config[key as keyof typeof config] as boolean}
                                onChange={(e) => handleChange(key, e.target.checked)}
                                className="sr-only peer"
                              />
                              <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer
                                peer-checked:after:translate-x-full peer-checked:bg-cyan-500
                                after:content-[''] after:absolute after:top-[2px] after:left-[2px]
                                after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all" />
                            </label>
                          ) : typeof config[key as keyof typeof config] === "number" ? (
                            <input
                              type="number"
                              value={config[key as keyof typeof config] as number}
                              onChange={(e) => handleChange(key, Number(e.target.value))}
                              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg
                                text-sm text-slate-200 focus:outline-none focus:border-cyan-500/50 transition-colors"
                            />
                          ) : (
                            <input
                              type="text"
                              value={config[key as keyof typeof config] as string}
                              onChange={(e) => handleChange(key, e.target.value)}
                              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg
                                text-sm text-slate-200 focus:outline-none focus:border-cyan-500/50 transition-colors font-mono"
                            />
                          )}
                          {key.includes("secret") || key.includes("key") ? (
                            <p className="text-xs text-amber-400/60 mt-1">Sensitive value</p>
                          ) : null}
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function SectionButton({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-all ${
        active
          ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"
          : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent"
      }`}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );
}

function ProfileSection({ user }: { user: ReturnType<typeof useAuthStore.getState>["user"] }) {
  if (!user) {
    return (
      <EmptyState
        icon={User}
        title="Not authenticated"
        description="Sign in to view your profile."
      />
    );
  }

  return (
    <div className="glass rounded-xl p-6 space-y-4">
      <h2 className="text-lg font-semibold text-slate-100">Profile</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-1">Username</label>
          <p className="text-slate-200 font-mono">{user.username}</p>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-1">Email</label>
          <p className="text-slate-200 font-mono">{user.email}</p>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-1">Roles</label>
          <div className="flex gap-2">
            {user.roles.map((role) => (
              <span key={role} className="px-2 py-0.5 text-xs rounded-full bg-cyan-500/10 text-cyan-400 capitalize border border-cyan-500/20">
                {role}
              </span>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-1">Admin</label>
          <span className={`px-2 py-0.5 text-xs rounded-full ${user.is_admin ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-slate-700/30 text-slate-500 border border-slate-700"}`}>
            {user.is_admin ? "Yes" : "No"}
          </span>
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-slate-400 mb-1">Permissions</label>
          <div className="flex flex-wrap gap-1.5">
            {user.permissions.map((perm) => (
              <span key={perm} className="px-2 py-0.5 text-xs rounded-full bg-slate-800/50 text-slate-400 border border-slate-700 font-mono">
                {perm}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ApiKeysSection({
  keys,
  onRefresh,
}: {
  keys: import("../types/api").ApiKeyResponse[];
  onRefresh: () => void;
}) {
  const [showCreateModal, setShowCreateModal] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-100">API Keys</h2>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-cyan-500/10 text-cyan-400 rounded-lg
            hover:bg-cyan-500/20 transition-all font-medium border border-cyan-500/20"
        >
          <Plus className="w-4 h-4" />
          Create Key
        </button>
      </div>

      {keys.length === 0 ? (
        <EmptyState
          icon={Key}
          title="No API keys"
          description="Create an API key to authenticate CLI tools and external services."
          action={{ label: "Create API Key", onClick: () => setShowCreateModal(true) }}
        />
      ) : (
        <div className="space-y-2">
          {keys.map((key) => (
            <ApiKeyRow key={key.id} keyData={key} onRevoked={onRefresh} />
          ))}
        </div>
      )}

      {showCreateModal && (
        <CreateApiKeyModal
          onClose={() => setShowCreateModal(false)}
          onCreated={() => {
            setShowCreateModal(false);
            onRefresh();
          }}
        />
      )}
    </div>
  );
}

function ApiKeyRow({
  keyData,
  onRevoked,
}: {
  keyData: import("../types/api").ApiKeyResponse;
  onRevoked: () => void;
}) {
  const toast = useToast();

  const handleRevoke = async () => {
    try {
      await api.auth.apiKeys.revoke(keyData.id);
      toast.success("API key revoked");
      onRevoked();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to revoke");
    }
  };

  return (
    <div className="glass rounded-xl p-4 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <div className={`p-2 rounded-lg ${keyData.is_active ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-700/30 text-slate-500"}`}>
          <Key className="w-4 h-4" />
        </div>
        <div>
          <p className="text-sm font-medium text-slate-200">{keyData.name}</p>
          <p className="text-xs font-mono text-slate-500">
            {keyData.prefix}...
            {keyData.expires_at && (
              <span className="ml-2">Expires {formatAbsolute(keyData.expires_at)}</span>
            )}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className={`text-xs px-2 py-0.5 rounded-full ${
          keyData.is_active ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-700/30 text-slate-500"
        }`}>
          {keyData.is_active ? "Active" : "Revoked"}
        </span>
        {keyData.is_active && (
          <button
            onClick={handleRevoke}
            className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}

function ModelsSection() {
  const toast = useToast();
  const { data, loading, refetch } = useApi(() => api.models.list());
  const [pulling, setPulling] = useState<string | null>(null);
  const [pullName, setPullName] = useState("");

  const handlePull = async () => {
    if (!pullName.trim()) return;
    setPulling(pullName.trim());
    try {
      await api.models.pull(pullName.trim());
      toast.success(`Model '${pullName.trim()}' pulled successfully`);
      setPullName("");
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to pull model");
    } finally {
      setPulling(null);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return "unknown";
    const gb = bytes / 1_000_000_000;
    return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / 1_000_000).toFixed(0)} MB`;
  };

  return (
    <div className="space-y-4">
      <div className="glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-slate-100 mb-1">Ollama Models</h2>
        <p className="text-sm text-slate-500 mb-4">
          Manage models installed on your Ollama server.
        </p>

        <div className="flex gap-3 mb-6">
          <input
            type="text"
            value={pullName}
            onChange={(e) => setPullName(e.target.value)}
            placeholder="e.g. llama3.2:3b, mistral, codellama"
            onKeyDown={(e) => e.key === "Enter" && handlePull()}
            className="flex-1 px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-lg text-sm
              text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 transition-colors font-mono"
          />
          <button
            onClick={handlePull}
            disabled={pulling !== null || !pullName.trim()}
            className="flex items-center gap-2 px-4 py-2.5 bg-cyan-500/10 text-cyan-400 rounded-lg
              hover:bg-cyan-500/20 transition-all text-sm font-medium border border-cyan-500/20 disabled:opacity-50"
          >
            <Download className="w-4 h-4" />
            {pulling ? "Pulling..." : "Pull"}
          </button>
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 bg-slate-800/30 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : !data || data.models.length === 0 ? (
          <div className="text-center py-8 text-sm text-slate-500">
            No models installed. Pull one above.
          </div>
        ) : (
          <div className="space-y-2">
            {data.models.map((model) => (
              <div
                key={model.name}
                className="flex items-center justify-between px-4 py-3 bg-slate-800/30 rounded-lg border border-slate-700/50"
              >
                <div className="flex items-center gap-3">
                  <Cpu className="w-4 h-4 text-cyan-400/70" />
                  <div>
                    <p className="text-sm font-medium text-slate-200 font-mono">{model.name}</p>
                    <p className="text-xs text-slate-500">
                      {formatSize(model.size)}
                    </p>
                  </div>
                </div>
                {data.default_model === model.name && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    Default
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function WorkspaceSection() {
  const toast = useToast();
  const [workspace, setWorkspace] = useState("");
  const [loading, setLoading] = useState(true);
  const [showBrowser, setShowBrowser] = useState(false);

  useEffect(() => {
    api.filesystem.getWorkspace()
      .then((res) => setWorkspace(res.workspace))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleClear = async () => {
    try {
      await api.filesystem.setWorkspace("");
      setWorkspace("");
      toast.success("Workspace cleared (using default data dir)");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to clear workspace");
    }
  };

  return (
    <div className="space-y-4">
      <div className="glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-slate-100 mb-1">Workspace Directory</h2>
        <p className="text-sm text-slate-500 mb-4">
          Agents run commands and access files relative to this directory.
        </p>

        {loading ? (
          <div className="h-10 bg-slate-800/30 rounded-lg animate-pulse" />
        ) : (
          <div className="flex items-center gap-3">
            <div className="flex-1 px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-lg font-mono text-sm text-slate-300 truncate">
              {workspace || (
                <span className="text-slate-500 italic">Default: /var/lib/forge</span>
              )}
            </div>
            <button
              onClick={() => setShowBrowser(true)}
              className="flex items-center gap-2 px-4 py-2.5 bg-cyan-500/10 text-cyan-400 rounded-lg
                hover:bg-cyan-500/20 transition-all text-sm font-medium border border-cyan-500/20"
            >
              <Folder className="w-4 h-4" />
              Browse
            </button>
            {workspace && (
              <button
                onClick={handleClear}
                className="px-4 py-2.5 text-sm text-slate-400 glass rounded-lg glass-hover"
              >
                Clear
              </button>
            )}
          </div>
        )}
      </div>

      {showBrowser && (
        <FolderBrowserModal
          currentPath={workspace}
          onSelect={async (path) => {
            try {
              await api.filesystem.setWorkspace(path);
              setWorkspace(path);
              setShowBrowser(false);
              toast.success("Workspace set to " + path);
            } catch (err) {
              toast.error(err instanceof Error ? err.message : "Failed to set workspace");
            }
          }}
          onClose={() => setShowBrowser(false)}
        />
      )}
    </div>
  );
}

function FolderBrowserModal({
  currentPath,
  onSelect,
  onClose,
}: {
  currentPath: string;
  onSelect: (path: string) => void;
  onClose: () => void;
}) {
  const [currentDir, setCurrentDir] = useState(currentPath || "");
  const [entries, setEntries] = useState<BrowseEntry[]>([]);
  const [parent, setParent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigate = useCallback(async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.filesystem.browse(path);
      setCurrentDir(res.path);
      setParent(res.parent);
      setEntries(res.entries.filter((e) => e.type === "directory"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to browse");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    navigate(currentPath || "");
  }, []);

  return (
    <Modal open onClose={onClose} title="Select Workspace Directory" size="lg">
      <div className="space-y-3">
        <div className="flex items-center gap-2 px-3 py-2 bg-slate-800/50 rounded-lg border border-slate-700">
          <Folder className="w-4 h-4 text-cyan-400 flex-shrink-0" />
          <span className="text-sm font-mono text-slate-300 truncate">
            {currentDir || "Home"}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate("")}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-400 glass rounded-lg glass-hover"
          >
            <Home className="w-3.5 h-3.5" />
            Home
          </button>
          {parent && (
            <button
              onClick={() => navigate(parent)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-400 glass rounded-lg glass-hover"
            >
              <ArrowUp className="w-3.5 h-3.5" />
              Up
            </button>
          )}
        </div>

        {error && (
          <div className="px-3 py-2 text-sm text-red-400 bg-red-500/10 rounded-lg border border-red-500/20">
            {error}
          </div>
        )}

        <div className="max-h-80 overflow-y-auto space-y-1 border border-slate-700/50 rounded-lg p-2">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="w-5 h-5 text-slate-500 animate-spin" />
            </div>
          ) : entries.length === 0 ? (
            <div className="text-center py-8 text-sm text-slate-500">
              No subdirectories
            </div>
          ) : (
            entries.map((entry) => (
              <button
                key={entry.path}
                onClick={() => navigate(entry.path)}
                className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-300
                  hover:bg-slate-800/50 transition-all group"
              >
                <Folder className="w-4 h-4 text-amber-400/70 flex-shrink-0" />
                <span className="truncate flex-1 text-left">{entry.name}</span>
                <ChevronRight className="w-3.5 h-3.5 text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity" />
              </button>
            ))
          )}
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-slate-700/50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-400 glass rounded-lg glass-hover"
          >
            Cancel
          </button>
          <button
            onClick={() => onSelect(currentDir)}
            className="px-4 py-2 text-sm font-medium bg-cyan-500/10 text-cyan-400 rounded-lg
              hover:bg-cyan-500/20 transition-all border border-cyan-500/20"
          >
            Select This Directory
          </button>
        </div>
      </div>
    </Modal>
  );
}

function CreateApiKeyModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [expiresDays, setExpiresDays] = useState(365);
  const [loading, setLoading] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name) {
      toast.error("Name is required");
      return;
    }
    setLoading(true);
    try {
      const result = await api.auth.apiKeys.create({
        name,
        expires_in_days: expiresDays,
      });
      setCreatedKey(result.key);
      toast.success("API key created");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create key");
    } finally {
      setLoading(false);
    }
  };

  if (createdKey) {
    return (
      <Modal open onClose={onClose} title="API Key Created" size="lg">
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
            <p className="text-sm text-amber-400 font-medium mb-1">
              Save this key — it will not be shown again!
            </p>
            <CodeBlock code={createdKey} language="text" title="Your API Key" />
          </div>
          <button
            onClick={() => {
              navigator.clipboard.writeText(createdKey);
              toast.success("Copied to clipboard");
            }}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-cyan-500/10 text-cyan-400
              rounded-lg hover:bg-cyan-500/20 transition-all text-sm font-medium border border-cyan-500/20"
          >
            <Copy className="w-4 h-4" />
            Copy to Clipboard
          </button>
          <button
            onClick={() => {
              onCreated();
              onClose();
            }}
            className="w-full px-4 py-2 text-sm text-slate-400 glass rounded-lg glass-hover"
          >
            Done
          </button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal open onClose={onClose} title="Create API Key">
      <form onSubmit={handleCreate} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., CI/CD Pipeline"
            className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg
              text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 transition-colors"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">Expires in (days)</label>
          <select
            value={expiresDays}
            onChange={(e) => setExpiresDays(Number(e.target.value))}
            className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg
              text-sm text-slate-200 focus:outline-none focus:border-cyan-500/50 transition-colors"
          >
            <option value={30}>30 days</option>
            <option value={90}>90 days</option>
            <option value={180}>180 days</option>
            <option value={365}>1 year</option>
          </select>
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-400 glass rounded-lg glass-hover"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 text-sm font-medium bg-cyan-500/10 text-cyan-400 rounded-lg
              hover:bg-cyan-500/20 transition-all border border-cyan-500/20 disabled:opacity-50"
          >
            {loading ? "Creating..." : "Create"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
