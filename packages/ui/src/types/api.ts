import type { ComponentProps } from "react";
import type { LucideIcon } from "lucide-react";

export type AgentStatus = "idle" | "busy" | "error" | "offline";
export type AgentCapability =
  | "search"
  | "analysis"
  | "code"
  | "writing"
  | "reasoning"
  | "summarization"
  | "custom";
export type OrchestrationStrategy =
  | "sequential"
  | "parallel"
  | "supervisor"
  | "auto";
export type SubTaskStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped";
export type ExecutionMode = "sync" | "async";
export type FallbackBehavior =
  | "error"
  | "retry"
  | "skip"
  | "delegate";

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  is_admin: boolean;
  roles: string[];
  permissions: string[];
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface CurrentUserResponse {
  id: number;
  username: string;
  email: string;
  is_admin: boolean;
  roles: string[];
  permissions: string[];
}

export interface ApiKeyResponse {
  id: number;
  prefix: string;
  name: string;
  is_active: boolean;
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string;
}

export interface AgentDescriptor {
  name: string;
  role: string;
  goal: string;
  capabilities: AgentCapability[];
  status: AgentStatus;
  last_heartbeat: string | null;
  endpoint: string | null;
  metadata: Record<string, unknown>;
}

export interface ModelConfig {
  name: string;
  provider: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
}

export interface ToolConfig {
  name: string;
  type: string;
  config: Record<string, unknown>;
}

export interface MemoryConfig {
  type: string;
  collection: string;
  embedding_model: string;
  top_k: number;
  score_threshold: number;
}

export interface AgentConfig {
  name: string;
  role: string;
  goal: string;
  model: ModelConfig;
  tools: ToolConfig[];
  memory: MemoryConfig;
  max_iterations: number;
  system_prompt_extra: string;
  environment: Record<string, string>;
}

export interface TaskResult {
  agent_name: string;
  task: string;
  output: string;
  iterations: number;
  tokens_used: number;
  error: string | null;
  duration_ms: number;
}

export interface AgentListResponse {
  agents: AgentDescriptor[];
}

export interface SubTaskDef {
  id: string;
  description: string;
  agent_role: string;
  agent_capabilities: AgentCapability[];
  depends_on: string[];
  context: string;
  max_iterations: number;
  priority: number;
  timeout_seconds: number;
}

export interface SubTaskResult {
  sub_task_id: string;
  description: string;
  status: SubTaskStatus;
  agent_name: string;
  output: string;
  error: string | null;
  iterations: number;
  tokens_used: number;
  duration_ms: number;
  started_at: string | null;
  finished_at: string | null;
}

export interface OrchestrationConfig {
  strategy: OrchestrationStrategy;
  agent_roles: string[];
  max_concurrency: number;
  timeout_seconds: number;
  max_iterations_per_agent: number;
  token_budget: number;
  fallback_behavior: FallbackBehavior;
  enable_task_planning: boolean;
  enable_supervisor: boolean;
  enable_parallel: boolean;
  execution_mode: ExecutionMode;
  context: Record<string, unknown>;
}

export interface OrchestrationResult {
  id: string;
  task: string;
  strategy: OrchestrationStrategy;
  status: SubTaskStatus;
  sub_results: SubTaskResult[];
  final_output: string;
  total_iterations: number;
  total_tokens: number;
  total_duration_ms: number;
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface OrchestrateResponse {
  id: string;
  status: string;
  result: OrchestrationResult | null;
  error: string | null;
}

export interface HealthCheck {
  status: string;
  version: string;
  services: {
    api: string;
    ollama: string;
  };
}

export interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
  badge?: number;
  requiredPermission?: string;
}

export interface StatCard {
  label: string;
  value: string | number;
  icon: LucideIcon;
  trend?: { value: number; positive: boolean };
  color: "cyan" | "emerald" | "violet" | "amber";
}

export interface BrowseEntry {
  name: string;
  path: string;
  type: "directory" | "file";
  size: number;
  modified: number;
}

export interface BrowseResponse {
  path: string;
  parent: string | null;
  entries: BrowseEntry[];
}

export interface WorkspaceResponse {
  workspace: string;
}

export interface ModelInfo {
  name: string;
  size: number;
  modified: string;
  digest: string;
}

export interface ModelListResponse {
  models: ModelInfo[];
  default_model: string;
}

export interface RunHistory {
  id: number;
  agent_name: string;
  input: string;
  output: string | null;
  status: string;
  error: string | null;
  iterations: number;
  tokens_used: number;
  duration_ms: number;
  created_at: string;
  finished_at: string | null;
}

export type MetricCardProps = ComponentProps<"div"> & {
  icon: LucideIcon;
  label: string;
  value: string | number;
  trend?: { value: number; positive: boolean };
  color: "cyan" | "emerald" | "violet" | "amber";
  loading?: boolean;
};

export type StatusBadgeProps = ComponentProps<"span"> & {
  status: AgentStatus | SubTaskStatus | OrchestrationStrategy;
  size?: "sm" | "md" | "lg";
  animated?: boolean;
};
