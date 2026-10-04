"""Ask the user in Telegram before a side-effecting tool call runs."""

from __future__ import annotations

import asyncio
import html
import logging
import secrets

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

log = logging.getLogger(__name__)

MAX_DETAILS = 3000


class ApprovalManager:
    def __init__(self, bot: Bot, timeout_s: int):
        self.bot = bot
        self.timeout_s = timeout_s
        self._pending: dict[str, asyncio.Future[bool]] = {}

    async def ask(self, chat_id: int, title: str, details: str) -> bool:
        approval_id = secrets.token_hex(6)
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._pending[approval_id] = future

        if len(details) > MAX_DETAILS:
            details = details[:MAX_DETAILS] + "\n…"
        text = (
            f"🔐 <b>نیاز به تأیید</b>\n<b>{html.escape(title)}</b>\n\n"
            f"<pre>{html.escape(details)}</pre>"
        )
        keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("✅ تأیید", callback_data=f"appr:{approval_id}:y"),
                InlineKeyboardButton("❌ رد", callback_data=f"appr:{approval_id}:n"),
            ]]
        )
        message = await self.bot.send_message(
            chat_id, text, parse_mode=ParseMode.HTML, reply_markup=keyboard
        )

        try:
            approved = await asyncio.wait_for(future, timeout=self.timeout_s)
            verdict = "✅ تأیید شد" if approved else "❌ رد شد"
        except asyncio.TimeoutError:
            approved, verdict = False, "⌛ بدون پاسخ ماند و رد شد"
        finally:
            self._pending.pop(approval_id, None)

        try:
            await message.edit_text(
                f"{text}\n\n{verdict}", parse_mode=ParseMode.HTML, reply_markup=None
            )
        except Exception:  # noqa: BLE001 - cosmetic only
            log.debug("could not edit approval message", exc_info=True)
        return approved

    def resolve(self, approval_id: str, approved: bool) -> bool:
        future = self._pending.get(approval_id)
        if future is None or future.done():
            return False
        future.set_result(approved)
        return True

    def cancel_all(self) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_result(False)
