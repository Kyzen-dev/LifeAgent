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
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id   INTEGER NOT NULL,
    ts        TEXT NOT NULL,
    cost_usd  REAL NOT NULL,
    turns     INTEGER NOT NULL
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
    created_at TEXT NOT NULL
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
                CHECK (status IN ('lead', 'proposal', 'active', 'paused', 'done', 'lost')),
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
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

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

    async def get_session(self, chat_id: int) -> str | None:
        row = await self.fetchone(
            "SELECT session_id FROM chat_sessions WHERE chat_id = ?", (chat_id,)
        )
        return row["session_id"] if row else None

    async def set_session(self, chat_id: int, session_id: str) -> None:
        await self.execute(
            "INSERT INTO chat_sessions (chat_id, session_id, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET session_id = excluded.session_id, "
            "updated_at = excluded.updated_at",
            (chat_id, session_id, utcnow_iso()),
        )

    async def clear_session(self, chat_id: int) -> None:
        await self.execute("DELETE FROM chat_sessions WHERE chat_id = ?", (chat_id,))

    # --- usage ----------------------------------------------------------

    async def add_usage(self, chat_id: int, cost_usd: float, turns: int) -> None:
        await self.execute(
            "INSERT INTO usage (chat_id, ts, cost_usd, turns) VALUES (?, ?, ?, ?)",
            (chat_id, utcnow_iso(), cost_usd, turns),
        )

    async def cost_since(self, since_iso_utc: str) -> float:
        row = await self.fetchone(
            "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM usage WHERE ts >= ?",
            (since_iso_utc,),
        )
        return float(row["total"]) if row else 0.0
