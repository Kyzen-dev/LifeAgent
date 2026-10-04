"""Ask the user in Telegram before a side-effecting tool call runs."""

from __future__ import annotations

import asyncio
import html
import logging
import secrets
from typing import Literal

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

log = logging.getLogger(__name__)

MAX_DETAILS = 3000

Verdict = Literal["once", "trust", "deny"]
VERDICT_TEXT = {"once": "✅ تأیید شد", "trust": "✅ تأیید شد (موقتاً مورد اعتماد)", "deny": "❌ رد شد"}


class ApprovalManager:
    def __init__(self, bot: Bot, timeout_s: int):
        self.bot = bot
        self.timeout_s = timeout_s
        self._pending: dict[str, asyncio.Future[Verdict]] = {}

    async def ask(self, chat_id: int, title: str, details: str, trust_minutes: int | None = None) -> Verdict:
        """Show the request with buttons; trust_minutes adds an "allow for N minutes" button."""
        approval_id = secrets.token_hex(6)
        future: asyncio.Future[Verdict] = asyncio.get_running_loop().create_future()
        self._pending[approval_id] = future

        if len(details) > MAX_DETAILS:
            details = details[:MAX_DETAILS] + "\n…"
        text = (
            f"🔐 <b>نیاز به تأیید</b>\n<b>{html.escape(title)}</b>\n\n"
            f"<pre>{html.escape(details)}</pre>"
        )
        rows = [[
            InlineKeyboardButton("✅ تأیید", callback_data=f"appr:{approval_id}:once"),
            InlineKeyboardButton("❌ رد", callback_data=f"appr:{approval_id}:deny"),
        ]]
        if trust_minutes:
            rows.append([InlineKeyboardButton(
                f"✅ تأیید موارد مشابه تا {trust_minutes} دقیقه", callback_data=f"appr:{approval_id}:trust"
            )])
        keyboard = InlineKeyboardMarkup(rows)
        message = await self.bot.send_message(
            chat_id, text, parse_mode=ParseMode.HTML, reply_markup=keyboard
        )

        try:
            verdict: Verdict = await asyncio.wait_for(future, timeout=self.timeout_s)
            label = VERDICT_TEXT[verdict]
        except asyncio.TimeoutError:
            verdict, label = "deny", "⌛ بدون پاسخ ماند و رد شد"
        finally:
            self._pending.pop(approval_id, None)

        try:
            await message.edit_text(
                f"{text}\n\n{label}", parse_mode=ParseMode.HTML, reply_markup=None
            )
        except Exception:  # noqa: BLE001 - cosmetic only
            log.debug("could not edit approval message", exc_info=True)
        return verdict

    def resolve(self, approval_id: str, verdict: str) -> bool:
        future = self._pending.get(approval_id)
        if future is None or future.done() or verdict not in VERDICT_TEXT:
            return False
        future.set_result(verdict)
        return True

    def cancel_all(self) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_result("deny")
