import { useAuthStore } from "../store/auth";
import type {
  AgentConfig,
  AgentDescriptor,
  AgentListResponse,
  ApiKeyResponse,
  BrowseResponse,
  CurrentUserResponse,
  HealthCheck,
  OrchestrateResponse,
  OrchestrationConfig,
  SubTaskResult,
  TaskResult,
  TokenResponse,
  WorkspaceResponse,
} from "../types/api";

const API_BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function getAuthHeaders(): Record<string, string> {
  const { accessToken } = useAuthStore.getState();
  if (accessToken) {
    return { Authorization: `Bearer ${accessToken}` };
  }
  return {};
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...getAuthHeaders(),
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    const { refreshToken, setTokens, logout } = useAuthStore.getState();
    if (refreshToken) {
      try {
        const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (refreshRes.ok) {
          const data = (await refreshRes.json()) as TokenResponse;
          setTokens(data.access_token, data.refresh_token);
          headers.Authorization = `Bearer ${data.access_token}`;
          const retryRes = await fetch(`${API_BASE}${path}`, {
            ...options,
            headers,
          });
          if (!retryRes.ok) {
            const body = await retryRes.json().catch(() => ({}));
            throw new ApiError(
              retryRes.status,
              (body as { detail?: string }).detail ?? retryRes.statusText,
            );
          }
          return retryRes.json() as Promise<T>;
        }
      } catch {
        logout();
        window.location.href = "/login";
        throw new ApiError(401, "Session expired");
      }
    }
    logout();
    window.location.href = "/login";
    throw new ApiError(401, "Authentication required");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      (body as { detail?: string }).detail ?? res.statusText,
    );
  }

  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthCheck>("/health"),

  auth: {
    register: (data: { username: string; email: string; password: string }) =>
      request<{ id: number; username: string; email: string }>(
        "/auth/register",
        { method: "POST", body: JSON.stringify(data) },
      ),

    login: (data: { username: string; password: string }) =>
      request<TokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    refresh: (data: { refresh_token: string }) =>
      request<TokenResponse>("/auth/refresh", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    me: () => request<CurrentUserResponse>("/auth/me"),

    changePassword: (data: { current_password: string; new_password: string }) =>
      request<{ message: string }>("/auth/change-password", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    apiKeys: {
      list: () => request<ApiKeyResponse[]>("/auth/api-keys"),
      create: (data: { name: string; expires_in_days?: number }) =>
        request<{ id: number; prefix: string; name: string; key: string; expires_at: string | null }>(
          "/auth/api-keys",
          { method: "POST", body: JSON.stringify(data) },
        ),
      revoke: (id: number) =>
        request<{ message: string }>(`/auth/api-keys/${id}`, {
          method: "DELETE",
        }),
    },
  },

  filesystem: {
    browse: (path?: string) =>
      request<BrowseResponse>(`/filesystem/browse?path=${encodeURIComponent(path ?? "")}`),

    getWorkspace: () =>
      request<WorkspaceResponse>("/filesystem/workspace"),

    setWorkspace: (workspace: string) =>
      request<WorkspaceResponse>("/filesystem/workspace", {
        method: "POST",
        body: JSON.stringify({ workspace }),
      }),
  },

  agents: {
    list: () => request<AgentListResponse>("/agents"),

    validate: (config: { config_path?: string; config?: AgentConfig }) =>
      request<{ valid: boolean; name: string; errors: string[] }>(
        "/agents/validate",
        { method: "POST", body: JSON.stringify(config) },
      ),

    run: (payload: {
      config_path?: string;
      config?: AgentConfig;
      task: string;
    }) =>
      request<TaskResult>("/agents/run", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  orchestrations: {
    create: (payload: {
      task: string;
      agents: Record<string, AgentConfig>;
      config?: Partial<OrchestrationConfig>;
    }) =>
      request<OrchestrateResponse>("/orchestrate", {
        method: "POST",
        body: JSON.stringify(payload),
      }),

    get: (id: string) => request<OrchestrateResponse>(`/orchestrate/${id}`),

    getSubTasks: (id: string) =>
      request<SubTaskResult[]>(`/orchestrate/${id}/sub-tasks`),
  },
};

export async function fetchAgentsWithStatus(): Promise<
  (AgentDescriptor & { running: boolean })[]
> {
  const { agents } = await api.agents.list();
  return agents.map((a) => ({ ...a, running: a.status === "busy" }));
}
