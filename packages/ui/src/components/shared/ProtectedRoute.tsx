import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "../../store/auth";
import type { ReactNode } from "react";

interface ProtectedRouteProps {
  children: ReactNode;
  requiredPermission?: string;
}

export function ProtectedRoute({
  children,
  requiredPermission,
}: ProtectedRouteProps) {
  const { isAuthenticated, user } = useAuthStore();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredPermission && user) {
    const hasPermission =
      user.is_admin || user.permissions.includes(requiredPermission);
    if (!hasPermission) {
      return (
        <div className="flex flex-col items-center justify-center py-16">
          <div className="p-4 rounded-full bg-red-500/10 mb-4">
            <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m0 0v2m0-2h2m-2 0H10" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-slate-300 mb-1">
            Access Denied
          </h2>
          <p className="text-sm text-slate-500 mb-4">
            You don't have permission to access this page.
          </p>
          <button
            onClick={() => window.history.back()}
            className="px-4 py-2 text-sm text-cyan-400 glass rounded-lg glass-hover"
          >
            Go Back
          </button>
        </div>
      );
    }
  }

  return <>{children}</>;
}
