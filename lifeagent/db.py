"""SQLite storage for sessions, usage and personal data (finance, habits, ...)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    chat_id     INTEGER PRIMARY KEY,
    session_id  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    provider    TEXT                        -- a session is only resumed on the same provider
);

CREATE TABLE IF NOT EXISTS chat_settings (
    chat_id     INTEGER PRIMARY KEY,
    model       TEXT,                       -- alias from lifeagent.models, NULL = default
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id   INTEGER NOT NULL,
    ts        TEXT NOT NULL,
    cost_usd  REAL NOT NULL,
    turns     INTEGER NOT NULL,
    model     TEXT,
    input_tokens  INTEGER,
    output_tokens INTEGER
);

CREATE TABLE IF NOT EXISTS transactions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    date      TEXT NOT NULL,              -- Gregorian YYYY-MM-DD
    kind      TEXT NOT NULL CHECK (kind IN ('expense', 'income')),
    amount    REAL NOT NULL CHECK (amount >= 0),
    currency  TEXT NOT NULL DEFAULT 'IRT', -- IRT = Toman
    category  TEXT NOT NULL,
    account   TEXT,
    note      TEXT,
    created_at TEXT NOT NULL,
    merchant  TEXT,                       -- shop, payee or payer
    items     TEXT,                       -- JSON list of {name, qty, price} from a receipt
    source    TEXT,                       -- manual / receipt / invoice / bank_sms / voice / forward / import
    attachment TEXT,                      -- workspace-relative path of the receipt image or PDF
    original_amount   REAL,               -- as written on the source, e.g. Rial before /10
    original_currency TEXT
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date);

CREATE TABLE IF NOT EXISTS budgets (
    category      TEXT NOT NULL,
    currency      TEXT NOT NULL DEFAULT 'IRT',
    monthly_limit REAL NOT NULL,
    PRIMARY KEY (category, currency)
);

CREATE TABLE IF NOT EXISTS habits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    target_per_week INTEGER NOT NULL DEFAULT 7,
    unit            TEXT,
    active          INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS habit_logs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id  INTEGER NOT NULL REFERENCES habits(id),
    date      TEXT NOT NULL,
    value     REAL NOT NULL DEFAULT 1,
    note      TEXT
);
CREATE INDEX IF NOT EXISTS idx_habit_logs ON habit_logs(habit_id, date);

CREATE TABLE IF NOT EXISTS health_logs (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    date    TEXT NOT NULL,
    metric  TEXT NOT NULL,
    value   REAL NOT NULL,
    unit    TEXT,
    note    TEXT
);
CREATE INDEX IF NOT EXISTS idx_health ON health_logs(metric, date);

CREATE TABLE IF NOT EXISTS journal (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT NOT NULL,
    mood    INTEGER,
    energy  INTEGER,
    text    TEXT NOT NULL,
    tags    TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    notes       TEXT,
    due         TEXT,                       -- YYYY-MM-DD
    priority    INTEGER NOT NULL DEFAULT 3, -- 1 = urgent .. 4 = someday
    area        TEXT,                       -- work / personal / health / learning / finance
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done', 'dropped')),
    created_at  TEXT NOT NULL,
    done_at     TEXT
);

CREATE TABLE IF NOT EXISTS goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    area        TEXT,
    why         TEXT,
    target_date TEXT,
    progress    INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'done', 'paused', 'dropped')),
    notes       TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    contact     TEXT,
    source      TEXT,                       -- referral / linkedin / x / upwork / direct ...
    currency    TEXT NOT NULL DEFAULT 'IRT',
    default_rate REAL,                      -- per hour, in currency
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('lead', 'active', 'past')),
    notes       TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id   INTEGER REFERENCES clients(id),
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('lead', 'proposal', 'interview', 'active', 'paused', 'done', 'lost')),
    source      TEXT,                       -- upwork / linkedin / x / referral / direct ...
    url         TEXT,                       -- job post or contract link
    connects    INTEGER,                    -- Upwork Connects spent on the proposal
    proposal_sent_at TEXT,                  -- set automatically on status changes
    interviewed_at   TEXT,
    hired_at         TEXT,
    billing     TEXT NOT NULL DEFAULT 'hourly' CHECK (billing IN ('hourly', 'fixed')),
    rate        REAL,                       -- hourly rate, or the fixed price
    currency    TEXT NOT NULL DEFAULT 'IRT',
    estimate_hours REAL,
    deadline    TEXT,                       -- YYYY-MM-DD
    next_action TEXT,
    next_action_date TEXT,                  -- YYYY-MM-DD, for follow-ups
    notes       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS time_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id),
    start       TEXT NOT NULL,              -- ISO datetime with offset
    end         TEXT,                       -- NULL while the timer runs
    minutes     REAL,
    note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_time_start ON time_entries(start);

CREATE TABLE IF NOT EXISTS reminders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    text        TEXT NOT NULL,
    run_at      TEXT NOT NULL,              -- ISO datetime with offset (first/next run)
    repeat      TEXT NOT NULL DEFAULT 'none' CHECK (repeat IN ('none', 'daily', 'weekly')),
    days        TEXT,                       -- for weekly: 'sat,mon,wed'
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL
);
"""


# Schema changes after the first release go here, keyed by the version they produce.
# SCHEMA above always describes the latest tables for fresh installs; an existing
# database is brought forward one step at a time and PRAGMA user_version records
# where it is. Example:  2: ["ALTER TABLE tasks ADD COLUMN estimate_min INTEGER"]
MIGRATIONS: dict[int, list[str]] = {
    2: [
        "ALTER TABLE chat_sessions ADD COLUMN provider TEXT",
        "ALTER TABLE usage ADD COLUMN model TEXT",
        "ALTER TABLE usage ADD COLUMN input_tokens INTEGER",
        "ALTER TABLE usage ADD COLUMN output_tokens INTEGER",
        "ALTER TABLE transactions ADD COLUMN merchant TEXT",
        "ALTER TABLE transactions ADD COLUMN items TEXT",
        "ALTER TABLE transactions ADD COLUMN source TEXT",
        "ALTER TABLE transactions ADD COLUMN attachment TEXT",
        "ALTER TABLE transactions ADD COLUMN original_amount REAL",
        "ALTER TABLE transactions ADD COLUMN original_currency TEXT",
    ],
}
SCHEMA_VERSION = max(MIGRATIONS, default=1)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path):
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        async with self._conn.execute("PRAGMA user_version") as cursor:
            version = (await cursor.fetchone())[0]
        is_new = not await self._has_tables()
        await self._conn.executescript(SCHEMA)
        if is_new:
            version = SCHEMA_VERSION  # fresh install: SCHEMA is already the latest
        for target in sorted(v for v in MIGRATIONS if v > max(version, 1)):
            for statement in MIGRATIONS[target]:
                await self._conn.execute(statement)
            version = target
        await self._conn.execute(f"PRAGMA user_version = {max(version, 1)}")
        await self._conn.commit()

    async def _has_tables(self) -> bool:
        async with self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'chat_sessions'"
        ) as cursor:
            return await cursor.fetchone() is not None

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected")
        return self._conn

    async def execute(self, sql: str, params: tuple | list = ()) -> int:
        """Run a write statement; returns lastrowid (or rowcount for updates)."""
        cursor = await self.conn.execute(sql, params)
        await self.conn.commit()
        return cursor.lastrowid if sql.lstrip().upper().startswith("INSERT") else cursor.rowcount

    async def fetchall(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        async with self.conn.execute(sql, params) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def fetchone(self, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
        async with self.conn.execute(sql, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    # --- sessions -------------------------------------------------------

    async def get_session(self, chat_id: int, provider: str | None = None) -> str | None:
        """The chat's session id; with provider, only if it was made on that provider.

        Sessions written before providers were tracked (provider NULL) came from Anthropic.
        """
        row = await self.fetchone(
            "SELECT session_id, provider FROM chat_sessions WHERE chat_id = ?", (chat_id,)
        )
        if not row:
            return None
        if provider is not None and (row["provider"] or "anthropic") != provider:
            return None
        return row["session_id"]

    async def set_session(self, chat_id: int, session_id: str, provider: str | None = None) -> None:
        await self.execute(
            "INSERT INTO chat_sessions (chat_id, session_id, updated_at, provider) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET session_id = excluded.session_id, "
            "updated_at = excluded.updated_at, provider = excluded.provider",
            (chat_id, session_id, utcnow_iso(), provider),
        )

    # --- per-chat settings ---------------------------------------------

    async def get_chat_model(self, chat_id: int) -> str | None:
        row = await self.fetchone("SELECT model FROM chat_settings WHERE chat_id = ?", (chat_id,))
        return row["model"] if row else None

    async def set_chat_model(self, chat_id: int, model: str | None) -> None:
        await self.execute(
            "INSERT INTO chat_settings (chat_id, model, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET model = excluded.model, updated_at = excluded.updated_at",
            (chat_id, model, utcnow_iso()),
        )

    async def clear_session(self, chat_id: int) -> None:
        await self.execute("DELETE FROM chat_sessions WHERE chat_id = ?", (chat_id,))

    # --- usage ----------------------------------------------------------

    async def add_usage(
        self,
        chat_id: int,
        cost_usd: float,
        turns: int,
        model: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        await self.execute(
            "INSERT INTO usage (chat_id, ts, cost_usd, turns, model, input_tokens, output_tokens) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (chat_id, utcnow_iso(), cost_usd, turns, model, input_tokens, output_tokens),
        )

    async def usage_by_model(self, since_iso_utc: str) -> list[dict[str, Any]]:
        return await self.fetchall(
            "SELECT COALESCE(model, '?') AS model, SUM(cost_usd) AS cost, COUNT(*) AS turns, "
            "SUM(COALESCE(input_tokens, 0)) AS input_tokens, SUM(COALESCE(output_tokens, 0)) AS output_tokens "
            "FROM usage WHERE ts >= ? GROUP BY COALESCE(model, '?') ORDER BY cost DESC",
            (since_iso_utc,),
        )

    async def cost_since(self, since_iso_utc: str) -> float:
        row = await self.fetchone(
            "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM usage WHERE ts >= ?",
            (since_iso_utc,),
        )
        return float(row["total"]) if row else 0.0
