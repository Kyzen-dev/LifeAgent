from datetime import datetime, timedelta

from lifeagent import prompts, scheduler as scheduler_mod
from lifeagent.agent import AgentReply
from lifeagent.scheduler import Scheduler, log_habit
from lifeagent.telegram_bot import run_turn


class FakeBot:
    def __init__(self):
        self.sent = []
        self.markups = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append(text)
        self.markups.append(kwargs.get("reply_markup"))

    async def send_chat_action(self, *args, **kwargs):
        pass


class FakeAgent:
    def __init__(self, text):
        self.text = text
        import asyncio
        self.lock = asyncio.Lock()
        self.prompts = []

    async def ask(self, prompt, on_tool=None, on_notice=None):
        self.prompts.append(prompt)
        return AgentReply(text=self.text)


class FakePool:
    def __init__(self, agent):
        self.agent = agent

    def get(self, chat_id):
        return self.agent


async def test_routine_skip_sends_nothing(tool_ctx):
    app = tool_ctx.app
    app.bot = FakeBot()
    app.agents = FakePool(FakeAgent(" SKIP "))
    await run_turn(app, 42, prompts.MIDDAY_CHECKIN, routine=True)
    assert app.bot.sent == []

    app.agents = FakePool(FakeAgent("⏱ امروز هنوز کاری ثبت نشده"))
    await run_turn(app, 42, prompts.MIDDAY_CHECKIN, routine=True)
    assert app.bot.sent and "امروز" in app.bot.sent[-1]

    # A user message that literally says SKIP is still answered.
    app.bot.sent.clear()
    app.agents = FakePool(FakeAgent("SKIP"))
    await run_turn(app, 42, "SKIP", routine=False)
    assert app.bot.sent


async def test_prayer_reminders_scheduled(tool_ctx, monkeypatch):
    app = tool_ctx.app
    now = datetime.now(app.settings.tz)
    later = (now + timedelta(hours=1)).strftime("%H:%M")
    earlier = (now - timedelta(hours=1)).strftime("%H:%M")

    async def fake_fetch(day, city, country, method):
        return {"fajr": earlier, "dhuhr": later, "maghrib": later, "isha": later}

    monkeypatch.setattr(scheduler_mod, "fetch_prayer_times", fake_fetch)
    sched = Scheduler(app, run_prompt=lambda *_: None)
    sched.sched.start()
    try:
        await sched.schedule_prayers()
        ids = {job.id for job in sched.sched.get_jobs()}
        assert "prayer:dhuhr" in ids and "prayer:maghrib" in ids
        assert "prayer:fajr" not in ids  # already passed
        assert "prayer:isha" not in ids  # not in the configured list
    finally:
        sched.shutdown()


async def test_prayer_fetch_failure_retries(tool_ctx, monkeypatch):
    async def broken(*args):
        raise OSError("network down")

    monkeypatch.setattr(scheduler_mod, "fetch_prayer_times", broken)
    sched = Scheduler(tool_ctx.app, run_prompt=lambda *_: None)
    sched.sched.start()
    try:
        await sched.schedule_prayers()
        assert sched.sched.get_job("routine:prayers-retry") is not None
    finally:
        sched.shutdown()


async def test_log_habit_creates_and_logs(tool_ctx):
    await log_habit(tool_ctx.app, "نماز")
    await log_habit(tool_ctx.app, "نماز")
    rows = await tool_ctx.db.fetchall(
        "SELECT h.name, COUNT(l.id) AS n FROM habits h JOIN habit_logs l ON l.habit_id = h.id GROUP BY h.id"
    )
    assert rows == [{"name": "نماز", "n": 2}]


async def test_doctor_reports_missing_config(monkeypatch, capsys):
    from lifeagent import doctor

    monkeypatch.setattr(doctor, "load_dotenv", lambda: None)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert await doctor.run(live=False) == 1
    assert "TELEGRAM_BOT_TOKEN" in capsys.readouterr().out
