"""Prepare the agent's working directory on startup."""

from __future__ import annotations

import shutil
from pathlib import Path

from .config import Settings

TEMPLATES = Path(__file__).parent / "templates"
SUBDIRS = (
    "memory", "inbox", "outbox",
    "notes/work", "notes/learning", "notes/people", "notes/research", "notes/reviews", "notes/health",
)


def ensure_workspace(settings: Settings) -> None:
    root = settings.workspace_dir
    for sub in SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    profile = root / "memory" / "profile.md"
    if not profile.exists():
        shutil.copy(TEMPLATES / "profile.md", profile)


def workspace_skills(workspace: Path) -> list[str]:
    skills_dir = workspace / ".claude" / "skills"
    return sorted(p.parent.name for p in skills_dir.glob("*/SKILL.md"))
