import { create } from "zustand";
import type { AgentDescriptor, OrchestrationResult } from "../types/api";

interface AppState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;

  currentOrchestrationId: string | null;
  setCurrentOrchestrationId: (id: string | null) => void;

  orchestrationHistory: OrchestrationResult[];
  addOrchestration: (r: OrchestrationResult) => void;

  agents: AgentDescriptor[];
  setAgents: (agents: AgentDescriptor[]) => void;
  updateAgent: (name: string, updates: Partial<AgentDescriptor>) => void;
}

export const useAppStore = create<AppState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () =>
    set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  currentOrchestrationId: null,
  setCurrentOrchestrationId: (id) =>
    set({ currentOrchestrationId: id }),

  orchestrationHistory: [],
  addOrchestration: (r) =>
    set((s) => ({
      orchestrationHistory: [r, ...s.orchestrationHistory].slice(0, 50),
    })),

  agents: [],
  setAgents: (agents) => set({ agents }),
  updateAgent: (name, updates) =>
    set((s) => ({
      agents: s.agents.map((a) =>
        a.name === name ? { ...a, ...updates } : a,
      ),
    })),
}));
