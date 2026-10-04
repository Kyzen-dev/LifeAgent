# LifeAgent — دستیار شخصی هوشمند در تلگرام

یک دستیار شخصی و کاری ۲۴ساعته که روی **Claude Agent SDK** ساخته شده و از طریق **تلگرام** با آن حرف می‌زنی.
به Gmail، Google Calendar، Drive و GitHub وصل می‌شود، مالی و عادت‌ها و سلامتت را ثبت و تحلیل می‌کند،
یادآور می‌فرستد، هر صبح گزارش می‌دهد و هر هفته با تو بازبینی می‌کند.

## قابلیت‌ها

| حوزه | چه کاری می‌کند |
|---|---|
| 💼 کار و بهره‌وری | مدیریت کارها و اهداف، خلاصه و مرتب‌سازی ایمیل، پیش‌نویس پاسخ، تقویم و آمادگی جلسه، یادداشت جلسه و action item |
| 🐙 برنامه‌نویسی | خلاصه PRها/issueها/CI در GitHub، code review با subagent مخصوص، ثبت تصمیم‌های فنی |
| 💰 مالی شخصی | ثبت هزینه/درآمد با یک جمله یا عکس رسید و پیامک بانکی، بودجه ماهانه، گزارش ماه شمسی، چندارزی |
| 🌱 سلامت و عادت‌ها | پیگیری عادت‌ها و streak، وزن/خواب/ورزش، ژورنال و حال روزانه، مربی سلامت |
| 📚 یادگیری | برنامه یادگیری، خلاصه کتاب/مقاله، مرور فاصله‌دار و امتحان گرفتن |
| 🔎 تحقیق | تحقیق عمیق وب با منبع (subagent `researcher`) و ذخیره در پایگاه دانش |
| ⏰ فعال (proactive) | گزارش صبحگاهی، چک‌این شبانه، بازبینی هفتگی (جمعه)، گزارش مالی اول هر ماه شمسی، یادآورها |
| 🎙️ ورودی‌ها | متن، پیام صوتی فارسی، عکس، PDF و هر فایل دیگر |
| 🧠 حافظه | پروفایل بلندمدت (`memory/profile.md`) + پایگاه دانش Markdown (`notes/`) + ادامه گفتگو بعد از ری‌استارت |

**امنیت:** خواندن آزاد است؛ هر کار با اثر بیرونی (ارسال ایمیل، تغییر تقویم/Drive، نوشتن در GitHub،
اجرای دستور shell) فقط بعد از زدن دکمه **✅ تأیید** در تلگرام انجام می‌شود. فقط user idهای مجاز
می‌توانند با ربات حرف بزنند.

## معماری

```
Telegram ──► lifeagent (python-telegram-bot)
                │
                ├─ ChatAgent ──► Claude Agent SDK (ClaudeSDKClient, یک session ماندگار برای هر چت)
                │                  ├─ System prompt فارسی + workspace/CLAUDE.md + memory/profile.md
                │                  ├─ Skills:    workspace/.claude/skills/*   (۱۰ مهارت)
                │                  ├─ Subagents: workspace/.claude/agents/*   (۵ زیرعامل)
                │                  ├─ MCP «life» (in-process): مالی، عادت، سلامت، ژورنال، کار، هدف، یادآور، ارسال فایل
                │                  ├─ MCP «google»: Gmail / Calendar / Drive / Tasks / Docs / Sheets
                │                  ├─ MCP «github»: سرور رسمی GitHub
                │                  └─ ابزارهای داخلی: WebSearch, WebFetch, Read, Write, Edit, Grep, Bash
                │
                ├─ can_use_tool ──► دکمه تأیید/رد در تلگرام برای کارهای با اثر بیرونی
                ├─ Scheduler (APScheduler) ──► روال‌ها و یادآورها
                └─ SQLite ──► sessionها، هزینه API، داده‌های شخصی
```

### Skills (در `workspace/.claude/skills/`)
`onboarding` · `morning-brief` · `evening-checkin` · `weekly-review` · `finance-report` · `receipt-scan` ·
`email-triage` · `meeting-prep` · `learning-plan` · `dev-digest`

### Subagents (در `workspace/.claude/agents/`)
`researcher` · `code-reviewer` · `finance-analyst` · `health-coach` · `learning-coach`

### ابزارهای MCP «life»
`finance_add_transaction` · `finance_list_transactions` · `finance_delete_transaction` · `finance_set_budget` ·
`finance_summary` · `habit_create` · `habit_archive` · `habit_log` · `habit_status` · `health_log` ·
`health_history` · `journal_add` · `journal_recent` · `task_add` · `task_list` · `task_update` · `goal_set` ·
`goal_list` · `reminder_add` · `reminder_list` · `reminder_cancel` · `date_convert` · `send_file`

---

## راه‌اندازی

### ۱. پیش‌نیازها
- یک VPS لینوکسی خارج از ایران (۱ تا ۲ گیگ رم کافی است) با Docker و Docker Compose
- **ربات تلگرام:** در [@BotFather](https://t.me/BotFather) دستور `/newbot` → توکن را بردار
- **user id تلگرام:** از [@userinfobot](https://t.me/userinfobot) بگیر (یا بعد از راه‌اندازی به ربات `/id` بفرست)
- **کلید Anthropic API:** از [console.anthropic.com](https://console.anthropic.com) → API Keys

### ۲. نصب
```bash
git clone <این ریپو> lifeagent && cd lifeagent
cp .env.example .env
nano .env        # حداقل TELEGRAM_BOT_TOKEN، TELEGRAM_ALLOWED_USER_IDS و ANTHROPIC_API_KEY
mkdir -p data && sudo chown -R 1000:1000 data workspace
docker compose up -d --build
docker compose logs -f
```
حالا در تلگرام به ربات `/start` بفرست و بعد بنویس: **«سلام، بیا با هم آشنا بشیم»** تا onboarding شروع شود
و دستیار پروفایلت را بسازد.

### ۳. اتصال Google (Gmail / Calendar / Drive) — اختیاری
از سرور [google_workspace_mcp](https://github.com/taylorwilsdon/google_workspace_mcp) استفاده می‌شود.

1. در [Google Cloud Console](https://console.cloud.google.com) یک پروژه بساز.
2. در **APIs & Services → Library** این‌ها را Enable کن: Gmail API، Google Calendar API، Google Drive API،
   Google Tasks API، Google Docs API، Google Sheets API.
3. **OAuth consent screen:** نوع External، ایمیل خودت را در Test users اضافه کن.
   > ⚠️ در حالت Testing، توکن‌ها هر ۷ روز منقضی می‌شوند. برای استفاده دائمی، اپ را **Publish** کن
   > (برای استفاده شخصی نیازی به verification نیست؛ فقط هشدار «unverified app» را رد می‌کنی).
4. **Credentials → Create OAuth client ID** با نوع **Desktop app** → Client ID و Secret را در `.env` بگذار
   (`GOOGLE_OAUTH_CLIENT_ID`، `GOOGLE_OAUTH_CLIENT_SECRET`، `USER_GOOGLE_EMAIL`) و `docker compose up -d` بزن.
5. **ورود یک‌باره:** روی لپ‌تاپت یک تونل SSH باز کن:
   ```bash
   ssh -L 8000:localhost:8000 user@your-vps
   ```
   در تلگرام بنویس «ایمیل‌های امروزم رو چک کن». ربات لینک ورود گوگل را می‌فرستد؛ آن را در مرورگر همان
   لپ‌تاپ باز کن و اجازه بده. callback از طریق تونل به کانتینر می‌رسد و توکن در `data/` ذخیره می‌شود.

### ۴. اتصال GitHub — اختیاری
در GitHub → Settings → Developer settings → **Fine-grained token** بساز با دسترسی به ریپوهای دلخواه
(Contents، Issues، Pull requests، Actions: Read؛ برای کامنت/PR: Read and write) و در
`GITHUB_PERSONAL_ACCESS_TOKEN` بگذار. از سرور MCP رسمی GitHub (`api.githubcopilot.com/mcp`) استفاده می‌شود.

### ۵. پیام صوتی — اختیاری
برای تبدیل ویس فارسی به متن، `OPENAI_API_KEY` را تنظیم کن (مدل پیش‌فرض `whisper-1`).

---

## استفاده

نمونه پیام‌ها:
- «۳۵۰ تومن ناهار، با کارت ملت» · «حقوق این ماه ۴۵ میلیون اومد» · «این ماه چقدر خرج کردم؟»
- «بودجه خوراک رو ماهی ۸ میلیون بذار»
- «فردا ساعت ۱۰ یادم بنداز قرارداد رو بفرستم» · «هر شنبه و سه‌شنبه ساعت ۷ یادم بنداز باشگاه»
- «امروز ۴۵ دقیقه دویدم، وزنم ۷۷.۵» · «یه عادت بساز: روزی ۲۰ صفحه کتاب»
- «ایمیل‌های مهم رو خلاصه کن و به ایمیل مدیرم یه جواب مودبانه بنویس»
- «جلسه ساعت ۳ امروز درباره چیه؟ آماده‌ام کن»
- «PRهایی که منتظر review من هستن؟» · «PR شماره ۱۲ ریپوی X رو review کن»
- «می‌خوام Kubernetes یاد بگیرم، هفته‌ای ۵ ساعت وقت دارم»
- «درباره بهترین لپ‌تاپ برنامه‌نویسی زیر ۱۵۰۰ دلار تحقیق کن»
- عکس رسید یا اسکرین‌شات پیامک بانکی → ثبت خودکار هزینه

دستورها: `/brief` گزارش صبحگاهی · `/review` بازبینی هفتگی · `/new` گفتگوی تازه · `/stop` توقف ·
`/cost` هزینه API · `/help`

## شخصی‌سازی
- **پروفایل/حافظه:** `workspace/memory/profile.md` (دستیار خودش به‌روزش می‌کند؛ تو هم می‌توانی ویرایش کنی)
- **مهارت جدید:** یک پوشه در `workspace/.claude/skills/<name>/SKILL.md` با frontmatter `name` و `description`
- **زیرعامل جدید:** یک فایل در `workspace/.claude/agents/<name>.md`
- **زمان روال‌ها:** متغیرهای `MORNING_BRIEF_TIME`، `EVENING_CHECKIN_TIME`، `WEEKLY_REVIEW`، `MONTHLY_REPORT_TIME`
- **مدل و عمق فکر:** `LIFEAGENT_MODEL` و `LIFEAGENT_EFFORT` (`low` ارزان‌تر و سریع‌تر، `high` دقیق‌تر)
- **قوانین تأیید:** `lifeagent/permissions.py`

تغییرات در `workspace/` بدون build دوباره اعمال می‌شوند (بعد از `/new` یا ری‌استارت).

## هزینه
هزینه بر اساس توکن مصرفی Anthropic API است. `/cost` هزینه تقریبی امروز و این ماه را نشان می‌دهد و
`DAILY_BUDGET_USD` وقتی از سقف روزانه بگذری هشدار می‌دهد. برای کاهش هزینه `LIFEAGENT_EFFORT=low`
یا مدل ارزان‌تر (مثلاً `claude-sonnet-5-5`) را امتحان کن و روال‌هایی که لازم نداری را خالی بگذار.

## پشتیبان‌گیری
همه داده‌ها در `data/` (SQLite، sessionها، توکن گوگل) و `workspace/memory` و `workspace/notes` است:
```bash
tar czf lifeagent-backup-$(date +%F).tgz data workspace/memory workspace/notes
```
این پوشه‌ها در `.gitignore` هستند تا داده شخصی وارد git نشود.

## توسعه و تست
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest
python -m lifeagent      # اجرای محلی با .env
```
