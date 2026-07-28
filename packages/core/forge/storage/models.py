from __future__ import annotations

from datetime import UTC, datetime

from forge.storage.postgres import Base
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AgentModel(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    role = Column(String(1024), nullable=False)
    goal = Column(Text, nullable=False)
    config_yaml = Column(Text, nullable=True)
    model_name = Column(String(128), default="llama3.2:3b")
    status = Column(String(32), default="inactive")
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<AgentModel(id={self.id}, name='{self.name}')>"


class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True, index=True)
    agent_name = Column(String(128), nullable=False)
    input = Column(Text, nullable=False)
    output = Column(Text, nullable=True)
    status = Column(String(32), default="pending", index=True)
    error = Column(Text, nullable=True)
    iterations = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<TaskModel(id={self.id}, agent='{self.agent_name}', status='{self.status}')>"


class LogModel(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True, index=True)
    agent_name = Column(String(128), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True, index=True)
    level = Column(String(16), default="INFO", index=True)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=_utcnow, nullable=False, index=True)
    metadata_json = Column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<LogModel(id={self.id}, level='{self.level}', agent='{self.agent_name}')>"


class McpServerModel(Base):
    __tablename__ = "mcp_servers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    transport_type = Column(String(16), nullable=False, default="http")
    url = Column(String(512), nullable=True)
    command = Column(String(512), nullable=True)
    cwd = Column(String(512), nullable=True)
    status = Column(String(32), default="disconnected")
    config = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<McpServerModel(id={self.id}, name='{self.name}', status='{self.status}')>"


class AgentTemplateModel(Base):
    __tablename__ = "agent_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    description = Column(Text, nullable=True)
    config_json = Column(JSON, nullable=False)
    category = Column(String(64), nullable=True)
    tags = Column(JSON, nullable=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<AgentTemplateModel(id={self.id}, name='{self.name}')>"


class WebhookModel(Base):
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    url = Column(String(512), nullable=False)
    events = Column(JSON, nullable=False, default=["agent.run.completed"])
    secret = Column(String(256), nullable=True)
    active = Column(Integer, default=1)
    last_triggered_at = Column(DateTime, nullable=True)
    last_response_code = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<WebhookModel(id={self.id}, name='{self.name}', active={self.active})>"


class RunModel(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    agent_name = Column(String(128), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    status = Column(String(32), default="running", index=True)
    iterations = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    started_at = Column(DateTime, default=_utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<RunModel(id={self.id}, agent='{self.agent_name}', status='{self.status}')>"
