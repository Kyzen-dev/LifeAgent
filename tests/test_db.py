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

    monkeypatch.setattr(db_module, "MIGRATIONS", {2: ["ALTER TABLE tasks ADD COLUMN estimate_min INTEGER"]})
    monkeypatch.setattr(db_module, "SCHEMA_VERSION", 2)
    for _ in range(2):  # second connect must not re-run the ALTER
        again = Database(path)
        await again.connect()
        await again.close()

    async with aiosqlite.connect(path) as conn:
        cols = [r[1] for r in await (await conn.execute("PRAGMA table_info(tasks)")).fetchall()]
        version = (await (await conn.execute("PRAGMA user_version")).fetchone())[0]
    assert "estimate_min" in cols and version == 2
