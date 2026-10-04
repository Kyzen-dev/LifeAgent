import json
from datetime import datetime, timedelta

from lifeagent.tools import freelance


def _data(result):
    assert not result.get("is_error"), result
    return json.loads(result["content"][0]["text"])


async def test_client_project_pipeline(tool_ctx):
    t = {x.name: x.handler for x in freelance.build(tool_ctx)}
    _data(await t["client_upsert"]({"name": "Acme", "currency": "usd", "default_rate": 40, "source": "linkedin"}))
    created = _data(await t["project_upsert"]({"client": "Acme", "title": "Support agent", "status": "proposal",
                                                "estimate_hours": 30, "deadline": "2000-01-05",
                                                "next_action": "follow-up", "next_action_date": "2000-01-01"}))
    rows = _data(await t["project_list"]({}))
    assert rows[0]["client"] == "Acme" and rows[0]["currency"] == "USD" and rows[0]["rate"] == 40
    assert rows[0]["follow_up_due"] is True and rows[0]["days_left"] < 0
    _data(await t["project_upsert"]({"id": created["id"], "status": "active"}))
    assert _data(await t["project_list"]({"status": "active"}))[0]["title"] == "Support agent"
    assert (await t["project_upsert"]({"title": ""}))["is_error"]
    clients = _data(await t["client_list"]({}))
    assert clients[0]["open_projects"] == 1


async def test_timer_and_report(tool_ctx):
    t = {x.name: x.handler for x in freelance.build(tool_ctx)}
    _data(await t["project_upsert"]({"title": "Shop bot", "billing": "hourly", "rate": 800000}))
    _data(await t["project_upsert"]({"title": "RAG audit", "billing": "fixed", "rate": 20000000}))

    started = _data(await t["timer_start"]({"project": "shop"}))
    assert started["started"] == "Shop bot" and started["stopped_previous"] is None
    # Pretend the timer started 90 minutes ago.
    start = (tool_ctx.now() - timedelta(minutes=90)).isoformat(timespec="seconds")
    await tool_ctx.db.execute("UPDATE time_entries SET start = ? WHERE end IS NULL", (start,))
    status = _data(await t["timer_status"]({}))
    assert status["running"]["project"] == "Shop bot" and 89 <= status["running"]["elapsed_minutes"] <= 91

    # Starting another project stops the first one.
    switched = _data(await t["timer_start"]({"project": "RAG"}))
    assert switched["stopped_previous"]["project"] == "Shop bot"
    stopped = _data(await t["timer_stop"]({"note": "reviewed retriever"}))
    assert stopped["project"] == "RAG audit"
    assert (await t["timer_stop"]({}))["is_error"]  # nothing running

    _data(await t["time_log"]({"project": "Shop bot", "minutes": 30}))
    report = _data(await t["time_report"]({}))
    shop = report["projects"]["Shop bot"]
    assert shop["hours"] == 2.0 and shop["earned_estimate"] == 1600000
    assert "earned_estimate" not in report["projects"]["RAG audit"]
    assert (await t["time_log"]({"project": "nope", "minutes": 10}))["is_error"]
    assert (await t["time_log"]({"project": "Shop bot", "minutes": 0}))["is_error"]


def test_entry_times_are_aware(tool_ctx):
    assert datetime.fromisoformat(tool_ctx.now().isoformat()).tzinfo is not None
