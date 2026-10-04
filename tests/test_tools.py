import json

from lifeagent.tools import finance, planning, wellbeing


def _tools(module, ctx):
    return {t.name: t.handler for t in module.build(ctx)}


def _data(result):
    assert not result.get("is_error"), result
    return json.loads(result["content"][0]["text"])


async def test_finance_flow(tool_ctx):
    t = _tools(finance, tool_ctx)
    _data(await t["finance_add_transaction"]({"kind": "expense", "amount": 250000, "category": "خوراک", "date": "1405/07/12"}))
    _data(await t["finance_add_transaction"]({"kind": "income", "amount": 50000000, "category": "حقوق", "date": "1405/07/01"}))
    _data(await t["finance_set_budget"]({"category": "خوراک", "monthly_limit": 1000000}))
    summary = _data(await t["finance_summary"]({"jalali_year": 1405, "jalali_month": 7}))
    assert summary["expenses_by_category"][0]["total"] == 250000
    assert summary["budgets"][0]["used_percent"] == 25
    rows = _data(await t["finance_list_transactions"]({"kind": "expense"}))
    assert rows[0]["date_jalali"] == "1405/07/12"
    bad = await t["finance_add_transaction"]({"kind": "expense", "amount": 1, "category": "x", "date": "bad"})
    assert bad["is_error"]


async def test_habits_and_tasks(tool_ctx):
    w = _tools(wellbeing, tool_ctx)
    _data(await w["habit_create"]({"name": "ورزش", "target_per_week": 4}))
    _data(await w["habit_log"]({"name": "ورزش"}))
    status = _data(await w["habit_status"]({}))
    assert status[0]["done_today"] and status[0]["streak_days"] == 1
    missing = await w["habit_log"]({"name": "نامعلوم"})
    assert missing["is_error"]

    p = _tools(planning, tool_ctx)
    task = _data(await p["task_add"]({"title": "deploy", "due": "2000-01-01", "priority": 1}))
    overdue = _data(await p["task_list"]({"overdue_only": True}))
    assert [r["id"] for r in overdue] == [task["id"]]
    _data(await p["task_update"]({"id": task["id"], "status": "done"}))
    assert _data(await p["task_list"]({})) == []

    goal = _data(await p["goal_set"]({"title": "یادگیری Rust", "area": "learning", "target_date": "1405/12/29"}))
    _data(await p["goal_set"]({"id": goal["id"], "progress": 30}))
    goals = _data(await p["goal_list"]({}))
    assert goals[0]["progress"] == 30 and goals[0]["target_date_jalali"] == "1405/12/29"
