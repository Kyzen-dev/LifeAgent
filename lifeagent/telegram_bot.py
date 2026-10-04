"""Telegram front-end: messages, files, voice, commands and button callbacks."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from contextlib import suppress
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from typing import Any

from telegram import BotCommand, Message, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import jalali, prompts
from .agent import AgentPool
from .approvals import ApprovalManager
from .context import AppContext
from .formatting import md_to_html, split_markdown
from .prompts import SKIP
from .scheduler import Scheduler, log_habit
from .voice import transcribe
from .workspace import ensure_workspace

log = logging.getLogger(__name__)

COMMANDS = [
    ("brief", "گزارش صبحگاهی همین حالا"),
    ("review", "بازبینی هفتگی همین حالا"),
    ("new", "شروع گفتگوی تازه (حافظه بلندمدت می‌ماند)"),
    ("stop", "توقف کار در حال اجرا"),
    ("cost", "هزینه مصرف API"),
    ("help", "راهنما"),
]

HELP_TEXT = """\
سلام! من دستیار شخصی‌ات هستم 👋

هر چیزی را عادی بنویس یا ویس بفرست، مثلاً:
• «شروع کار روی پروژه چت‌بات» / «تموم کردم» → ثبت ساعت کار
• «این هفته چند ساعت کار کردم و چقدر درآوردم؟» / «برای این پروژه پروپوزال بنویس»
• «۲۵۰ تومن ناهار دادم»  → ثبت هزینه
• «فردا ساعت ۱۰ یادم بنداز به علی زنگ بزنم»
• «امروز ۳۰ دقیقه دویدم» / «وزنم ۷۸ شد»
• «ایمیل‌های مهم امروز چیه؟» / «برنامه این هفته‌ام؟»
• «PRهای باز ریپوی X رو بررسی کن»
• «درباره Rust async تحقیق کن و خلاصه‌اش رو برام بنویس»
• «امروز رو تایم‌بلاک کن» / «این ایده رو بکوب» / «بین این دو پیشنهاد کاری کدوم؟»
• «گزارش هزینه‌ها رو اکسل کن» / «هوای فردا؟» / «قیمت تتر؟» / «این ویدیو یوتیوب رو خلاصه کن»
• عکس رسید، جواب آزمایش، PDF یا اسکرین‌شات بفرست تا تحلیل/ثبت کنم.

کارهایی که بیرون از سیستم اثر دارند (ارسال ایمیل، تغییر تقویم، GitHub، اجرای دستور)
فقط با زدن دکمه «✅ تأیید» انجام می‌شوند.

دستورها: /brief /review /new /stop /cost /help"""

TOOL_LABELS: list[tuple[str, str]] = [
    ("mcp__life__finance", "💰 امور مالی"),
    ("mcp__life__habit", "🌱 عادت‌ها"),
    ("mcp__life__health", "❤️ سلامت"),
    ("mcp__life__journal", "📓 ژورنال"),
    ("mcp__life__task", "📋 کارها"),
    ("mcp__life__goal", "🎯 اهداف"),
    ("mcp__life__reminder", "⏰ یادآورها"),
    ("mcp__life__client", "🤝 مشتری‌ها"),
    ("mcp__life__project", "💼 پروژه‌ها"),
    ("mcp__life__timer", "⏱ ثبت زمان کار"),
    ("mcp__life__time_", "⏱ ثبت زمان کار"),
    ("mcp__life__prayer", "🕌 اوقات شرعی"),
    ("mcp__life__send_file", "📤 ارسال فایل"),
    ("mcp__google__", "🔵 Google"),
    ("mcp__github__", "🐙 GitHub"),
    ("mcp__context7__", "📚 مستندات کتابخانه"),
    ("mcp__browser__", "🧭 مرورگر"),
    ("mcp__life__weather", "🌤 آب‌وهوا"),
    ("mcp__life__market", "📈 قیمت‌ها"),
    ("mcp__life__youtube", "▶️ YouTube"),
    ("WebSearch", "🔎 جستجو در وب"),
    ("WebFetch", "🌐 خواندن صفحه وب"),
    ("Read", "📄 خواندن فایل"),
    ("Grep", "🗂 جستجو در یادداشت‌ها"),
    ("Glob", "🗂 جستجو در یادداشت‌ها"),
    ("Write", "✍️ نوشتن یادداشت"),
    ("Edit", "✍️ به‌روزرسانی یادداشت"),
    ("Bash", "💻 اجرای دستور"),
    ("Task", "🤝 سپردن به زیرعامل"),
    ("Agent", "🤝 سپردن به زیرعامل"),
    ("Skill", "🧩 استفاده از مهارت"),
]
GOOGLE_HINTS = {"gmail": "📧 Gmail", "calendar": "📅 تقویم", "event": "📅 تقویم", "drive": "📁 Drive",
                "doc": "📝 Docs", "sheet": "📊 Sheets", "task": "✅ Google Tasks"}


def tool_label(name: str) -> str | None:
    if name.startswith("mcp__google__"):
        action = name.split("__", 2)[2]
        for hint, label in GOOGLE_HINTS.items():
            if hint in action:
                return label
    for prefix, label in TOOL_LABELS:
        if name.startswith(prefix):
            return label
    return None


# --- sending -----------------------------------------------------------------


async def send_markdown(bot: Any, chat_id: int, text: str) -> None:
    for chunk in split_markdown(text):
        if not chunk.strip():
            continue
        try:
            await bot.send_message(chat_id, md_to_html(chunk), parse_mode=ParseMode.HTML,
                                   disable_web_page_preview=True)
        except BadRequest:
            log.warning("HTML send failed, falling back to plain text", exc_info=True)
            await bot.send_message(chat_id, chunk, disable_web_page_preview=True)


class Progress:
    """A single status message listing what the agent is doing, deleted at the end."""

    def __init__(self, bot: Any, chat_id: int):
        self.bot, self.chat_id = bot, chat_id
        self.steps: list[str] = []
        self.message: Message | None = None
        self._last_edit = 0.0

    async def on_tool(self, name: str, _input: dict[str, Any]) -> None:
        label = tool_label(name)
        if not label or (self.steps and self.steps[-1] == label):
            return
        self.steps.append(label)
        text = "⏳ در حال کار...\n" + "\n".join(self.steps[-8:])
        if self.message is None:
            self.message = await self.bot.send_message(self.chat_id, text)
        elif time.monotonic() - self._last_edit > 1.5:
            with suppress(BadRequest):
                await self.message.edit_text(text)
        self._last_edit = time.monotonic()

    async def close(self) -> None:
        if self.message is not None:
            with suppress(Exception):
                await self.message.delete()


async def _keep_typing(bot: Any, chat_id: int) -> None:
    while True:
        with suppress(Exception):
            await bot.send_chat_action(chat_id, ChatAction.TYPING)
        await asyncio.sleep(4.5)


async def run_turn(app: AppContext, chat_id: int, prompt: str, routine: bool = False) -> None:
    """Send one user turn to the agent and deliver its reply to the chat.

    Routine turns may answer with just SKIP when there is nothing worth sending.
    """
    bot = app.bot
    agent = app.agents.get(chat_id)
    if agent.lock.locked() and not routine:
        await bot.send_message(chat_id, "📥 در صف؛ بعد از تمام شدن کار فعلی بررسی می‌کنم.")

    progress = Progress(bot, chat_id)
    typing = asyncio.create_task(_keep_typing(bot, chat_id))
    try:
        reply = await agent.ask(f"{jalali.time_context(app.now())}\n{prompt}", on_tool=progress.on_tool)
    except Exception as exc:  # noqa: BLE001
        log.exception("agent turn failed")
        await bot.send_message(chat_id, f"❌ خطا: {type(exc).__name__}: {exc}"[:1000])
        return
    finally:
        typing.cancel()
        await progress.close()

    if routine and reply.text.strip().strip("[]`*").upper() == SKIP:
        log.info("routine had nothing to report")
        return
    await send_markdown(bot, chat_id, reply.text)
    await _budget_warning(app, chat_id)


async def _budget_warning(app: AppContext, chat_id: int) -> None:
    budget = app.settings.daily_budget_usd
    if not budget:
        return
    start_of_day = datetime.combine(app.now().date(), dtime.min, tzinfo=app.settings.tz)
    spent = await app.db.cost_since(start_of_day.astimezone(timezone.utc).isoformat(timespec="seconds"))
    if spent >= budget and not app.extra.get(f"budget_warned:{start_of_day.date()}"):
        app.extra[f"budget_warned:{start_of_day.date()}"] = True
        await app.bot.send_message(chat_id, f"⚠️ هزینه امروز به ${spent:.2f} رسید (سقف: ${budget:.2f}).")


# --- inbound files -----------------------------------------------------------

_SAFE_NAME_RE = re.compile(r"[^\w.\-]+", re.U)


def _inbox_path(app: AppContext, filename: str) -> Path:
    inbox = app.settings.workspace_dir / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    name = _SAFE_NAME_RE.sub("_", Path(filename).name).strip("._") or "file"
    return inbox / f"{app.now():%Y%m%d-%H%M%S}-{name}"


def _quoted_context(message: Message) -> str:
    quoted = message.reply_to_message
    if quoted is None:
        return ""
    body = quoted.text or quoted.caption or ""
    return f"\n[در پاسخ به این پیام: «{body[:1500]}»]" if body else ""


# --- handlers ----------------------------------------------------------------


def _app(context: ContextTypes.DEFAULT_TYPE) -> AppContext:
    return context.application.bot_data["app"]


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    await run_turn(_app(context), update.effective_chat.id, message.text + _quoted_context(message))


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app, message = _app(context), update.effective_message
    photo = message.photo[-1]  # largest size
    path = _inbox_path(app, f"photo-{photo.file_unique_id}.jpg")
    await (await photo.get_file()).download_to_drive(path)
    caption = message.caption or (
        "این تصویر را بررسی کن. اگر رسید/فاکتور/صورت‌حساب است، اقلام و مبلغ را استخراج و "
        "طبق skill receipt-scan ثبت کن؛ در غیر این صورت بگو چه می‌بینی و چه کمکی می‌توانم بکنم."
    )
    rel = path.relative_to(app.settings.workspace_dir)
    await run_turn(app, update.effective_chat.id, f"{caption}\n[پیوست: تصویر در {rel}]" + _quoted_context(message))


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app, message = _app(context), update.effective_message
    doc = message.document
    if doc.file_size and doc.file_size > 20 * 1024 * 1024:
        await message.reply_text("حجم فایل بیشتر از ۲۰ مگابایت است و تلگرام اجازه دریافتش را به ربات نمی‌دهد.")
        return
    path = _inbox_path(app, doc.file_name or "file")
    await (await doc.get_file()).download_to_drive(path)
    caption = message.caption or "این فایل را بررسی کن، خلاصه‌اش را بگو و اگر کاری لازم است پیشنهاد بده."
    rel = path.relative_to(app.settings.workspace_dir)
    await run_turn(app, update.effective_chat.id, f"{caption}\n[پیوست: فایل در {rel}]" + _quoted_context(message))


async def on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app, message = _app(context), update.effective_message
    if not app.settings.openai_api_key:
        await message.reply_text("پیام صوتی فعال نیست: OPENAI_API_KEY را در .env تنظیم کن.")
        return
    media = message.voice or message.audio
    data = bytes(await (await media.get_file()).download_as_bytearray())
    filename = "voice.ogg" if message.voice else (message.audio.file_name or "audio.mp3")
    try:
        text = await transcribe(
            data, filename, app.settings.openai_api_key, app.settings.transcribe_model,
            app.settings.transcribe_language,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("transcription failed")
        await message.reply_text(f"❌ تبدیل گفتار به متن ناموفق بود: {exc}"[:500])
        return
    if not text:
        await message.reply_text("صدایی تشخیص داده نشد.")
        return
    await message.reply_text(f"🎙️ {text}")
    await run_turn(app, update.effective_chat.id, f"(پیام صوتی) {text}" + _quoted_context(message))


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_TEXT)


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(f"user id: {update.effective_user.id}")


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _app(context).agents.get(update.effective_chat.id).reset()
    await update.effective_message.reply_text("🆕 گفتگوی تازه شروع شد. حافظه بلندمدت و داده‌هایت سر جایش است.")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app = _app(context)
    app.approvals.cancel_all()
    stopped = await app.agents.get(update.effective_chat.id).interrupt()
    await update.effective_message.reply_text("⏹ متوقف شد." if stopped else "کاری در حال اجرا نیست.")


async def cmd_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app = _app(context)
    now = app.now()
    today = datetime.combine(now.date(), dtime.min, tzinfo=app.settings.tz)
    year, month = jalali.current_jalali_month(now.date())
    month_start, _ = jalali.jalali_month_range(year, month)
    month_start_dt = datetime.combine(month_start, dtime.min, tzinfo=app.settings.tz)
    spent_today = await app.db.cost_since(today.astimezone(timezone.utc).isoformat(timespec="seconds"))
    spent_month = await app.db.cost_since(month_start_dt.astimezone(timezone.utc).isoformat(timespec="seconds"))
    await update.effective_message.reply_text(
        f"💵 هزینه تقریبی API\nامروز: ${spent_today:.2f}\nاین ماه ({year}/{month:02d}): ${spent_month:.2f}"
    )


async def cmd_brief(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_turn(_app(context), update.effective_chat.id, prompts.MORNING_BRIEF.replace("[روال خودکار] ", ""))


async def cmd_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_turn(_app(context), update.effective_chat.id, prompts.WEEKLY_REVIEW.replace("[روال خودکار] ", ""))


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app, query = _app(context), update.callback_query
    if query.from_user.id not in app.settings.allowed_user_ids:
        await query.answer()
        return
    parts = (query.data or "").split(":")

    if parts[0] == "appr" and len(parts) == 3:
        found = app.approvals.resolve(parts[1], parts[2])
        await query.answer("ثبت شد" if found else "این درخواست منقضی شده است")
        return

    if parts[0] == "prayer" and len(parts) == 3 and parts[1] == "done":
        await log_habit(app, "نماز")
        await query.answer("قبول باشد 🤲")
        with suppress(BadRequest):
            await query.edit_message_text((query.message.text or "") + "\n\n✅ ثبت شد", reply_markup=None)
        return

    if parts[0] == "rem" and len(parts) == 3:
        action, reminder_id = parts[1], int(parts[2])
        if action == "done":
            await query.answer("👍")
            suffix = "\n\n✅ انجام شد"
        else:
            minutes = 10 if action == "snooze10" else 60
            await app.scheduler.snooze(reminder_id, minutes)
            await query.answer(f"{minutes} دقیقه دیگر یادآوری می‌کنم")
            suffix = f"\n\n⏰ به تعویق افتاد ({minutes} دقیقه)"
        with suppress(BadRequest):
            await query.edit_message_text((query.message.text or "") + suffix, reply_markup=None)
        return

    await query.answer()


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("unhandled telegram error", exc_info=context.error)


# --- wiring ------------------------------------------------------------------


def build_application(app: AppContext) -> Application:
    s = app.settings

    async def post_init(application: Application) -> None:
        ensure_workspace(s)
        await app.db.connect()
        app.bot = application.bot
        app.approvals = ApprovalManager(application.bot, s.approval_timeout_s)
        app.agents = AgentPool(app)
        app.scheduler = Scheduler(app, lambda chat_id, prompt: run_turn(app, chat_id, prompt, routine=True))
        await app.scheduler.start()
        await application.bot.set_my_commands([BotCommand(c, d) for c, d in COMMANDS])
        log.info("LifeAgent is up (model=%s)", s.model)

    async def post_shutdown(application: Application) -> None:
        if app.scheduler:
            app.scheduler.shutdown()
        if app.agents:
            await app.agents.close_all()
        await app.db.close()

    application = (
        ApplicationBuilder()
        .token(s.telegram_token)
        # Needed so approval button taps are handled while an agent turn is awaiting them.
        .concurrent_updates(True)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.bot_data["app"] = app

    owner = filters.User(user_id=list(s.allowed_user_ids))
    application.add_handler(CommandHandler("id", cmd_id))
    application.add_handler(CommandHandler(["start", "help"], cmd_start, filters=owner))
    application.add_handler(CommandHandler("new", cmd_new, filters=owner))
    application.add_handler(CommandHandler("stop", cmd_stop, filters=owner))
    application.add_handler(CommandHandler("cost", cmd_cost, filters=owner))
    application.add_handler(CommandHandler("brief", cmd_brief, filters=owner))
    application.add_handler(CommandHandler("review", cmd_review, filters=owner))
    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(MessageHandler(owner & filters.TEXT & ~filters.COMMAND, on_text))
    application.add_handler(MessageHandler(owner & filters.PHOTO, on_photo))
    application.add_handler(MessageHandler(owner & filters.Document.ALL, on_document))
    application.add_handler(MessageHandler(owner & (filters.VOICE | filters.AUDIO), on_voice))
    application.add_error_handler(on_error)
    return application

