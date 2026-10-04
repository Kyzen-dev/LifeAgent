---
name: dev-digest
description: Developer digest from GitHub (خلاصه وضعیت GitHub) — PRs awaiting review, my open PRs and their CI, assigned issues, notifications; plus help reviewing a PR. Use when the user asks about PRs, issues, CI, notifications, or code review.
---

# خلاصه وضعیت توسعه

## Digest
با ابزارهای GitHub (فقط خواندنی):
- PRهایی که review کاربر را خواسته‌اند (قدیمی‌ترین اول)
- PRهای باز خود کاربر: وضعیت CI، reviewهای در انتظار، conflict
- issueهای assign‌شده به کاربر، مرتب بر اساس به‌روزرسانی
- notificationهای مهم (mention، review request)

خروجی: فهرست کوتاه با لینک، و یک پیشنهاد «اول این را ببین».

## Code review
وقتی کاربر review یک PR را خواست، کار را به subagent `code-reviewer` بسپار و نتیجه را خلاصه کن.
ثبت کامنت/review روی GitHub فقط با تأیید کاربر انجام می‌شود؛ متن کامنت‌ها را اول در چت نشان بده.

## ثبت
تصمیم‌های فنی مهم و نکات معماری را در `notes/work/` ذخیره کن.
