"""Runtime settings, read once from environment variables (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_float(name: str) -> float | None:
    value = _env(name)
    return float(value) if value is not None else None


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    allowed_user_ids: frozenset[int]
    owner_chat_id: int

    model: str
    effort: str
    max_turns: int

    tz: ZoneInfo
    data_dir: Path
    workspace_dir: Path

    morning_brief_time: str | None
    evening_checkin_time: str | None
    weekly_review: str | None
    monthly_report_time: str | None

    openai_api_key: str | None
    transcribe_model: str

    google_client_id: str | None
    google_client_secret: str | None
    google_user_email: str | None
    github_token: str | None
    github_toolsets: str

    auto_approve_bash: bool
    approval_timeout_s: int
    daily_budget_usd: float | None

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def github_enabled(self) -> bool:
        return bool(self.github_token)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "lifeagent.sqlite3"

    @classmethod
    def from_env(cls) -> "Settings":
        token = _env("TELEGRAM_BOT_TOKEN")
        if not token:
            raise SystemExit("TELEGRAM_BOT_TOKEN is not set")

        raw_ids = _env("TELEGRAM_ALLOWED_USER_IDS")
        if not raw_ids:
            raise SystemExit(
                "TELEGRAM_ALLOWED_USER_IDS is not set — the bot refuses to run "
                "without an allow-list, since it can read your email and data."
            )
        user_ids = [int(x) for x in raw_ids.replace(" ", "").split(",") if x]

        root = Path(__file__).resolve().parent.parent
        data_dir = Path(_env("LIFEAGENT_DATA_DIR", str(root / "data"))).resolve()
        workspace_dir = Path(_env("LIFEAGENT_WORKSPACE_DIR", str(root / "workspace"))).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            telegram_token=token,
            allowed_user_ids=frozenset(user_ids),
            # Scheduled briefs go to the first listed user's private chat.
            owner_chat_id=user_ids[0],
            model=_env("LIFEAGENT_MODEL", "claude-opus-5-5"),
            effort=_env("LIFEAGENT_EFFORT", "medium"),
            max_turns=int(_env("LIFEAGENT_MAX_TURNS", "40")),
            tz=ZoneInfo(_env("LIFEAGENT_TIMEZONE", "Asia/Tehran")),
            data_dir=data_dir,
            workspace_dir=workspace_dir,
            morning_brief_time=_env("MORNING_BRIEF_TIME", "07:30"),
            evening_checkin_time=_env("EVENING_CHECKIN_TIME", "22:00"),
            weekly_review=_env("WEEKLY_REVIEW", "fri 18:00"),
            monthly_report_time=_env("MONTHLY_REPORT_TIME", "09:00"),
            openai_api_key=_env("OPENAI_API_KEY"),
            transcribe_model=_env("TRANSCRIBE_MODEL", "whisper-1"),
            google_client_id=_env("GOOGLE_OAUTH_CLIENT_ID"),
            google_client_secret=_env("GOOGLE_OAUTH_CLIENT_SECRET"),
            google_user_email=_env("USER_GOOGLE_EMAIL"),
            github_token=_env("GITHUB_PERSONAL_ACCESS_TOKEN"),
            github_toolsets=_env(
                "GITHUB_TOOLSETS", "repos,issues,pull_requests,actions,notifications"
            ),
            auto_approve_bash=_env_bool("AUTO_APPROVE_BASH", False),
            approval_timeout_s=int(_env("APPROVAL_TIMEOUT_SECONDS", "900")),
            daily_budget_usd=_env_float("DAILY_BUDGET_USD"),
        )
