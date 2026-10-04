"""Shared application objects, passed to tools, handlers and jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .config import Settings
from .db import Database

if TYPE_CHECKING:
    from telegram import Bot

    from .agent import AgentPool
    from .approvals import ApprovalManager
    from .scheduler import Scheduler


@dataclass
class AppContext:
    settings: Settings
    db: Database
    bot: "Bot | None" = None
    approvals: "ApprovalManager | None" = None
    scheduler: "Scheduler | None" = None
    agents: "AgentPool | None" = None
    extra: dict[str, Any] = field(default_factory=dict)

    def now(self) -> datetime:
        return datetime.now(self.settings.tz)


@dataclass
class ToolContext:
    """What an in-process tool sees: the app plus the chat it is serving."""

    app: AppContext
    chat_id: int

    @property
    def db(self) -> Database:
        return self.app.db

    @property
    def settings(self) -> Settings:
        return self.app.settings

    def now(self) -> datetime:
        return self.app.now()
