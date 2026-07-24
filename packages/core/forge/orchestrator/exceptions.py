from __future__ import annotations


class OrchestratorError(Exception):
    """Base orchestrator exception."""


class AgentNotFoundError(OrchestratorError):
    """Requested agent is not registered."""


class AgentBusyError(OrchestratorError):
    """Agent is currently busy and cannot accept tasks."""


class AgentUnhealthyError(OrchestratorError):
    """Agent failed health check."""


class TaskDecompositionError(OrchestratorError):
    """LLM failed to decompose the task."""


class TaskExecutionError(OrchestratorError):
    """A sub-task failed during execution."""


class OrchestrationTimeoutError(OrchestratorError):
    """Orchestration exceeded its time budget."""


class TokenBudgetExceededError(OrchestratorError):
    """Combined token usage exceeded the configured budget."""
