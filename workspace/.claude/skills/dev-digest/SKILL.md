---
name: dev-digest
description: "GitHub status digest and PR review help (خلاصه وضعیت GitHub: PRها، issueها، CI، نوتیفیکیشن): PRs waiting for the user's review, the user's open PRs with CI/review/conflict status, assigned issues, important notifications, root cause of failing CI, and delegating a PR review to the code-reviewer subagent. Read-only by default and degrades gracefully when the GitHub connection is absent. Use when the user asks «PRهام چی شد؟», «CI چرا fail شد؟», «این PR رو review کن», or about GitHub issues and notifications."
---

# خلاصه وضعیت توسعه (GitHub)

**هدف:** در یک نگاه بداند چه کسی منتظر اوست و چه چیزی خراب است، و از کجا شروع کند.

## ۰. دسترسی (اول)
- ابزارهای `mcp__github__*` در این جلسه هستند؟ نام دقیق ابزارها ممکن است با نسخه سرور فرق کند؛ از همان‌هایی که در فهرست ابزارها هست استفاده کن. اول `get_me` برای نام کاربری.
- **GitHub MCP نیست (حالت محدود):** یک خط صادقانه بگو اتصال GitHub فعال نیست (مدیر ربات باید توکن GitHub را در تنظیمات سرور اضافه کند). بعد:
  - repo یا PR **عمومی**: WebFetch روی صفحه PR/issue/Actions (فقط خواندن؛ ممکن است محدود باشد).
  - یا کاربر لینک، diff یا لاگ CI را بفرستد (فایل در inbox) → تحلیل و review روی همان.
  - repoهای مهم را از بخش «کار» پروفایل بردار.
  - **هرگز وضعیت PR یا CI را حدس نزن.**

## ۱. Digest (فقط ابزارهای خواندنی)
نمونه ابزارها: جستجوی PR و issue، خواندن PR (وضعیت، reviewها، فایل‌ها)، فهرست اجراهای Actions، notifications (اگر toolset فعال است).
1. **منتظر review کاربر** — قدیمی‌ترین اول (query: `is:pr is:open review-requested:<user>`).
2. **PRهای باز خود کاربر** (`is:pr is:open author:<user>`): CI (✅/❌/⏳)، review (approved / changes requested / منتظر)، conflict، روزهای بی‌حرکت.
3. **issueهای assign‌شده** (`is:issue is:open assignee:<user>`)، مرتب بر اساس به‌روزرسانی.
4. **notificationهای مهم:** mention، review request، CI fail.
تعداد زیاد → محدود به repoهای مهم پروفایل و ۵ مورد اول هر بخش.

## ۲. CI قرمز
لاگ job شکست‌خورده را بخوان؛ **علت ریشه‌ای** را در ۱-۲ خط بگو (تست، lint، dependency، env/secret، flaky) + اصلاح پیشنهادی. باگ پیچیده → روش skill `systematic-debugging`.

## ۳. خروجی تلگرام (بدون جدول)
**🛠️ GitHub — {تاریخ شمسی}**
**👀 منتظر review تو (n):**
- [repo#123 عنوان](لینک) — ۴ روز
**📤 PRهای تو:**
- [repo#45 عنوان](لینک) — ❌ CI: علت کوتاه · 🔁 changes requested
**📌 issueها:** …
**🔔 مهم:** …
**👉 اول این:** یک مورد با دلیل (مثلاً review قدیمی که کسی را بلاک کرده، یا CI قرمز PR نزدیک به merge).
همه‌چیز آرام → یک خط «چیزی منتظرت نیست ✅».
پایان: `[[options: 🔍 review PR اول | 🧯 بررسی CI | 👌 ممنون]]`

## ۴. Code review
- PR را با repo و شماره به subagent `code-reviewer` بسپار؛ PR مربوط به agent/LLM → چک‌لیست skill `agent-architect` را هم اعمال کن.
- خلاصه نتیجه: حکم + ۳ مورد مهم با شدت.
- **نوشتن روی GitHub** (کامنت، review، approve، merge، issue) فقط بعد از نمایش متن دقیق در چت و تأیید کاربر؛ سیستم هم دکمه تأیید نشان می‌دهد.

## ۵. ثبت
- تصمیم فنی مهم → `notes/work/`؛ تصمیم معماری → ADR در `notes/work/adr/` طبق `agent-architect`.
- کار پیگیری («فردا PR X را review کنم») → `task_add` با تأیید.
