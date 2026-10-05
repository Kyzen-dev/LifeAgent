---
name: personal-brand
description: "Grow the user's personal brand as an AI-agent engineer on LinkedIn and X in English (برند شخصی، پست لینکدین و توییتر، تقویم محتوا): positioning and profile review, content pillars, a weekly content calendar, drafting posts and threads from real work, ADRs and the AI digest, logging published posts and their results, and a monthly what-works review. Never publishes anything itself — the user posts. Use for «یه پست لینکدین بنویس», «برنامه محتوای هفته», «پروفایلم رو بررسی کن», «پست رو گذاشتم», or getting more visibility to attract clients."
---

# Personal Brand — LinkedIn و X (انگلیسی)

**هدف تجاری:** دیده‌شدن توسط مشتری‌های هدف و تبدیل به lead (← `client-acquisition` / `upwork-growth`). معیار موفقیت: پیام/درخواست مشتری و بازدید پروفایل، نه لایک.
**قانون ثابت:** تو هیچ‌وقت منتشر یا زمان‌بندی نمی‌کنی؛ پیش‌نویس می‌دهی، کاربر خودش منتشر می‌کند و خبر می‌دهد.

## فایل‌ها در `notes/brand/` (نبود → با همین ساختار بساز)
- `positioning.md` — جمله جایگاه، مخاطب هدف، ستون‌های محتوا، ۲-۳ نمونه از نوشته‌های خود کاربر (برای صدا).
- `calendar.md` — تقویم محتوا، یک خط برای هر پست، مرتب بر اساس تاریخ:
  `- YYYY-MM-DD | LinkedIn/X | pillar | موضوع | status: idea/draft/ready/posted | draft: drafts/...md`
- `drafts/YYYY-MM-DD-<slug>.md` — خط خلاصه، platform، pillar، source (یادداشت/ADR/digest)، status، دو نسخه متن.
- `log.md` — پست‌های منتشرشده (skill `weekly-review` از این می‌خواند):
  `- YYYY-MM-DD | LinkedIn/X | pillar | موضوع | لینک | impressions, comments, profile views, DMs/leads`

## ۱. جایگاه و پروفایل (یک‌بار، بعد هر فصل)
- از `memory/profile.md` (niche، استک، هدف درآمدی) و هم‌راستا با `upwork-growth`/`client-acquisition`: یک جمله «I help [who] [achieve what] with [how]» → `positioning.md`.
- **بررسی پروفایل:** متن یا اسکرین‌شات را بخواه (Read از inbox). LinkedIn: headline (niche + نتیجه)، About (مسئله مشتری → کار تو → اثبات → CTA)، Featured (case study، repo، دمو)، Experience با نتایج واقعی. X: bio یک‌خطی و pinned post. GitHub: repoهای pin‌شده با README و دمو.
  خروجی: فقط ۳-۵ تغییر پراثر + متن پیشنهادی انگلیسی.
- قواعد پلتفرم (طول، فرمت، الگوریتم) عوض می‌شوند؛ ادعا درباره‌شان فقط با جستجوی وب و تاریخ منبع.

## ۲. ستون‌های محتوا (پیش‌فرض؛ در `positioning.md` شخصی‌سازی شود)
1. **Build in public:** آموخته واقعی از پروژه‌ها — از `notes/work/`، ADRهای `notes/work/adr/`، `time_report`.
2. **الگوهای مهندسی agent:** LangGraph، eval، هزینه، شکست و راه‌حل؛ کد کوتاه با API تأییدشده (قاعده صفر skill `agent-architect`).
3. **نظر بر خبرها:** از `notes/research/ai-digest-*.md` (skill `ai-digest`) با زاویه تجربه شخصی.
4. **داستان فریلنس:** فرایند، اشتباه، نتیجه — بدون اغراق.
**محرمانگی:** نام مشتری، داده، کد یا عدد پروژه فقط با اجازه صریح؛ پیش‌فرض ناشناس‌سازی.

## ۳. تقویم محتوا (هفتگی، یا در بازبینی هفتگی)
1. `calendar.md` و `log.md` را بخوان: چه منتشر شده، چه عقب مانده، کدام ستون بهتر جواب داده.
2. ظرفیت را از پروفایل و اهداف (`goal_list`) بگیر. ثبات مهم‌تر از حجم است؛ اگر هفته قبل عقب ماند، برنامه را کوچک کن نه فشرده.
3. برای هفته بعد: روز، پلتفرم، ستون، موضوع و **منبع واقعی** هر پست؛ ستون‌ها را بچرخان؛ در `calendar.md` با status: idea ثبت کن.
4. با تأیید کاربر: یادآور روز انتشار با `reminder_add` («پست امروز: <موضوع> — پیش‌نویس در notes/brand/drafts/...»)؛ اگر عادت تعامل روزانه (کامنت مفید روی پست افراد هدف) در `habit_status` نیست، ساختنش را با `habit_create` پیشنهاد بده.

## ۴. نوشتن پست
1. ماده خام واقعی پیدا کن (Grep در notes) یا یک جزئیات واقعی از کاربر بپرس. بدون ماده خام، پست کلی ننویس.
2. صدای کاربر: نمونه‌های `positioning.md` و پست‌های قبلی.
3. قواعد: خط اول قلاب مشخص بدون clickbait؛ یک ایده در هر پست؛ مثال یا عدد واقعی؛ پایان با سؤال یا CTA نرم.
   LinkedIn: حدود ۸۰۰-۱۳۰۰ کاراکتر، پاراگراف کوتاه، حداکثر ۳ هشتگ. X: یک پست کوتاه یا thread ۴-۸ تایی.
   انگلیسی طبیعی و ساده؛ بدون کلیشه‌های AI («In today's fast-paced world», «game-changer», «delve», «unlock») و emoji زیاد.
4. همیشه **۲ نسخه** (مثلاً روایی و فهرستی) + یک خط فارسی «چرا این زاویه».
5. ادعای فنی/عددی فقط اگر درست و قابل دفاع است؛ تجربه‌ای که کاربر نگفته نساز → `[your real result]`.
6. ذخیره در `drafts/` و status در `calendar.md` → draft.
پایان پیام: `[[options: ✅ منتشر کردم | ✏️ ویرایش | 🔁 زاویه دیگر | 📅 بعداً]]`

## ۵. بعد از انتشار («منتشر کردم» / «گذاشتمش»)
1. لینک را بپرس (اختیاری) → سطر جدید در `log.md`؛ status در `calendar.md` → posted؛ اگر عادت مرتبطی هست، `habit_log`.
2. با تأیید: `reminder_add` سه روز بعد «آمار پست <موضوع> را بگو (impressions، کامنت، پیام)».
3. آمار رسید → همان سطر `log.md` را کامل کن. پیام یا درخواست مشتری → `project_upsert` (status=lead، source=linkedin یا x، next_action) و skill `client-acquisition`.

## ۶. مرور ماهانه
از `log.md`: تعداد پست به‌تفکیک ستون و پلتفرم، ثبات در برابر برنامه، ۲ پست برتر (اول بر اساس DM/lead، بعد comment). یک تصمیم برای ماه بعد (ستون بیشتر/کمتر، فرمت، زمان). کوتاه و بدون جدول؛ نتیجه را در `positioning.md` بخش «آموخته‌ها» ثبت کن.

## خطاها
- «خودت منتشر کن / زمان‌بندی کن» → توضیح بده انتشار با خودش است؛ متن نهایی + یادآور زمان انتشار پیشنهاد بده.
- خرید فالوور، engagement pod یا اتوماسیون اسپمی → توصیه نکن؛ ریسک حساب و اعتبار را بگو.
- متن انگلیسی خود کاربر برای اصلاح → اصلاح کن و اشتباه‌های تکراری را طبق skill `english-coach` در فایل مرور ثبت کن.

## چک نهایی قبل از تحویل پیش‌نویس
- [ ] بر پایه ماده خام واقعی است و ادعای ساختگی ندارد
- [ ] محرمانگی مشتری رعایت شده
- [ ] انگلیسی طبیعی، بدون کلیشه؛ یک ایده
- [ ] فایل پیش‌نویس و `calendar.md` به‌روز شد
