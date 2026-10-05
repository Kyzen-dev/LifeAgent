import aiosqlite

from lifeagent import db as db_module
from lifeagent.db import Database


async def test_fresh_install_sets_version(tmp_path):
    database = Database(tmp_path / "a.sqlite3")
    await database.connect()
    row = await database.fetchone("PRAGMA user_version")
    assert list(row.values())[0] == db_module.SCHEMA_VERSION
    await database.close()


async def test_migrations_apply_once_to_existing_db(tmp_path, monkeypatch):
    path = tmp_path / "b.sqlite3"
    first = Database(path)
    await first.connect()  # version 1
    await first.close()

    target = db_module.SCHEMA_VERSION + 1
    monkeypatch.setattr(db_module, "MIGRATIONS", {target: ["ALTER TABLE tasks ADD COLUMN estimate_min INTEGER"]})
    monkeypatch.setattr(db_module, "SCHEMA_VERSION", target)
    for _ in range(2):  # second connect must not re-run the ALTER
        again = Database(path)
        await again.connect()
        await again.close()

    async with aiosqlite.connect(path) as conn:
        cols = [r[1] for r in await (await conn.execute("PRAGMA table_info(tasks)")).fetchall()]
        version = (await (await conn.execute("PRAGMA user_version")).fetchone())[0]
    assert "estimate_min" in cols and version == target


V1_TABLES = """
CREATE TABLE chat_sessions (chat_id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE usage (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL, ts TEXT NOT NULL,
                    cost_usd REAL NOT NULL, turns INTEGER NOT NULL);
CREATE TABLE transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, kind TEXT NOT NULL,
                           amount REAL NOT NULL, currency TEXT NOT NULL DEFAULT 'IRT', category TEXT NOT NULL,
                           account TEXT, note TEXT, created_at TEXT NOT NULL);
INSERT INTO chat_sessions VALUES (42, 'old-session', '2026-01-01');
INSERT INTO transactions (date, kind, amount, category, created_at) VALUES ('2026-01-01', 'expense', 5, 'x', 'now');
PRAGMA user_version = 1;
"""


async def test_version_1_database_is_upgraded(tmp_path):
    path = tmp_path / "v1.sqlite3"
    async with aiosqlite.connect(path) as conn:
        await conn.executescript(V1_TABLES)
        await conn.commit()

    database = Database(path)
    await database.connect()
    tx_cols = {r["name"] for r in await database.fetchall("PRAGMA table_info(transactions)")}
    assert {"merchant", "items", "source", "attachment", "original_amount"} <= tx_cols
    # the old session predates provider tracking and counts as Anthropic
    assert await database.get_session(42, "anthropic") == "old-session"
    assert await database.get_session(42, "openrouter") is None
    await database.set_chat_model(42, "opus")
    assert await database.get_chat_model(42) == "opus"
    await database.add_usage(42, 0.01, 1, "opus", 100, 20)
    rows = await database.usage_by_model("2000-01-01")
    assert rows[0]["model"] == "opus" and rows[0]["input_tokens"] == 100
    await database.close()
