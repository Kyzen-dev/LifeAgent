"""Entry point: `python -m lifeagent`."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from .config import Settings
from .context import AppContext
from .db import Database
from .telegram_bot import build_application


def main() -> None:
    load_dotenv()
    # In Docker HOME lives on the data volume (~/.claude sessions, uv cache); make sure it exists.
    if os.environ.get("HOME"):
        Path(os.environ["HOME"]).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # The Telegram library logs every poll at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    settings = Settings.from_env()
    app = AppContext(settings=settings, db=Database(settings.db_path))
    build_application(app).run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
