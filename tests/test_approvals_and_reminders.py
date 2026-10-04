import asyncio
import json
from datetime import datetime, timedelta

from lifeagent.approvals import ApprovalManager
from lifeagent.scheduler import Scheduler
from lifeagent.tools import reminders


class FakeMessage:
    def __init__(self, text, reply_markup=None):
        self.text, self.reply_markup = text, reply_markup

    async def edit_text(self, text, **kwargs):
        self.text = text


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kwargs):
        msg = FakeMessage(text, kwargs.get("reply_markup"))
        self.sent.append(msg)
        return msg


async def test_approval_resolves_from_button():
    bot = FakeBot()
    manager = ApprovalManager(bot, timeout_s=5)
    task = asyncio.create_task(manager.ask(42, "gmail → send_gmail_message", "to: a@b.c"))
    await asyncio.sleep(0.01)
    data = bot.sent[0].reply_markup.inline_keyboard[0][0].callback_data
    _, approval_id, _ = data.split(":")
    assert manager.resolve(approval_id, True)
    assert await task is True
    assert "تأیید شد" in bot.sent[0].text
    assert not manager.resolve(approval_id, True)  # already handled


async def test_approval_times_out_as_deny():
    manager = ApprovalManager(FakeBot(), timeout_s=0.05)
    assert await manager.ask(42, "x", "y") is False


async def test_reminder_tool_schedules_and_fires(tool_ctx):
    bot = FakeBot()
    tool_ctx.app.bot = bot
    sched = Scheduler(tool_ctx.app, run_prompt=lambda *_: None)
    tool_ctx.app.scheduler = sched
    sched.sched.start()
    try:
        t = {x.name: x.handler for x in reminders.build(tool_ctx)}
        when = (tool_ctx.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        res = json.loads((await t["reminder_add"]({"text": "زنگ به علی", "at": when}))["content"][0]["text"])
        assert res["next_run"]
        listed = json.loads((await t["reminder_list"]({}))["content"][0]["text"])
        assert listed[0]["text"] == "زنگ به علی"

        weekly = await t["reminder_add"]({"text": "ورزش", "at": when, "repeat": "weekly", "days": "sat,mon"})
        assert not weekly.get("is_error")
        assert (await t["reminder_add"]({"text": "x", "at": when, "repeat": "weekly", "days": "funday"}))["is_error"]
        assert (await t["reminder_add"]({"text": "x", "at": "2000-01-01 10:00"}))["is_error"]

        await sched._fire_reminder(res["id"])
        assert "زنگ به علی" in bot.sent[-1].text
        row = await tool_ctx.db.fetchone("SELECT active FROM reminders WHERE id = ?", (res["id"],))
        assert row["active"] == 0

        await t["reminder_cancel"]({"id": res["id"]})
        assert sched.next_run(res["id"]) is None
    finally:
        sched.shutdown()


def test_now_is_aware(tool_ctx):
    assert isinstance(tool_ctx.now(), datetime) and tool_ctx.now().tzinfo is not None
