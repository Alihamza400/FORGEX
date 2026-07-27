import { useAuthStore } from "../store/auth";
import type {
  AgentConfig,
  AgentDescriptor,
  AgentRow,
  ApiKeyResponse,
  BrowseResponse,
  CurrentUserResponse,
  FileListResponse,
  HealthCheck,
  McpServer,
  McpServerConnectResult,
  McpServerTestResult,
  ModelListResponse,
  OrchestrateResponse,
  OrchestrationConfig,
  RunHistory,
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

  files: {
    list: (prefix?: string) =>
      request<FileListResponse>(`/files?prefix=${encodeURIComponent(prefix ?? "")}`),

    upload: (file: File, onProgress?: (pct: number) => void): Promise<{ status: string; key: string; path: string }> => {
      return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append("file", file);
        const xhr = new XMLHttpRequest();
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
        };
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText));
          else reject(new Error(xhr.responseText ? JSON.parse(xhr.responseText).detail : "Upload failed"));
        };
        xhr.onerror = () => reject(new Error("Upload failed"));
        const { accessToken } = useAuthStore.getState();
        xhr.open("POST", `${API_BASE}/files/upload`);
        if (accessToken) xhr.setRequestHeader("Authorization", `Bearer ${accessToken}`);
        xhr.send(formData);
      });
    },

    download: (key: string): string => {
      const { accessToken } = useAuthStore.getState();
      const params = accessToken ? `?token=${accessToken}` : "";
      return `${API_BASE}/files/${encodeURIComponent(key)}${params}`;
    },

    delete: (key: string) =>
      request<{ status: string; key: string }>(`/files/${encodeURIComponent(key)}`, { method: "DELETE" }),
  },

  mcp: {
    list: () => request<McpServer[]>("/mcp/servers"),

    create: (data: {
      name: string;
      transport_type?: string;
      url?: string;
      command?: string;
      cwd?: string;
      config?: Record<string, unknown>;
    }) =>
      request<McpServer>("/mcp/servers", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    delete: (id: number) =>
      request<{ status: string; name: string }>(`/mcp/servers/${id}`, {
        method: "DELETE",
      }),

    test: (id: number) =>
      request<McpServerTestResult>(`/mcp/servers/${id}/test`, {
        method: "POST",
      }),

    connect: (id: number) =>
      request<McpServerConnectResult>(`/mcp/servers/${id}/connect`, {
        method: "POST",
      }),

    disconnect: (id: number) =>
      request<{ status: string; name: string }>(`/mcp/servers/${id}/disconnect`, {
        method: "POST",
      }),
  },

  models: {
    list: () => request<ModelListResponse>("/models"),

    pull: (name: string) =>
      request<{ status: string; model: string }>("/models/pull", {
        method: "POST",
        body: JSON.stringify({ name }),
      }),
  },

  agents: {
    list: () => request<AgentRow[]>("/agents"),

    runs: (name: string, limit?: number, offset?: number) =>
      request<RunHistory[]>(`/agents/${encodeURIComponent(name)}/runs?limit=${limit ?? 20}&offset=${offset ?? 0}`),

    runDetail: (name: string, taskId: number) =>
      request<RunHistory>(`/agents/${encodeURIComponent(name)}/runs/${taskId}`),

    runStream: (
      payload: { config_path?: string; config?: AgentConfig; task: string },
      onEvent: (event: { type: string; data: Record<string, unknown> }) => void,
      onDone: () => void,
      onError: (err: Error) => void,
    ): AbortController => {
      const controller = new AbortController();
      const { accessToken } = useAuthStore.getState();

      fetch(`${API_BASE}/agents/run/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      }).then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          onError(new Error((body as { detail?: string }).detail ?? res.statusText));
          return;
        }
        const reader = res.body?.getReader();
        if (!reader) {
          onError(new Error("No response body"));
          return;
        }
        const decoder = new TextDecoder();
        let buffer = "";
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() ?? "";
            for (const line of lines) {
              const trimmed = line.trim();
              if (!trimmed || !trimmed.startsWith("data: ")) continue;
              try {
                const parsed = JSON.parse(trimmed.slice(6));
                onEvent(parsed);
              } catch {
                // skip malformed events
              }
            }
          }
        } catch (err) {
          if (err instanceof Error && err.name !== "AbortError") {
            onError(err);
          }
          return;
        }
        onDone();
      }).catch((err) => {
        if (err.name !== "AbortError") onError(err);
      });

      return controller;
    },

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
  const rows = await api.agents.list();
  return rows.map((a) => ({
    name: a.name,
    role: a.role,
    goal: a.goal,
    capabilities: [] as import("../types/api").AgentCapability[],
    status: a.status as import("../types/api").AgentStatus,
    last_heartbeat: null,
    endpoint: null,
    metadata: {},
    running: a.status === "busy",
  }));
}
