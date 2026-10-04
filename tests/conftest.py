import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifeagent.config import Settings  # noqa: E402
from lifeagent.context import AppContext, ToolContext  # noqa: E402
from lifeagent.db import Database  # noqa: E402


def make_settings(tmp_path: Path) -> Settings:
    os.environ.update(
        {
            "TELEGRAM_BOT_TOKEN": "test",
            "TELEGRAM_ALLOWED_USER_IDS": "42",
            "LIFEAGENT_DATA_DIR": str(tmp_path / "data"),
            "LIFEAGENT_WORKSPACE_DIR": str(tmp_path / "ws"),
        }
    )
    (tmp_path / "ws").mkdir(exist_ok=True)
    return Settings.from_env()


@pytest.fixture
async def tool_ctx(tmp_path):
    settings = make_settings(tmp_path)
    db = Database(settings.db_path)
    await db.connect()
    app = AppContext(settings=settings, db=db)
    yield ToolContext(app=app, chat_id=42)
    await db.close()


@pytest.fixture
def tz():
    return ZoneInfo("Asia/Tehran")
