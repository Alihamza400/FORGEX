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
} from "lucide-react";
import { useAppStore } from "../../store/app";
import { useAuthStore } from "../../store/auth";
import type { NavItem } from "../../types/api";

const navItems: NavItem[] = [
  { label: "Dashboard", path: "/", icon: LayoutDashboard },
  { label: "Agents", path: "/agents", icon: Bot, requiredPermission: "agent:list" },
  { label: "Orchestration", path: "/orchestrate", icon: GitBranch, requiredPermission: "orchestrate:read" },
  { label: "Logs", path: "/logs", icon: Logs, requiredPermission: "log:read" },
  { label: "Settings", path: "/settings", icon: Settings, requiredPermission: "settings:read" },
];

export function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { sidebarCollapsed, toggleSidebar } = useAppStore();
  const { isAuthenticated, user, logout } = useAuthStore();

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
