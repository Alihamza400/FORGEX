import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Bot,
  GitBranch,
  Logs,
  Settings,
  ChevronLeft,
  ChevronRight,
  LogOut,
  User,
  Key,
  FileJson,
  Folder,
  FolderOpen,
  Home,
  ArrowUp,
} from "lucide-react";
import { useAppStore } from "../../store/app";
import { useAuthStore } from "../../store/auth";
import { api } from "../../api/client";
import { Modal } from "../shared/Modal";
import type { BrowseEntry, NavItem } from "../../types/api";

const navItems: NavItem[] = [
  { label: "Dashboard", path: "/", icon: LayoutDashboard },
  { label: "Agents", path: "/agents", icon: Bot, requiredPermission: "agent:list" },
  { label: "Templates", path: "/templates", icon: FileJson, requiredPermission: "agent:list" },
  { label: "Orchestration", path: "/orchestrate", icon: GitBranch, requiredPermission: "orchestrate:read" },
  { label: "Logs", path: "/logs", icon: Logs, requiredPermission: "log:read" },
  { label: "Settings", path: "/settings", icon: Settings, requiredPermission: "settings:read" },
];

export function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { sidebarCollapsed, toggleSidebar } = useAppStore();
  const { isAuthenticated, user, logout } = useAuthStore();
  const [workspace, setWorkspace] = useState("");
  const [showBrowser, setShowBrowser] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      api.filesystem.getWorkspace()
        .then((res) => setWorkspace(res.workspace))
        .catch(() => {});
    }
  }, [isAuthenticated]);

  const visibleNavItems = navItems.filter((item) => {
    if (!item.requiredPermission) return true;
    if (!user) return false;
    return user.is_admin || user.permissions.includes(item.requiredPermission);
  });

  return (
    <aside
      className={`flex flex-col border-r border-slate-800 bg-slate-900/50 backdrop-blur-xl transition-all duration-300 ${
        sidebarCollapsed ? "w-16" : "w-60"
      }`}
    >
      <div className="flex items-center h-16 px-4 border-b border-slate-800">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-emerald-400 flex items-center justify-center flex-shrink-0">
            <span className="text-slate-950 font-bold text-sm">F</span>
          </div>
          <span
            className={`font-bold text-lg text-gradient-cyan whitespace-nowrap transition-opacity duration-300 ${
              sidebarCollapsed ? "opacity-0 w-0" : "opacity-100"
            }`}
          >
            Forge
          </span>
        </div>
      </div>

      <nav className="flex-1 py-4 px-2 space-y-1">
        {visibleNavItems.map((item) => {
          const Icon = item.icon;
          const active = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 group relative ${
                active
                  ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent"
              }`}
              title={sidebarCollapsed ? item.label : undefined}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              <span
                className={`text-sm font-medium whitespace-nowrap transition-opacity duration-300 ${
                  sidebarCollapsed ? "opacity-0 w-0" : "opacity-100"
                }`}
              >
                {item.label}
              </span>
              {item.badge && (
                <span
                  className={`ml-auto px-1.5 py-0.5 text-xs rounded-full bg-cyan-500/20 text-cyan-400 ${
                    sidebarCollapsed ? "hidden" : ""
                  }`}
                >
                  {item.badge}
                </span>
              )}
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-cyan-400 rounded-full" />
              )}
            </Link>
          );
        })}
      </nav>

      {isAuthenticated && (
        <div className="px-2 pb-2">
          <button
            onClick={() => setShowBrowser(true)}
            className={`flex items-center gap-3 w-full px-3 py-2 rounded-xl text-slate-400
              hover:text-cyan-400 hover:bg-cyan-500/10 transition-all border border-transparent hover:border-cyan-500/20 ${
              sidebarCollapsed ? "justify-center" : ""
            }`}
            title={sidebarCollapsed ? (workspace || "Set workspace") : undefined}
          >
            <FolderOpen className="w-4 h-4 flex-shrink-0" />
            <span className={`text-xs font-medium truncate transition-opacity duration-300 ${
              sidebarCollapsed ? "opacity-0 w-0" : "opacity-100"
            }`}>
              {workspace ? (
                <span className="text-slate-400">{workspace}</span>
              ) : (
                <span className="text-slate-500 italic">Open folder...</span>
              )}
            </span>
          </button>
        </div>
      )}

      {showBrowser && (
        <SidebarFolderBrowser
          currentPath={workspace}
          onSelect={async (path) => {
            try {
              await api.filesystem.setWorkspace(path);
              setWorkspace(path);
              setShowBrowser(false);
            } catch {
              /* ignore */
            }
          }}
          onClose={() => setShowBrowser(false)}
        />
      )}

      <div className="border-t border-slate-800 px-2 py-3 space-y-1">
        {isAuthenticated && user ? (
          <>
            <div
              onClick={() => navigate("/settings")}
              className="flex items-center gap-3 px-3 py-2 rounded-xl cursor-pointer
                text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-all"
              title={sidebarCollapsed ? user.username : undefined}
            >
              <div className="w-7 h-7 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center flex-shrink-0">
                <User className="w-4 h-4" />
              </div>
              <div className={`flex-1 min-w-0 transition-opacity duration-300 ${sidebarCollapsed ? "opacity-0 w-0" : "opacity-100"}`}>
                <p className="text-sm font-medium text-slate-200 truncate">{user.username}</p>
                <p className="text-xs text-slate-500 truncate">{user.roles.join(", ") || "user"}</p>
              </div>
            </div>

            <button
              onClick={() => {
                logout();
                navigate("/login");
              }}
              className="flex items-center gap-3 w-full px-3 py-2 rounded-xl text-slate-400
                hover:text-red-400 hover:bg-red-500/10 transition-all"
              title="Logout"
            >
              <LogOut className="w-4 h-4 flex-shrink-0" />
              <span className={`text-sm whitespace-nowrap transition-opacity duration-300 ${sidebarCollapsed ? "opacity-0 w-0" : "opacity-100"}`}>
                Logout
              </span>
            </button>
          </>
        ) : (
          <>
            <Link
              to="/login"
              className="flex items-center gap-3 px-3 py-2 rounded-xl text-slate-400
                hover:text-cyan-400 hover:bg-cyan-500/10 transition-all"
            >
              <Key className="w-4 h-4 flex-shrink-0" />
              <span className={`text-sm whitespace-nowrap transition-opacity duration-300 ${sidebarCollapsed ? "opacity-0 w-0" : "opacity-100"}`}>
                Sign In
              </span>
            </Link>
            <Link
              to="/register"
              className="flex items-center gap-3 px-3 py-2 rounded-xl text-slate-400
                hover:text-emerald-400 hover:bg-emerald-500/10 transition-all"
            >
              <User className="w-4 h-4 flex-shrink-0" />
              <span className={`text-sm whitespace-nowrap transition-opacity duration-300 ${sidebarCollapsed ? "opacity-0 w-0" : "opacity-100"}`}>
                Register
              </span>
            </Link>
          </>
        )}

        <button
          onClick={toggleSidebar}
          className="flex items-center justify-center w-full p-2 rounded-xl text-slate-400
            hover:text-slate-200 hover:bg-slate-800/50 transition-all"
        >
          {sidebarCollapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <ChevronLeft className="w-4 h-4" />
          )}
        </button>
      </div>
    </aside>
  );
}

function SidebarFolderBrowser({
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
    <Modal open onClose={onClose} title="Open Folder" size="lg">
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
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400">
            {error}
          </div>
        )}

        <div className="max-h-72 overflow-y-auto space-y-1">
          {loading ? (
            <div className="space-y-2 p-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-8 bg-slate-800/30 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : entries.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-8">No subdirectories</p>
          ) : (
            entries.map((entry) => (
              <button
                key={entry.name}
                onClick={() => navigate(entry.path)}
                className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-300
                  hover:bg-slate-800/50 transition-all text-left"
              >
                <Folder className="w-4 h-4 text-amber-400 flex-shrink-0" />
                <span className="truncate">{entry.name}</span>
              </button>
            ))
          )}
        </div>

        <div className="flex justify-end gap-3 pt-2 border-t border-slate-800">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-400 glass rounded-lg glass-hover"
          >
            Cancel
          </button>
          <button
            onClick={() => onSelect(currentDir)}
            disabled={!currentDir}
            className="px-4 py-2 text-sm font-medium bg-cyan-500/10 text-cyan-400 rounded-lg
              hover:bg-cyan-500/20 transition-all border border-cyan-500/20 disabled:opacity-50"
          >
            Select Folder
          </button>
        </div>
      </div>
    </Modal>
  );
}
