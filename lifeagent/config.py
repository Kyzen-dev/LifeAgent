"""Runtime settings, read once from environment variables (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

# .env variables the model registry reads (provider keys and endpoint overrides).
LLM_ENV_KEYS = (
    "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "MOONSHOT_API_KEY", "ZAI_API_KEY",
    "LITELLM_MASTER_KEY", "LITELLM_URL", "CUSTOM_LLM_API_KEY", "CUSTOM_LLM_BASE_URL",
)


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
    fallback_model: str | None
    effort: str
    max_turns: int

    tz: ZoneInfo
    data_dir: Path
    workspace_dir: Path

    morning_brief_time: str | None
    evening_checkin_time: str | None
    weekly_review: str | None
    monthly_report_time: str | None
    midday_checkin_time: str | None
    ai_digest: str | None

    prayer_reminders: bool
    prayer_city: str
    prayer_country: str
    prayer_method: int
    prayer_names: tuple[str, ...]

    openai_api_key: str | None
    groq_api_key: str | None
    transcribe_provider: str
    transcribe_model: str | None
    transcribe_language: str | None

    google_client_id: str | None
    google_client_secret: str | None
    google_user_email: str | None
    github_token: str | None
    github_toolsets: str
    context7_enabled: bool
    context7_api_key: str | None
    browser_enabled: bool
    tavily_api_key: str | None
    iran_prices_key: str | None

    city: str
    finance_cards: bool

    auto_approve_bash: bool
    approval_timeout_s: int
    trust_window_min: int
    daily_budget_usd: float | None

    llm_env: dict[str, str] = field(default_factory=dict)

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def github_enabled(self) -> bool:
        return bool(self.github_token)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "lifeagent.sqlite3"

    @property
    def models_file(self) -> Path:
        return self.data_dir / "models.toml"

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
            model=_env("LIFEAGENT_MODEL", "sonnet"),
            fallback_model=_env("LIFEAGENT_FALLBACK_MODEL"),
            effort=_env("LIFEAGENT_EFFORT", "medium"),
            max_turns=int(_env("LIFEAGENT_MAX_TURNS", "40")),
            tz=ZoneInfo(_env("LIFEAGENT_TIMEZONE", "Asia/Tehran")),
            data_dir=data_dir,
            workspace_dir=workspace_dir,
            morning_brief_time=_env("MORNING_BRIEF_TIME", "08:00"),
            evening_checkin_time=_env("EVENING_CHECKIN_TIME", "23:00"),
            weekly_review=_env("WEEKLY_REVIEW", "fri 18:00"),
            monthly_report_time=_env("MONTHLY_REPORT_TIME", "09:00"),
            midday_checkin_time=_env("MIDDAY_CHECKIN_TIME", "14:00"),
            ai_digest=_env("AI_DIGEST", "thu 10:00"),
            prayer_reminders=_env_bool("PRAYER_REMINDERS", False),
            prayer_city=_env("PRAYER_CITY", _env("LIFEAGENT_CITY", "Tehran")),
            prayer_country=_env("PRAYER_COUNTRY", "Iran"),
            # 7 = Institute of Geophysics, University of Tehran (aladhan.com methods)
            prayer_method=int(_env("PRAYER_METHOD", "7")),
            prayer_names=tuple(
                x.strip().lower() for x in _env("PRAYER_TIMES", "fajr,dhuhr,maghrib").split(",") if x.strip()
            ),
            openai_api_key=_env("OPENAI_API_KEY"),
            groq_api_key=_env("GROQ_API_KEY"),
            transcribe_provider=(_env("TRANSCRIBE_PROVIDER", "auto") or "auto").lower(),
            transcribe_model=_env("TRANSCRIBE_MODEL"),
            transcribe_language=_env("TRANSCRIBE_LANGUAGE"),
            google_client_id=_env("GOOGLE_OAUTH_CLIENT_ID"),
            google_client_secret=_env("GOOGLE_OAUTH_CLIENT_SECRET"),
            google_user_email=_env("USER_GOOGLE_EMAIL"),
            github_token=_env("GITHUB_PERSONAL_ACCESS_TOKEN"),
            github_toolsets=_env(
                "GITHUB_TOOLSETS", "repos,issues,pull_requests,actions,notifications"
            ),
            context7_enabled=_env_bool("ENABLE_CONTEXT7", True),
            context7_api_key=_env("CONTEXT7_API_KEY"),
            browser_enabled=_env_bool("ENABLE_BROWSER", False),
            tavily_api_key=_env("TAVILY_API_KEY"),
            iran_prices_key=_env("BRSAPI_KEY"),
            city=_env("LIFEAGENT_CITY", "Tehran"),
            finance_cards=_env_bool("FINANCE_CONFIRM_CARDS", True),
            auto_approve_bash=_env_bool("AUTO_APPROVE_BASH", False),
            approval_timeout_s=int(_env("APPROVAL_TIMEOUT_SECONDS", "900")),
            trust_window_min=int(_env("TRUST_WINDOW_MINUTES", "30")),
            daily_budget_usd=_env_float("DAILY_BUDGET_USD"),
            llm_env={k: v for k in LLM_ENV_KEYS if (v := _env(k))},
        )
